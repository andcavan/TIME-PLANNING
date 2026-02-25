from __future__ import annotations

from datetime import datetime
from typing import Any


def list_diary_entries_impl(
    db: Any,
    client_id: int | None = None,
    project_id: int | None = None,
    activity_id: int | None = None,
    user_id: int | None = None,
    show_completed: bool = True,
    only_pending_reminders: bool = False,
) -> list[dict[str, Any]]:
    """Elenca le voci del diario con filtri opzionali."""
    query = """
        SELECT d.id, d.client_id, d.project_id, d.activity_id, d.user_id,
               d.created_at, d.reminder_date, d.content, d.is_completed, d.priority,
               c.name AS client_name,
               p.name AS project_name,
               a.name AS activity_name,
               u.full_name AS user_name
        FROM diary_entries d
        LEFT JOIN clients c ON c.id = d.client_id
        LEFT JOIN projects p ON p.id = d.project_id
        LEFT JOIN activities a ON a.id = d.activity_id
        JOIN users u ON u.id = d.user_id
        WHERE 1=1
    """
    params: list[Any] = []

    if client_id:
        query += " AND d.client_id = ?"
        params.append(client_id)
    if project_id:
        query += " AND d.project_id = ?"
        params.append(project_id)
    if activity_id:
        query += " AND d.activity_id = ?"
        params.append(activity_id)
    if user_id:
        query += " AND d.user_id = ?"
        params.append(user_id)
    if not show_completed:
        query += " AND d.is_completed = 0"
    if only_pending_reminders:
        today = datetime.now().strftime("%Y-%m-%d")
        query += " AND d.reminder_date IS NOT NULL AND d.reminder_date <= ? AND d.is_completed = 0"
        params.append(today)

    query += " ORDER BY d.priority DESC, d.reminder_date ASC NULLS LAST, d.created_at DESC"
    return db._fetchall(query, tuple(params))


def get_diary_entry_impl(db: Any, entry_id: int) -> dict[str, Any] | None:
    """Restituisce una singola voce del diario."""
    return db._fetchone(
        """
        SELECT d.id, d.client_id, d.project_id, d.activity_id, d.user_id,
               d.created_at, d.reminder_date, d.content, d.is_completed, d.priority,
               c.name AS client_name,
               p.name AS project_name,
               a.name AS activity_name,
               u.full_name AS user_name
        FROM diary_entries d
        LEFT JOIN clients c ON c.id = d.client_id
        LEFT JOIN projects p ON p.id = d.project_id
        LEFT JOIN activities a ON a.id = d.activity_id
        JOIN users u ON u.id = d.user_id
        WHERE d.id = ?
        """,
        (entry_id,),
    )


def create_diary_entry_impl(
    db: Any,
    user_id: int,
    content: str,
    client_id: int | None = None,
    project_id: int | None = None,
    activity_id: int | None = None,
    reminder_date: str | None = None,
    priority: int = 0,
) -> int:
    """Crea una nuova voce nel diario. Ritorna l'ID."""
    if not client_id and not project_id and not activity_id:
        raise ValueError("Almeno uno tra cliente, commessa o attivita deve essere specificato.")

    cursor = db.conn.execute(
        """
        INSERT INTO diary_entries (user_id, content, client_id, project_id, activity_id, reminder_date, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, content.strip(), client_id, project_id, activity_id, reminder_date or None, priority),
    )
    db.conn.commit()
    return cursor.lastrowid  # type: ignore


def update_diary_entry_impl(
    db: Any,
    entry_id: int,
    content: str | None = None,
    client_id: int | None = None,
    project_id: int | None = None,
    activity_id: int | None = None,
    reminder_date: str | None = None,
    priority: int | None = None,
    is_completed: int | None = None,
) -> bool:
    """Aggiorna una voce del diario."""
    fields: list[str] = []
    params: list[Any] = []

    if content is not None:
        fields.append("content = ?")
        params.append(content.strip())
    if client_id is not None:
        fields.append("client_id = ?")
        params.append(client_id if client_id else None)
    if project_id is not None:
        fields.append("project_id = ?")
        params.append(project_id if project_id else None)
    if activity_id is not None:
        fields.append("activity_id = ?")
        params.append(activity_id if activity_id else None)
    if reminder_date is not None:
        fields.append("reminder_date = ?")
        params.append(reminder_date if reminder_date else None)
    if priority is not None:
        fields.append("priority = ?")
        params.append(priority)
    if is_completed is not None:
        fields.append("is_completed = ?")
        params.append(is_completed)

    if not fields:
        return False

    params.append(entry_id)
    db.conn.execute(
        f"UPDATE diary_entries SET {', '.join(fields)} WHERE id = ?",
        tuple(params),
    )
    db.conn.commit()
    return True


def delete_diary_entry_impl(db: Any, entry_id: int) -> bool:
    """Elimina una voce del diario."""
    cursor = db.conn.execute("DELETE FROM diary_entries WHERE id = ?", (entry_id,))
    db.conn.commit()
    return cursor.rowcount > 0


def toggle_diary_completed_impl(db: Any, entry_id: int) -> bool:
    """Inverte lo stato completato di una voce."""
    db.conn.execute(
        "UPDATE diary_entries SET is_completed = 1 - is_completed WHERE id = ?",
        (entry_id,),
    )
    db.conn.commit()
    return True


def count_pending_reminders_impl(db: Any, user_id: int | None = None) -> int:
    """Conta i promemoria scaduti o in scadenza oggi (non completati)."""
    today = datetime.now().strftime("%Y-%m-%d")
    query = """
        SELECT COUNT(*) AS cnt FROM diary_entries
        WHERE reminder_date IS NOT NULL AND reminder_date <= ? AND is_completed = 0
    """
    params: list[Any] = [today]
    if user_id:
        query += " AND user_id = ?"
        params.append(user_id)
    row = db.conn.execute(query, tuple(params)).fetchone()
    return row[0] if row else 0
