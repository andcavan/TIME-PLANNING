from __future__ import annotations

from typing import Any


def get_report_client_data_impl(
    db: Any,
    client_id: int,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Recupera dati per report cliente."""
    client = db._fetchone("SELECT * FROM clients WHERE id = ?", (client_id,))
    if not client:
        return None

    date_filter = ""
    params = [client_id]
    if start_date and end_date:
        date_filter = " AND s.start_date <= ? AND s.end_date >= ?"
        params.extend([end_date, start_date])

    schedules = db._fetchall(
        f"""
        SELECT s.*, p.name AS project_name, a.name AS activity_name
        FROM schedules s
        JOIN projects p ON p.id = s.project_id
        LEFT JOIN activities a ON a.id = s.activity_id
        WHERE p.client_id = ? {date_filter}
        ORDER BY s.start_date DESC
        """,
        tuple(params),
    )

    total_planned_hours = 0.0
    total_budget = 0.0
    total_actual_hours = 0.0
    total_actual_cost = 0.0

    schedule_details = []
    for sched in schedules:
        if sched["activity_id"]:
            actual = db._fetchone(
                "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE project_id = ? AND activity_id = ? AND work_date >= ? AND work_date <= ?",
                (sched["project_id"], sched["activity_id"], sched["start_date"], sched["end_date"]),
            )
        else:
            actual = db._fetchone(
                "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE project_id = ? AND work_date >= ? AND work_date <= ?",
                (sched["project_id"], sched["start_date"], sched["end_date"]),
            )

        actual_hours = float(actual["hours"]) if actual else 0.0
        actual_cost = float(actual["cost"]) if actual else 0.0

        total_planned_hours += float(sched["planned_hours"])
        total_budget += float(sched.get("budget", 0.0))
        total_actual_hours += actual_hours
        total_actual_cost += actual_cost

        schedule_details.append(
            {
                "project_name": sched["project_name"],
                "activity_name": sched["activity_name"] or "(Tutta la commessa)",
                "start_date": sched["start_date"],
                "end_date": sched["end_date"],
                "planned_hours": float(sched["planned_hours"]),
                "budget": float(sched.get("budget", 0.0)),
                "actual_hours": actual_hours,
                "actual_cost": actual_cost,
            }
        )

    return {
        "client": dict(client),
        "schedules": schedule_details,
        "total_planned_hours": total_planned_hours,
        "total_budget": total_budget,
        "total_actual_hours": total_actual_hours,
        "total_actual_cost": total_actual_cost,
    }


def get_report_project_data_impl(db: Any, project_id: int) -> dict[str, Any]:
    """Recupera dati per report commessa."""
    project = db._fetchone(
        "SELECT p.*, c.name AS client_name FROM projects p JOIN clients c ON c.id = p.client_id WHERE p.id = ?",
        (project_id,),
    )
    if not project:
        return None

    schedules = db._fetchall(
        """
        SELECT s.*, a.name AS activity_name
        FROM schedules s
        LEFT JOIN activities a ON a.id = s.activity_id
        WHERE s.project_id = ?
        ORDER BY s.start_date DESC
        """,
        (project_id,),
    )

    timesheets = db._fetchall(
        """
        SELECT t.*, u.username, u.full_name, a.name AS activity_name
        FROM timesheets t
        JOIN users u ON u.id = t.user_id
        JOIN activities a ON a.id = t.activity_id
        WHERE t.project_id = ?
        ORDER BY t.work_date DESC
        """,
        (project_id,),
    )

    activities_summary = db._fetchall(
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
        (project_id,),
    )

    users_summary = db._fetchall(
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
        (project_id,),
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
        "total_actual_cost": total_cost,
    }


def get_report_period_data_impl(
    db: Any,
    start_date: str,
    end_date: str,
    client_id: int | None = None,
    project_id: int | None = None,
) -> dict[str, Any]:
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

    timesheets = db._fetchall(
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
        tuple(params),
    )

    clients_summary = db._fetchall(
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
        tuple(params),
    )

    projects_summary = db._fetchall(
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
        tuple(params),
    )

    users_summary = db._fetchall(
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
        tuple(params),
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
        "total_cost": total_cost,
    }


def get_report_user_data_impl(
    db: Any,
    user_id: int,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Recupera dati per report utente."""
    user = db._fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user:
        return None

    timesheets = db._fetchall(
        """
        SELECT t.*, c.name AS client_name, p.name AS project_name, a.name AS activity_name
        FROM timesheets t
        JOIN projects p ON p.id = t.project_id
        JOIN clients c ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        WHERE t.user_id = ? AND t.work_date >= ? AND t.work_date <= ?
        ORDER BY t.work_date DESC
        """,
        (user_id, start_date, end_date),
    )

    clients_summary = db._fetchall(
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
        (user_id, start_date, end_date),
    )

    projects_summary = db._fetchall(
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
        (user_id, start_date, end_date),
    )

    activities_summary = db._fetchall(
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
        (user_id, start_date, end_date),
    )

    total_hours = sum(float(t["hours"]) for t in timesheets)
    total_cost = sum(float(t["cost"]) for t in timesheets)

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
        "avg_hours_per_day": avg_hours_per_day,
    }


