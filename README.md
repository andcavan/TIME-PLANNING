# APP Timesheet

Applicazione desktop Python con UI `customtkinter` per:

- inserimento ore giornaliere da calendario
- gestione anagrafiche `cliente > commessa > attivita`
- gestione programmazione ore su commessa/attivita
- strumenti di controllo (consuntivo, pianificato, costi, scostamenti)
- piattaforma multiutente con ruoli `admin` e `user`

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

## Build EXE (Windows)

```powershell
.\build.ps1
```

Lo script:
- pulisce `build/` e `dist/` (usa `.\build.ps1 -NoClean` per non pulire)
- installa `pyinstaller` se mancante
- genera l'eseguibile in `dist\APP-Timesheet-v<versione>\APP-Timesheet-v<versione>.exe`

## Credenziali iniziali

- username: `admin`
- password: `admin`

Al primo accesso e consigliato cambiare password dall'apposita tab `Utenti`.
