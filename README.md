# APP Timesheet - v3.7.8

Applicazione desktop Python con UI `PyQt6` per:

- inserimento ore giornaliere da calendario
- gestione anagrafiche `cliente > commessa > attivita`
- gestione programmazione ore su commessa/attivita
- strumenti di controllo (consuntivo, pianificato, costi, scostamenti)
- piattaforma multiutente con ruoli `admin` e `user`

## Novita v3.7.8

- calendario: intestazioni giorni settimana e numeri settimana aggiornate a grigio piu scuro.
- calendario: testo intestazioni impostato bianco per miglior contrasto.

## Novita v3.7.7

- calendario: fix strutturale della griglia interna (`qt_calendar_calendarview`) con resize `Fixed` al posto di `Stretch`.
- riga giorni settimana e colonna numero settimana ora vengono ridimensionate realmente (non solo via CSS).
- intestazioni (giorni + numeri settimana) forzate con sfondo grigio e testo nero bold grande per maggiore leggibilita.

## Novita v3.7.6

- calendario: intestazioni giorni settimana e numeri settimana con testo nero, grassetto e piu grande.
- calendario: sfondo intestazioni impostato su grigio piu visibile.
- calendario: ulteriore riduzione dimensioni intestazioni (`riga giorni` a `9px`, `colonna settimane` a `16px`).

## Novita v3.7.5

- calendario: riga giorni settimana (`Lun`, `Mar`, `Mer`...) impostata a meta altezza del layout standard (`10px`).
- calendario: testo intestazione giorni aumentato e reso piu leggibile (font piu grande e bold).

## Novita v3.7.4

- calendario: riga superiore dei giorni settimana ridotta a meta dell’altezza precedente.
- mantenuto sfondo grigio per la riga giorni della settimana.

## Novita v3.7.3

- calendario: se viene selezionata la data odierna, prevale il colore giallo di selezione.
- sabato e domenica evidenziati con celle rosse.
- riga giorni della settimana ridotta in altezza e resa grigio chiaro.
- colonna numero settimana ridotta in larghezza e resa grigio chiaro.
- ore inserite nel giorno rese piu evidenti con badge dedicato dentro la cella.

## Novita v3.7.2

- ripristinata la logica di gestione commesse/attivita del riferimento base (`eca9f0ac0b1ba7d0f7d4ece8f8da1f57fbcebb82`) mantenendo UI `PyQt6`.
- popup commessa con campi completi: nome, referente, costo, note, descrizione, data inizio/fine, ore preventivate e budget.
- popup attivita con campi completi: nome, tariffa, note, data inizio/fine, ore preventivate e budget.
- ripristinata la gestione pianificazione in salvataggio/modifica (creazione, aggiornamento, eventuale eliminazione schedule).
- ripristinati warning di coerenza attivita rispetto ai limiti della commessa (date, ore, budget).
- abilitato doppio click su riga commessa e riga attivita per aprire direttamente la modifica.
- tab separata `Programmazione` rimossa dalla UI principale per riallineamento al comportamento della versione base.

## Novita v3.7.1

- calendario ore PyQt6 riallineato al comportamento base del commit `eca9f0ac0b1ba7d0f7d4ece8f8da1f57fbcebb82` per la gestione visuale giornaliera.
- intestazione giorni settimana e colonna numero settimana con tono colore dedicato (diverso dal corpo calendario).
- ridotta altezza riga giorni settimana e ridotta larghezza colonna numero settimana.
- giorno corrente sempre evidenziato in blu.
- giorno selezionato evidenziato in giallo.
- nelle celle giorno ora viene mostrato il totale ore (`xh`) registrato per quel giorno.

## Novita v3.7.0

- migrazione UI da `customtkinter` a `PyQt6`, mantenendo logica e operazioni su `db.py`.
- struttura principale ora in stile `QMainWindow` con tab laterali (come `PDM-SW-2`), login dedicato e tema dark/light.
- portati su PyQt6 i flussi principali: calendario ore, gestione commesse/attivita/clienti, programmazione, controllo, diario e utenti.
- dialog report PDF migrato su PyQt6 con gli stessi filtri operativi (cliente/commessa/attivita/utente/periodo).

## Novita v3.6.11

- tab Calendario Ore: al cambio giorno il form viene azzerato automaticamente, evitando che restino cliente, commessa, attivita, ore e note del giorno precedente.
- tab Calendario Ore: mantenuta l'opzione vuota nel combo cliente per consentire il reset completo del form.

## Novita v3.6.10

- tab Calendario Ore: aggiunto il pulsante `Modifica selezionata` per aggiornare un inserimento ore selezionato.
- selezione riga ore: il form si popola automaticamente con cliente, commessa, attività, ore e note della voce scelta.
- uniformati i colori UI: pulsanti `Modifica` in arancione e pulsanti `Elimina` in rosso nelle tab e nei dialog principali.

## Novita v3.6.9

- ridimensionamento `db.py`: estratte le funzioni Diario in `db_diary.py`.
- `db.py` mantiene la stessa API pubblica Diario tramite wrapper di delega.

## Novita v3.6.8

- ridimensionamento `db.py`: estratta la logica report in `db_reports.py`.
- `db.py` mantiene la stessa API pubblica (`get_report_*`) tramite wrapper di delega, senza impatti sulla UI.

## Novita v3.6.7

- estratte le utility di formattazione controllo in `ui/tabs/formatters.py`.
- `ui/tabs/control_tab.py` usa ora formatter condivisi; metodi `_format_*` rimossi da `main.py`.

## Novita v3.6.6

- ridimensionamento tab Utenti: estratta la logica da `main.py` in `ui/tabs/users_tab.py`.
- `main.py` usa ora wrapper/delega per gestione utenti (crea/modifica, permessi tab, attiva/disattiva, reset password).

