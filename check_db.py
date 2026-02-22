import sqlite3

conn = sqlite3.connect('CFG/timesheet.db')

print("\n=== PROGETTI CON STATUS ===")
cursor = conn.execute("""
    SELECT p.id, p.name, p.closed, s.status 
    FROM projects p 
    LEFT JOIN schedules s ON s.project_id = p.id AND s.activity_id IS NULL 
    ORDER BY p.id
""")
print(f"{'ID':<5} {'Nome':<40} {'Closed':<8} {'Status Schedule':<15}")
print("-" * 70)
for row in cursor.fetchall():
    status = row[3] if row[3] else "N/A"
    print(f"{row[0]:<5} {row[1]:<40} {row[2]:<8} {status:<15}")

print("\n=== TUTTE LE SCHEDULES ===")
cursor = conn.execute("""
    SELECT s.id, p.name, a.name, s.status, s.start_date, s.end_date 
    FROM schedules s
    JOIN projects p ON p.id = s.project_id
    LEFT JOIN activities a ON a.id = s.activity_id
    ORDER BY s.id
""")
print(f"{'ID':<5} {'Progetto':<30} {'Attività':<20} {'Status':<10} {'Inizio':<12} {'Fine':<12}")
print("-" * 90)
for row in cursor.fetchall():
    activity = row[2] if row[2] else "(Progetto)"
    print(f"{row[0]:<5} {row[1]:<30} {activity:<20} {row[3]:<10} {row[4]:<12} {row[5]:<12}")

conn.close()
