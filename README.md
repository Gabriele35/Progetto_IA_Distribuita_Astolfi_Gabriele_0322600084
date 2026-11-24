# Implementazione del Bully Algorithm

Implementazione in Python dell'algoritmo di elezione distribuita **Bully** per un sistema composto da **5 nodi indipendenti** (`P1` – `P5`) in esecuzione su processi separati.

---

## 1. Requisiti e Dipendenze

* **Linguaggio:** Python 3.8+(Versione usata 3.15.2)
* **Librerie utilizzate:** Esclusivamente librerie della *Standard Library* di Python (`sys`, `socket`, `threading`, `json`, `time`, `datetime`).
* **Dipendenze esterne:** Nessuna (non è richiesta l'installazione di pacchetti tramite `pip`).

---

## 2. Architettura del Sistema

Ogni nodo viene avviato come processo indipendente e comunica tramite socket **UDP** su rete locale (`127.0.0.1`).

| Nodo | Identificativo (`ID`) | Indirizzo IP | Porta UDP |
| :--- | :---: | :---: | :---: |
| **P1** | `1` | `127.0.0.1` | `5001` |
| **P2** | `2` | `127.0.0.1` | `5002` |
| **P3** | `3` | `127.0.0.1` | `5003` |
| **P4** | `4` | `127.0.0.1` | `5004` |
| **P5** | `5` | `127.0.0.1` | `5005` |

### Protocollo dei Messaggi
Il sistema utilizza esclusivamente i **3 messaggi** previsti dal protocollo Bully, in formato JSON (`{"type": "<TIPO>", "sender_id": <ID>}`):
1. `ELECTION`: inviato da un nodo verso i processi con ID superiore per avviare un'elezione (o per verificare lo stato del coordinatore attuale).
2. `ANSWER`: risposta inviata da un nodo con ID superiore per confermare la propria presenza e prendere in carico l'elezione.
3. `COORDINATOR`: inviato dal nodo vincitore a tutti i nodi con ID inferiore per proclamarsi nuovo coordinatore.

### Gestione dei Timer Reali ($T$ e $T'$)
* **Timeout $T$ (`2.0s`):** tempo massimo di attesa per ricevere un messaggio `ANSWER` dopo l'invio di `ELECTION`, oppure per rilevare il mancato riscontro del coordinatore in caso di crash.
* **Timeout $T'$ (`4.0s`):** tempo massimo di attesa per ricevere la proclamazione `COORDINATOR` dopo aver ricevuto almeno un `ANSWER` da un nodo con ID superiore.

---

## 3. Guida all'Esecuzione

### Avvio dei 5 Nodi
Aprire **5 terminali separati** nella directory del progetto ed eseguire i seguenti comandi:

```bash
# Terminale 1
python nodo.py 1

# Terminale 2
python nodo.py 2

# Terminale 3
python nodo.py 3

# Terminale 4
python nodo.py 4

# Terminale 5
python nodo.py 5
### Sequenza di Test (Elezione, Guasto e Rielezione)
1. **Prima Elezione:** Premere `INVIO` sul terminale di **P1**. Viene avviata l'elezione a cascata e **P5** si proclama coordinatore.
2. **Simulazione Guasto:** Sul terminale di **P5**, premere `Ctrl + C` per terminare bruscamente il processo.
3. **Rilevazione Guasto e Seconda Elezione:** Premere `INVIO` sul terminale di **P3**. Allo scadere del timer reale $T = 2.0\text{s}$, **P3** rileva l'assenza di **P5**, avvia una nuova elezione e **P4** viene eletto nuovo coordinatore.

---

## 4. Struttura del Codice (`nodo.py`)

Per agevolare la revisione, le sezioni principali del protocollo sono evidenziate nel codice tramite commenti dedicati:
* `[PUNTO 1]` Gestione scambio messaggi (`ELECTION`, `ANSWER`, `COORDINATOR`).
* `[PUNTO 2]` Gestione attese e timeout reali $T$ e $T'$.
* `[PUNTO 3]` Proclamazione del coordinatore.
* `[PUNTO 4]` Arresto immediato dell'elezione alla ricezione di `COORDINATOR`.

---
## 5. Video Dimostrativo

Il video dimostrativo integrale (senza tagli, con tutti e 5 i terminali visibili simultaneamente e log con timestamp delle fasi di prima elezione, guasto di P5 e rielezione di P4) è disponibile direttamente in questo repository nel file Video_Dimostrativo_Astolfi_Gabriele.mov
