import sqlite3
from db import Database

db = Database()

# Test close_project
print("=== TEST CHIUSURA COMMESSA RPM12 (ID=1) ===")
print("Prima:")
conn = sqlite3.connect('CFG/timesheet.db')
cursor = conn.execute("SELECT status FROM schedules WHERE project_id = 1 AND activity_id IS NULL")
row = cursor.fetchone()
print(f"Status schedule RPM12: {row[0] if row else 'N/A'}")
conn.close()

print("\nChiudo commessa RPM12...")
db.close_project(1)

print("Dopo:")
conn = sqlite3.connect('CFG/timesheet.db')
cursor = conn.execute("SELECT status FROM schedules WHERE project_id = 1 AND activity_id IS NULL")
row = cursor.fetchone()
print(f"Status schedule RPM12: {row[0] if row else 'N/A'}")
conn.close()

print("\n\n=== TEST APERTURA COMMESSA RPM12 (ID=1) ===")
print("Riapro commessa RPM12...")
db.open_project(1)

print("Dopo:")
conn = sqlite3.connect('CFG/timesheet.db')
cursor = conn.execute("SELECT status FROM schedules WHERE project_id = 1 AND activity_id IS NULL")
row = cursor.fetchone()
print(f"Status schedule RPM12: {row[0] if row else 'N/A'}")
conn.close()

print("\n✓ Test completato")
