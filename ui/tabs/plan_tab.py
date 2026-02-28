from __future__ import annotations

import sqlite3
from datetime import datetime
from tkinter import messagebox, ttk

import customtkinter as ctk


def build_plan_tab(app) -> None:
    app.tab_plan.grid_columnconfigure(0, weight=1)
    app.tab_plan.grid_rowconfigure(1, weight=1)

    form = ctk.CTkFrame(app.tab_plan)
    form.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
    for i in range(6):
        form.grid_columnconfigure(i, weight=1)

    ctk.CTkLabel(form, text="Commessa").grid(row=0, column=0, padx=8, pady=4, sticky="w")
    app.plan_project_combo = ctk.CTkComboBox(
        form, state="readonly", command=app.on_plan_project_change, width=260, values=[""]
    )
    app.plan_project_combo.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Attivita (opzionale)").grid(row=0, column=1, padx=8, pady=4, sticky="w")
    app.plan_activity_combo = ctk.CTkComboBox(form, state="readonly", width=260, values=[""])
    app.plan_activity_combo.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Data inizio (gg/mm/aaaa)").grid(row=0, column=2, padx=8, pady=4, sticky="w")
    app.plan_start_date_entry = ctk.CTkEntry(form, placeholder_text="01/01/2026")
    app.plan_start_date_entry.grid(row=1, column=2, padx=8, pady=4, sticky="ew")
    app.setup_date_entry_helpers(app.plan_start_date_entry)

    ctk.CTkLabel(form, text="Data fine (gg/mm/aaaa)").grid(row=0, column=3, padx=8, pady=4, sticky="w")
    app.plan_end_date_entry = ctk.CTkEntry(form, placeholder_text="31/12/2026")
    app.plan_end_date_entry.grid(row=1, column=3, padx=8, pady=4, sticky="ew")
    app.setup_date_entry_helpers(app.plan_end_date_entry)

    ctk.CTkLabel(form, text="Ore preventivate").grid(row=0, column=4, padx=8, pady=4, sticky="w")
    app.plan_hours_entry = ctk.CTkEntry(form, placeholder_text="160")
    app.plan_hours_entry.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Budget (€)").grid(row=0, column=5, padx=8, pady=4, sticky="w")
    app.plan_budget_entry = ctk.CTkEntry(form, placeholder_text="5000.00")
    app.plan_budget_entry.grid(row=1, column=5, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Note").grid(row=2, column=0, padx=8, pady=4, sticky="w")
    app.plan_note_entry = ctk.CTkEntry(form)
    app.plan_note_entry.grid(row=2, column=1, columnspan=5, padx=8, pady=4, sticky="ew")

    ctk.CTkButton(form, text="Salva programmazione", command=app.add_schedule_entry).grid(
        row=3, column=0, columnspan=1, padx=8, pady=(8, 10), sticky="ew"
    )
    edit_btn = ctk.CTkButton(form, text="Modifica selezionata", command=app.edit_selected_schedule)
    app.apply_edit_button_style(edit_btn)
    edit_btn.grid(row=3, column=1, padx=8, pady=(8, 10), sticky="ew")
    ctk.CTkButton(form, text="Chiudi/Apri", command=app.toggle_schedule_status).grid(
        row=3, column=2, padx=8, pady=(8, 10), sticky="ew"
    )
    delete_btn = ctk.CTkButton(form, text="Elimina selezionata", command=app.delete_selected_schedule)
    app.apply_delete_button_style(delete_btn)
    delete_btn.grid(row=3, column=3, padx=8, pady=(8, 10), sticky="ew")

    list_frame = ctk.CTkFrame(app.tab_plan)
    list_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)

    columns = ("client", "project", "activity", "start_date", "end_date", "hours", "budget", "status", "note")
    app.plan_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
    app.plan_tree.heading("client", text="Cliente")
    app.plan_tree.heading("project", text="Commessa")
    app.plan_tree.heading("activity", text="Attivita")
    app.plan_tree.heading("start_date", text="Data inizio")
    app.plan_tree.heading("end_date", text="Data fine")
    app.plan_tree.heading("hours", text="Ore preventivate")
    app.plan_tree.heading("budget", text="Budget €")
    app.plan_tree.heading("status", text="Stato")
    app.plan_tree.heading("note", text="Note")
    app.plan_tree.column("client", width=120, anchor="w")
    app.plan_tree.column("project", width=150, anchor="w")
    app.plan_tree.column("activity", width=150, anchor="w")
    app.plan_tree.column("start_date", width=90, anchor="center")
    app.plan_tree.column("end_date", width=90, anchor="center")
    app.plan_tree.column("hours", width=100, anchor="e")
    app.plan_tree.column("budget", width=100, anchor="e")
    app.plan_tree.column("status", width=70, anchor="center")
    app.plan_tree.column("note", width=180, anchor="w")
    app.plan_tree.grid(row=0, column=0, sticky="nsew")

    # Bind per popolare il form al click
    app.plan_tree.bind("<<TreeviewSelect>>", app.on_schedule_tree_select)

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=app.plan_tree.yview)
    app.plan_tree.configure(yscrollcommand=scroll.set)
    scroll.grid(row=0, column=1, sticky="ns")


