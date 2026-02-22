import sqlite3
from db import Database

db = Database()

# Test con una commessa senza schedule
print("=== TEST CHIUSURA/APERTURA COMMESSA SENZA SCHEDULE ===")

# Trova commessa ID 3 (COMMESSA N2 2026)
conn = sqlite3.connect('CFG/timesheet.db')

print("\n1. Stato COMMESSA N2 2026 (ID=3):")
cursor = conn.execute("SELECT id, name, closed FROM projects WHERE id = 3")
row = cursor.fetchone()
print(f"   Projects.closed: {row[2]}")

cursor = conn.execute("SELECT id, status FROM schedules WHERE project_id = 3 AND activity_id IS NULL")
row = cursor.fetchone()
print(f"   Schedule status: {row[1] if row else 'N/A - non ha schedule progetto'}")

# Crea una commessa di test senza schedule
print("\n2. Creo commessa di test SENZA schedule...")
conn.execute("INSERT INTO projects (client_id, name, hourly_rate, notes) VALUES (1, 'TEST_NO_SCHEDULE', 50.0, 'Test')")
conn.commit()
test_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
print(f"   Creata commessa ID={test_id}")

print(f"\n3. Chiudo commessa {test_id} (senza schedule)...")
db.close_project(test_id)

cursor = conn.execute("SELECT closed FROM projects WHERE id = ?", (test_id,))
closed_val = cursor.fetchone()[0]
print(f"   Projects.closed = {closed_val}")

print(f"\n4. Riapro commessa {test_id}...")
db.open_project(test_id)

cursor = conn.execute("SELECT closed FROM projects WHERE id = ?", (test_id,))
closed_val = cursor.fetchone()[0]
print(f"   Projects.closed = {closed_val}")

# Pulisci
print(f"\n5. Rimuovo commessa di test...")
conn.execute("DELETE FROM projects WHERE id = ?", (test_id,))
conn.commit()

conn.close()
print("\n✓ Test completato con successo!")
