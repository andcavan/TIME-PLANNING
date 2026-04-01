from __future__ import annotations

from tkinter import ttk

import customtkinter as ctk

from ui.tabs.formatters import (
    format_budget_remaining,
    format_date_short,
    format_hours_diff,
    format_remaining_days,
)


def build_control_tab(app) -> None:
    app.tab_control.grid_columnconfigure(0, weight=1)
    app.tab_control.grid_rowconfigure(1, weight=1)

    header = ctk.CTkFrame(app.tab_control)
    header.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

    ctk.CTkLabel(header, text="Controllo Programmazione", font=ctk.CTkFont(size=16, weight="bold")).pack(
        side="left", padx=10, pady=8
    )
    ctk.CTkButton(header, text="Aggiorna", command=app.refresh_control_panel).pack(side="left", padx=12, pady=8)
    ctk.CTkButton(header, text="📄 Genera Report PDF", command=app.show_pdf_report_dialog).pack(side="left", padx=12, pady=8)

    # Separatore visivo
    ttk.Separator(header, orient="vertical").pack(side="left", fill="y", padx=8, pady=4)

    # Filtro Da
    ctk.CTkLabel(header, text="Da:").pack(side="left", padx=(4, 2), pady=8)
    app.ctrl_filter_date_from = ctk.CTkEntry(header, width=90, placeholder_text="GG/MM/AAAA")
    app.ctrl_filter_date_from.pack(side="left", padx=2, pady=8)

    # Filtro A
    ctk.CTkLabel(header, text="A:").pack(side="left", padx=(8, 2), pady=8)
    app.ctrl_filter_date_to = ctk.CTkEntry(header, width=90, placeholder_text="GG/MM/AAAA")
    app.ctrl_filter_date_to.pack(side="left", padx=2, pady=8)

    # Filtro Utente
    ctk.CTkLabel(header, text="Utente:").pack(side="left", padx=(8, 2), pady=8)
    users = app.db.list_users(include_inactive=False)
    user_names = ["Tutti"] + [u["username"] for u in users]
    app.ctrl_filter_user = ctk.CTkComboBox(header, values=user_names, width=130)
    app.ctrl_filter_user.set("Tutti")
    app.ctrl_filter_user.pack(side="left", padx=2, pady=8)

    # Bottoni Applica / Azzera
    ctk.CTkButton(header, text="Applica", width=70, command=app.refresh_control_panel).pack(side="left", padx=(8, 2), pady=8)
    ctk.CTkButton(
        header, text="Azzera", width=70, fg_color="gray",
        command=lambda: _reset_filters(app)
    ).pack(side="left", padx=2, pady=8)

    table_frame = ctk.CTkFrame(app.tab_control)
    table_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    columns = (
        "status",
        "start_date", "end_date", "working_days", "remaining_days",
        "planned_hours", "actual_hours", "hours_diff",
        "budget", "actual_cost", "budget_remaining",
        "user_cost", "margin",
        "user", "date", "note"
    )

    is_admin = getattr(app, "is_admin", False)

    # Usa show="tree headings" per struttura gerarchica
    app.ctrl_tree = ttk.Treeview(table_frame, columns=columns, show="tree headings", selectmode="browse")
    app.ctrl_tree.heading("#0", text="Cliente / Commessa / Attività")
    app.ctrl_tree.heading("status", text="Stato")
    app.ctrl_tree.heading("start_date", text="Inizio")
    app.ctrl_tree.heading("end_date", text="Fine")
    app.ctrl_tree.heading("working_days", text="Gg lav.")
    app.ctrl_tree.heading("remaining_days", text="Gg rest.")
    app.ctrl_tree.heading("planned_hours", text="Ore pianif.")
    app.ctrl_tree.heading("actual_hours", text="Ore effett.")
    app.ctrl_tree.heading("hours_diff", text="Diff. ore")
    app.ctrl_tree.heading("budget", text="Budget €")
    app.ctrl_tree.heading("actual_cost", text="Ricavo €")
    app.ctrl_tree.heading("budget_remaining", text="Budget rest. €")
    app.ctrl_tree.heading("user_cost", text="Costo ut. €")
    app.ctrl_tree.heading("margin", text="Margine €")
    app.ctrl_tree.heading("user", text="Utente")
    app.ctrl_tree.heading("date", text="Data")
    app.ctrl_tree.heading("note", text="Note")

    app.ctrl_tree.column("#0", width=250, anchor="w")
    app.ctrl_tree.column("status", width=80, anchor="center")
    app.ctrl_tree.column("start_date", width=80, anchor="center")
    app.ctrl_tree.column("end_date", width=80, anchor="center")
    app.ctrl_tree.column("working_days", width=80, anchor="e")
    app.ctrl_tree.column("remaining_days", width=80, anchor="e")
    app.ctrl_tree.column("planned_hours", width=90, anchor="e")
    app.ctrl_tree.column("actual_hours", width=90, anchor="e")
    app.ctrl_tree.column("hours_diff", width=90, anchor="e")
    app.ctrl_tree.column("budget", width=90, anchor="e")
    app.ctrl_tree.column("actual_cost", width=90, anchor="e")
    app.ctrl_tree.column("budget_remaining", width=110, anchor="e")
    app.ctrl_tree.column("user_cost", width=100 if is_admin else 0, minwidth=0, anchor="e")
    app.ctrl_tree.column("margin", width=100 if is_admin else 0, minwidth=0, anchor="e")
    app.ctrl_tree.column("user", width=100, anchor="w")
    app.ctrl_tree.column("date", width=80, anchor="center")
    app.ctrl_tree.column("note", width=150, anchor="w")

    app.ctrl_tree.grid(row=0, column=0, sticky="nsew")

    # Tag per colorare i diversi livelli (rimuovo bold dal cliente)
    app.ctrl_tree.tag_configure("client", foreground="#1565c0")
    app.ctrl_tree.tag_configure("project", foreground="#1976d2")
    app.ctrl_tree.tag_configure("activity", foreground="#388e3c")
    app.ctrl_tree.tag_configure("timesheet", foreground="#666666")
    app.ctrl_tree.tag_configure("closed", foreground="#999999")  # Commesse chiuse

    scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=app.ctrl_tree.yview)
    app.ctrl_tree.configure(yscrollcommand=scroll_y.set)
    scroll_y.grid(row=0, column=1, sticky="ns")

    scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=app.ctrl_tree.xview)
    app.ctrl_tree.configure(xscrollcommand=scroll_x.set)
    scroll_x.grid(row=1, column=0, sticky="ew")


