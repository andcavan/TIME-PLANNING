"""Script debug per verificare contenuto database"""
import sqlite3

from db import DEFAULT_DB_PATH

conn = sqlite3.connect(DEFAULT_DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== ATTIVITÀ ===")
activities = cursor.execute("SELECT * FROM activities ORDER BY id DESC LIMIT 5").fetchall()
for act in activities:
    print(f"ID: {act['id']}, Project: {act['project_id']}, Nome: {act['name']}")

print("\n=== SCHEDULES ===")
schedules = cursor.execute("SELECT * FROM schedules ORDER BY id DESC LIMIT 5").fetchall()
for sched in schedules:
    print(f"ID: {sched['id']}, Project: {sched['project_id']}, Activity: {sched['activity_id']}, "
          f"Date: {sched['start_date']} - {sched['end_date']}, Ore: {sched['planned_hours']}, Budget: {sched['budget']}")

conn.close()