def refresh_programming_options(app) -> None:
    if not hasattr(app, "plan_project_combo"):
        return
    projects = app.db.list_projects()
    app._set_combo_values(app.plan_project_combo, [app._project_option(row) for row in projects])
    app.on_plan_project_change(app.plan_project_combo.get())


def on_plan_project_change(app, _value: str) -> None:
    project_id = app._id_from_option(app.plan_project_combo.get())
    activities = app.db.list_activities(project_id)
    # Aggiungi opzione vuota per "tutta la commessa"
    options = ["(Tutta la commessa)"] + [app._activity_option(row) for row in activities]
    app._set_combo_values(app.plan_activity_combo, options)
    app.plan_activity_combo.set("(Tutta la commessa)")


def add_schedule_entry(app) -> None:
    try:
        project_id = app._id_from_option(app.plan_project_combo.get())
        if not project_id:
            raise ValueError("Seleziona una commessa.")

        # Activity può essere None se selezioniamo "Tutta la commessa"
        activity_str = app.plan_activity_combo.get()
        activity_id = None if activity_str == "(Tutta la commessa)" else app._id_from_option(activity_str)

        # Converti date da dd/mm/yyyy a YYYY-MM-DD
        start_date_str = app.plan_start_date_entry.get().strip()
        end_date_str = app.plan_end_date_entry.get().strip()

        start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

        if start_date > end_date:
            raise ValueError("La data di inizio deve essere precedente alla data di fine.")

        planned_hours = app._to_float(app.plan_hours_entry.get().strip(), "Ore preventivate")
        if planned_hours <= 0:
            raise ValueError("Ore preventivate: il valore deve essere > 0.")

        budget_str = app.plan_budget_entry.get().strip()
        budget = app._to_float(budget_str, "Budget") if budget_str else 0.0

        note = app.plan_note_entry.get().strip()
        app.db.add_schedule(project_id, activity_id, start_date, end_date, planned_hours, note, budget)
    except (ValueError, sqlite3.IntegrityError) as exc:
        messagebox.showerror("Programmazione", str(exc))
        return

    app.plan_start_date_entry.delete(0, "end")
    app.plan_end_date_entry.delete(0, "end")
    app.plan_hours_entry.delete(0, "end")
    app.plan_budget_entry.delete(0, "end")
    app.plan_note_entry.delete(0, "end")
    app.refresh_schedule_list()
    if hasattr(app, "refresh_control_panel"):
        app.refresh_control_panel()
    messagebox.showinfo("Programmazione", "Programmazione salvata.")


