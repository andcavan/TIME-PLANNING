import sqlite3

# Backup prima di tutto
import shutil
from pathlib import Path
backup_path = Path("CFG/backups/timesheet_pre_fix.db")
backup_path.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2("CFG/timesheet.db", backup_path)
print(f"✓ Backup creato: {backup_path}")

conn = sqlite3.connect('CFG/timesheet.db')

print("\n=== STATO PRIMA DELLA PULIZIA ===")
cursor = conn.execute("""
    SELECT s.id, p.name as project, a.name as activity, s.start_date, s.end_date
    FROM schedules s
    JOIN projects p ON p.id = s.project_id
    LEFT JOIN activities a ON a.id = s.activity_id
    WHERE s.project_id = 3
    ORDER BY s.id
""")
print(f"{'ID':<5} {'Progetto':<20} {'Attività':<20} {'Inizio':<12} {'Fine':<12}")
print("-" * 75)
for row in cursor.fetchall():
    activity = row[2] if row[2] else "(Progetto)"
    print(f"{row[0]:<5} {row[1]:<20} {activity:<20} {row[3]:<12} {row[4]:<12}")

# Trova lo schedule di progetto valido (quello con ID più basso)
cursor = conn.execute("""
    SELECT MIN(id) FROM schedules 
    WHERE project_id = 3 AND activity_id IS NULL
""")
valid_project_schedule_id = cursor.fetchone()[0]
print(f"\n✓ Schedule progetto valido: ID {valid_project_schedule_id}")

# Elimina tutti gli altri schedule di progetto duplicati
cursor = conn.execute("""
    DELETE FROM schedules 
    WHERE project_id = 3 
    AND activity_id IS NULL 
    AND id != ?
""", (valid_project_schedule_id,))
deleted = cursor.rowcount
conn.commit()
print(f"✓ Eliminati {deleted} schedule di progetto duplicati")

# Ora dobbiamo ricostruire gli schedule delle attività
# Prima recuperiamo le attività della commessa 3
cursor = conn.execute("""
    SELECT id, name FROM activities WHERE project_id = 3 ORDER BY id
""")
activities = cursor.fetchall()
print(f"\n✓ Trovate {len(activities)} attività per COMMESSA N2 2026:")
for act in activities:
    print(f"   - ID {act[0]}: {act[1]}")

# Per ogni attività, verifica se ha uno schedule
for activity_id, activity_name in activities:
    cursor = conn.execute("""
        SELECT id FROM schedules 
        WHERE project_id = 3 AND activity_id = ?
    """, (activity_id,))
    
    if cursor.fetchone():
        print(f"✓ Attività '{activity_name}' ha già uno schedule valido")
    else:
        print(f"✗ Attività '{activity_name}' NON ha uno schedule - devi ricrearlo manualmente dall'app")

print("\n=== STATO DOPO LA PULIZIA ===")
cursor = conn.execute("""
    SELECT s.id, p.name as project, a.name as activity, s.start_date, s.end_date
    FROM schedules s
    JOIN projects p ON p.id = s.project_id
    LEFT JOIN activities a ON a.id = s.activity_id
    WHERE s.project_id = 3
    ORDER BY s.id
""")
print(f"{'ID':<5} {'Progetto':<20} {'Attività':<20} {'Inizio':<12} {'Fine':<12}")
print("-" * 75)
for row in cursor.fetchall():
    activity = row[2] if row[2] else "(Progetto)"
    print(f"{row[0]:<5} {row[1]:<20} {activity:<20} {row[3]:<12} {row[4]:<12}")

conn.close()
print("\n✓ Database pulito!")