## Novita v3.6.5

- ridimensionamento tab Programmazione: estratta la logica CRUD schedule da `main.py` in `ui/tabs/plan_tab.py`.
- `main.py` usa ora wrapper/delega per `build_plan_tab`, opzioni progetto/attività e operazioni su pianificazioni.

## Novita v3.6.4

- ridimensionamento tab Controllo Programmazione: estratta la logica da `main.py` in `ui/tabs/control_tab.py`.
- `main.py` usa ora wrapper/delega per `build_control_tab`, `refresh_control_panel` e doppio click tree controllo.

## Novita v3.6.3

- ridimensionamento tab Diario: estratta la logica da `main.py` in `ui/tabs/diary_tab.py`.
- `main.py` usa ora wrapper/delega per i metodi Diario, mantenendo invariato il comportamento UI.

## Novita v3.6.2

- ridimensionamento `main.py`: estratti i dialog principali in moduli dedicati (`ui/dialogs`) per ridurre complessità e migliorare manutenzione.
- delega da `main.py` verso moduli esterni per: gestione clienti, gestione commesse, report programmazione, report PDF.

## Novita v3.6.1

- gestione clienti: separata la riga dei pulsanti CRUD dal campo `Costo orario (EUR/h)` per evitare sovrapposizioni UI.

## Regola costo orario

La tariffa usata in fase di inserimento ore e:

1. costo `attivita` se diverso da `0`
2. altrimenti costo `commessa` se diverso da `0`
3. altrimenti costo `cliente`

Il costo effettivo viene salvato nella riga ore al momento dell'inserimento.

## Avvio

```bash
pip install -r requirements.txt
python main.py
```

## Dati persistenti

- sviluppo: cartella configurazione/dati `TIME-PLANNING\CFG` (workspace del progetto)
- distribuzione `.exe`: cartella configurazione/dati `CFG` accanto all'eseguibile
- database principale: `CFG\timesheet.db`
- backup automatici: `CFG\backups\timesheet_YYYYMMDD_HHMMSS.db`

La cartella viene creata automaticamente al primo avvio.
L'app crea un backup all'avvio e poi ogni 6 ore, mantenendo gli ultimi 30 file.

## Build EXE (Windows)

```powershell
.\build.ps1
```

Lo script:
- pulisce `build/` e `dist/` (usa `.\build.ps1 -NoClean` per non pulire)
- installa `pyinstaller` se mancante
- genera l'eseguibile in `dist\APP-Timesheet-v<versione>\APP-Timesheet-v<versione>.exe`

## Report PDF

Tutti i report sono generati in **A4 orizzontale (landscape)**.
I campi testo lunghi vanno a capo automaticamente senza sovrapposizioni.

### Vista gerarchica

Il metodo `generate_hierarchical_report` accetta i dati di `get_report_filtered_data` e produce un PDF con la struttura:

```
▶ Cliente          [ore totali]  [costo €]
    ▷ Commessa     [ore totali]  [costo €]
        • Attività [ore totali]  [costo €]
          Data | Utente | Ore | Costo € | Note
          ...
```

Chiamarlo da `main.py` / report view:

```python
data = db.get_report_filtered_data(client_id=..., start_date=..., end_date=...)
pdf  = gen.generate_hierarchical_report(data, title="Report Ore", subtitle="Periodo: ...")
```

## Diario Note & Promemoria

Tab **Diario** per gestire note, promemoria e indicazioni legate a cliente/commessa/attività.

Funzionalità:
- Filtri per cliente, commessa, attività
- Priorità normale/alta (⚡)
- Data promemoria con alert visivo (🔔) se scaduto/oggi
- Stato completato/aperto
- Doppio click per modificare, pulsanti per completare/eliminare

## Credenziali iniziali

- username: `admin`
- password: `admin`

Al primo accesso e consigliato cambiare password dall'apposita tab `Utenti`.

## Icona sul Desktop (senza finestra terminale)

### Opzione 1 — Collegamento diretto da sorgente `.py`

1. Fare clic destro sul Desktop → **Nuovo → Collegamento**
2. Nel campo percorso incollare (adattare il percorso se necessario):
   ```
   "C:\Users\<utente>\AppData\Local\Programs\Python\Python314\pythonw.exe" "C:\Users\prog3\Desktop\APP MECCANICA\TIME-PLANNING\main.py"
   ```
   > `pythonw.exe` è identico a `python.exe` ma **non apre il terminale**.
3. Cliccare **Avanti**, assegnare un nome (es. `APP Timesheet`) e **Fine**.
4. *(Facoltativo)* Clic destro sul collegamento → **Proprietà** → **Cambia icona** per impostare un'icona personalizzata.

### Opzione 2 — Collegamento all'eseguibile `.exe` (consigliato per distribuzione)

1. Eseguire il build:
   ```powershell
   .\build.ps1
   ```
2. Aprire la cartella `dist\APP-Timesheet-v<versione>\`.
3. Fare clic destro su `APP-Timesheet-v<versione>.exe` → **Invia a → Desktop (crea collegamento)**.

L'eseguibile è già compilato con `--noconsole`, quindi non apre mai il terminale.

### Opzione 3 — File `.vbs` launcher (alternativa universale)

Creare un file `avvia.vbs` nella cartella del progetto con il contenuto:

```vbscript
Set oShell = CreateObject("WScript.Shell")
oShell.Run """C:\Users\<utente>\AppData\Local\Programs\Python\Python314\pythonw.exe"" """ & _
    """C:\Users\prog3\Desktop\APP MECCANICA\TIME-PLANNING\main.py""", 0, False
```

Poi creare un collegamento sul Desktop che punta a questo file `.vbs`.



