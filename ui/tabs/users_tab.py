from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk


def build_users_tab(app) -> None:
    app.tab_users.grid_columnconfigure(0, weight=1)
    app.tab_users.grid_rowconfigure(3, weight=1)

    if not app.is_admin:
        ctk.CTkLabel(
            app.tab_users,
            text="Sezione riservata admin.",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=40)
        return

    # Variabile per tracciare se stiamo modificando un utente
    app.editing_user_id = None

    form = ctk.CTkFrame(app.tab_users)
    form.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
    for i in range(5):
        form.grid_columnconfigure(i, weight=1)

    ctk.CTkLabel(form, text="Username").grid(row=0, column=0, padx=8, pady=4, sticky="w")
    app.new_user_username_entry = ctk.CTkEntry(form)
    app.new_user_username_entry.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Nome completo").grid(row=0, column=1, padx=8, pady=4, sticky="w")
    app.new_user_fullname_entry = ctk.CTkEntry(form)
    app.new_user_fullname_entry.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

    ctk.CTkLabel(form, text="Ruolo").grid(row=0, column=2, padx=8, pady=4, sticky="w")
    app.new_user_role_combo = ctk.CTkComboBox(form, values=["user", "admin"], state="readonly")
    app.new_user_role_combo.grid(row=1, column=2, padx=8, pady=4, sticky="ew")
    app.new_user_role_combo.set("user")

    ctk.CTkLabel(form, text="Password (solo per nuovo)").grid(row=0, column=3, padx=8, pady=4, sticky="w")
    app.new_user_password_entry = ctk.CTkEntry(form)
    app.new_user_password_entry.grid(row=1, column=3, padx=8, pady=4, sticky="ew")

    app.save_user_button = ctk.CTkButton(form, text="Crea utente", command=app.save_user)
    app.save_user_button.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

    # Permessi tab (solo per ruolo user)
    tabs_frame = ctk.CTkFrame(app.tab_users)
    tabs_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")

    ctk.CTkLabel(tabs_frame, text="Tab visibili utente selezionato:", font=ctk.CTkFont(weight="bold")).pack(
        side="left", padx=(10, 20), pady=8
    )

    app.tab_calendar_var = tk.BooleanVar(value=True)
    app.tab_master_var = tk.BooleanVar(value=True)
    app.tab_control_var = tk.BooleanVar(value=True)

    ctk.CTkCheckBox(tabs_frame, text="Calendario Ore", variable=app.tab_calendar_var).pack(side="left", padx=8, pady=8)
    ctk.CTkCheckBox(tabs_frame, text="Gestione Commesse", variable=app.tab_master_var).pack(side="left", padx=8, pady=8)
    ctk.CTkCheckBox(tabs_frame, text="Controllo Programmazione", variable=app.tab_control_var).pack(side="left", padx=8, pady=8)

    ctk.CTkButton(tabs_frame, text="Salva permessi", command=app.save_user_tabs).pack(side="left", padx=20, pady=8)

    actions = ctk.CTkFrame(app.tab_users)
    actions.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="ew")

    ctk.CTkButton(actions, text="Modifica utente", command=app.load_user_for_edit).pack(side="left", padx=(10, 6), pady=8)
    ctk.CTkButton(actions, text="Annulla modifica", command=app.cancel_user_edit).pack(side="left", padx=6, pady=8)
    ctk.CTkLabel(actions, text="Nuova password utente selezionato").pack(side="left", padx=(20, 6), pady=8)
    app.reset_password_entry = ctk.CTkEntry(actions, width=200)
    app.reset_password_entry.pack(side="left", padx=6, pady=8)
    ctk.CTkButton(actions, text="Reset password", command=app.reset_selected_password).pack(side="left", padx=6, pady=8)
    ctk.CTkButton(actions, text="Attiva/Disattiva", command=app.toggle_selected_user).pack(side="left", padx=6, pady=8)
    ctk.CTkButton(actions, text="Aggiorna", command=app.refresh_users_data).pack(side="left", padx=6, pady=8)

    table = ctk.CTkFrame(app.tab_users)
    table.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="nsew")
    table.grid_rowconfigure(0, weight=1)
    table.grid_columnconfigure(0, weight=1)

    columns = ("id", "username", "fullname", "role", "active")
    app.users_tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
    app.users_tree.heading("id", text="ID")
    app.users_tree.heading("username", text="Username")
    app.users_tree.heading("fullname", text="Nome")
    app.users_tree.heading("role", text="Ruolo")
    app.users_tree.heading("active", text="Attivo")
    app.users_tree.column("id", width=70, anchor="center")
    app.users_tree.column("username", width=120, anchor="w")
    app.users_tree.column("fullname", width=220, anchor="w")
    app.users_tree.column("role", width=90, anchor="center")
    app.users_tree.column("active", width=90, anchor="center")
    app.users_tree.grid(row=0, column=0, sticky="nsew")

    # Bind per popolare i checkbox tab quando si seleziona un utente
    app.users_tree.bind("<<TreeviewSelect>>", app.on_user_select)

    scroll = ttk.Scrollbar(table, orient="vertical", command=app.users_tree.yview)
    app.users_tree.configure(yscrollcommand=scroll.set)
    scroll.grid(row=0, column=1, sticky="ns")


