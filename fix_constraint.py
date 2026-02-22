"""
Fix schedules table constraint: allow planned_hours >= 0 instead of > 0
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "CFG" / "timesheet.db"

def fix_constraint():
    print(f"Fixing constraint in: {DB_PATH}")
    
    if not DB_PATH.exists():
        print("Database not found!")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # Backup existing data
        print("Reading existing schedules...")
        cursor = conn.execute("SELECT * FROM schedules")
        schedules = cursor.fetchall()
        print(f"Found {len(schedules)} schedules")
        
        # Drop old table
        print("Dropping old table...")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("DROP TABLE IF EXISTS schedules")
        
        # Create new table with correct constraint
        print("Creating new table with correct constraint...")
        conn.execute("""
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                activity_id INTEGER REFERENCES activities(id),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                planned_hours REAL NOT NULL DEFAULT 0 CHECK(planned_hours >= 0),
                note TEXT NOT NULL DEFAULT '',
                budget REAL NOT NULL DEFAULT 0 CHECK(budget >= 0),
                status TEXT NOT NULL DEFAULT 'aperta' CHECK(status IN ('aperta', 'chiusa')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Restore data
        print("Restoring data...")
        for schedule in schedules:
            # Get column names from the row
            cols = schedule.keys()
            placeholders = ','.join(['?' for _ in cols])
            col_names = ','.join(cols)
            values = [schedule[col] for col in cols]
            
            conn.execute(f"INSERT INTO schedules ({col_names}) VALUES ({placeholders})", values)
        
        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print("✓ Constraint fixed successfully!")
        
        # Verify
        cursor = conn.execute("SELECT COUNT(*) FROM schedules")
        count = cursor.fetchone()[0]
        print(f"✓ Verified: {count} schedules in new table")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    fix_constraint()
