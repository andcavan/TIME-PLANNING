# APP Timesheet - v3.6.1

Applicazione desktop Python con UI `customtkinter` per:

- inserimento ore giornaliere da calendario
- gestione anagrafiche `cliente > commessa > attivita`
- gestione programmazione ore su commessa/attivita
- strumenti di controllo (consuntivo, pianificato, costi, scostamenti)
- piattaforma multiutente con ruoli `admin` e `user`

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