def on_user_select(app, _event: object) -> None:
    """Popola i checkbox tab quando un utente viene selezionato."""
    selected_items = app.users_tree.selection()
    if not selected_items:
        return

    user_id = int(selected_items[0])
    users = app.db.list_users(include_inactive=True)
    selected_user = next((u for u in users if u["id"] == user_id), None)

    if selected_user:
        app.tab_calendar_var.set(bool(selected_user.get("tab_calendar", 1)))
        app.tab_master_var.set(bool(selected_user.get("tab_master", 1)))
        app.tab_control_var.set(bool(selected_user.get("tab_control", 1)))


def save_user_tabs(app) -> None:
    """Salva i permessi tab per l'utente selezionato."""
    selected_items = app.users_tree.selection()
    if not selected_items:
        messagebox.showinfo("Utenti", "Seleziona un utente dall'elenco.")
        return

    user_id = int(selected_items[0])

    try:
        app.db.update_user_tabs(
            user_id,
            app.tab_calendar_var.get(),
            app.tab_master_var.get(),
            1,
            app.tab_control_var.get()
        )
        messagebox.showinfo("Utenti", "Permessi aggiornati. L'utente deve rifare il login per applicare le modifiche.")
        app.refresh_users_data()
    except Exception as exc:
        messagebox.showerror("Utenti", f"Errore: {exc}")


def refresh_users_data(app) -> None:
    users = app.db.list_users(include_inactive=True)
    # Programmazione e Controllo: rimosso filtro utente, non più necessario

    if hasattr(app, "users_tree"):
        for item in app.users_tree.get_children():
            app.users_tree.delete(item)
        for user in users:
            app.users_tree.insert(
                "",
                "end",
                iid=str(user["id"]),
                values=(
                    user["id"],
                    user["username"],
                    user["full_name"],
                    user["role"],
                    "SI" if user["active"] else "NO",
                ),
            )