def get_report_general_data_impl(
    db: Any,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Recupera dati per report generale/riepilogativo."""
    date_filter = ""
    params = []

    if start_date and end_date:
        date_filter = " WHERE t.work_date >= ? AND t.work_date <= ?"
        params = [start_date, end_date]

    schedules = db.get_schedule_control_data()

    clients_summary = db._fetchall(
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
        tuple(params),
    )

    projects_summary = db._fetchall(
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
        tuple(params),
    )

    users_summary = db._fetchall(
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
        tuple(params),
    )

    if params:
        total_hours = db._fetchone(
            "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets WHERE work_date >= ? AND work_date <= ?",
            tuple(params),
        )
    else:
        total_hours = db._fetchone(
            "SELECT COALESCE(SUM(hours), 0) AS hours, COALESCE(SUM(cost), 0) AS cost FROM timesheets"
        )

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
        "num_at_risk": len(at_risk),
    }


def get_report_filtered_data_impl(
    db: Any,
    client_id: int | None = None,
    project_id: int | None = None,
    activity_id: int | None = None,
    user_id: int | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Recupera dati per report con filtri flessibili (cliente, commessa, attivita, utente, periodo)."""
    conditions: list[str] = []
    params: list[Any] = []

    if start_date:
        conditions.append("t.work_date >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("t.work_date <= ?")
        params.append(end_date)
    if client_id:
        conditions.append("p.client_id = ?")
        params.append(client_id)
    if project_id:
        conditions.append("t.project_id = ?")
        params.append(project_id)
    if activity_id:
        conditions.append("t.activity_id = ?")
        params.append(activity_id)
    if user_id:
        conditions.append("t.user_id = ?")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    p = tuple(params)

    timesheets = db._fetchall(
        f"""
        SELECT t.work_date, t.hours, t.cost, t.note,
               c.name AS client_name, p.name AS project_name,
               a.name AS activity_name, u.full_name, u.username
        FROM timesheets t
        JOIN projects p ON p.id = t.project_id
        JOIN clients c  ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        JOIN users u ON u.id = t.user_id
        {where}
        ORDER BY t.work_date DESC, c.name, p.name, a.name
        """,
        p,
    )

    clients_summary = db._fetchall(
        f"""
        SELECT c.name AS client_name,
               SUM(t.hours) AS total_hours, SUM(t.cost) AS total_cost
        FROM timesheets t
        JOIN projects p  ON p.id = t.project_id
        JOIN clients c   ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        JOIN users u ON u.id = t.user_id
        {where}
        GROUP BY c.id ORDER BY total_hours DESC
        """,
        p,
    )

    projects_summary = db._fetchall(
        f"""
        SELECT c.name AS client_name, p.name AS project_name,
               SUM(t.hours) AS total_hours, SUM(t.cost) AS total_cost
        FROM timesheets t
        JOIN projects p  ON p.id = t.project_id
        JOIN clients c   ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        JOIN users u ON u.id = t.user_id
        {where}
        GROUP BY p.id ORDER BY total_hours DESC
        """,
        p,
    )

    activities_summary = db._fetchall(
        f"""
        SELECT a.name AS activity_name,
               SUM(t.hours) AS total_hours, SUM(t.cost) AS total_cost
        FROM timesheets t
        JOIN projects p  ON p.id = t.project_id
        JOIN clients c   ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        JOIN users u ON u.id = t.user_id
        {where}
        GROUP BY a.id ORDER BY total_hours DESC
        """,
        p,
    )

    users_summary = db._fetchall(
        f"""
        SELECT u.full_name,
               SUM(t.hours) AS total_hours, SUM(t.cost) AS total_cost
        FROM timesheets t
        JOIN projects p  ON p.id = t.project_id
        JOIN clients c   ON c.id = p.client_id
        JOIN activities a ON a.id = t.activity_id
        JOIN users u ON u.id = t.user_id
        {where}
        GROUP BY u.id ORDER BY total_hours DESC
        """,
        p,
    )

    total_hours = sum(float(t["hours"]) for t in timesheets)
    total_cost = sum(float(t["cost"]) for t in timesheets)

    return {
        "timesheets": timesheets,
        "clients_summary": clients_summary,
        "projects_summary": projects_summary,
        "activities_summary": activities_summary,
        "users_summary": users_summary,
        "total_hours": total_hours,
        "total_cost": total_cost,
        "start_date": start_date,
        "end_date": end_date,
    }
