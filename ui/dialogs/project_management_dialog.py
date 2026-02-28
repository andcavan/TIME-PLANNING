from __future__ import annotations

import sqlite3
import traceback
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk


def open_project_management_dialog(app) -> None:
    """Apre finestra popup per gestione completa della commessa (nuova o esistente)."""
    # Modalità: se c'è una commessa selezionata -> modifica, altrimenti -> crea nuova
    is_new = not app.selected_project_id

    if is_new:
        # Modalità creazione: serve almeno un cliente selezionato
        client_id = app._id_from_option(app.pm_client_combo.get())
        if not client_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona prima un cliente.")
            return

        # Carica dati cliente per la nuova commessa
        clients = app.db.list_clients()
        client = next((c for c in clients if c["id"] == client_id), None)
        if not client:
            messagebox.showerror("Gestione Commesse", "Cliente non trovato.")
            return

        project = {
            "name": "",
            "referente_commessa": "",
            "hourly_rate": client["hourly_rate"],  # Eredita dal cliente
            "notes": "",
            "descrizione_commessa": "",
        }
        project_schedule = None
    else:
        # Modalità modifica: carica dati commessa esistente
        projects = app.db.list_projects()
        project = next((p for p in projects if p["id"] == app.selected_project_id), None)

        if not project:
            messagebox.showerror("Gestione Commesse", "Commessa non trovata.")
            return

        client_id = project["client_id"]

        # Carica pianificazione esistente
        schedules = app.db.list_schedules()
        project_schedule = next((s for s in schedules if s["project_id"] == app.selected_project_id and s["activity_id"] is None), None)

    popup = ctk.CTkToplevel(app)
    if is_new:
        popup.title("Nuova Commessa")
    else:
        popup.title(f"Gestione Commessa: {project['name']}")
    popup.geometry("800x700")
    popup.transient(app)
    popup.grab_set()

    # Frame con scrollbar
    main_scroll_frame = ctk.CTkScrollableFrame(popup)
    main_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

    # Form modifica dati commessa
    form_frame = ctk.CTkFrame(main_scroll_frame)
    form_frame.pack(fill="x", pady=(0, 10))
    form_frame.grid_columnconfigure(1, weight=1)
    form_frame.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(form_frame, text="Nome commessa:", font=ctk.CTkFont(weight="bold")).grid(
        row=0, column=0, padx=5, pady=5, sticky="w"
    )
    project_name_entry = ctk.CTkEntry(form_frame, placeholder_text="Inserisci nome commessa")
    project_name_entry.insert(0, project["name"])
    project_name_entry.grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

    ctk.CTkLabel(form_frame, text="Referente commessa:", font=ctk.CTkFont(weight="bold")).grid(
        row=1, column=0, padx=5, pady=5, sticky="w"
    )
    project_referente_entry = ctk.CTkEntry(form_frame, placeholder_text="Nome referente per questa commessa")
    project_referente_entry.insert(0, project.get("referente_commessa", ""))
    project_referente_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

    if app.is_admin:
        ctk.CTkLabel(form_frame, text="Costo orario (€/h):", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        project_rate_entry = ctk.CTkEntry(form_frame, width=120)
        project_rate_entry.insert(0, str(project["hourly_rate"]))
        project_rate_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

    ctk.CTkLabel(form_frame, text="Note:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
    project_notes_entry = ctk.CTkEntry(form_frame)
    project_notes_entry.insert(0, project.get("notes", ""))
    project_notes_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")

    # Descrizione commessa (multilinea)
    ctk.CTkLabel(form_frame, text="Descrizione Commessa:", font=ctk.CTkFont(weight="bold")).grid(
        row=4, column=0, padx=5, pady=(10, 5), sticky="nw"
    )
    project_desc_text = ctk.CTkTextbox(form_frame, height=100, wrap="word")
    project_desc_text.insert("1.0", project.get("descrizione_commessa", ""))
    project_desc_text.grid(row=4, column=1, columnspan=3, padx=5, pady=(10, 5), sticky="ew")

    # Pianificazione
    ctk.CTkLabel(form_frame, text="Pianificazione", font=ctk.CTkFont(size=12, weight="bold")).grid(
        row=5, column=0, columnspan=4, padx=5, pady=(15, 5), sticky="w"
    )

    ctk.CTkLabel(form_frame, text="Data inizio:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
    project_start_entry = ctk.CTkEntry(form_frame, placeholder_text="gg/mm/aaaa", width=120)
    project_start_entry.grid(row=6, column=1, padx=5, pady=5, sticky="w")
    app.setup_date_entry_helpers(project_start_entry)

    ctk.CTkLabel(form_frame, text="Data fine:").grid(row=6, column=2, padx=5, pady=5, sticky="w")
    project_end_entry = ctk.CTkEntry(form_frame, placeholder_text="gg/mm/aaaa", width=120)
    project_end_entry.grid(row=6, column=3, padx=5, pady=5, sticky="w")
    app.setup_date_entry_helpers(project_end_entry)

    ctk.CTkLabel(form_frame, text="Ore preventivate:").grid(row=7, column=0, padx=5, pady=5, sticky="w")
    project_hours_entry = ctk.CTkEntry(form_frame, width=120)
    project_hours_entry.grid(row=7, column=1, padx=5, pady=5, sticky="w")

    ctk.CTkLabel(form_frame, text="Budget (€):").grid(row=7, column=2, padx=5, pady=5, sticky="w")
    project_budget_entry = ctk.CTkEntry(form_frame, width=120)
    project_budget_entry.grid(row=7, column=3, padx=5, pady=5, sticky="w")

    # Carica pianificazione esistente (solo se modifica)
    if project_schedule:
        start = datetime.strptime(project_schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        end = datetime.strptime(project_schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        project_start_entry.insert(0, start)
        project_end_entry.insert(0, end)
        project_hours_entry.insert(0, str(project_schedule["planned_hours"]))
        project_budget_entry.insert(0, str(project_schedule.get("budget", 0)))

    def save_project():
        try:
            # Salva il project_id corretto all'inizio (in caso di modifica)
            current_project_id = app.selected_project_id if is_new else project["id"]

            name = project_name_entry.get().strip()
            if not name:
                raise ValueError("Nome commessa obbligatorio.")

            if app.is_admin:
                rate = app._to_float(project_rate_entry.get().strip() or "0", "Costo commessa")
            else:
                rate = project["hourly_rate"]

            notes = project_notes_entry.get().strip()
            referente_commessa = project_referente_entry.get().strip()
            descrizione_commessa = project_desc_text.get("1.0", "end-1c").strip()

            # VALIDAZIONE PIANIFICAZIONE PRIMA DI SALVARE LA COMMESSA
            start_date_str = project_start_entry.get().strip()
            end_date_str = project_end_entry.get().strip()
            hours_str = project_hours_entry.get().strip()
            budget_str = project_budget_entry.get().strip()

            # Crea schedule se ci sono date O se ci sono ore/budget
            has_any_planning = any([start_date_str, end_date_str, hours_str, budget_str])

            # Variabili per schedule
            start_date = None
            end_date = None
            planned_hours = 0
            budget = 0

            if has_any_planning:
                # Converti ore e budget (senza validazioni)
                planned_hours = app._to_float(hours_str, "Ore preventivate") if hours_str else 0
                budget = app._to_float(budget_str, "Budget") if budget_str else 0

                # Gestisci date
                if start_date_str and end_date_str:
                    # Usa le date inserite dall'utente
                    start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")

                    if start_date > end_date:
                        raise ValueError("La data di inizio deve essere precedente alla data di fine.")
                else:
                    # Usa date default dell'anno corrente
                    current_year = datetime.now().year
                    start_date = f"{current_year}-01-01"
                    end_date = f"{current_year}-12-31"

            # VALIDAZIONE SUPERATA - ORA SALVA LA COMMESSA
            if is_new:
                # Crea nuova commessa
                new_project_id = app.db.add_project(client_id, name, rate, notes, referente_commessa, descrizione_commessa)
                current_project_id = new_project_id
                app.selected_project_id = new_project_id
            else:
                # Aggiorna commessa esistente
                app.db.update_project(current_project_id, name, rate, notes, referente_commessa, descrizione_commessa)

            # GESTIONE SCHEDULE
            if has_any_planning:
                # Salva schedule
                if project_schedule and not is_new:
                    app.db.update_schedule(project_schedule["id"], current_project_id, None, start_date, end_date, planned_hours, "", budget)
                else:
                    app.db.add_schedule(current_project_id, None, start_date, end_date, planned_hours, "", budget)
            elif not has_any_planning and project_schedule and not is_new:
                # L'utente ha cancellato tutti i dati di pianificazione e c'è uno schedule esistente -> elimina lo schedule
                if messagebox.askyesno("Conferma", "Vuoi eliminare la pianificazione di questa commessa?"):
                    app.db.delete_schedule(project_schedule["id"])

            if is_new:
                messagebox.showinfo("Gestione Commesse", "Nuova commessa creata con successo.")
            else:
                messagebox.showinfo("Gestione Commesse", "Commessa aggiornata con successo.")

            # Aggiorna app.selected_project_id per sincronizzazione
            app.selected_project_id = current_project_id

            popup.destroy()
            app.refresh_master_data()
            app.refresh_projects_tree()

            if hasattr(app, "refresh_control_panel"):
                app.refresh_control_panel()

        except ValueError as exc:
            messagebox.showerror("Gestione Commesse", str(exc))
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                messagebox.showerror("Gestione Commesse", "Esiste già una commessa con questo nome per questo cliente.\nScegli un nome diverso.")
            else:
                messagebox.showerror("Gestione Commesse", f"Errore database: {exc}")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("Gestione Commesse", f"Errore generico: {exc}")

    def delete_project():
        if is_new:
            return

        if not messagebox.askyesno("Conferma", "Eliminare la commessa? Verranno eliminati anche attività, pianificazioni e timesheet associati."):
            return

        try:
            project_id_to_delete = project["id"]
            app.db.delete_project(project_id_to_delete)
            messagebox.showinfo("Gestione Commesse", "Commessa eliminata.")
            popup.destroy()

            app.selected_project_id = None
            app.selected_activity_id = None
            app.refresh_master_data()
            if hasattr(app, "refresh_control_panel"):
                app.refresh_control_panel()
        except Exception as exc:
            messagebox.showerror("Gestione Commesse", f"Errore: {exc}")

    # Verifica chiusura: se ha schedule usa il suo status, altrimenti usa campo closed
    is_closed = False
    if not is_new:
        if project_schedule:
            is_closed = project_schedule.get("status", "aperta") == "chiusa"
        else:
            is_closed = project.get("closed", 0) == 1

    # Non disabilitiamo più i campi - solo i pulsanti saranno disabilitati
    # Questo permette di leggere i valori dei campi anche quando la commessa è chiusa

    # Pulsanti
    btn_frame = ctk.CTkFrame(main_scroll_frame, fg_color="transparent")
    btn_frame.pack(pady=20)

    if is_new:
        ctk.CTkButton(btn_frame, text="Crea Commessa", command=save_project, width=150).pack(side="left", padx=5)
    else:
        # Salva modifiche abilitato solo se aperta
        save_btn = ctk.CTkButton(btn_frame, text="Salva Modifiche", command=save_project, width=150)
        app.apply_edit_button_style(save_btn)
        save_btn.pack(side="left", padx=5)
        if is_closed:
            save_btn.configure(state="disabled")

        delete_btn = ctk.CTkButton(btn_frame, text="🗑️ Elimina Commessa", command=delete_project, width=150)
        app.apply_delete_button_style(delete_btn)
        delete_btn.pack(side="left", padx=5)
        if is_closed:
            delete_btn.configure(state="disabled")

        # Definisco le funzioni close/open DOPO aver creato i pulsanti
        def close_project_action():
            try:
                project_id_to_close = project["id"]
                app.db.close_project(project_id_to_close)
                messagebox.showinfo("Gestione Commesse", "Commessa chiusa con successo.")

                # Aggiorna pulsanti senza disabilitare i campi
                save_btn.configure(state="disabled")
                delete_btn.configure(state="disabled")
                close_btn.configure(state="disabled")
                open_btn.configure(state="normal")

                app.refresh_master_data()
                app.refresh_projects_tree()
                if hasattr(app, "refresh_control_panel"):
                    app.refresh_control_panel()
            except Exception as exc:
                messagebox.showerror("Gestione Commesse", f"Errore: {exc}")

        def open_project_action():
            try:
                project_id_to_open = project["id"]
                app.db.open_project(project_id_to_open)
                messagebox.showinfo("Gestione Commesse", "Commessa riaperta con successo.")

                # Aggiorna pulsanti senza abilitare i campi
                save_btn.configure(state="normal")
                delete_btn.configure(state="normal")
                close_btn.configure(state="normal")
                open_btn.configure(state="disabled")

                app.refresh_master_data()
                app.refresh_projects_tree()
                if hasattr(app, "refresh_control_panel"):
                    app.refresh_control_panel()
            except Exception as exc:
                messagebox.showerror("Gestione Commesse", f"Errore: {exc}")

        # Pulsanti Chiudi/Apri: abilita solo il relativo
        close_btn = ctk.CTkButton(btn_frame, text="🔒 Chiudi", command=close_project_action, width=100)
        close_btn.pack(side="left", padx=5)
        if is_closed:
            close_btn.configure(state="disabled")

        open_btn = ctk.CTkButton(btn_frame, text="🔓 Apri", command=open_project_action, width=100)
        open_btn.pack(side="left", padx=5)
        if not is_closed:
            open_btn.configure(state="disabled")

    ctk.CTkButton(btn_frame, text="Annulla", command=popup.destroy, width=100).pack(side="left", padx=5)
