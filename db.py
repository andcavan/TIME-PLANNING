from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "timesheet.db"


class Database:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._create_schema()
        self._seed_admin()

    def close(self) -> None:
        self.conn.close()

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def calculate_working_days(start_date_str: str, end_date_str: str) -> int:
        """Calcola i giorni lavorativi (esclusi sabato e domenica) tra due date.
        
        Args:
            start_date_str: Data inizio in formato YYYY-MM-DD
            end_date_str: Data fine in formato YYYY-MM-DD
            
        Returns:
            Numero di giorni lavorativi (lunedì-venerdì)
        """
        if not start_date_str or not end_date_str:
            return 0
        
        try:
            from datetime import datetime, timedelta
            
            start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            
            if start > end:
                return 0
            
            working_days = 0
            current = start
            
            while current <= end:
                # lunedì=0, domenica=6
                if current.weekday() < 5:  # 0-4 sono lun-ven
                    working_days += 1
                current += timedelta(days=1)
            
            return working_days
        except:
            return 0

    def _create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'user')),
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                hourly_rate REAL NOT NULL DEFAULT 0 CHECK(hourly_rate >= 0),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                hourly_rate REAL NOT NULL DEFAULT 0 CHECK(hourly_rate >= 0),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(client_id, name)
            );

            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                hourly_rate REAL NOT NULL DEFAULT 0 CHECK(hourly_rate >= 0),
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(project_id, name)
            );

            CREATE TABLE IF NOT EXISTS timesheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                work_date TEXT NOT NULL,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                project_id INTEGER NOT NULL REFERENCES projects(id),
                activity_id INTEGER NOT NULL REFERENCES activities(id),
                hours REAL NOT NULL CHECK(hours > 0),
                note TEXT NOT NULL DEFAULT '',
                effective_rate REAL NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                activity_id INTEGER REFERENCES activities(id),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                planned_hours REAL NOT NULL CHECK(planned_hours > 0),
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS user_project_assignments (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (user_id, project_id)
            );
            """
        )
        self.conn.commit()
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Aggiunge colonne notes se non esistono già."""
        # Verifica e aggiungi notes a clients
        cursor = self.conn.execute("PRAGMA table_info(clients)")
        columns = [row[1] for row in cursor.fetchall()]
        if "notes" not in columns:
            self.conn.execute("ALTER TABLE clients ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        
        # Verifica e aggiungi notes a projects
        cursor = self.conn.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]
        if "notes" not in columns:
            self.conn.execute("ALTER TABLE projects ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        
        # Verifica e aggiungi notes a activities
        cursor = self.conn.execute("PRAGMA table_info(activities)")
        columns = [row[1] for row in cursor.fetchall()]
        if "notes" not in columns:
            self.conn.execute("ALTER TABLE activities ADD COLUMN notes TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        
        # Migrazione schedules: da vecchia struttura (user_id, planned_date) a nuova (start_date, end_date, no user_id)
        cursor = self.conn.execute("PRAGMA table_info(schedules)")
        columns = [row[1] for row in cursor.fetchall()]
        if "start_date" not in columns:
            # Tabella vecchia, ricreo con nuova struttura (perdendo dati vecchi se esistenti)
            self.conn.execute("DROP TABLE IF EXISTS schedules")
            self.conn.execute("""
                CREATE TABLE schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id),
                    activity_id INTEGER REFERENCES activities(id),
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    planned_hours REAL NOT NULL CHECK(planned_hours > 0),
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            self.conn.commit()
        
        # Aggiungi budget a schedules
        cursor = self.conn.execute("PRAGMA table_info(schedules)")
        columns = [row[1] for row in cursor.fetchall()]
        if "budget" not in columns:
            self.conn.execute("ALTER TABLE schedules ADD COLUMN budget REAL NOT NULL DEFAULT 0 CHECK(budget >= 0)")
            self.conn.commit()
        
        # Aggiungi status a schedules
        cursor = self.conn.execute("PRAGMA table_info(schedules)")
        columns = [row[1] for row in cursor.fetchall()]
        if "status" not in columns:
            self.conn.execute("ALTER TABLE schedules ADD COLUMN status TEXT NOT NULL DEFAULT 'aperta' CHECK(status IN ('aperta', 'chiusa'))")
            self.conn.commit()
        
        # Aggiungi referente, telefono, email a clients
        cursor = self.conn.execute("PRAGMA table_info(clients)")
        columns = [row[1] for row in cursor.fetchall()]
        if "referente" not in columns:
            self.conn.execute("ALTER TABLE clients ADD COLUMN referente TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        if "telefono" not in columns:
            self.conn.execute("ALTER TABLE clients ADD COLUMN telefono TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        if "email" not in columns:
            self.conn.execute("ALTER TABLE clients ADD COLUMN email TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        
        # Aggiungi referente_commessa e descrizione_commessa a projects
        cursor = self.conn.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]
        if "referente_commessa" not in columns:
            self.conn.execute("ALTER TABLE projects ADD COLUMN referente_commessa TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        if "descrizione_commessa" not in columns:
            self.conn.execute("ALTER TABLE projects ADD COLUMN descrizione_commessa TEXT NOT NULL DEFAULT ''")
            self.conn.commit()
        
        # Aggiungi colonne permessi tab a users
        cursor = self.conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if "tab_calendar" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN tab_calendar INTEGER NOT NULL DEFAULT 1 CHECK(tab_calendar IN (0, 1))")
            self.conn.commit()
        if "tab_master" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN tab_master INTEGER NOT NULL DEFAULT 1 CHECK(tab_master IN (0, 1))")
            self.conn.commit()
        if "tab_plan" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN tab_plan INTEGER NOT NULL DEFAULT 1 CHECK(tab_plan IN (0, 1))")
            self.conn.commit()
        if "tab_control" not in columns:
            self.conn.execute("ALTER TABLE users ADD COLUMN tab_control INTEGER NOT NULL DEFAULT 1 CHECK(tab_control IN (0, 1))")
            self.conn.commit()

    def _seed_admin(self) -> None:
        row = self.conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if row:
            return

        self.conn.execute(
            """
            INSERT INTO users (username, full_name, role, password_hash, active)
            VALUES (?, ?, ?, ?, 1)
            """,
            ("admin", "Amministratore", "admin", self.hash_password("admin")),
        )
        self.conn.commit()

    def _fetchall(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _fetchone(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        row = self.conn.execute(query, params).fetchone()
        return dict(row) if row else None

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT id, username, full_name, role, active, tab_calendar, tab_master, tab_plan, tab_control
            FROM users
            WHERE username = ? AND password_hash = ? AND active = 1
            """,
            (username.strip(), self.hash_password(password)),
        )

    def list_users(self, include_inactive: bool = True) -> list[dict[str, Any]]:
        query = "SELECT id, username, full_name, role, active, tab_calendar, tab_master, tab_plan, tab_control FROM users"
        if not include_inactive:
            query += " WHERE active = 1"
        query += " ORDER BY username"
        return self._fetchall(query)

    def create_user(
        self, 
        username: str, 
        full_name: str, 
        role: str, 
        password: str,
        tab_calendar: bool = True,
        tab_master: bool = True,
        tab_plan: bool = True,
        tab_control: bool = True
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO users (username, full_name, role, password_hash, active, tab_calendar, tab_master, tab_plan, tab_control)
            VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                username.strip(), 
                full_name.strip(), 
                role, 
                self.hash_password(password),
                1 if tab_calendar else 0,
                1 if tab_master else 0,
                1 if tab_plan else 0,
                1 if tab_control else 0
            ),
        )
        self.conn.commit()

    def update_user(
        self, 
        user_id: int,
        username: str, 
        full_name: str, 
        role: str,
        tab_calendar: bool = True,
        tab_master: bool = True,
        tab_plan: bool = True,
        tab_control: bool = True
    ) -> None:
        """Aggiorna i dati di un utente (senza password)."""
        self.conn.execute(
            """
            UPDATE users 
            SET username = ?, full_name = ?, role = ?, tab_calendar = ?, tab_master = ?, tab_plan = ?, tab_control = ?
            WHERE id = ?
            """,
            (
                username.strip(), 
                full_name.strip(), 
                role,
                1 if tab_calendar else 0,
                1 if tab_master else 0,
                1 if tab_plan else 0,
                1 if tab_control else 0,
                user_id
            ),
        )
        self.conn.commit()

    def set_user_active(self, user_id: int, is_active: bool) -> None:
        self.conn.execute(
            "UPDATE users SET active = ? WHERE id = ?",
            (1 if is_active else 0, user_id),
        )
        self.conn.commit()

    def reset_user_password(self, user_id: int, new_password: str) -> None:
        self.conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (self.hash_password(new_password), user_id),
        )
        self.conn.commit()

    def update_user_tabs(
        self, 
        user_id: int, 
        tab_calendar: bool, 
        tab_master: bool, 
        tab_plan: bool, 
        tab_control: bool
    ) -> None:
        """Aggiorna i permessi tab per un utente."""
        self.conn.execute(
            "UPDATE users SET tab_calendar = ?, tab_master = ?, tab_plan = ?, tab_control = ? WHERE id = ?",
            (1 if tab_calendar else 0, 1 if tab_master else 0, 1 if tab_plan else 0, 1 if tab_control else 0, user_id),
        )
        self.conn.commit()

    # === USER PROJECT ASSIGNMENTS ===
    
    def assign_user_to_project(self, user_id: int, project_id: int) -> None:
        """Assegna un utente a una commessa."""
        self.conn.execute(
            "INSERT OR IGNORE INTO user_project_assignments (user_id, project_id) VALUES (?, ?)",
            (user_id, project_id),
        )
        self.conn.commit()
    
    def unassign_user_from_project(self, user_id: int, project_id: int) -> None:
        """Rimuove l'assegnazione di un utente da una commessa."""
        self.conn.execute(
            "DELETE FROM user_project_assignments WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        )
        self.conn.commit()
    
    def list_users_assigned_to_project(self, project_id: int) -> list[dict[str, Any]]:
        """Restituisce gli utenti assegnati a una commessa."""
        return self._fetchall(
            """
            SELECT u.id, u.username, u.full_name, u.role
            FROM users u
            JOIN user_project_assignments upa ON upa.user_id = u.id
            WHERE upa.project_id = ? AND u.active = 1
            ORDER BY u.full_name
            """,
            (project_id,),
        )
    
    def list_projects_assigned_to_user(self, user_id: int, only_open: bool = False) -> list[dict[str, Any]]:
        """Restituisce le commesse a cui un utente è assegnato."""
        where_clause = "AND s.status = 'aperta'" if only_open else ""
        return self._fetchall(
            f"""
            SELECT DISTINCT p.id, p.name, p.client_id, c.name AS client_name, p.hourly_rate, p.notes
            FROM projects p
            JOIN clients c ON c.id = p.client_id
            JOIN user_project_assignments upa ON upa.project_id = p.id
            LEFT JOIN schedules s ON s.project_id = p.id AND s.activity_id IS NULL
            WHERE upa.user_id = ? {where_clause}
            ORDER BY c.name, p.name
            """,
            (user_id,),
        )
    
    def is_user_assigned_to_project(self, user_id: int, project_id: int) -> bool:
        """Verifica se un utente è assegnato a una commessa."""
        row = self._fetchone(
            "SELECT 1 FROM user_project_assignments WHERE user_id = ? AND project_id = ?",
            (user_id, project_id),
        )
        return row is not None
    
    def user_can_access_activity(self, user_id: int, project_id: int, activity_id: int) -> bool:
        """Verifica se un utente può accedere a un'attività (tramite assegnazione alla commessa)."""
        # Verifica che l'attività appartenga alla commessa
        activity = self._fetchone(
            "SELECT id FROM activities WHERE id = ? AND project_id = ?",
            (activity_id, project_id),
        )
        if not activity:
            return False
        
        # Verifica assegnazione utente alla commessa
        return self.is_user_assigned_to_project(user_id, project_id)

    # === CLIENTS ===

    def add_client(self, name: str, hourly_rate: float, notes: str = "", referente: str = "", telefono: str = "", email: str = "") -> None:
        self.conn.execute(
            "INSERT INTO clients (name, hourly_rate, notes, referente, telefono, email) VALUES (?, ?, ?, ?, ?, ?)",
            (name.strip(), hourly_rate, notes.strip(), referente.strip(), telefono.strip(), email.strip()),
        )
        self.conn.commit()

    def update_client(self, client_id: int, name: str, hourly_rate: float, notes: str = "", referente: str = "", telefono: str = "", email: str = "") -> None:
        self.conn.execute(
            "UPDATE clients SET name = ?, hourly_rate = ?, notes = ?, referente = ?, telefono = ?, email = ? WHERE id = ?",
            (name.strip(), hourly_rate, notes.strip(), referente.strip(), telefono.strip(), email.strip(), client_id),
        )
        self.conn.commit()

    def delete_client(self, client_id: int) -> None:
        """Elimina un cliente e tutti i suoi dati associati (progetti, attività, timesheet, schedules)."""
        # Elimina timesheet di tutti i progetti del cliente
        self.conn.execute("DELETE FROM timesheets WHERE client_id = ?", (client_id,))
        # Elimina schedule di tutti i progetti del cliente
        self.conn.execute("DELETE FROM schedules WHERE project_id IN (SELECT id FROM projects WHERE client_id = ?)", (client_id,))
        # Elimina attività di tutti i progetti del cliente
        self.conn.execute("DELETE FROM activities WHERE project_id IN (SELECT id FROM projects WHERE client_id = ?)", (client_id,))
        # Elimina progetti del cliente
        self.conn.execute("DELETE FROM projects WHERE client_id = ?", (client_id,))
        # Elimina il cliente
        self.conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        self.conn.commit()

    def add_project(self, client_id: int, name: str, hourly_rate: float, notes: str = "", referente_commessa: str = "", descrizione_commessa: str = "") -> int:
        cursor = self.conn.execute(
            "INSERT INTO projects (client_id, name, hourly_rate, notes, referente_commessa, descrizione_commessa) VALUES (?, ?, ?, ?, ?, ?)",
            (client_id, name.strip(), hourly_rate, notes.strip(), referente_commessa.strip(), descrizione_commessa.strip()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def update_project(self, project_id: int, name: str, hourly_rate: float, notes: str = "", referente_commessa: str = "", descrizione_commessa: str = "") -> None:
        self.conn.execute(
            "UPDATE projects SET name = ?, hourly_rate = ?, notes = ?, referente_commessa = ?, descrizione_commessa = ? WHERE id = ?",
            (name.strip(), hourly_rate, notes.strip(), referente_commessa.strip(), descrizione_commessa.strip(), project_id),
        )
        self.conn.commit()

    def delete_project(self, project_id: int) -> None:
        """Elimina un progetto e tutti i suoi dati associati (attività, timesheet, schedules)."""
        # Elimina timesheet del progetto
        self.conn.execute("DELETE FROM timesheets WHERE project_id = ?", (project_id,))
        # Elimina schedule del progetto
        self.conn.execute("DELETE FROM schedules WHERE project_id = ?", (project_id,))
        # Elimina attività del progetto
        self.conn.execute("DELETE FROM activities WHERE project_id = ?", (project_id,))
        # Elimina il progetto
        self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self.conn.commit()

    def add_activity(self, project_id: int, name: str, hourly_rate: float, notes: str = "") -> int:
        cursor = self.conn.execute(
            "INSERT INTO activities (project_id, name, hourly_rate, notes) VALUES (?, ?, ?, ?)",
            (project_id, name.strip(), hourly_rate, notes.strip()),
        )
        self.conn.commit()
        return cursor.lastrowid

    def list_clients(self) -> list[dict[str, Any]]:
        return self._fetchall(
            """
            SELECT id, name, hourly_rate, notes, referente, telefono, email
            FROM clients
            ORDER BY name
            """
        )

    def list_projects(self, client_id: int | None = None, only_with_open_schedules: bool = False, user_id: int | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where_clauses = []
        joins = ""
        
        if client_id is not None:
            where_clauses.append("p.client_id = ?")
            params.append(client_id)
        
        if only_with_open_schedules:
            # Mostra solo progetti con almeno una schedule aperta
            where_clauses.append("p.id IN (SELECT DISTINCT project_id FROM schedules WHERE status = 'aperta')")
            # Escludi progetti che hanno una schedule chiusa a livello progetto
            where_clauses.append("p.id NOT IN (SELECT DISTINCT project_id FROM schedules WHERE status = 'chiusa' AND activity_id IS NULL)")
        
        if user_id is not None:
            # Filtra solo progetti assegnati all'utente
            joins = "JOIN user_project_assignments upa ON upa.project_id = p.id"
            where_clauses.append("upa.user_id = ?")
            params.append(user_id)
        
        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)

        return self._fetchall(
            f"""
            SELECT p.id, p.client_id, p.name, p.hourly_rate, p.notes, p.referente_commessa, p.descrizione_commessa, 
                   c.name AS client_name, c.referente AS client_referente, c.telefono AS client_telefono, c.email AS client_email
            FROM projects p
            JOIN clients c ON c.id = p.client_id
            {joins}
            {where}
            ORDER BY c.name, p.name
            """,
            tuple(params),
        )

    def list_activities(self, project_id: int | None = None, only_with_open_schedules: bool = False) -> list[dict[str, Any]]:
        params: list[Any] = []
        where_clauses = []
        
        if project_id is not None:
            where_clauses.append("a.project_id = ?")
            params.append(project_id)
        
        if only_with_open_schedules:
            # Mostra solo attività con almeno una schedule aperta
            where_clauses.append("a.id IN (SELECT DISTINCT activity_id FROM schedules WHERE status = 'aperta' AND activity_id IS NOT NULL)")
            # Escludi attività di progetti che hanno una schedule chiusa a livello progetto
            where_clauses.append("a.project_id NOT IN (SELECT DISTINCT project_id FROM schedules WHERE status = 'chiusa' AND activity_id IS NULL)")
        
        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)

        return self._fetchall(
            f"""
            SELECT a.id, a.project_id, a.name, a.hourly_rate, a.notes, p.name AS project_name
            FROM activities a
            JOIN projects p ON p.id = a.project_id
            {where}
            ORDER BY p.name, a.name
            """,
            tuple(params),
        )

    def update_activity(self, activity_id: int, name: str, hourly_rate: float, notes: str = "") -> None:
        self.conn.execute(
            "UPDATE activities SET name = ?, hourly_rate = ?, notes = ? WHERE id = ?",
            (name.strip(), hourly_rate, notes.strip(), activity_id),
        )
        self.conn.commit()

    def delete_activity(self, activity_id: int) -> None:
        """Elimina un'attività e tutti i suoi dati associati (timesheet, schedules)."""
        # Elimina prima i timesheet associati
        self.conn.execute("DELETE FROM timesheets WHERE activity_id = ?", (activity_id,))
        # Elimina gli schedule associati
        self.conn.execute("DELETE FROM schedules WHERE activity_id = ?", (activity_id,))
        # Elimina l'attività
        self.conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
        self.conn.commit()

    def resolve_effective_rate(self, client_id: int, project_id: int, activity_id: int) -> float:
        row = self._fetchone(
            """
            SELECT c.hourly_rate AS client_rate,
                   p.hourly_rate AS project_rate,
                   a.hourly_rate AS activity_rate
            FROM activities a
            JOIN projects p ON p.id = a.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE c.id = ? AND p.id = ? AND a.id = ?
            """,
            (client_id, project_id, activity_id),
        )
        if not row:
            raise ValueError("Relazione cliente, commessa e attivita non valida.")

        if row["activity_rate"] != 0:
            return float(row["activity_rate"])
        if row["project_rate"] != 0:
            return float(row["project_rate"])
        return float(row["client_rate"])

    def add_timesheet(
        self,
        user_id: int,
        work_date: str,
        client_id: int,
        project_id: int,
        activity_id: int,
        hours: float,
        note: str,
    ) -> None:
        rate = self.resolve_effective_rate(client_id, project_id, activity_id)
        cost = round(hours * rate, 2)
        self.conn.execute(
            """
            INSERT INTO timesheets (
                user_id, work_date, client_id, project_id, activity_id,
                hours, note, effective_rate, cost
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, work_date, client_id, project_id, activity_id, hours, note.strip(), rate, cost),
        )
        self.conn.commit()

    def delete_timesheet(self, entry_id: int, user_id: int, is_admin: bool) -> None:
        if is_admin:
            self.conn.execute("DELETE FROM timesheets WHERE id = ?", (entry_id,))
        else:
            self.conn.execute(
                "DELETE FROM timesheets WHERE id = ? AND user_id = ?",
                (entry_id, user_id),
            )
        self.conn.commit()

    def list_timesheets_for_day(self, work_date: str, user_id: int | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [work_date]
        where = "WHERE t.work_date = ?"
        if user_id is not None:
            where += " AND t.user_id = ?"
            params.append(user_id)

        return self._fetchall(
            f"""
            SELECT t.id, t.work_date, t.hours, t.note, t.effective_rate, t.cost,
                   u.username,
                   c.name AS client_name,
                   p.name AS project_name,
                   a.name AS activity_name
            FROM timesheets t
            JOIN users u ON u.id = t.user_id
            JOIN clients c ON c.id = t.client_id
            JOIN projects p ON p.id = t.project_id
            JOIN activities a ON a.id = t.activity_id
            {where}
            ORDER BY t.created_at DESC
            """,
            tuple(params),
        )

    def get_month_hours_summary(self, year: int, month: int, user_id: int | None = None) -> dict[int, float]:
        """Restituisce un dizionario {giorno: ore_totali} per il mese specificato."""
        year_month = f"{year:04d}-{month:02d}"
        params: list[Any] = [year_month]
        where = "WHERE substr(t.work_date, 1, 7) = ?"
        if user_id is not None:
            where += " AND t.user_id = ?"
            params.append(user_id)

        rows = self._fetchall(
            f"""
            SELECT substr(t.work_date, 9, 2) AS day, SUM(t.hours) AS total_hours
            FROM timesheets t
            {where}
            GROUP BY substr(t.work_date, 9, 2)
            """,
            tuple(params),
        )
        return {int(row["day"]): row["total_hours"] for row in rows}

    def get_activity_actual_data(self, project_id: int, activity_id: int) -> dict[str, float]:
        """Restituisce ore effettive e costo effettivo per un'attività specifica.
        
        Args:
            project_id: ID del progetto
            activity_id: ID dell'attività
            
        Returns:
            Dizionario con chiavi 'actual_hours' e 'actual_cost'
        """
        result = self._fetchone(
            """
            SELECT COALESCE(SUM(hours), 0) AS actual_hours,
                   COALESCE(SUM(cost), 0) AS actual_cost
            FROM timesheets
            WHERE project_id = ? AND activity_id = ?
            """,
            (project_id, activity_id)
        )
        
        if result:
            return {
                "actual_hours": float(result["actual_hours"]),
                "actual_cost": float(result["actual_cost"])
            }
        else:
            return {"actual_hours": 0.0, "actual_cost": 0.0}

    def add_schedule(
        self,
        project_id: int,
        activity_id: int | None,
        start_date: str,
        end_date: str,
        planned_hours: float,
        note: str,
        budget: float = 0.0,
    ) -> None:
        if activity_id is not None:
            check = self._fetchone(
                "SELECT id FROM activities WHERE id = ? AND project_id = ?",
                (activity_id, project_id),
            )
            if not check:
                raise ValueError("Attivita non coerente con la commessa selezionata.")

        self.conn.execute(
            """
            INSERT INTO schedules (project_id, activity_id, start_date, end_date, planned_hours, note, budget)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, activity_id, start_date, end_date, planned_hours, note.strip(), budget),
        )
        self.conn.commit()

    def update_schedule(
        self,
        schedule_id: int,
        project_id: int,
        activity_id: int | None,
        start_date: str,
        end_date: str,
        planned_hours: float,
        note: str,
        budget: float = 0.0,
    ) -> None:
        if activity_id is not None:
            check = self._fetchone(
                "SELECT id FROM activities WHERE id = ? AND project_id = ?",
                (activity_id, project_id),
            )
            if not check:
                raise ValueError("Attivita non coerente con la commessa selezionata.")

        self.conn.execute(
            """
            UPDATE schedules 
            SET project_id = ?, activity_id = ?, start_date = ?, end_date = ?, planned_hours = ?, note = ?, budget = ?
            WHERE id = ?
            """,
            (project_id, activity_id, start_date, end_date, planned_hours, note.strip(), budget, schedule_id),
        )
        self.conn.commit()

    def delete_schedule(self, schedule_id: int) -> None:
        self.conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        self.conn.commit()
    
    def update_schedule_status(self, schedule_id: int, status: str) -> None:
        """Aggiorna lo status di una schedulazione (aperta/chiusa)."""
        if status not in ('aperta', 'chiusa'):
            raise ValueError("Status deve essere 'aperta' o 'chiusa'")
        self.conn.execute(
            "UPDATE schedules SET status = ? WHERE id = ?",
            (status, schedule_id)
        )
        self.conn.commit()

    def list_schedules(self, only_open: bool = False) -> list[dict[str, Any]]:
        """Elenca tutte le programmazioni con dettagli cliente/commessa/attività.
        
        Args:
            only_open: Se True, filtra solo le schedule con status='aperta'
        """
        where_clause = "WHERE s.status = 'aperta'" if only_open else ""
        query = f"""
            SELECT s.id, s.project_id, s.activity_id, s.start_date, s.end_date, 
                   s.planned_hours, s.note, s.budget, s.status,
                   c.name AS client_name,
                   p.name AS project_name,
                   a.name AS activity_name
            FROM schedules s
            JOIN projects p ON p.id = s.project_id
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN activities a ON a.id = s.activity_id
            {where_clause}
            ORDER BY s.start_date DESC, c.name, p.name
        """
        return self._fetchall(query)

    def get_schedule_control_data(self) -> list[dict[str, Any]]:
        """Calcola per ogni programmazione: ore pianificate, ore svolte, ore mancanti, giorni mancanti, budget e costi effettivi."""
        schedules = self.list_schedules()
        result = []
        
        for schedule in schedules:
            # Calcola ore svolte e costi effettivi nel periodo per il progetto/attività
            if schedule["activity_id"] is not None:
                # Programmazione per attività specifica
                actual = self._fetchone(
                    """
                    SELECT COALESCE(SUM(hours), 0) AS actual_hours,
                           COALESCE(SUM(cost), 0) AS actual_cost
                    FROM timesheets
                    WHERE project_id = ? AND activity_id = ? 
                      AND work_date >= ? AND work_date <= ?
                    """,
                    (schedule["project_id"], schedule["activity_id"], 
                     schedule["start_date"], schedule["end_date"]),
                )
                
                # Recupera i singoli inserimenti timesheet
                timesheet_details = self._fetchall(
                    """
                    SELECT t.work_date, t.hours, t.note, u.username, u.full_name
                    FROM timesheets t
                    JOIN users u ON u.id = t.user_id
                    WHERE t.project_id = ? AND t.activity_id = ? 
                      AND t.work_date >= ? AND t.work_date <= ?
                    ORDER BY t.work_date DESC
                    """,
                    (schedule["project_id"], schedule["activity_id"], 
                     schedule["start_date"], schedule["end_date"]),
                )
            else:
                # Programmazione per commessa (tutte le attività)
                actual = self._fetchone(
                    """
                    SELECT COALESCE(SUM(hours), 0) AS actual_hours,
                           COALESCE(SUM(cost), 0) AS actual_cost
                    FROM timesheets
                    WHERE project_id = ? 
                      AND work_date >= ? AND work_date <= ?
                    """,
                    (schedule["project_id"], schedule["start_date"], schedule["end_date"]),
                )
                
                # Recupera i singoli inserimenti timesheet
                timesheet_details = self._fetchall(
                    """
                    SELECT t.work_date, t.hours, t.note, u.username, u.full_name, a.name AS activity_name
                    FROM timesheets t
                    JOIN users u ON u.id = t.user_id
                    JOIN activities a ON a.id = t.activity_id
                    WHERE t.project_id = ? 
                      AND t.work_date >= ? AND t.work_date <= ?
                    ORDER BY t.work_date DESC
                    """,
                    (schedule["project_id"], schedule["start_date"], schedule["end_date"]),
                )
            
            actual_hours = float(actual["actual_hours"]) if actual else 0.0
            actual_cost = float(actual["actual_cost"]) if actual else 0.0
            planned_hours = float(schedule["planned_hours"])
            remaining_hours = planned_hours - actual_hours
            
            # Budget e costo residuo
            budget = float(schedule.get("budget", 0))
            remaining_budget = budget - actual_cost
            
            # Calcola giorni mancanti (end_date - oggi)
            from datetime import datetime, date
            try:
                end_date = datetime.strptime(schedule["end_date"], "%Y-%m-%d").date()
                today = date.today()
                remaining_days = (end_date - today).days
            except:
                remaining_days = 0
            
            result.append({
                "id": schedule["id"],
                "client_name": schedule["client_name"],
                "project_name": schedule["project_name"],
                "activity_name": schedule["activity_name"] or "(Tutta la commessa)",
                "start_date": schedule["start_date"],
                "end_date": schedule["end_date"],
                "planned_hours": planned_hours,
                "actual_hours": actual_hours,
                "remaining_hours": remaining_hours,
                "remaining_days": remaining_days,
                "budget": budget,
                "actual_cost": actual_cost,
                "remaining_budget": remaining_budget,
                "status": schedule.get("status", "aperta"),
                "note": schedule["note"],
                "timesheet_details": timesheet_details,
            })
        
        return result

    def get_hierarchical_timesheet_data(self) -> list[dict[str, Any]]:
        """Recupera tutti i dati organizzati gerarchicamente con pianificazione: Cliente > Commessa > Attività > Inserimenti."""
        from datetime import datetime, date
        
        # Recupera tutti i clienti che hanno progetti con schedules O timesheet
        clients = self._fetchall(
            """
            SELECT DISTINCT c.id, c.name, c.hourly_rate
            FROM clients c
            JOIN projects p ON p.client_id = c.id
            LEFT JOIN schedules s ON s.project_id = p.id
            LEFT JOIN timesheets t ON t.project_id = p.id
            WHERE s.id IS NOT NULL OR t.id IS NOT NULL
            ORDER BY c.name
            """
        )
        
        result = []
        today = date.today()
        
        for client in clients:
            # Recupera tutte le commesse del cliente con schedules O timesheet
            projects = self._fetchall(
                """
                SELECT DISTINCT p.id, p.name, p.hourly_rate
                FROM projects p
                LEFT JOIN schedules s ON s.project_id = p.id
                LEFT JOIN timesheets t ON t.project_id = p.id
                WHERE p.client_id = ? AND (s.id IS NOT NULL OR t.id IS NOT NULL)
                ORDER BY p.name
                """,
                (client["id"],)
            )
            
            projects_data = []
            
            for project in projects:
                # Verifica se esiste una schedule a livello progetto (senza activity_id)
                project_schedule = self._fetchone(
                    """
                    SELECT id, start_date, end_date, planned_hours, budget, status, note
                    FROM schedules
                    WHERE project_id = ? AND activity_id IS NULL
                    ORDER BY end_date DESC
                    LIMIT 1
                    """,
                    (project["id"],)
                )
                
                # Recupera le attività con schedules O timesheet per questo progetto
                activities = self._fetchall(
                    """
                    SELECT DISTINCT a.id, a.name, a.hourly_rate
                    FROM activities a
                    LEFT JOIN schedules s ON s.activity_id = a.id AND s.project_id = ?
                    LEFT JOIN timesheets t ON t.activity_id = a.id AND t.project_id = ?
                    WHERE (s.id IS NOT NULL OR t.id IS NOT NULL)
                    ORDER BY a.name
                    """,
                    (project["id"], project["id"])
                )
                
                activities_data = []
                project_planned_hours = 0.0
                project_actual_hours = 0.0
                project_budget = 0.0
                project_actual_cost = 0.0
                project_start_date = None
                project_end_date = None
                
                if project_schedule:
                    # Schedule a livello progetto
                    project_planned_hours = float(project_schedule["planned_hours"])
                    project_budget = float(project_schedule.get("budget", 0))
                    project_start_date = project_schedule["start_date"]
                    project_end_date = project_schedule["end_date"]
                    
                    # Recupera timesheet per l'intero progetto
                    timesheets_summary = self._fetchone(
                        """
                        SELECT COALESCE(SUM(hours), 0) AS total_hours,
                               COALESCE(SUM(cost), 0) AS total_cost
                        FROM timesheets
                        WHERE project_id = ?
                        """,
                        (project["id"],)
                    )
                    project_actual_hours = float(timesheets_summary["total_hours"])
                    project_actual_cost = float(timesheets_summary["total_cost"])
                
                for activity in activities:
                    # Recupera schedule per l'attività
                    activity_schedule = self._fetchone(
                        """
                        SELECT id, start_date, end_date, planned_hours, budget, status, note
                        FROM schedules
                        WHERE project_id = ? AND activity_id = ?
                        ORDER BY end_date DESC
                        LIMIT 1
                        """,
                        (project["id"], activity["id"])
                    )
                    
                    # Recupera timesheet per l'attività
                    timesheets = self._fetchall(
                        """
                        SELECT t.id, t.work_date, t.hours, t.cost, t.note,
                               u.username, u.full_name
                        FROM timesheets t
                        JOIN users u ON u.id = t.user_id
                        WHERE t.project_id = ? AND t.activity_id = ?
                        ORDER BY t.work_date DESC
                        """,
                        (project["id"], activity["id"])
                    )
                    
                    activity_actual_hours = sum(float(ts["hours"]) for ts in timesheets)
                    activity_actual_cost = sum(float(ts["cost"]) for ts in timesheets)
                    
                    activity_data = {
                        "id": activity["id"],
                        "name": activity["name"],
                        "hourly_rate": activity["hourly_rate"],
                        "actual_hours": activity_actual_hours,
                        "actual_cost": activity_actual_cost,
                        "timesheets": timesheets
                    }
                    
                    if activity_schedule:
                        activity_data["schedule_id"] = activity_schedule["id"]
                        activity_data["start_date"] = activity_schedule["start_date"]
                        activity_data["end_date"] = activity_schedule["end_date"]
                        activity_data["planned_hours"] = float(activity_schedule["planned_hours"])
                        activity_data["budget"] = float(activity_schedule.get("budget", 0))
                        activity_data["status"] = activity_schedule.get("status", "aperta")
                        activity_data["schedule_note"] = activity_schedule.get("note", "")
                        
                        # Calcola giorni restanti
                        try:
                            end_date = datetime.strptime(activity_schedule["end_date"], "%Y-%m-%d").date()
                            activity_data["remaining_days"] = (end_date - today).days
                        except:
                            activity_data["remaining_days"] = 0
                        
                        # Calcola giorni lavorativi
                        activity_data["working_days"] = self.calculate_working_days(
                            activity_schedule["start_date"], 
                            activity_schedule["end_date"]
                        )
                        
                        # Calcola differenze
                        activity_data["hours_diff"] = activity_data["planned_hours"] - activity_actual_hours
                        activity_data["budget_remaining"] = activity_data["budget"] - activity_actual_cost
                    else:
                        activity_data["schedule_id"] = None
                        activity_data["start_date"] = None
                        activity_data["end_date"] = None
                        activity_data["planned_hours"] = 0.0
                        activity_data["budget"] = 0.0
                        activity_data["status"] = None
                        activity_data["schedule_note"] = ""
                        activity_data["remaining_days"] = 0
                        activity_data["working_days"] = 0
                        activity_data["hours_diff"] = 0.0
                        activity_data["budget_remaining"] = 0.0
                    
                    activities_data.append(activity_data)
                    
                    # Aggrega al progetto (solo se non c'è schedule a livello progetto)
                    if not project_schedule:
                        if activity_data["planned_hours"] > 0:
                            project_planned_hours += activity_data["planned_hours"]
                        project_actual_hours += activity_actual_hours
                        if activity_data["budget"] > 0:
                            project_budget += activity_data["budget"]
                        project_actual_cost += activity_actual_cost
                        
                        # Aggregazione date (prendi la più recente)
                        if activity_data["start_date"]:
                            if not project_start_date or activity_data["start_date"] < project_start_date:
                                project_start_date = activity_data["start_date"]
                        if activity_data["end_date"]:
                            if not project_end_date or activity_data["end_date"] > project_end_date:
                                project_end_date = activity_data["end_date"]
                
                # Calcola dati aggregati del progetto
                project_hours_diff = project_planned_hours - project_actual_hours
                project_budget_remaining = project_budget - project_actual_cost
                
                # Calcola giorni restanti del progetto
                project_remaining_days = 0
                if project_end_date:
                    try:
                        end_date = datetime.strptime(project_end_date, "%Y-%m-%d").date()
                        project_remaining_days = (end_date - today).days
                    except:
                        pass
                
                # Calcola giorni lavorativi del progetto
                project_working_days = self.calculate_working_days(project_start_date, project_end_date)
                
                project_data = {
                    "id": project["id"],
                    "name": project["name"],
                    "hourly_rate": project["hourly_rate"],
                    "start_date": project_start_date,
                    "end_date": project_end_date,
                    "planned_hours": project_planned_hours,
                    "actual_hours": project_actual_hours,
                    "hours_diff": project_hours_diff,
                    "budget": project_budget,
                    "actual_cost": project_actual_cost,
                    "budget_remaining": project_budget_remaining,
                    "remaining_days": project_remaining_days,
                    "working_days": project_working_days,
                    "status": project_schedule.get("status") if project_schedule else None,
                    "activities": activities_data
                }
                
                projects_data.append(project_data)
            
            # Aggrega dati del cliente
            client_planned_hours = sum(p["planned_hours"] for p in projects_data)
            client_actual_hours = sum(p["actual_hours"] for p in projects_data)
            client_hours_diff = client_planned_hours - client_actual_hours
            client_budget = sum(p["budget"] for p in projects_data)
            client_actual_cost = sum(p["actual_cost"] for p in projects_data)
            client_budget_remaining = client_budget - client_actual_cost
            
            # Data più recente per il cliente
            client_start_dates = [p["start_date"] for p in projects_data if p["start_date"]]
            client_end_dates = [p["end_date"] for p in projects_data if p["end_date"]]
            client_start_date = min(client_start_dates) if client_start_dates else None
            client_end_date = max(client_end_dates) if client_end_dates else None
            
            client_remaining_days = 0
            if client_end_date:
                try:
                    end_date = datetime.strptime(client_end_date, "%Y-%m-%d").date()
                    client_remaining_days = (end_date - today).days
                except:
                    pass
            
            # Calcola giorni lavorativi del cliente
            client_working_days = self.calculate_working_days(client_start_date, client_end_date)
            
            result.append({
                "id": client["id"],
                "name": client["name"],
                "hourly_rate": client["hourly_rate"],
                "start_date": client_start_date,
                "end_date": client_end_date,
                "planned_hours": client_planned_hours,
                "actual_hours": client_actual_hours,
                "hours_diff": client_hours_diff,
                "budget": client_budget,
                "actual_cost": client_actual_cost,
                "budget_remaining": client_budget_remaining,
                "remaining_days": client_remaining_days,
                "working_days": client_working_days,
                "projects": projects_data
            })
        
        return result

    def get_schedule_report_data(self, schedule_id: int) -> dict[str, Any] | None:
        """Recupera tutti i dati necessari per il report di una programmazione specifica."""
        schedule = self._fetchone(
            """
            SELECT s.id, s.project_id, s.activity_id, s.start_date, s.end_date,
                   s.planned_hours, s.note, s.budget,
                   c.name AS client_name, c.hourly_rate AS client_rate,
                   p.name AS project_name, p.hourly_rate AS project_rate,
                   a.name AS activity_name, a.hourly_rate AS activity_rate
            FROM schedules s
            JOIN projects p ON p.id = s.project_id
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN activities a ON a.id = s.activity_id
            WHERE s.id = ?
            """,
            (schedule_id,),
        )
        
        if not schedule:
            return None
        
        # Calcola ore svolte e costi
        if schedule["activity_id"] is not None:
            # Programmazione per attività specifica
            actual = self._fetchone(
                """
                SELECT COALESCE(SUM(hours), 0) AS actual_hours,
                       COALESCE(SUM(cost), 0) AS actual_cost
                FROM timesheets
                WHERE project_id = ? AND activity_id = ?
                  AND work_date >= ? AND work_date <= ?
                """,
                (schedule["project_id"], schedule["activity_id"],
                 schedule["start_date"], schedule["end_date"]),
            )
            
            # Recupera dettagli timesheet con aggregazione per utente
            timesheet_details = self._fetchall(
                """
                SELECT t.work_date, t.hours, t.cost, t.note, u.username, u.full_name
                FROM timesheets t
                JOIN users u ON u.id = t.user_id
                WHERE t.project_id = ? AND t.activity_id = ?
                  AND t.work_date >= ? AND t.work_date <= ?
                ORDER BY t.work_date DESC
                """,
                (schedule["project_id"], schedule["activity_id"],
                 schedule["start_date"], schedule["end_date"]),
            )
            
            # Aggregazione per utente
            user_hours = self._fetchall(
                """
                SELECT u.username, u.full_name, SUM(t.hours) AS hours, SUM(t.cost) AS cost
                FROM timesheets t
                JOIN users u ON u.id = t.user_id
                WHERE t.project_id = ? AND t.activity_id = ?
                  AND t.work_date >= ? AND t.work_date <= ?
                GROUP BY u.id
                ORDER BY hours DESC
                """,
                (schedule["project_id"], schedule["activity_id"],
                 schedule["start_date"], schedule["end_date"]),
            )
        else:
            # Programmazione per commessa
            actual = self._fetchone(
                """
                SELECT COALESCE(SUM(hours), 0) AS actual_hours,
                       COALESCE(SUM(cost), 0) AS actual_cost
                FROM timesheets
                WHERE project_id = ?
                  AND work_date >= ? AND work_date <= ?
                """,
                (schedule["project_id"], schedule["start_date"], schedule["end_date"]),
            )
            
            timesheet_details = self._fetchall(
                """
                SELECT t.work_date, t.hours, t.cost, t.note, u.username, u.full_name, a.name AS activity_name
                FROM timesheets t
                JOIN users u ON u.id = t.user_id
                JOIN activities a ON a.id = t.activity_id
                WHERE t.project_id = ?
                  AND t.work_date >= ? AND t.work_date <= ?
                ORDER BY t.work_date DESC
                """,
                (schedule["project_id"], schedule["start_date"], schedule["end_date"]),
            )
            
            user_hours = self._fetchall(
                """
                SELECT u.username, u.full_name, SUM(t.hours) AS hours, SUM(t.cost) AS cost
                FROM timesheets t
                JOIN users u ON u.id = t.user_id
                WHERE t.project_id = ?
                  AND t.work_date >= ? AND t.work_date <= ?
                GROUP BY u.id
                ORDER BY hours DESC
                """,
                (schedule["project_id"], schedule["start_date"], schedule["end_date"]),
            )
        
        actual_hours = float(actual["actual_hours"]) if actual else 0.0
        actual_cost = float(actual["actual_cost"]) if actual else 0.0
        planned_hours = float(schedule["planned_hours"])
        budget = float(schedule.get("budget", 0.0))
        remaining_hours = planned_hours - actual_hours
        remaining_budget = budget - actual_cost
        
        # Calcola giorni mancanti e trascorsi
        from datetime import datetime, date
        try:
            start_date = datetime.strptime(schedule["start_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(schedule["end_date"], "%Y-%m-%d").date()
            today = date.today()
            total_days = (end_date - start_date).days + 1
            elapsed_days = max(0, (today - start_date).days + 1) if today >= start_date else 0
            remaining_days = (end_date - today).days
        except:
            total_days = 0
            elapsed_days = 0
            remaining_days = 0
        
        return {
            "id": schedule["id"],
            "client_name": schedule["client_name"],
            "project_name": schedule["project_name"],
            "activity_name": schedule["activity_name"] or "(Tutta la commessa)",
            "start_date": schedule["start_date"],
            "end_date": schedule["end_date"],
            "planned_hours": planned_hours,
            "actual_hours": actual_hours,
            "remaining_hours": remaining_hours,
            "budget": budget,
            "actual_cost": actual_cost,
            "remaining_budget": remaining_budget,
            "total_days": total_days,
            "elapsed_days": elapsed_days,
            "remaining_days": remaining_days,
            "note": schedule["note"],
            "timesheet_details": timesheet_details,
            "user_hours": user_hours,
        }

    def control_snapshot(self, year: int, month: int, user_id: int | None = None) -> dict[str, Any]:
        month_key = f"{year:04d}-{month:02d}"

        actual_params: list[Any] = [month_key]
        actual_filter = "WHERE substr(t.work_date, 1, 7) = ?"
        if user_id is not None:
            actual_filter += " AND t.user_id = ?"
            actual_params.append(user_id)

        planned_params: list[Any] = [month_key]
        planned_filter = "WHERE substr(s.planned_date, 1, 7) = ?"
        if user_id is not None:
            planned_filter += " AND s.user_id = ?"
            planned_params.append(user_id)

        totals_actual = self._fetchone(
            f"""
            SELECT COALESCE(SUM(t.hours), 0) AS total_hours,
                   COALESCE(SUM(t.cost), 0) AS total_cost
            FROM timesheets t
            {actual_filter}
            """,
            tuple(actual_params),
        ) or {"total_hours": 0.0, "total_cost": 0.0}

        totals_planned = self._fetchone(
            f"""
            SELECT COALESCE(SUM(s.planned_hours), 0) AS planned_hours
            FROM schedules s
            {planned_filter}
            """,
            tuple(planned_params),
        ) or {"planned_hours": 0.0}

        actual_rows = self._fetchall(
            f"""
            SELECT t.project_id,
                   p.name AS project_name,
                   t.activity_id,
                   a.name AS activity_name,
                   SUM(t.hours) AS actual_hours,
                   SUM(t.cost) AS actual_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN activities a ON a.id = t.activity_id
            {actual_filter}
            GROUP BY t.project_id, t.activity_id
            ORDER BY p.name, a.name
            """,
            tuple(actual_params),
        )

        planned_rows = self._fetchall(
            f"""
            SELECT s.project_id,
                   p.name AS project_name,
                   s.activity_id,
                   a.name AS activity_name,
                   SUM(s.planned_hours) AS planned_hours
            FROM schedules s
            JOIN projects p ON p.id = s.project_id
            JOIN activities a ON a.id = s.activity_id
            {planned_filter}
            GROUP BY s.project_id, s.activity_id
            ORDER BY p.name, a.name
            """,
            tuple(planned_params),
        )

        merged: dict[tuple[int, int], dict[str, Any]] = {}
        for row in actual_rows:
            key = (row["project_id"], row["activity_id"])
            merged[key] = {
                "project_name": row["project_name"],
                "activity_name": row["activity_name"],
                "actual_hours": float(row["actual_hours"] or 0),
                "planned_hours": 0.0,
                "actual_cost": float(row["actual_cost"] or 0),
            }

        for row in planned_rows:
            key = (row["project_id"], row["activity_id"])
            if key not in merged:
                merged[key] = {
                    "project_name": row["project_name"],
                    "activity_name": row["activity_name"],
                    "actual_hours": 0.0,
                    "planned_hours": float(row["planned_hours"] or 0),
                    "actual_cost": 0.0,
                }
            else:
                merged[key]["planned_hours"] = float(row["planned_hours"] or 0)

        return {
            "total_hours": float(totals_actual["total_hours"] or 0),
            "total_cost": float(totals_actual["total_cost"] or 0),
            "planned_hours": float(totals_planned["planned_hours"] or 0),
            "rows": sorted(
                merged.values(),
                key=lambda x: (x["project_name"].lower(), x["activity_name"].lower()),
            ),
        }

    # === Funzioni per Report PDF ===
    
    def get_report_client_data(self, client_id: int, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Recupera dati per report cliente."""
        client = self._fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))
        if not client:
            return None
        
        date_filter = ""
        params = [client_id]
        if start_date and end_date:
            date_filter = " AND s.start_date <= ? AND s.end_date >= ?"
            params.extend([end_date, start_date])
        
        # Programmazioni del cliente
        schedules = self._fetchall(
            f"""
            SELECT s.*, p.name AS project_name, a.name AS activity_name
            FROM schedules s
            JOIN projects p ON p.id = s.project_id
            LEFT JOIN activities a ON a.id = s.activity_id
            WHERE p.client_id = ? {date_filter}
            ORDER BY s.start_date DESC
            """,
            tuple(params)
        )
        
        # Calcola totali
        total_planned_hours = 0.0
        total_budget = 0.0
        total_actual_hours = 0.0
        total_actual_cost = 0.0
        
        schedule_details = []
        for sched in schedules:
            # Ore svolte per questa programmazione
            if sched["activity_id"]:
                actual = self._fetchone(
                    "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE project_id = ? AND activity_id = ? AND work_date >= ? AND work_date <= ?",
                    (sched["project_id"], sched["activity_id"], sched["start_date"], sched["end_date"])
                )
            else:
                actual = self._fetchone(
                    "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE project_id = ? AND work_date >= ? AND work_date <= ?",
                    (sched["project_id"], sched["start_date"], sched["end_date"])
                )
            
            actual_hours = float(actual["hours"]) if actual else 0.0
            actual_cost = float(actual["cost"]) if actual else 0.0
            
            total_planned_hours += float(sched["planned_hours"])
            total_budget += float(sched.get("budget", 0.0))
            total_actual_hours += actual_hours
            total_actual_cost += actual_cost
            
            schedule_details.append({
                "project_name": sched["project_name"],
                "activity_name": sched["activity_name"] or "(Tutta la commessa)",
                "start_date": sched["start_date"],
                "end_date": sched["end_date"],
                "planned_hours": float(sched["planned_hours"]),
                "budget": float(sched.get("budget", 0.0)),
                "actual_hours": actual_hours,
                "actual_cost": actual_cost,
            })
        
        return {
            "client": dict(client),
            "schedules": schedule_details,
            "total_planned_hours": total_planned_hours,
            "total_budget": total_budget,
            "total_actual_hours": total_actual_hours,
            "total_actual_cost": total_actual_cost
        }
    
    def get_report_project_data(self, project_id: int) -> dict[str, Any]:
        """Recupera dati per report commessa."""
        project = self._fetchone(
            "SELECT p.*, c.name AS client_name FROM projects p JOIN clients c ON c.id = p.client_id WHERE p.id = ?",
            (project_id,)
        )
        if not project:
            return None
        
        # Programmazioni della commessa
        schedules = self._fetchall(
            """
            SELECT s.*, a.name AS activity_name
            FROM schedules s
            LEFT JOIN activities a ON a.id = s.activity_id
            WHERE s.project_id = ?
            ORDER BY s.start_date DESC
            """,
            (project_id,)
        )
        
        # Timesheet della commessa
        timesheets = self._fetchall(
            """
            SELECT t.*, u.username, u.full_name, a.name AS activity_name
            FROM timesheets t
            JOIN users u ON u.id = t.user_id
            JOIN activities a ON a.id = t.activity_id
            WHERE t.project_id = ?
            ORDER BY t.work_date DESC
            """,
            (project_id,)
        )
        
        # Aggregazione per attività
        activities_summary = self._fetchall(
            """
            SELECT a.name AS activity_name, 
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN activities a ON a.id = t.activity_id
            WHERE t.project_id = ?
            GROUP BY a.id
            ORDER BY total_hours DESC
            """,
            (project_id,)
        )
        
        # Aggregazione per utente
        users_summary = self._fetchall(
            """
            SELECT u.username, u.full_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN users u ON u.id = t.user_id
            WHERE t.project_id = ?
            GROUP BY u.id
            ORDER BY total_hours DESC
            """,
            (project_id,)
        )
        
        total_planned = sum(float(s["planned_hours"]) for s in schedules)
        total_budget = sum(float(s.get("budget", 0.0)) for s in schedules)
        total_actual = sum(float(t["hours"]) for t in timesheets)
        total_cost = sum(float(t["cost"]) for t in timesheets)
        
        return {
            "project": dict(project),
            "schedules": schedules,
            "timesheets": timesheets,
            "activities_summary": activities_summary,
            "users_summary": users_summary,
            "total_planned_hours": total_planned,
            "total_budget": total_budget,
            "total_actual_hours": total_actual,
            "total_actual_cost": total_cost
        }
    
    def get_report_period_data(self, start_date: str, end_date: str, client_id: int | None = None, project_id: int | None = None) -> dict[str, Any]:
        """Recupera dati per report periodo."""
        filters = []
        params = [start_date, end_date]
        
        if client_id:
            filters.append("p.client_id = ?")
            params.append(client_id)
        if project_id:
            filters.append("t.project_id = ?")
            params.append(project_id)
        
        where_clause = " AND " + " AND ".join(filters) if filters else ""
        
        # Timesheet nel periodo
        timesheets = self._fetchall(
            f"""
            SELECT t.*, c.name AS client_name, p.name AS project_name, 
                   a.name AS activity_name, u.username, u.full_name
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            JOIN activities a ON a.id = t.activity_id
            JOIN users u ON u.id = t.user_id
            WHERE t.work_date >= ? AND t.work_date <= ? {where_clause}
            ORDER BY t.work_date DESC
            """,
            tuple(params)
        )
        
        # Aggregazione per cliente
        clients_summary = self._fetchall(
            f"""
            SELECT c.name AS client_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE t.work_date >= ? AND t.work_date <= ? {where_clause}
            GROUP BY c.id
            ORDER BY total_hours DESC
            """,
            tuple(params)
        )
        
        # Aggregazione per commessa
        projects_summary = self._fetchall(
            f"""
            SELECT c.name AS client_name, p.name AS project_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE t.work_date >= ? AND t.work_date <= ? {where_clause}
            GROUP BY p.id
            ORDER BY total_hours DESC
            """,
            tuple(params)
        )
        
        # Aggregazione per utente
        users_summary = self._fetchall(
            f"""
            SELECT u.username, u.full_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN users u ON u.id = t.user_id
            WHERE t.work_date >= ? AND t.work_date <= ? {where_clause}
            GROUP BY u.id
            ORDER BY total_hours DESC
            """,
            tuple(params)
        )
        
        total_hours = sum(float(t["hours"]) for t in timesheets)
        total_cost = sum(float(t["cost"]) for t in timesheets)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "timesheets": timesheets,
            "clients_summary": clients_summary,
            "projects_summary": projects_summary,
            "users_summary": users_summary,
            "total_hours": total_hours,
            "total_cost": total_cost
        }
    
    def get_report_user_data(self, user_id: int, start_date: str, end_date: str) -> dict[str, Any]:
        """Recupera dati per report utente."""
        user = self._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
        if not user:
            return None
        
        # Timesheet dell'utente nel periodo
        timesheets = self._fetchall(
            """
            SELECT t.*, c.name AS client_name, p.name AS project_name, a.name AS activity_name
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            JOIN activities a ON a.id = t.activity_id
            WHERE t.user_id = ? AND t.work_date >= ? AND t.work_date <= ?
            ORDER BY t.work_date DESC
            """,
            (user_id, start_date, end_date)
        )
        
        # Aggregazione per cliente
        clients_summary = self._fetchall(
            """
            SELECT c.name AS client_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE t.user_id = ? AND t.work_date >= ? AND t.work_date <= ?
            GROUP BY c.id
            ORDER BY total_hours DESC
            """,
            (user_id, start_date, end_date)
        )
        
        # Aggregazione per commessa
        projects_summary = self._fetchall(
            """
            SELECT c.name AS client_name, p.name AS project_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            WHERE t.user_id = ? AND t.work_date >= ? AND t.work_date <= ?
            GROUP BY p.id
            ORDER BY total_hours DESC
            """,
            (user_id, start_date, end_date)
        )
        
        # Aggregazione per attività
        activities_summary = self._fetchall(
            """
            SELECT a.name AS activity_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN activities a ON a.id = t.activity_id
            WHERE t.user_id = ? AND t.work_date >= ? AND t.work_date <= ?
            GROUP BY a.id
            ORDER BY total_hours DESC
            """,
            (user_id, start_date, end_date)
        )
        
        total_hours = sum(float(t["hours"]) for t in timesheets)
        total_cost = sum(float(t["cost"]) for t in timesheets)
        
        # Calcola giorni lavorativi
        work_dates = set(t["work_date"] for t in timesheets)
        work_days = len(work_dates)
        avg_hours_per_day = total_hours / work_days if work_days > 0 else 0
        
        return {
            "user": dict(user),
            "start_date": start_date,
            "end_date": end_date,
            "timesheets": timesheets,
            "clients_summary": clients_summary,
            "projects_summary": projects_summary,
            "activities_summary": activities_summary,
            "total_hours": total_hours,
            "total_cost": total_cost,
            "work_days": work_days,
            "avg_hours_per_day": avg_hours_per_day
        }
    
    def get_report_general_data(self, start_date: str | None = None, end_date: str | None = None) -> dict[str, Any]:
        """Recupera dati per report generale/riepilogativo."""
        date_filter = ""
        params = []
        
        if start_date and end_date:
            date_filter = " WHERE t.work_date >= ? AND t.work_date <= ?"
            params = [start_date, end_date]
        
        # Programmazioni attive
        schedules = self.get_schedule_control_data()
        
        # Totali per cliente
        clients_summary = self._fetchall(
            f"""
            SELECT c.id, c.name AS client_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            {date_filter}
            GROUP BY c.id
            ORDER BY total_cost DESC
            """,
            tuple(params)
        )
        
        # Totali per commessa
        projects_summary = self._fetchall(
            f"""
            SELECT c.name AS client_name, p.name AS project_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN projects p ON p.id = t.project_id
            JOIN clients c ON c.id = p.client_id
            {date_filter}
            GROUP BY p.id
            ORDER BY total_cost DESC
            LIMIT 10
            """,
            tuple(params)
        )
        
        # Totali per utente
        users_summary = self._fetchall(
            f"""
            SELECT u.username, u.full_name,
                   SUM(t.hours) AS total_hours,
                   SUM(t.cost) AS total_cost
            FROM timesheets t
            JOIN users u ON u.id = t.user_id
            {date_filter}
            GROUP BY u.id
            ORDER BY total_hours DESC
            """,
            tuple(params)
        )
        
        # KPI generali
        if params:
            total_hours = self._fetchone(
                "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE work_date >= ? AND work_date <= ?",
                tuple(params)
            )
        else:
            total_hours = self._fetchone(
                "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets"
            )
        
        # Programmazioni in ritardo o a rischio
        at_risk = [s for s in schedules if s["remaining_hours"] < 0 or (s["remaining_days"] < 7 and s["remaining_hours"] > 0)]
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "schedules": schedules,
            "schedules_at_risk": at_risk,
            "clients_summary": clients_summary,
            "projects_summary": projects_summary,
            "users_summary": users_summary,
            "total_hours": float(total_hours["hours"]) if total_hours else 0.0,
            "total_cost": float(total_hours["cost"]) if total_hours else 0.0,
            "num_active_schedules": len(schedules),
            "num_at_risk": len(at_risk)
        }

