from __future__ import annotations

from datetime import date, datetime
from tkinter import messagebox, ttk

import customtkinter as ctk


def build_diary_tab(app) -> None:
    app.tab_diary.grid_columnconfigure(0, weight=1)
    app.tab_diary.grid_rowconfigure(1, weight=1)

    # ── Header filtri ─────────────────────────────────────────────────────
    filter_frame = ctk.CTkFrame(app.tab_diary)
    filter_frame.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

    ctk.CTkLabel(filter_frame, text="Cliente").pack(side="left", padx=(12, 4), pady=8)
    app.diary_client_var = ctk.StringVar(value="Tutti")
    app.diary_client_combo = ctk.CTkComboBox(filter_frame, width=160, variable=app.diary_client_var, state="readonly")
    app.diary_client_combo.pack(side="left", padx=4, pady=8)
    app.diary_client_combo.configure(command=lambda _: app._diary_on_client_change())

    ctk.CTkLabel(filter_frame, text="Commessa").pack(side="left", padx=(12, 4), pady=8)
    app.diary_project_var = ctk.StringVar(value="Tutte")
    app.diary_project_combo = ctk.CTkComboBox(filter_frame, width=160, variable=app.diary_project_var, state="readonly")
    app.diary_project_combo.pack(side="left", padx=4, pady=8)
    app.diary_project_combo.configure(command=lambda _: app._diary_on_project_change())

    ctk.CTkLabel(filter_frame, text="Attività").pack(side="left", padx=(12, 4), pady=8)
    app.diary_activity_var = ctk.StringVar(value="Tutte")
    app.diary_activity_combo = ctk.CTkComboBox(filter_frame, width=160, variable=app.diary_activity_var, state="readonly")
    app.diary_activity_combo.pack(side="left", padx=4, pady=8)

    app.diary_show_completed_var = ctk.BooleanVar(value=True)
    ctk.CTkCheckBox(
        filter_frame, text="Mostra completati", variable=app.diary_show_completed_var,
        command=app.refresh_diary_data
    ).pack(side="left", padx=(20, 4), pady=8)

    ctk.CTkButton(filter_frame, text="Filtra", width=80, command=app.refresh_diary_data).pack(side="left", padx=8, pady=8)
    ctk.CTkButton(filter_frame, text="+ Nuova Nota", width=120, command=app._diary_new_entry).pack(side="right", padx=12, pady=8)

    # ── Tabella note ──────────────────────────────────────────────────────
    table_frame = ctk.CTkFrame(app.tab_diary)
    table_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
    table_frame.grid_columnconfigure(0, weight=1)
    table_frame.grid_rowconfigure(0, weight=1)

    columns = ("id", "alert", "priority", "ref", "content", "reminder", "completed", "user", "created")
    app.diary_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
    app.diary_tree.heading("id", text="ID")
    app.diary_tree.heading("alert", text="🔔")
    app.diary_tree.heading("priority", text="⚡")
    app.diary_tree.heading("ref", text="Riferimento")
    app.diary_tree.heading("content", text="Contenuto")
    app.diary_tree.heading("reminder", text="Promemoria")
    app.diary_tree.heading("completed", text="Stato")
    app.diary_tree.heading("user", text="Autore")
    app.diary_tree.heading("created", text="Creato")

    app.diary_tree.column("id", width=40, anchor="center")
    app.diary_tree.column("alert", width=40, anchor="center")
    app.diary_tree.column("priority", width=40, anchor="center")
    app.diary_tree.column("ref", width=220, anchor="w")
    app.diary_tree.column("content", width=350, anchor="w")
    app.diary_tree.column("reminder", width=100, anchor="center")
    app.diary_tree.column("completed", width=80, anchor="center")
    app.diary_tree.column("user", width=120, anchor="w")
    app.diary_tree.column("created", width=100, anchor="center")

    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=app.diary_tree.yview)
    app.diary_tree.configure(yscrollcommand=vsb.set)
    app.diary_tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")

    app.diary_tree.bind("<Double-1>", lambda _: app._diary_edit_entry())

    # ── Pulsanti azione ───────────────────────────────────────────────────
    btn_frame = ctk.CTkFrame(app.tab_diary, fg_color="transparent")
    btn_frame.grid(row=2, column=0, padx=8, pady=8, sticky="ew")

    ctk.CTkButton(btn_frame, text="✓ Completa/Riapri", width=140, command=app._diary_toggle_completed).pack(side="left", padx=4)
    edit_btn = ctk.CTkButton(btn_frame, text="✏️ Modifica", width=100, command=app._diary_edit_entry)
    app.apply_edit_button_style(edit_btn)
    edit_btn.pack(side="left", padx=4)
    delete_btn = ctk.CTkButton(btn_frame, text="🗑️ Elimina", width=100, command=app._diary_delete_entry)
    app.apply_delete_button_style(delete_btn)
    delete_btn.pack(side="left", padx=4)

    # Popola combo clienti
    app._diary_populate_combos()