def on_schedule_tree_select(app, event) -> None:
    """Popola i campi del form quando si seleziona una programmazione."""
    selection = app.plan_tree.selection()
    if not selection:
        return

    schedule_id = int(selection[0])
    schedules = app.db.list_schedules()

    for schedule in schedules:
        if schedule["id"] == schedule_id:
            # Imposta il progetto nella combo
            project_option = app._project_option({
                "id": schedule["project_id"],
                "name": schedule["project_name"],
                "client_name": schedule["client_name"]
            })
            app.plan_project_combo.set(project_option)
            app.on_plan_project_change(project_option)

            # Imposta l'attività (se presente)
            if schedule["activity_id"] is not None:
                activities = app.db.list_activities(schedule["project_id"])
                for act in activities:
                    if act["id"] == schedule["activity_id"]:
                        activity_option = app._activity_option(act)
                        app.plan_activity_combo.set(activity_option)
                        break
            else:
                app.plan_activity_combo.set("(Tutta la commessa)")

            # Imposta le date (converti da YYYY-MM-DD a dd/mm/yyyy)
            try:
                start_display = datetime.strptime(schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                end_display = datetime.strptime(schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                start_display = schedule["start_date"]
                end_display = schedule["end_date"]

            app.plan_start_date_entry.delete(0, "end")
            app.plan_start_date_entry.insert(0, start_display)
            app.plan_end_date_entry.delete(0, "end")
            app.plan_end_date_entry.insert(0, end_display)
            app.plan_hours_entry.delete(0, "end")
            app.plan_hours_entry.insert(0, str(schedule["planned_hours"]))
            app.plan_budget_entry.delete(0, "end")
            app.plan_budget_entry.insert(0, str(schedule.get("budget", 0.0)))
            app.plan_note_entry.delete(0, "end")
            app.plan_note_entry.insert(0, schedule["note"])
            break


def edit_selected_schedule(app) -> None:
    """Modifica la programmazione selezionata."""
    selection = app.plan_tree.selection()
    if not selection:
        messagebox.showinfo("Programmazione", "Seleziona una programmazione dall'elenco.")
        return

    schedule_id = int(selection[0])

    try:
        project_id = app._id_from_option(app.plan_project_combo.get())
        if not project_id:
            raise ValueError("Seleziona una commessa.")

        # Activity può essere None se selezioniamo "Tutta la commessa"
        activity_str = app.plan_activity_combo.get()
        activity_id = None if activity_str == "(Tutta la commessa)" else app._id_from_option(activity_str)

        # Converti date da dd/mm/yyyy a YYYY-MM-DD
        start_date_str = app.plan_start_date_entry.get().strip()
        end_date_str = app.plan_end_date_entry.get().strip()

        start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

        if start_date > end_date:
            raise ValueError("La data di inizio deve essere precedente alla data di fine.")

        planned_hours = app._to_float(app.plan_hours_entry.get().strip(), "Ore preventivate")
        if planned_hours <= 0:
            raise ValueError("Ore preventivate: il valore deve essere > 0.")

        budget_str = app.plan_budget_entry.get().strip()
        budget = app._to_float(budget_str, "Budget") if budget_str else 0.0

        note = app.plan_note_entry.get().strip()
        app.db.update_schedule(schedule_id, project_id, activity_id, start_date, end_date, planned_hours, note, budget)
    except (ValueError, sqlite3.IntegrityError) as exc:
        messagebox.showerror("Programmazione", str(exc))
        return

    app.refresh_schedule_list()
    if hasattr(app, "refresh_control_panel"):
        app.refresh_control_panel()
    messagebox.showinfo("Programmazione", "Programmazione aggiornata.")


def refresh_schedule_list(app) -> None:
    if not hasattr(app, "plan_tree"):
        return

    for item in app.plan_tree.get_children():
        app.plan_tree.delete(item)

    rows = app.db.list_schedules()
    for row in rows:
        # Converti date da YYYY-MM-DD a dd/mm/yyyy per visualizzazione
        start_display = app.format_date_ui(row["start_date"])
        end_display = app.format_date_ui(row["end_date"])

        status_display = "✓" if row.get("status") == "aperta" else "✗"

        app.plan_tree.insert(
            "",
            "end",
            iid=str(row["id"]),
            values=(
                row["client_name"],
                row["project_name"],
                row["activity_name"] or "(Tutta la commessa)",
                start_display,
                end_display,
                f"{row['planned_hours']:.2f}",
                f"{row.get('budget', 0.0):.2f}",
                status_display,
                row["note"],
            ),
        )


def delete_selected_schedule(app) -> None:
    selection = app.plan_tree.selection()
    if not selection:
        messagebox.showwarning("Programmazione", "Seleziona una riga da eliminare.")
        return
    if not messagebox.askyesno("Conferma", "Eliminare la programmazione selezionata?"):
        return

    schedule_id = int(selection[0])
    app.db.delete_schedule(schedule_id)
    app.refresh_schedule_list()


def toggle_schedule_status(app) -> None:
    """Apre o chiude una programmazione."""
    selection = app.plan_tree.selection()
    if not selection:
        messagebox.showwarning("Programmazione", "Seleziona una programmazione.")
        return

    schedule_id = int(selection[0])
    schedules = app.db.list_schedules()
    schedule = next((s for s in schedules if s["id"] == schedule_id), None)

    if not schedule:
        return

    current_status = schedule.get("status", "aperta")
    new_status = "chiusa" if current_status == "aperta" else "aperta"

    app.db.update_schedule_status(schedule_id, new_status)
    app.refresh_schedule_list()

    # Aggiorna anche il calendario ore e il controllo se la schedule era aperta/chiusa
    if hasattr(app, "ts_client_combo"):
        app.on_timesheet_client_change(app.ts_client_combo.get())
    if hasattr(app, "ctrl_tree"):
        app.refresh_control_panel()
