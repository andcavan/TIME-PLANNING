import sqlite3
import shutil
from datetime import datetime

# Connessione al backup per recuperare i dati
backup_conn = sqlite3.connect('CFG/backups/timesheet_pre_fix.db')
backup_c = backup_conn.cursor()

# Connessione al database corrente
conn = sqlite3.connect('CFG/timesheet.db')
c = conn.cursor()

print("\n=== RECUPERO SCHEDULE ATTIVITA' ===\n")

# Ottieni le attività di COMMESSA N2 2026
c.execute("SELECT id, name FROM activities WHERE project_id = 3")
activities = c.fetchall()

print(f"Trovate {len(activities)} attività per COMMESSA N2 2026:")
for act_id, act_name in activities:
    print(f"   - ID {act_id}: {act_name}")

print("\n=== DATI SCHEDULE ELIMINATI (dal backup) ===")
# Recupera gli schedule eliminati (ID 7-11) dal backup
backup_c.execute("""
    SELECT id, project_id, activity_id, start_date, end_date, 
           planned_hours, budget, status, note
    FROM schedules 
    WHERE id IN (7, 8, 9, 10, 11)
    ORDER BY id
""")

deleted_schedules = backup_c.fetchall()
for sched in deleted_schedules:
    print(f"Schedule ID {sched[0]}: inizio={sched[3]}, fine={sched[4]}, "
          f"ore_previste={sched[5]}, budget={sched[6]}, status={sched[7]}")

print("\n=== MAPPATURA SCHEDULE -> ATTIVITA' ===")
# Gli schedule 7-11 corrispondono alle attività 7-11
# Verifichiamo e ripristiniamo
mapping = []
for sched in deleted_schedules:
    sched_id = sched[0]
    # L'activity_id dovrebbe essere uguale allo schedule_id in questo caso
    # perché erano stati creati insieme
    activity_id = sched_id
    
    # Verifica che l'attività esista
    c.execute("SELECT id, name FROM activities WHERE id = ? AND project_id = 3", (activity_id,))
    activity = c.fetchone()
    
    if activity:
        mapping.append((sched, activity))
        print(f"✓ Schedule {sched_id} -> Attività {activity[0]} '{activity[1]}'")
    else:
        print(f"✗ Schedule {sched_id} -> Nessuna attività corrispondente")

if not mapping:
    print("\n✗ Nessuno schedule da ripristinare")
    backup_conn.close()
    conn.close()
    exit()

print(f"\n=== RIPRISTINO {len(mapping)} SCHEDULE ===")

for sched, activity in mapping:
    sched_id, project_id, _, start_date, end_date, planned_hours, budget, status, note = sched
    activity_id, activity_name = activity
    
    # Inserisci lo schedule corretto per l'attività
    # Usiamo lo stesso ID originale
    try:
        c.execute("""
            INSERT INTO schedules (id, project_id, activity_id, start_date, end_date,
                                 planned_hours, budget, status, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sched_id, project_id, activity_id, start_date, end_date,
              planned_hours, budget, status, note))
        
        print(f"✓ Ripristinato schedule {sched_id} per attività '{activity_name}'")
        print(f"   Periodo: {start_date} - {end_date}")
        print(f"   Budget: {budget}, Ore previste: {planned_hours}")
    except sqlite3.IntegrityError as e:
        print(f"✗ Errore ripristinando schedule {sched_id}: {e}")

conn.commit()

print("\n=== VERIFICA FINALE ===")
c.execute("""
    SELECT s.id, p.name, a.name, s.start_date, s.end_date, s.status
    FROM schedules s
    JOIN projects p ON s.project_id = p.id
    LEFT JOIN activities a ON s.activity_id = a.id
    WHERE p.id = 3
    ORDER BY s.id
""")

for row in c.fetchall():
    activity = row[2] if row[2] else "(Progetto)"
    print(f"Schedule {row[0]}: {row[1]} - {activity}")
    print(f"   {row[3]} → {row[4]} ({row[5]})")

backup_conn.close()
conn.close()

print("\n✓ Ripristino completato!")