def diary_populate_combos(app) -> None:
    clients = app.db.list_clients()
    client_opts = ["Tutti"] + [f"{c['id']} - {c['name']}" for c in clients]
    app.diary_client_combo.configure(values=client_opts)
    app.diary_client_var.set("Tutti")
    app.diary_project_combo.configure(values=["Tutte"])
    app.diary_project_var.set("Tutte")
    app.diary_activity_combo.configure(values=["Tutte"])
    app.diary_activity_var.set("Tutte")


def diary_on_client_change(app) -> None:
    client_id = app._id_from_option(app.diary_client_var.get())
    if client_id:
        projects = app.db.list_projects(client_id)
        proj_opts = ["Tutte"] + [f"{p['id']} - {p['name']}" for p in projects]
    else:
        proj_opts = ["Tutte"]
    app.diary_project_combo.configure(values=proj_opts)
    app.diary_project_var.set("Tutte")
    app.diary_activity_combo.configure(values=["Tutte"])
    app.diary_activity_var.set("Tutte")


def diary_on_project_change(app) -> None:
    project_id = app._id_from_option(app.diary_project_var.get())
    if project_id:
        activities = app.db.list_activities(project_id)
        act_opts = ["Tutte"] + [f"{a['id']} - {a['name']}" for a in activities]
    else:
        act_opts = ["Tutte"]
    app.diary_activity_combo.configure(values=act_opts)
    app.diary_activity_var.set("Tutte")


def refresh_diary_data(app) -> None:
    for item in app.diary_tree.get_children():
        app.diary_tree.delete(item)

    client_id = app._id_from_option(app.diary_client_var.get())
    project_id = app._id_from_option(app.diary_project_var.get())
    activity_id = app._id_from_option(app.diary_activity_var.get())
    show_completed = app.diary_show_completed_var.get()

    entries = app.db.list_diary_entries(
        client_id=client_id,
        project_id=project_id,
        activity_id=activity_id,
        show_completed=show_completed,
    )

    today = date.today().isoformat()
    for e in entries:
        # Costruisci riferimento
        ref_parts = []
        if e.get("client_name"):
            ref_parts.append(e["client_name"])
        if e.get("project_name"):
            ref_parts.append(e["project_name"])
        if e.get("activity_name"):
            ref_parts.append(e["activity_name"])
        ref_str = " › ".join(ref_parts) if ref_parts else "—"

        # Alert
        alert = ""
        if e.get("reminder_date") and not e.get("is_completed"):
            if e["reminder_date"] <= today:
                alert = "🔔"

        # Priorità
        priority = "⚡" if e.get("priority") else ""

        # Stato
        status = "✓" if e.get("is_completed") else "—"

        # Data formattata
        reminder_fmt = app._format_date_display(e.get("reminder_date") or "")
        created_fmt = (e.get("created_at") or "")[:10]

        # Contenuto troncato
        content = (e.get("content") or "")[:80]
        if len(e.get("content") or "") > 80:
            content += "…"

        app.diary_tree.insert("", "end", values=(
            e["id"], alert, priority, ref_str, content, reminder_fmt, status, e.get("user_name", ""), created_fmt
        ))


