import sqlite3

conn = sqlite3.connect('CFG/timesheet.db')
c = conn.cursor()

print("\n=== SCHEDULES CON activity_id=None (escluso progetto) ===")
c.execute("""
    SELECT s.id, p.name, s.start_date, s.end_date, s.planned_hours, s.budget
    FROM schedules s
    JOIN projects p ON s.project_id = p.id
    WHERE s.activity_id IS NULL AND p.id = 3
    ORDER BY s.id
""")

wrong_schedules = c.fetchall()
for sched in wrong_schedules:
    print(f"Schedule ID {sched[0]}: {sched[1]}, {sched[2]} → {sched[3]}, ore={sched[4]}, budget={sched[5]}")

print("\n=== ATTIVITA' DI COMMESSA N2 2026 ===")
c.execute("SELECT id, name FROM activities WHERE project_id = 3 ORDER BY id")
activities = c.fetchall()
for act in activities:
    print(f"Attività ID {act[0]}: {act[1]}")

print("\n=== CORREZIONE ACTIVITY_ID NEGLI SCHEDULES ===")

# Gli schedule 7, 8, 9, 10 dovrebbero corrispondere alle attività 7, 8, 9, 10
# Ma prima verifico se questa corrispondenza ha senso
corrections = [
    (7, 7),   # STUDIO LAYOUT
    (8, 8),   # PROGETTAZIONE  
    (9, 9),   # CORREZIONI
    (10, 10), # DISEGNI
]

for schedule_id, activity_id in corrections:
    # Verifica se lo schedule esiste e ha activity_id=None
    c.execute("SELECT id, activity_id FROM schedules WHERE id = ?", (schedule_id,))
    sched = c.fetchone()
    
    if not sched:
        print(f"✗ Schedule {schedule_id} non esiste")
        continue
        
    if sched[1] is not None:
        print(f"✓ Schedule {schedule_id} ha già activity_id={sched[1]}")
        continue
    
    # Verifica se l'attività esiste
    c.execute("SELECT id, name FROM activities WHERE id = ? AND project_id = 3", (activity_id,))
    act = c.fetchone()
    
    if not act:
        print(f"✗ Attività {activity_id} non esiste")
        continue
    
    # Correggi
    c.execute("UPDATE schedules SET activity_id = ? WHERE id = ?", (activity_id, schedule_id))
    print(f"✓ Schedule {schedule_id} → activity_id={activity_id} ({act[1]})")

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

conn.close()
print("\n✓ Correzione completata!")