def _reset_filters(app) -> None:
    """Azzera tutti i filtri e aggiorna il pannello."""
    app.ctrl_filter_date_from.delete(0, "end")
    app.ctrl_filter_date_to.delete(0, "end")
    app.ctrl_filter_user.set("Tutti")
    app.refresh_control_panel()


def _parse_filter_date(value: str) -> str | None:
    """Converte una data GG/MM/AAAA in YYYY-MM-DD. Restituisce None se vuota o non valida."""
    from datetime import datetime
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def on_control_tree_double_click(app, event) -> None:
    """Gestisce doppio clic sul tree del controllo."""
    selection = app.ctrl_tree.selection()
    if not selection:
        return

    item_id = selection[0]

    # Espande o collassa l'elemento
    if app.ctrl_tree.get_children(item_id):
        current_state = app.ctrl_tree.item(item_id, "open")
        app.ctrl_tree.item(item_id, open=not current_state)


def refresh_control_panel(app) -> None:
    if not hasattr(app, "ctrl_tree"):
        return

    is_admin = getattr(app, "is_admin", False)

    for item in app.ctrl_tree.get_children():
        app.ctrl_tree.delete(item)

    # Leggi filtri
    filter_user_id = None
    filter_date_from = None
    filter_date_to = None
    filters_active = False

    if hasattr(app, "ctrl_filter_date_from"):
        filter_date_from = _parse_filter_date(app.ctrl_filter_date_from.get())
        if filter_date_from:
            filters_active = True

    if hasattr(app, "ctrl_filter_date_to"):
        filter_date_to = _parse_filter_date(app.ctrl_filter_date_to.get())
        if filter_date_to:
            filters_active = True

    if hasattr(app, "ctrl_filter_user"):
        selected_user = app.ctrl_filter_user.get()
        if selected_user and selected_user != "Tutti":
            users = app.db.list_users(include_inactive=False)
            for u in users:
                if u["username"] == selected_user:
                    filter_user_id = u["id"]
                    filters_active = True
                    break

    data = app.db.get_hierarchical_timesheet_data(
        user_id=filter_user_id,
        date_from=filter_date_from,
        date_to=filter_date_to,
    )

    for client in data:
        # Formatta date per il cliente
        client_start = format_date_short(client["start_date"]) if client["start_date"] else ""
        client_end = format_date_short(client["end_date"]) if client["end_date"] else ""

        # Indicatori per il cliente
        client_days_text = format_remaining_days(client["remaining_days"], client["start_date"], client["end_date"])
        client_hours_text = format_hours_diff(client["hours_diff"], client["planned_hours"])
        client_budget_text = format_budget_remaining(client["budget_remaining"], client["budget"])

        # Inserisci il cliente
        client_id = f"client_{client['id']}"
        c_user_cost = float(client.get("user_cost", 0) or 0)
        c_ricavo = float(client.get("actual_cost", 0) or 0)
        c_margin_str = f"{c_ricavo - c_user_cost:.2f}" if is_admin else ""
        c_user_cost_str = f"{c_user_cost:.2f}" if is_admin else ""

        app.ctrl_tree.insert(
            "",
            "end",
            iid=client_id,
            text=client["name"],
            values=(
                "",  # stato vuoto per cliente
                client_start,
                client_end,
                str(client.get("working_days", 0)) if client.get("working_days", 0) > 0 else "",
                client_days_text,
                f"{client['planned_hours']:.1f}" if client['planned_hours'] > 0 else "",
                f"{client['actual_hours']:.1f}",
                client_hours_text,
                f"{client['budget']:.2f}" if client['budget'] > 0 else "",
                f"{client['actual_cost']:.2f}",
                client_budget_text,
                c_user_cost_str,
                c_margin_str,
                "",  # utente vuoto per cliente
                "",  # data vuota per cliente
                "",  # note vuote per cliente
            ),
            tags=("client",),
            open=filters_active
        )

        for project in client["projects"]:
            # Formatta date per la commessa
            project_start = format_date_short(project["start_date"]) if project["start_date"] else ""
            project_end = format_date_short(project["end_date"]) if project["end_date"] else ""

            # Indicatori per la commessa
            project_days_text = format_remaining_days(project["remaining_days"], project["start_date"], project["end_date"])
            project_hours_text = format_hours_diff(project["hours_diff"], project["planned_hours"])
            project_budget_text = format_budget_remaining(project["budget_remaining"], project["budget"])

            # Tag: se commessa chiusa, usa tag apposito
            project_tags = ("closed",) if project.get("status") == "chiusa" else ("project",)
            project_status = "✗ Chiusa" if project.get("status") == "chiusa" else "✓ Aperta" if project.get("status") else ""

            # Inserisci la commessa sotto il cliente
            project_id = f"project_{project['id']}"
            p_user_cost = float(project.get("user_cost", 0) or 0)
            p_ricavo = float(project.get("actual_cost", 0) or 0)
            p_margin_str = f"{p_ricavo - p_user_cost:.2f}" if is_admin else ""
            p_user_cost_str = f"{p_user_cost:.2f}" if is_admin else ""

            app.ctrl_tree.insert(
                client_id,
                "end",
                iid=project_id,
                text=project["name"],
                values=(
                    project_status,
                    project_start,
                    project_end,
                    str(project.get("working_days", 0)) if project.get("working_days", 0) > 0 else "",
                    project_days_text,
                    f"{project['planned_hours']:.1f}" if project['planned_hours'] > 0 else "",
                    f"{project['actual_hours']:.1f}",
                    project_hours_text,
                    f"{project['budget']:.2f}" if project['budget'] > 0 else "",
                    f"{project['actual_cost']:.2f}",
                    project_budget_text,
                    p_user_cost_str,
                    p_margin_str,
                    "",  # utente vuoto per commessa
                    "",  # data vuota per commessa
                    "",  # note vuote per commessa
                ),
                tags=project_tags,
                open=filters_active
            )

            for activity in project["activities"]:
                # Formatta date per l'attività
                activity_start = format_date_short(activity["start_date"]) if activity["start_date"] else ""
                activity_end = format_date_short(activity["end_date"]) if activity["end_date"] else ""

                # Indicatori per l'attività
                activity_days_text = format_remaining_days(activity.get("remaining_days", 0), activity["start_date"], activity["end_date"])
                activity_hours_text = format_hours_diff(activity.get("hours_diff", 0), activity.get("planned_hours", 0))
                activity_budget_text = format_budget_remaining(activity.get("budget_remaining", 0), activity.get("budget", 0))

                # Tag: se attività chiusa, usa tag apposito
                activity_tags = ("closed",) if activity.get("status") == "chiusa" else ("activity",)
                activity_status = "✗ Chiusa" if activity.get("status") == "chiusa" else "✓ Aperta" if activity.get("status") else ""

                # Inserisci l'attività sotto la commessa
                activity_id = f"activity_{activity['id']}"
                a_user_cost = float(activity.get("user_cost", 0) or 0)
                a_ricavo = float(activity.get("actual_cost", 0) or 0)
                a_margin_str = f"{a_ricavo - a_user_cost:.2f}" if is_admin else ""
                a_user_cost_str = f"{a_user_cost:.2f}" if is_admin else ""

                app.ctrl_tree.insert(
                    project_id,
                    "end",
                    iid=activity_id,
                    text=activity["name"],
                    values=(
                        activity_status,
                        activity_start,
                        activity_end,
                        str(activity.get("working_days", 0)) if activity.get("working_days", 0) > 0 else "",
                        activity_days_text,
                        f"{activity.get('planned_hours', 0):.1f}" if activity.get('planned_hours', 0) > 0 else "",
                        f"{activity['actual_hours']:.1f}",
                        activity_hours_text,
                        f"{activity.get('budget', 0):.2f}" if activity.get('budget', 0) > 0 else "",
                        f"{activity['actual_cost']:.2f}",
                        activity_budget_text,
                        a_user_cost_str,
                        a_margin_str,
                        "",  # utente vuoto per attività
                        "",  # data vuota per attività
                        activity.get("schedule_note", ""),  # note dalla schedule
                    ),
                    tags=activity_tags,
                    open=filters_active
                )

                for ts in activity["timesheets"]:
                    # Inserisci i timesheet sotto l'attività
                    work_date_display = format_date_short(ts["work_date"])

                    ts_user_cost = float(ts.get("user_cost", 0) or 0)
                    ts_ricavo = float(ts.get("cost", 0) or 0)
                    ts_ucr = float(ts.get("user_cost_rate", 0) or 0)
                    ts_user_cost_str = f"{ts_user_cost:.2f}" if (is_admin and ts_ucr > 0) else ("N/D" if is_admin else "")
                    ts_margin_str = f"{ts_ricavo - ts_user_cost:.2f}" if (is_admin and ts_ucr > 0) else ("N/D" if is_admin else "")

                    timesheet_id = f"timesheet_{ts['id']}"
                    app.ctrl_tree.insert(
                        activity_id,
                        "end",
                        iid=timesheet_id,
                        text="",  # Testo vuoto per timesheet
                        values=(
                            "",  # stato vuoto
                            "",  # inizio vuoto
                            "",  # fine vuoto
                            "",  # giorni lavorativi vuoti
                            "",  # giorni restanti vuoti
                            "",  # ore pianif. vuote
                            f"{ts['hours']:.1f}",
                            "",  # diff ore vuoto
                            "",  # budget vuoto
                            f"{ts['cost']:.2f}",
                            "",  # budget rest. vuoto
                            ts_user_cost_str,
                            ts_margin_str,
                            ts["username"],
                            work_date_display,
                            ts["note"],
                        ),
                        tags=("timesheet",),
                        open=False
                    )
