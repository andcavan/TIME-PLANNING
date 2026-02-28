from __future__ import annotations

import sqlite3
from tkinter import messagebox, ttk

import customtkinter as ctk


def open_clients_management_dialog(app) -> None:
    """Apre finestra popup per gestione completa clienti."""
    popup = ctk.CTkToplevel(app)
    popup.title("Gestione Clienti")
    popup.geometry("800x600")
    popup.transient(app)
    popup.grab_set()

    # Form creazione/modifica
    form_frame = ctk.CTkFrame(popup)
    form_frame.pack(fill="x", padx=10, pady=10)
    form_frame.grid_columnconfigure(1, weight=1)
    form_frame.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(form_frame, text="Nome cliente:", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=0, padx=5, pady=5, sticky="w"
    )
    client_name_entry = ctk.CTkEntry(form_frame, placeholder_text="Nome cliente")
    client_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

    ctk.CTkLabel(form_frame, text="Referente:", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=2, padx=5, pady=5, sticky="w"
    )
    client_referente_entry = ctk.CTkEntry(form_frame, placeholder_text="Nome referente")
    client_referente_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

    ctk.CTkLabel(form_frame, text="Telefono:", font=ctk.CTkFont(weight="bold")).grid(
        row=1, column=0, padx=5, pady=5, sticky="w"
    )
    client_telefono_entry = ctk.CTkEntry(form_frame, placeholder_text="Numero telefono")
    client_telefono_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    ctk.CTkLabel(form_frame, text="Email:", font=ctk.CTkFont(weight="bold")).grid(
        row=1, column=2, padx=5, pady=5, sticky="w"
    )
    client_email_entry = ctk.CTkEntry(form_frame, placeholder_text="Indirizzo email")
    client_email_entry.grid(row=1, column=3, padx=5, pady=5, sticky="ew")

    notes_row = 3 if app.is_admin else 2
    buttons_row = notes_row + 1

    if app.is_admin:
        ctk.CTkLabel(form_frame, text="Costo orario (€/h):", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        client_rate_entry = ctk.CTkEntry(form_frame, placeholder_text="0.00", width=120)
        client_rate_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

    ctk.CTkLabel(form_frame, text="Note:", font=ctk.CTkFont(weight="bold")).grid(
        row=notes_row, column=0, padx=5, pady=5, sticky="w"
    )
    client_notes_entry = ctk.CTkEntry(form_frame, placeholder_text="Note opzionali")
    client_notes_entry.grid(row=notes_row, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

    # Funzioni CRUD
    editing_client_id = [None]  # Lista per permettere modifica da inner function

    def add_or_update_client():
        try:
            name = client_name_entry.get().strip()
            if not name:
                raise ValueError("Nome cliente obbligatorio.")

            if app.is_admin:
                rate = app._to_float(client_rate_entry.get().strip() or "0", "Costo cliente")
            else:
                rate = 0.0

            notes = client_notes_entry.get().strip()
            referente = client_referente_entry.get().strip()
            telefono = client_telefono_entry.get().strip()
            email = client_email_entry.get().strip()

            if editing_client_id[0] is None:
                app.db.add_client(name, rate, notes, referente, telefono, email)
                messagebox.showinfo("Gestione Clienti", "Cliente aggiunto con successo.")
            else:
                app.db.update_client(editing_client_id[0], name, rate, notes, referente, telefono, email)
                messagebox.showinfo("Gestione Clienti", "Cliente modificato con successo.")
                editing_client_id[0] = None
                save_btn.configure(text="Aggiungi Cliente")
                save_btn.configure(**save_btn_default_style)

            client_name_entry.delete(0, "end")
            client_referente_entry.delete(0, "end")
            client_telefono_entry.delete(0, "end")
            client_email_entry.delete(0, "end")
            if app.is_admin:
                client_rate_entry.delete(0, "end")
            client_notes_entry.delete(0, "end")

            refresh_clients_list()
            app.refresh_master_data()
            if hasattr(app, "refresh_control_panel"):
                app.refresh_control_panel()

        except ValueError as exc:
            messagebox.showerror("Gestione Clienti", str(exc))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                messagebox.showerror("Gestione Clienti", "Esiste già un cliente con questo nome.\nScegli un nome diverso.")
            else:
                messagebox.showerror("Gestione Clienti", f"Errore database: {exc}")

    def load_client_for_edit():
        selected_items = clients_tree.selection()
        if not selected_items:
            messagebox.showinfo("Gestione Clienti", "Seleziona un cliente dall'elenco.")
            return

        client_id = int(selected_items[0])
        clients = app.db.list_clients()
        client = next((c for c in clients if c["id"] == client_id), None)

        if client:
            editing_client_id[0] = client_id
            client_name_entry.delete(0, "end")
            client_name_entry.insert(0, client["name"])
            client_referente_entry.delete(0, "end")
            client_referente_entry.insert(0, client.get("referente", ""))
            client_telefono_entry.delete(0, "end")
            client_telefono_entry.insert(0, client.get("telefono", ""))
            client_email_entry.delete(0, "end")
            client_email_entry.insert(0, client.get("email", ""))
            if app.is_admin:
                client_rate_entry.delete(0, "end")
                client_rate_entry.insert(0, str(client["hourly_rate"]))
            client_notes_entry.delete(0, "end")
            client_notes_entry.insert(0, client.get("notes", ""))
            save_btn.configure(text="Salva Modifiche")
            app.apply_edit_button_style(save_btn)

    def delete_client():
        selected_items = clients_tree.selection()
        if not selected_items:
            messagebox.showinfo("Gestione Clienti", "Seleziona un cliente dall'elenco.")
            return

        if not messagebox.askyesno("Conferma", "Eliminare il cliente? Verranno eliminati anche commesse, attività e timesheet associati."):
            return

        client_id = int(selected_items[0])
        try:
            app.db.delete_client(client_id)
            messagebox.showinfo("Gestione Clienti", "Cliente eliminato.")
            refresh_clients_list()
            app.refresh_master_data()
            if hasattr(app, "refresh_control_panel"):
                app.refresh_control_panel()
        except Exception as exc:
            messagebox.showerror("Gestione Clienti", f"Errore: {exc}")

    def refresh_clients_list():
        for item in clients_tree.get_children():
            clients_tree.delete(item)

        clients = app.db.list_clients()
        for client in clients:
            if app.is_admin:
                values = (
                    client.get("referente", ""),
                    client.get("telefono", ""),
                    client.get("email", ""),
                    f"{client['hourly_rate']:.2f} €",
                    client.get("notes", ""),
                )
            else:
                values = (
                    client.get("referente", ""),
                    client.get("telefono", ""),
                    client.get("email", ""),
                    client.get("notes", ""),
                )
            clients_tree.insert("", "end", iid=str(client["id"]), text=client["name"], values=values)

    # Pulsanti CRUD
    btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
    btn_frame.grid(row=buttons_row, column=0, columnspan=4, pady=(12, 6))

    save_btn = ctk.CTkButton(btn_frame, text="Aggiungi Cliente", command=add_or_update_client, width=120)
    save_btn.pack(side="left", padx=5)
    save_btn_default_style = {
        "fg_color": save_btn.cget("fg_color"),
        "hover_color": save_btn.cget("hover_color"),
    }

    edit_btn = ctk.CTkButton(btn_frame, text="Modifica Selezionato", command=load_client_for_edit, width=140)
    app.apply_edit_button_style(edit_btn)
    edit_btn.pack(side="left", padx=5)
    delete_btn = ctk.CTkButton(btn_frame, text="Elimina Selezionato", command=delete_client, width=140)
    app.apply_delete_button_style(delete_btn)
    delete_btn.pack(side="left", padx=5)

    # Lista clienti
    list_frame = ctk.CTkFrame(popup)
    list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    list_frame.grid_rowconfigure(0, weight=1)
    list_frame.grid_columnconfigure(0, weight=1)

    if app.is_admin:
        columns = ("referente", "telefono", "email", "rate", "notes")
        clients_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings")
        clients_tree.heading("#0", text="Nome Cliente")
        clients_tree.heading("referente", text="Referente")
        clients_tree.heading("telefono", text="Telefono")
        clients_tree.heading("email", text="Email")
        clients_tree.heading("rate", text="Costo orario")
        clients_tree.heading("notes", text="Note")
        clients_tree.column("#0", width=180)
        clients_tree.column("referente", width=140)
        clients_tree.column("telefono", width=110)
        clients_tree.column("email", width=180)
        clients_tree.column("rate", width=100)
        clients_tree.column("notes", width=200)
    else:
        columns = ("referente", "telefono", "email", "notes")
        clients_tree = ttk.Treeview(list_frame, columns=columns, show="tree headings")
        clients_tree.heading("#0", text="Nome Cliente")
        clients_tree.heading("referente", text="Referente")
        clients_tree.heading("telefono", text="Telefono")
        clients_tree.heading("email", text="Email")
        clients_tree.heading("notes", text="Note")
        clients_tree.column("#0", width=200)
        clients_tree.column("referente", width=150)
        clients_tree.column("telefono", width=120)
        clients_tree.column("email", width=180)
        clients_tree.column("notes", width=250)

    clients_tree.grid(row=0, column=0, sticky="nsew")

    scroll = ttk.Scrollbar(list_frame, orient="vertical", command=clients_tree.yview)
    clients_tree.configure(yscrollcommand=scroll.set)
    scroll.grid(row=0, column=1, sticky="ns")

    refresh_clients_list()