def save_user(app) -> None:
    """Salva utente (crea nuovo o modifica esistente)."""
    try:
        username = app.new_user_username_entry.get().strip()
        full_name = app.new_user_fullname_entry.get().strip()
        role = app.new_user_role_combo.get().strip()
        password = app.new_user_password_entry.get().strip()

        if not username or not full_name:
            raise ValueError("Compila username e nome.")
        if role not in {"admin", "user"}:
            raise ValueError("Ruolo non valido.")

        if app.editing_user_id is None:
            # Modalità creazione
            if not password:
                raise ValueError("Compila la password per il nuovo utente.")

            # Per gli admin tutte le tab sono sempre visibili, per i user usa i checkbox
            if role == "admin":
                app.db.create_user(username, full_name, role, password, True, True, True, True)
            else:
                app.db.create_user(
                    username, full_name, role, password,
                    app.tab_calendar_var.get(),
                    app.tab_master_var.get(),
                    1,
                    app.tab_control_var.get()
                )
            messagebox.showinfo("Utenti", "Utente creato con successo.")
        else:
            # Modalità modifica
            if role == "admin":
                app.db.update_user(app.editing_user_id, username, full_name, role, True, True, True, True)
            else:
                app.db.update_user(
                    app.editing_user_id, username, full_name, role,
                    app.tab_calendar_var.get(),
                    app.tab_master_var.get(),
                    1,
                    app.tab_control_var.get()
                )
            messagebox.showinfo("Utenti", "Utente modificato con successo.")

    except (ValueError, sqlite3.IntegrityError) as exc:
        messagebox.showerror("Utenti", str(exc))
        return

    app.cancel_user_edit()
    app.refresh_users_data()
    app.refresh_day_entries()
    app.refresh_schedule_list()


def load_user_for_edit(app) -> None:
    """Carica i dati dell'utente selezionato nel form per la modifica."""
    selected_items = app.users_tree.selection()
    if not selected_items:
        messagebox.showinfo("Utenti", "Seleziona un utente dall'elenco.")
        return

    user_id = int(selected_items[0])
    users = app.db.list_users(include_inactive=True)
    selected_user = next((u for u in users if u["id"] == user_id), None)

    if not selected_user:
        return

    # Imposta modalità modifica
    app.editing_user_id = user_id

    # Popola il form
    app.new_user_username_entry.delete(0, "end")
    app.new_user_username_entry.insert(0, selected_user["username"])

    app.new_user_fullname_entry.delete(0, "end")
    app.new_user_fullname_entry.insert(0, selected_user["full_name"])

    app.new_user_role_combo.set(selected_user["role"])

    app.new_user_password_entry.delete(0, "end")

    # Aggiorna checkbox
    app.tab_calendar_var.set(bool(selected_user.get("tab_calendar", 1)))
    app.tab_master_var.set(bool(selected_user.get("tab_master", 1)))
    app.tab_control_var.set(bool(selected_user.get("tab_control", 1)))

    # Cambia etichetta pulsante
    app.save_user_button.configure(text="Salva modifiche")


def cancel_user_edit(app) -> None:
    """Annulla la modalità modifica e pulisce il form."""
    app.editing_user_id = None
    app.new_user_username_entry.delete(0, "end")
    app.new_user_fullname_entry.delete(0, "end")
    app.new_user_password_entry.delete(0, "end")
    app.new_user_role_combo.set("user")
    app.save_user_button.configure(text="Crea utente")

    # Reset checkbox a default
    app.tab_calendar_var.set(True)
    app.tab_master_var.set(True)
    app.tab_control_var.set(True)


def toggle_selected_user(app) -> None:
    selection = app.users_tree.selection()
    if not selection:
        messagebox.showwarning("Utenti", "Seleziona un utente.")
        return

    user_id = int(selection[0])
    if user_id == int(app.current_user["id"]):
        messagebox.showwarning("Utenti", "Non puoi disattivare il tuo utente.")
        return

    user_row = [u for u in app.db.list_users(include_inactive=True) if int(u["id"]) == user_id]
    if not user_row:
        return
    current_state = bool(user_row[0]["active"])
    app.db.set_user_active(user_id, not current_state)
    app.refresh_users_data()


def reset_selected_password(app) -> None:
    selection = app.users_tree.selection()
    if not selection:
        messagebox.showwarning("Utenti", "Seleziona un utente.")
        return
    new_password = app.reset_password_entry.get().strip()
    if not new_password:
        messagebox.showwarning("Utenti", "Inserisci la nuova password.")
        return

    user_id = int(selection[0])
    app.db.reset_user_password(user_id, new_password)
    app.reset_password_entry.delete(0, "end")
    messagebox.showinfo("Utenti", "Password aggiornata.")