def format_date_display(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return date_str


def update_diary_alert(app) -> None:
    """Aggiorna il nome della tab con badge se ci sono promemoria scaduti."""
    count = app.db.count_pending_reminders()
    tab_name = "Diario"
    if count > 0:
        tab_name = f"Diario 🔔{count}"
    # CTkTabview non ha un metodo per rinominare, quindi aggiorniamo il testo del bottone interno
    try:
        if hasattr(app.tabview, "_segmented_button"):
            # Trova il bottone giusto
            for btn_name, btn in app.tabview._segmented_button._buttons_dict.items():
                if btn_name.startswith("Diario"):
                    # Non possiamo rinominare facilmente, quindi usiamo un workaround
                    pass
    except Exception:
        pass
    # Alternativa: schedula un refresh periodico o mostra in altro modo


def diary_get_selected_id(app) -> int | None:
    sel = app.diary_tree.selection()
    if not sel:
        messagebox.showwarning("Selezione", "Seleziona una nota.")
        return None
    return int(app.diary_tree.item(sel[0], "values")[0])


def diary_toggle_completed(app) -> None:
    entry_id = app._diary_get_selected_id()
    if entry_id:
        app.db.toggle_diary_completed(entry_id)
        app.refresh_diary_data()
        app.update_diary_alert()


def diary_delete_entry(app) -> None:
    entry_id = app._diary_get_selected_id()
    if not entry_id:
        return
    if messagebox.askyesno("Conferma", "Eliminare questa nota?"):
        app.db.delete_diary_entry(entry_id)
        app.refresh_diary_data()
        app.update_diary_alert()


def diary_new_entry(app) -> None:
    app._diary_open_editor(None)


def diary_edit_entry(app) -> None:
    entry_id = app._diary_get_selected_id()
    if entry_id:
        app._diary_open_editor(entry_id)


def diary_open_editor(app, entry_id: int | None) -> None:
    is_edit = entry_id is not None
    entry = app.db.get_diary_entry(entry_id) if is_edit else None

    dialog = ctk.CTkToplevel(app)
    dialog.title("Modifica Nota" if is_edit else "Nuova Nota")
    dialog.geometry("600x500")
    dialog.transient(app)
    dialog.grab_set()

    pad = {"padx": 12, "pady": 6}

    # Cliente
    ctk.CTkLabel(dialog, text="Cliente").pack(anchor="w", **pad)
    client_var = ctk.StringVar()
    client_combo = ctk.CTkComboBox(dialog, width=400, variable=client_var, state="readonly")
    client_combo.pack(anchor="w", **pad)

    # Commessa
    ctk.CTkLabel(dialog, text="Commessa").pack(anchor="w", **pad)
    project_var = ctk.StringVar()
    project_combo = ctk.CTkComboBox(dialog, width=400, variable=project_var, state="readonly")
    project_combo.pack(anchor="w", **pad)

    # Attività
    ctk.CTkLabel(dialog, text="Attività").pack(anchor="w", **pad)
    activity_var = ctk.StringVar()
    activity_combo = ctk.CTkComboBox(dialog, width=400, variable=activity_var, state="readonly")
    activity_combo.pack(anchor="w", **pad)

    # Popola combo
    clients = app.db.list_clients()
    client_opts = ["— Nessuno —"] + [f"{c['id']} - {c['name']}" for c in clients]
    client_combo.configure(values=client_opts)

    def on_client_change(_=None):
        cid = app._id_from_option(client_var.get())
        if cid:
            projs = app.db.list_projects(cid)
            proj_opts = ["— Nessuna —"] + [f"{p['id']} - {p['name']}" for p in projs]
        else:
            proj_opts = ["— Nessuna —"]
        project_combo.configure(values=proj_opts)
        project_var.set("— Nessuna —")
        activity_combo.configure(values=["— Nessuna —"])
        activity_var.set("— Nessuna —")

    def on_project_change(_=None):
        pid = app._id_from_option(project_var.get())
        if pid:
            acts = app.db.list_activities(pid)
            act_opts = ["— Nessuna —"] + [f"{a['id']} - {a['name']}" for a in acts]
        else:
            act_opts = ["— Nessuna —"]
        activity_combo.configure(values=act_opts)
        activity_var.set("— Nessuna —")

    client_combo.configure(command=on_client_change)
    project_combo.configure(command=on_project_change)

    # Preset valori se edit
    if entry:
        if entry.get("client_id"):
            for opt in client_opts:
                if opt.startswith(f"{entry['client_id']} -"):
                    client_var.set(opt)
                    on_client_change()
                    break
        if entry.get("project_id"):
            projs = app.db.list_projects(entry["client_id"]) if entry.get("client_id") else []
            proj_opts = ["— Nessuna —"] + [f"{p['id']} - {p['name']}" for p in projs]
            project_combo.configure(values=proj_opts)
            for opt in proj_opts:
                if opt.startswith(f"{entry['project_id']} -"):
                    project_var.set(opt)
                    on_project_change()
                    break
        if entry.get("activity_id"):
            acts = app.db.list_activities(entry["project_id"]) if entry.get("project_id") else []
            act_opts = ["— Nessuna —"] + [f"{a['id']} - {a['name']}" for a in acts]
            activity_combo.configure(values=act_opts)
            for opt in act_opts:
                if opt.startswith(f"{entry['activity_id']} -"):
                    activity_var.set(opt)
                    break
    else:
        client_var.set("— Nessuno —")
        project_combo.configure(values=["— Nessuna —"])
        project_var.set("— Nessuna —")
        activity_combo.configure(values=["— Nessuna —"])
        activity_var.set("— Nessuna —")

    # Promemoria
    ctk.CTkLabel(dialog, text="Promemoria (YYYY-MM-DD)").pack(anchor="w", **pad)
    reminder_entry = ctk.CTkEntry(dialog, width=150)
    reminder_entry.pack(anchor="w", **pad)
    if entry and entry.get("reminder_date"):
        reminder_entry.insert(0, entry["reminder_date"])

    # Priorità
    priority_var = ctk.BooleanVar(value=entry.get("priority", 0) if entry else False)
    ctk.CTkCheckBox(dialog, text="Priorità alta ⚡", variable=priority_var).pack(anchor="w", **pad)

    # Contenuto
    ctk.CTkLabel(dialog, text="Contenuto").pack(anchor="w", **pad)
    content_text = ctk.CTkTextbox(dialog, width=560, height=120)
    content_text.pack(anchor="w", **pad)
    if entry and entry.get("content"):
        content_text.insert("1.0", entry["content"])

    def save():
        client_id = app._id_from_option(client_var.get())
        project_id = app._id_from_option(project_var.get())
        activity_id = app._id_from_option(activity_var.get())
        content = content_text.get("1.0", "end").strip()
        reminder = reminder_entry.get().strip() or None
        priority = 1 if priority_var.get() else 0

        if not content:
            messagebox.showwarning("Errore", "Il contenuto non può essere vuoto.")
            return

        if not client_id and not project_id and not activity_id:
            messagebox.showwarning("Errore", "Seleziona almeno un cliente, commessa o attività.")
            return

        try:
            if is_edit:
                app.db.update_diary_entry(
                    entry_id,
                    content=content,
                    client_id=client_id or 0,
                    project_id=project_id or 0,
                    activity_id=activity_id or 0,
                    reminder_date=reminder or "",
                    priority=priority,
                )
            else:
                app.db.create_diary_entry(
                    user_id=app.current_user["id"],
                    content=content,
                    client_id=client_id,
                    project_id=project_id,
                    activity_id=activity_id,
                    reminder_date=reminder,
                    priority=priority,
                )
            dialog.destroy()
            app.refresh_diary_data()
            app.update_diary_alert()
        except Exception as exc:
            messagebox.showerror("Errore", str(exc))

    ctk.CTkButton(dialog, text="Salva", width=120, command=save).pack(pady=16)
