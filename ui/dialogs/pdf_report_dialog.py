from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from pdf_reports import PDFReportGenerator


def show_pdf_report_dialog(app) -> None:
    """Apre finestra di dialogo per configurare e generare report PDF."""
    dialog = ctk.CTkToplevel(app)
    dialog.title("Genera Report PDF")
    dialog.geometry("560x680")
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    pad = {"padx": 12, "pady": 6}

    # ── titolo ──────────────────────────────────────────────────────
    ctk.CTkLabel(
        dialog, text="Generazione Report PDF",
        font=ctk.CTkFont(size=18, weight="bold"),
    ).pack(pady=(16, 8))

    # ── frame selezione cliente / commessa / attività ────────────────
    sel_frame = ctk.CTkFrame(dialog)
    sel_frame.pack(fill="x", **pad)

    ctk.CTkLabel(sel_frame, text="Filtri", font=ctk.CTkFont(size=13, weight="bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 4)
    )

    def _lbl(text, row):
        ctk.CTkLabel(sel_frame, text=text, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(10, 4), pady=3
        )

    _lbl("Cliente:", 1)
    _lbl("Commessa:", 2)
    _lbl("Attività:", 3)

    # carica dati base
    all_clients = app.db.list_clients()
    all_projects = app.db.list_projects()
    all_activities = app.db.list_activities()

    client_options = ["Tutti i clienti"] + [f"{c['id']} - {c['name']}" for c in all_clients]
    project_options = ["Tutte le commesse"] + [f"{p['id']} - {p['client_name']} / {p['name']}" for p in all_projects]
    activity_options = ["Tutte le attività"] + [f"{a['id']} - {a['name']}" for a in all_activities]

    client_var = ctk.StringVar(value=client_options[0])
    project_var = ctk.StringVar(value=project_options[0])
    activity_var = ctk.StringVar(value=activity_options[0])

    client_cb = ctk.CTkComboBox(sel_frame, variable=client_var, values=client_options, width=380, state="readonly")
    client_cb.grid(row=1, column=1, sticky="w", padx=(4, 10), pady=3)

    project_cb = ctk.CTkComboBox(sel_frame, variable=project_var, values=project_options, width=380, state="readonly")
    project_cb.grid(row=2, column=1, sticky="w", padx=(4, 10), pady=3)

    activity_cb = ctk.CTkComboBox(sel_frame, variable=activity_var, values=activity_options, width=380, state="readonly")
    activity_cb.grid(row=3, column=1, sticky="w", padx=(4, 10), pady=(3, 10))

    # cascade: cambio cliente → aggiorna commesse
    def on_client_change(*_):
        cid = app._id_from_option(client_var.get())
        if cid:
            projs = app.db.list_projects(client_id=cid)
            opts = ["Tutte le commesse"] + [
                f"{p['id']} - {p['client_name']} / {p['name']}" for p in projs
            ]
        else:
            opts = ["Tutte le commesse"] + [
                f"{p['id']} - {p['client_name']} / {p['name']}" for p in all_projects
            ]
        project_cb.configure(values=opts)
        project_var.set(opts[0])
        on_project_change()

    # cascade: cambio commessa → aggiorna attività
    def on_project_change(*_):
        pid = app._id_from_option(project_var.get())
        if pid:
            acts = app.db.list_activities(project_id=pid)
            opts = ["Tutte le attività"] + [f"{a['id']} - {a['name']}" for a in acts]
        else:
            # filtra per cliente se selezionato
            cid = app._id_from_option(client_var.get())
            if cid:
                projs_of_client = app.db.list_projects(client_id=cid)
                pid_list = [p["id"] for p in projs_of_client]
                acts = [a for a in all_activities if any(True for p in pid_list if app.db.list_activities(project_id=p))]
                # semplice: rimostra tutte
            acts = all_activities
            opts = ["Tutte le attività"] + [f"{a['id']} - {a['name']}" for a in acts]
        activity_cb.configure(values=opts)
        activity_var.set(opts[0])

    client_var.trace_add("write", on_client_change)
    project_var.trace_add("write", on_project_change)

    # ── frame utente ─────────────────────────────────────────────────
    usr_frame = ctk.CTkFrame(dialog)
    usr_frame.pack(fill="x", **pad)

    ctk.CTkLabel(usr_frame, text="Utente", font=ctk.CTkFont(size=13, weight="bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 4)
    )
    ctk.CTkLabel(usr_frame, text="Utente:", anchor="w").grid(
        row=1, column=0, sticky="w", padx=(10, 4), pady=(3, 10)
    )
    all_users = app.db.list_users(include_inactive=False)
    user_options = ["Tutti gli utenti"] + [f"{u['id']} - {u['full_name']}" for u in all_users]
    user_var = ctk.StringVar(value=user_options[0])
    ctk.CTkComboBox(usr_frame, variable=user_var, values=user_options, width=380, state="readonly").grid(
        row=1, column=1, sticky="w", padx=(4, 10), pady=(3, 10)
    )

    # ── frame periodo (opzionale) ─────────────────────────────────────
    per_frame = ctk.CTkFrame(dialog)
    per_frame.pack(fill="x", **pad)

    ctk.CTkLabel(per_frame, text="Periodo (opzionale)", font=ctk.CTkFont(size=13, weight="bold")).grid(
        row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(8, 4)
    )
    ctk.CTkLabel(per_frame, text="Da:", anchor="w").grid(row=1, column=0, sticky="w", padx=(10, 4), pady=(3, 10))
    start_entry = ctk.CTkEntry(per_frame, placeholder_text="YYYY-MM-DD", width=130)
    start_entry.grid(row=1, column=1, sticky="w", padx=4, pady=(3, 10))
    ctk.CTkLabel(per_frame, text="A:", anchor="w").grid(row=1, column=2, sticky="w", padx=(10, 4), pady=(3, 10))
    end_entry = ctk.CTkEntry(per_frame, placeholder_text="YYYY-MM-DD", width=130)
    end_entry.grid(row=1, column=3, sticky="w", padx=4, pady=(3, 10))

    # ── frame tipo report ─────────────────────────────────────────────
    type_frame = ctk.CTkFrame(dialog)
    type_frame.pack(fill="x", **pad)

    ctk.CTkLabel(type_frame, text="Tipo Report", font=ctk.CTkFont(size=13, weight="bold")).pack(
        anchor="w", padx=10, pady=(8, 4)
    )
    mode_var = ctk.StringVar(value="sintetica")
    radio_row = ctk.CTkFrame(type_frame, fg_color="transparent")
    radio_row.pack(anchor="w", padx=10, pady=(0, 10))
    ctk.CTkRadioButton(radio_row, text="Sintetica", variable=mode_var, value="sintetica").pack(side="left", padx=(0, 24))
    ctk.CTkRadioButton(radio_row, text="Dettagliata", variable=mode_var, value="dettagliata").pack(side="left", padx=(0, 24))
    ctk.CTkRadioButton(radio_row, text="Gerarchica", variable=mode_var, value="gerarchica").pack(side="left")

    # ── pulsanti ─────────────────────────────────────────────────────
    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(fill="x", padx=12, pady=(8, 16))

    def generate_pdf():
        try:
            client_id = app._id_from_option(client_var.get())
            project_id = app._id_from_option(project_var.get())
            activity_id = app._id_from_option(activity_var.get())
            user_id = app._id_from_option(user_var.get())
            start_date = start_entry.get().strip() or None
            end_date = end_entry.get().strip() or None
            mode = mode_var.get()

            # Costruisci sottotitolo descrittivo
            parts = []
            if client_id:
                parts.append(client_var.get().split(" - ", 1)[-1] if " - " in client_var.get() else client_var.get())
            if project_id:
                raw = project_var.get().split(" - ", 1)[-1] if " - " in project_var.get() else project_var.get()
                parts.append(raw.split(" / ")[-1] if " / " in raw else raw)
            if activity_id:
                parts.append(activity_var.get().split(" - ", 1)[-1] if " - " in activity_var.get() else activity_var.get())
            if user_id:
                parts.append("Utente: " + (user_var.get().split(" - ", 1)[-1] if " - " in user_var.get() else user_var.get()))
            if start_date and end_date:
                parts.append(f"Dal {start_date} al {end_date}")

            subtitle = "  ›  ".join(parts) if parts else "Tutti i dati"
            title_mode = "Dettagliato" if mode == "dettagliata" else ("Gerarchico" if mode == "gerarchica" else "Sintetico")
            title = f"Report {title_mode}"

            data = app.db.get_report_filtered_data(
                client_id=client_id,
                project_id=project_id,
                activity_id=activity_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            if not data["timesheets"]:
                messagebox.showwarning("Nessun dato", "Nessun inserimento trovato con i filtri selezionati.")
                return

            generator = PDFReportGenerator()
            if mode == "gerarchica":
                output_path = generator.generate_hierarchical_report(
                    data=data,
                    title=title,
                    subtitle=subtitle,
                )
            else:
                output_path = generator.generate_filtered_report(
                    data=data,
                    mode=mode,
                    title=title,
                    subtitle=subtitle,
                )

            messagebox.showinfo(
                "Report Generato",
                f"PDF generato:\n{output_path.name}\n\nCartella: {output_path.parent}",
            )
            dialog.destroy()

        except Exception as exc:
            messagebox.showerror("Errore", f"Errore durante la generazione del report:\n{str(exc)}")

    ctk.CTkButton(
        btn_frame, text="Genera PDF", command=generate_pdf,
        width=200, height=40, font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_frame, text="Annulla", command=dialog.destroy,
        width=100, height=40,
    ).pack(side="left")

