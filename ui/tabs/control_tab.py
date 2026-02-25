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

    table_frame = ctk.CTkFrame(app.tab_control)
    table_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)

    columns = (
        "status",
        "start_date", "end_date", "working_days", "remaining_days",
        "planned_hours", "actual_hours", "hours_diff",
        "budget", "actual_cost", "budget_remaining",
        "user", "date", "note"
    )

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
    app.ctrl_tree.heading("actual_cost", text="Costo €")
    app.ctrl_tree.heading("budget_remaining", text="Budget rest. €")
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

    for item in app.ctrl_tree.get_children():
        app.ctrl_tree.delete(item)

    data = app.db.get_hierarchical_timesheet_data()

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
                "",  # utente vuoto per cliente
                "",  # data vuota per cliente
                "",  # note vuote per cliente
            ),
            tags=("client",),
            open=False
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
                    "",  # utente vuoto per commessa
                    "",  # data vuota per commessa
                    "",  # note vuote per commessa
                ),
                tags=project_tags,
                open=False
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
                        "",  # utente vuoto per attività
                        "",  # data vuota per attività
                        activity.get("schedule_note", ""),  # note dalla schedule
                    ),
                    tags=activity_tags,
                    open=False
                )

                for ts in activity["timesheets"]:
                    # Inserisci i timesheet sotto l'attività
                    work_date_display = format_date_short(ts["work_date"])

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
                            ts["username"],
                            work_date_display,
                            ts["note"],
                        ),
                        tags=("timesheet",),
                        open=False
                    )
