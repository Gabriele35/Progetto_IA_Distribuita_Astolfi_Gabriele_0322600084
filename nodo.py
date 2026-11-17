import sys
import socket
import threading
import json
import time
from datetime import datetime

# Configurazione rete locale e porte dei 5 nodi (da P1 a P5)
HOST = "127.0.0.1"
NODES = {
    1: 5001,
    2: 5002,
    3: 5003,
    4: 5004,
    5: 5005,
}

# Valori dei timer (in secondi)
TIMEOUT_T = 2.0        # Attesa risposta ANSWER o risposta dal Coordinatore
TIMEOUT_T_PRIME = 4.0  # Attesa messaggio COORDINATOR dopo aver ricevuto ANSWER


class BullyNode:
    def __init__(self, node_id: int):
        self.node_id = node_id
        self.port = NODES[node_id]
        self.coordinator_id = None
        self.in_election = False
        self.running = True

        # Lock per proteggere lo stato condiviso tra i thread del singolo processo
        self.lock = threading.Lock()

        # Eventi di sincronizzazione per i timer e l'interruzione immediata
        self.answer_event = threading.Event()
        self.coordinator_event = threading.Event()
        self.coord_ack_event = threading.Event()

        # Socket UDP per comunicazione asincrona senza connessioni persistenti
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((HOST, self.port))
        self.sock.settimeout(0.5)

    def log(self, message: str):
        """Stampa i log con timestamp al millisecondo per verificare i timeout nel video."""
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        coord_str = f"P{self.coordinator_id}" if self.coordinator_id else "Nessuno"
        print(f"[{now}] [P{self.node_id} | Coord: {coord_str}] {message}", flush=True)

    # [PUNTO 1] GESTIONE SCAMBIO MESSAGGI (ELECTION, ANSWER, COORDINATOR)

    def send_message(self, target_id: int, msg_type: str):
        """Invia uno dei 3 messaggi ammessi dal protocollo Bully in formato JSON."""
        if msg_type not in ("ELECTION", "ANSWER", "COORDINATOR"):
            raise ValueError(f"Tipo messaggio non consentito: {msg_type}")

        payload = json.dumps({
            "type": msg_type,
            "sender_id": self.node_id
        }).encode("utf-8")

        target_port = NODES[target_id]
        self.sock.sendto(payload, (HOST, target_port))

    def listen_loop(self):
        """Thread server UDP: ascolta continuamente i messaggi in arrivo."""
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                msg = json.loads(data.decode("utf-8"))
                msg_type = msg.get("type")
                sender_id = msg.get("sender_id")

                if msg_type == "ELECTION":
                    self.handle_election_msg(sender_id)
                elif msg_type == "ANSWER":
                    self.handle_answer_msg(sender_id)
                elif msg_type == "COORDINATOR":
                    self.handle_coordinator_msg(sender_id)

            except socket.timeout:
                continue
            except OSError:
                break

    def handle_election_msg(self, sender_id: int):
        """Gestisce la ricezione di ELECTION da un nodo con ID inferiore (o check coordinatore)."""
        with self.lock:
            is_coord = (self.coordinator_id == self.node_id)

        # Risponde sempre con ANSWER al mittente con ID inferiore
        if sender_id < self.node_id:
            self.log(f"Ricevuto ELECTION da P{sender_id} -> Invio ANSWER a P{sender_id}")
            self.send_message(sender_id, "ANSWER")

            # Se questo nodo e' gia' il coordinatore attivo, ribadisce la propria leadership
            # evitando un'elezione superflua; altrimenti avvia la propria elezione.
            if is_coord:
                self.send_message(sender_id, "COORDINATOR")
            else:
                self.trigger_election_async()

    def handle_answer_msg(self, sender_id: int):
        """Gestisce la ricezione di ANSWER da un nodo superiore (o dal coordinatore attivo)."""
        self.log(f"Ricevuto ANSWER da P{sender_id}")
        self.answer_event.set()
        self.coord_ack_event.set()

    # [PUNTO 4] ARRESTO IMMEDIATO DELL'ELEZIONE ALLA RICEZIONE DI COORDINATOR

    def handle_coordinator_msg(self, sender_id: int):
        """Interrompe istantaneamente qualsiasi elezione in corso e aggiorna il capo."""
        with self.lock:
            self.coordinator_id = sender_id
            self.in_election = False

        # Sblocca immediatamente qualsiasi attesa su T o T'
        self.answer_event.set()
        self.coordinator_event.set()
        self.log(f"Ricevuto COORDINATOR da P{sender_id} -> Elezione terminata. Nuovo capo: P{sender_id}")

    # [PUNTO 2] GESTIONE ATTESE E TIMEOUT T E T'

    def trigger_election_async(self):
        """Avvia la procedura di elezione in un thread separato se non e' gia' attiva."""
        with self.lock:
            if self.in_election:
                return
            self.in_election = True
            self.answer_event.clear()
            self.coordinator_event.clear()

        threading.Thread(target=self.run_election, daemon=True).start()

    def run_election(self):
        """Esegue l'algoritmo Bully gestendo i due timeout reali T e T'."""
        higher_nodes = [nid for nid in NODES if nid > self.node_id]

        # Se non esistono nodi con ID superiore (es. P5), vince subito
        if not higher_nodes:
            self.proclaim_coordinator()
            return

        self.log(f"Avvio ELEZIONE -> Invio ELECTION a {[f'P{n}' for n in higher_nodes]}")
        for target_id in higher_nodes:
            self.send_message(target_id, "ELECTION")

        # Attesa Timeout T: aspetta almeno un messaggio ANSWER dai nodi superiori
        got_answer = self.answer_event.wait(timeout=TIMEOUT_T)

        # Controllo se nel frattempo e' gia' arrivato un COORDINATOR (arresto immediato)
        with self.lock:
            if not self.in_election:
                return

        if not got_answer:
            # Nessuno ha risposto entro T: questo nodo diventa coordinatore
            self.log(f"Timeout T ({TIMEOUT_T}s) scaduto: nessuna ANSWER ricevuta.")
            self.proclaim_coordinator()
            return

        # Ha ricevuto almeno un ANSWER: ora attende Timeout T' per il messaggio COORDINATOR
        self.log(f"In attesa del messaggio COORDINATOR (Timeout T' = {TIMEOUT_T_PRIME}s)...")
        got_coordinator = self.coordinator_event.wait(timeout=TIMEOUT_T_PRIME)

        with self.lock:
            if not self.in_election:
                return

        if not got_coordinator:
            # Il nodo superiore che aveva risposto ANSWER e' crashato prima di proclamarsi:
            # resetta lo stato e riavvia l'elezione da capo.
            self.log(f"Timeout T' ({TIMEOUT_T_PRIME}s) scaduto: nessun COORDINATOR ricevuto! Riavvio elezione.")
            with self.lock:
                self.in_election = False
            self.trigger_election_async()

    # [PUNTO 3] PROCLAMAZIONE DEL COORDINATORE

    def proclaim_coordinator(self):
        """Proclama questo nodo come nuovo Coordinatore e notifica i nodi inferiori."""
        with self.lock:
            self.coordinator_id = self.node_id
            self.in_election = False

        lower_nodes = [nid for nid in NODES if nid < self.node_id]
        self.log(f"*** MI PROCLAMO COORDINATORE (P{self.node_id}) *** -> Invio COORDINATOR a {[f'P{n}' for n in lower_nodes]}")
        for target_id in lower_nodes:
            self.send_message(target_id, "COORDINATOR")

    def check_coordinator_or_elect(self):
        """Verifica se il coordinatore attuale e' vivo (entro Timeout T) o avvia l'elezione."""
        with self.lock:
            current_coord = self.coordinator_id

        if current_coord is None:
            self.log("Nessun coordinatore noto -> Avvio prima elezione.")
            self.trigger_election_async()
            return

        if current_coord == self.node_id:
            self.log("Sono io il coordinatore attuale.")
            return

        # Verifica raggiungibilita' del coordinatore inviando ELECTION e attendendo ANSWER entro T
        self.log(f"Verifica stato del coordinatore P{current_coord} (attesa max T = {TIMEOUT_T}s)...")
        self.coord_ack_event.clear()
        self.send_message(current_coord, "ELECTION")

        alive = self.coord_ack_event.wait(timeout=TIMEOUT_T)
        if alive:
            self.log(f"Il coordinatore P{current_coord} e' attivo e ha risposto.")
        else:
            self.log(f"GUASTO RILEVATO: il coordinatore P{current_coord} non risponde entro T ({TIMEOUT_T}s)!")
            with self.lock:
                self.coordinator_id = None
            self.trigger_election_async()

    def stop(self):
        self.running = False
        self.sock.close()


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        print("Uso corretto: python nodo.py <ID_NODO> (dove ID_NODO e' 1, 2, 3, 4 o 5)")
        sys.exit(1)

    node_id = int(sys.argv[1])
    if node_id not in NODES:
        print("Errore: ID_NODO deve essere compreso tra 1 e 5.")
        sys.exit(1)

    node = BullyNode(node_id)
    listener_thread = threading.Thread(target=node.listen_loop, daemon=True)
    listener_thread.start()

    node.log(f"Avviato su {HOST}:{node.port}. Premi [INVIO] per verificare il coordinatore / avviare elezione.")

    try:
        while True:
            input()
            node.check_coordinator_or_elect()
    except (KeyboardInterrupt, EOFError):
        node.log("Arresto nodo (Ctrl+C). Nodo offline.")
        node.stop()


if __name__ == "__main__":
    main()
