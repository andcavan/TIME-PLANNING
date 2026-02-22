from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from db import AUTO_BACKUP_INTERVAL_MINUTES, Database
from style import ui_style as mystyle
from style.ui_ttk import configure_treeview_style
from pdf_reports import PDFReportGenerator

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()


class TimesheetApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.backup_job_id: str | None = None
        self.current_user: dict | None = None
        self.selected_date = date.today()
        self.is_dark_mode = True

        self.title(f"APP Timesheet v{APP_VERSION}")
        self.geometry("1360x860")
        self.minsize(1200, 760)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Applica MyStyle
        self.palette = mystyle.apply_style(dark=self.is_dark_mode)
        configure_treeview_style(self, self.palette)

        self.build_login_view()
        self._backup_now_and_schedule()

    @property
    def is_admin(self) -> bool:
        return bool(self.current_user and self.current_user["role"] == "admin")

    def toggle_theme(self) -> None:
        """Cambia tra modalità dark e light."""
        self.is_dark_mode = not self.is_dark_mode
        self.palette = mystyle.apply_style(dark=self.is_dark_mode)
        configure_treeview_style(self, self.palette)
        
        # Rigenera la vista corrente
        if self.current_user:
            self.build_main_view()
        else:
            self.build_login_view()

    @staticmethod
    def _entity_option(entity_id: int, name: str) -> str:
        return f"{entity_id} - {name}"

    @staticmethod
    def _project_option(row: dict) -> str:
        return f"{row['id']} - {row['client_name']} / {row['name']}"

    @staticmethod
    def _activity_option(row: dict) -> str:
        project_name = row.get("project_name", "")
        prefix = f"{project_name} / " if project_name else ""
        return f"{row['id']} - {prefix}{row['name']}"

    @staticmethod
    def _id_from_option(value: str) -> int | None:
        if not value:
            return None
        try:
            return int(value.split("-", 1)[0].strip())
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _to_float(value: str, field_name: str) -> float:
        try:
            parsed = float(value.replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"{field_name}: valore non valido.") from exc
        if parsed < 0:
            raise ValueError(f"{field_name}: valore non puo essere negativo.")
        return parsed

    def _set_combo_values(self, combo: ctk.CTkComboBox, values: list[str]) -> None:
        safe_values = values or [""]
        current_value = combo.get()
        combo.configure(values=safe_values)
        combo.set(current_value if current_value in safe_values else safe_values[0])

    def _get_paned_bg(self) -> str:
        """Restituisce il colore di sfondo appropriato per il PanedWindow in base al tema."""
        return "#2b2b2b" if self.is_dark_mode else "#dbdbdb"

    def _backup_now_and_schedule(self) -> None:
        try:
            self.db.create_backup()
        except Exception as exc:
            print(f"[backup] Errore creazione backup: {exc}")
        self._schedule_next_backup()

    def _schedule_next_backup(self) -> None:
        interval_ms = AUTO_BACKUP_INTERVAL_MINUTES * 60 * 1000
        self.backup_job_id = self.after(interval_ms, self._run_periodic_backup)

    def _run_periodic_backup(self) -> None:
        self.backup_job_id = None
        try:
            self.db.create_backup()
        except Exception as exc:
            print(f"[backup] Errore backup periodico: {exc}")
        finally:
            if self.winfo_exists():
                self._schedule_next_backup()

    def build_login_view(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        self.login_frame = ctk.CTkFrame(self, corner_radius=12)
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            self.login_frame,
            text=f"APP Timesheet v{APP_VERSION}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 16), sticky="w")

        ctk.CTkLabel(self.login_frame, text="Username").grid(row=1, column=0, padx=24, pady=6, sticky="w")
        self.login_username_entry = ctk.CTkEntry(self.login_frame, width=220)
        self.login_username_entry.grid(row=1, column=1, padx=(0, 24), pady=6, sticky="ew")
        self.login_username_entry.insert(0, "admin")

        ctk.CTkLabel(self.login_frame, text="Password").grid(row=2, column=0, padx=24, pady=6, sticky="w")
        self.login_password_entry = ctk.CTkEntry(self.login_frame, width=220, show="*")
        self.login_password_entry.grid(row=2, column=1, padx=(0, 24), pady=6, sticky="ew")
        self.login_password_entry.insert(0, "admin")

        ctk.CTkButton(self.login_frame, text="Accedi", command=self.login).grid(
            row=3, column=0, columnspan=2, padx=24, pady=(14, 20), sticky="ew"
        )

        self.bind("<Return>", self.login)
        self.login_username_entry.focus_set()

    def setup_date_entry_helpers(self, entry_widget: ctk.CTkEntry) -> None:
        """Configura helper per campo data: inserisce '/' automaticamente e calendario al doppio click."""
        def on_focus_in(event):
            current = entry_widget.get().strip()
            if not current:
                entry_widget.insert(0, "  /  /    ")
                entry_widget.icursor(0)
        
        def on_double_click(event):
            self.open_date_picker(entry_widget)
        
        entry_widget.bind("<FocusIn>", on_focus_in)
        entry_widget.bind("<Double-Button-1>", on_double_click)
    
    def open_date_picker(self, entry_widget: ctk.CTkEntry) -> None:
        """Apre un calendario popup per selezionare una data."""
        picker = tk.Toplevel(self)
        picker.title("Seleziona data")
        picker.geometry("320x280")
        picker.resizable(False, False)
        picker.transient(self)
        picker.grab_set()
        
        # Posiziona al centro della finestra principale
        picker.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (picker.winfo_width() // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (picker.winfo_height() // 2)
        picker.geometry(f"+{x}+{y}")
        
        # Determina data iniziale dal campo o oggi
        try:
            current_text = entry_widget.get().strip().replace(" ", "")
            if current_text and len(current_text) == 10:
                picker_date = datetime.strptime(current_text, "%d/%m/%Y").date()
            else:
                picker_date = date.today()
        except:
            picker_date = date.today()
        
        selected_date = tk.StringVar(value=picker_date.isoformat())
        
        # Header con mese/anno
        header = tk.Frame(picker)
        header.pack(fill="x", padx=10, pady=10)
        
        tk.Button(header, text="◄", width=3, command=lambda: change_month(-1)).pack(side="left")
        
        month_label = tk.Label(header, text="", font=("Arial", 12, "bold"))
        month_label.pack(side="left", expand=True)
        
        tk.Button(header, text="►", width=3, command=lambda: change_month(1)).pack(side="right")
        
        # Frame per il calendario
        cal_frame = tk.Frame(picker)
        cal_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Giorni della settimana
        days = ["Lu", "Ma", "Me", "Gi", "Ve", "Sa", "Do"]
        for idx, day in enumerate(days):
            tk.Label(cal_frame, text=day, font=("Arial", 9, "bold"), width=4).grid(row=0, column=idx, pady=2)
        
        def render_calendar():
            # Pulisci il calendario
            for widget in cal_frame.grid_slaves():
                if int(widget.grid_info()["row"]) > 0:
                    widget.destroy()
            
            current = datetime.fromisoformat(selected_date.get()).date()
            month_label.config(text=f"{calendar.month_name[current.month]} {current.year}")
            
            cal = calendar.monthcalendar(current.year, current.month)
            
            for week_num, week in enumerate(cal, start=1):
                for day_num, day in enumerate(week):
                    if day == 0:
                        tk.Label(cal_frame, text="", width=4).grid(row=week_num, column=day_num)
                    else:
                        day_date = date(current.year, current.month, day)
                        is_today = day_date == date.today()
                        is_selected = day_date == current
                        
                        bg = "#4a90e2" if is_selected else "#e0e0e0" if is_today else "white"
                        fg = "white" if is_selected else "black"
                        
                        btn = tk.Button(
                            cal_frame, 
                            text=str(day), 
                            width=4, 
                            bg=bg, 
                            fg=fg,
                            command=lambda d=day_date: select_date(d)
                        )
                        btn.grid(row=week_num, column=day_num, padx=1, pady=1)
        
        def change_month(delta):
            current = datetime.fromisoformat(selected_date.get()).date()
            if delta > 0:
                if current.month == 12:
                    new_date = date(current.year + 1, 1, 1)
                else:
                    new_date = date(current.year, current.month + 1, 1)
            else:
                if current.month == 1:
                    new_date = date(current.year - 1, 12, 1)
                else:
                    new_date = date(current.year, current.month - 1, 1)
            selected_date.set(new_date.isoformat())
            render_calendar()
        
        def select_date(day_date):
            selected_date.set(day_date.isoformat())
            render_calendar()
        
        def confirm():
            current = datetime.fromisoformat(selected_date.get()).date()
            entry_widget.delete(0, "end")
            entry_widget.insert(0, current.strftime("%d/%m/%Y"))
            picker.destroy()
        
        render_calendar()
        
        # Pulsanti
        btn_frame = tk.Frame(picker)
        btn_frame.pack(fill="x", padx=10, pady=10)
        tk.Button(btn_frame, text="OK", width=10, command=confirm).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Annulla", width=10, command=picker.destroy).pack(side="right")

    def login(self, _event: object | None = None) -> None:
        username = self.login_username_entry.get().strip()
        password = self.login_password_entry.get()
        user = self.db.authenticate(username, password)
        if not user:
            messagebox.showerror("Accesso", "Credenziali non valide o utente disattivato.")
            return

        self.current_user = user
        self.unbind("<Return>")
        self.build_main_view()

    def build_main_view(self) -> None:
        for child in self.winfo_children():
            child.destroy()

        topbar = ctk.CTkFrame(self, corner_radius=0)
        topbar.pack(fill="x")

        ctk.CTkLabel(
            topbar,
            text=f"APP Timesheet v{APP_VERSION}",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(side="left", padx=14, pady=8)

        user_text = f"{self.current_user['username']} ({self.current_user['role']})"
        ctk.CTkLabel(topbar, text=f"Utente: {user_text}").pack(side="left", padx=10)
        
        # Pulsante cambio tema
        theme_text = "☀️ Light" if self.is_dark_mode else "🌙 Dark"
        ctk.CTkButton(
            topbar, 
            text=theme_text, 
            width=100, 
            command=self.toggle_theme
        ).pack(side="right", padx=6, pady=8)
        
        ctk.CTkButton(topbar, text="Logout", width=90, command=self.logout).pack(side="right", padx=8, pady=8)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        # Aggiungi tab in base ai permessi utente (admin vede sempre tutto)
        if self.is_admin or self.current_user.get("tab_calendar", 1):
            self.tab_calendar = self.tabview.add("Calendario Ore")
        else:
            self.tab_calendar = None
            
        if self.is_admin or self.current_user.get("tab_master", 1):
            self.tab_master = self.tabview.add("Gestione Commesse")
        else:
            self.tab_master = None
            
        if self.is_admin or self.current_user.get("tab_control", 1):
            self.tab_control = self.tabview.add("Controllo Programmazione")
        else:
            self.tab_control = None
            
        if self.is_admin:
            self.tab_users = self.tabview.add("Utenti")
        else:
            self.tab_users = None

        # Build solo le tab abilitate
        if self.tab_calendar:
            self.build_calendar_tab()
        if self.tab_master:
            self.build_project_management_tab()
        if self.tab_control:
            self.build_control_tab()
        if self.tab_users:
            self.build_users_tab()

        # Refresh solo le tab esistenti
        if self.tab_users:
            self.refresh_users_data()
        # refresh_master_data popola anche i combo del calendario, quindi chiamalo se calendario o gestione commesse sono attive
        if self.tab_master or self.tab_calendar:
            self.refresh_master_data()
        if self.tab_calendar:
            self.render_calendar()
        if self.tab_control:
            self.refresh_control_panel()

    def logout(self) -> None:
        self.current_user = None
        self.selected_date = date.today()
        self.build_login_view()

    def build_calendar_tab(self) -> None:
        self.tab_calendar.rowconfigure(1, weight=1)
        self.tab_calendar.columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self.tab_calendar)
        header.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(header, text="Mese").pack(side="left", padx=(12, 6), pady=10)
        self.cal_month_combo = ctk.CTkComboBox(
            header, width=90, values=[f"{i:02d}" for i in range(1, 13)], state="readonly"
        )
        self.cal_month_combo.pack(side="left", padx=6, pady=10)
        self.cal_month_combo.set(f"{self.selected_date.month:02d}")

        ctk.CTkLabel(header, text="Anno").pack(side="left", padx=(10, 6), pady=10)
        years = [str(self.selected_date.year + offset) for offset in range(-3, 4)]
        self.cal_year_combo = ctk.CTkComboBox(header, width=100, values=years, state="readonly")
        self.cal_year_combo.pack(side="left", padx=6, pady=10)
        self.cal_year_combo.set(str(self.selected_date.year))

        ctk.CTkButton(header, text="Mostra", width=90, command=self.render_calendar).pack(side="left", padx=12, pady=10)
        
        ctk.CTkButton(header, text="◄", width=35, command=self.goto_prev_month).pack(side="left", padx=2, pady=10)
        ctk.CTkButton(header, text="Oggi", width=70, command=self.goto_today).pack(side="left", padx=2, pady=10)
        ctk.CTkButton(header, text="►", width=35, command=self.goto_next_month).pack(side="left", padx=2, pady=10)

        # PanedWindow per ridimensionamento interattivo tra calendario e form
        paned = tk.PanedWindow(self.tab_calendar, orient=tk.HORIZONTAL, sashwidth=8, bg=self._get_paned_bg())
        paned.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")

        # Frame sinistro: calendario
        left_container = ctk.CTkFrame(paned)
        paned.add(left_container, minsize=350, stretch="always")
        
        self.calendar_frame = ctk.CTkFrame(left_container)
        self.calendar_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Frame destro: form + lista
        right_container = ctk.CTkFrame(paned)
        paned.add(right_container, minsize=350, stretch="always")
        
        right_panel = ctk.CTkFrame(right_container)
        right_panel.pack(fill="both", expand=True, padx=8, pady=8)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(right_panel)
        form.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        form.grid_columnconfigure(1, weight=1)

        self.selected_date_var = tk.StringVar(value="")
        ctk.CTkLabel(form, textvariable=self.selected_date_var, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=10, pady=(8, 10), sticky="w"
        )

        ctk.CTkLabel(form, text="Cliente").grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.ts_client_combo = ctk.CTkComboBox(
            form, state="readonly", command=self.on_timesheet_client_change, width=260, values=[""]
        )
        self.ts_client_combo.grid(row=1, column=1, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Commessa").grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.ts_project_combo = ctk.CTkComboBox(
            form, state="readonly", command=self.on_timesheet_project_change, width=260, values=[""]
        )
        self.ts_project_combo.grid(row=2, column=1, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Attivita").grid(row=3, column=0, padx=10, pady=4, sticky="w")
        self.ts_activity_combo = ctk.CTkComboBox(form, state="readonly", width=260, values=[""])
        self.ts_activity_combo.grid(row=3, column=1, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Ore").grid(row=4, column=0, padx=10, pady=4, sticky="w")
        self.ts_hours_entry = ctk.CTkEntry(form)
        self.ts_hours_entry.grid(row=4, column=1, padx=10, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Note").grid(row=5, column=0, padx=10, pady=4, sticky="nw")
        self.ts_note_text = ctk.CTkTextbox(form, height=64)
        self.ts_note_text.grid(row=5, column=1, padx=10, pady=4, sticky="ew")

        button_row = ctk.CTkFrame(form, fg_color="transparent")
        button_row.grid(row=6, column=0, columnspan=2, padx=10, pady=(6, 10), sticky="ew")
        ctk.CTkButton(button_row, text="Salva ore", command=self.save_timesheet_entry).pack(side="left", padx=(0, 8))
        ctk.CTkButton(button_row, text="Elimina selezionata", command=self.delete_selected_timesheet).pack(side="left")

        self.day_total_var = tk.StringVar(value="Totale giornata: 0.00 h | 0.00 EUR")
        ctk.CTkLabel(form, textvariable=self.day_total_var).grid(
            row=7, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="w"
        )

        list_frame = ctk.CTkFrame(right_panel)
        list_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        if self.is_admin:
            columns = ("user", "client", "project", "activity", "hours", "rate", "cost", "note")
        else:
            columns = ("user", "client", "project", "activity", "hours", "note")
        
        self.ts_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.ts_tree.heading("user", text="Utente")
        self.ts_tree.heading("client", text="Cliente")
        self.ts_tree.heading("project", text="Commessa")
        self.ts_tree.heading("activity", text="Attivita")
        self.ts_tree.heading("hours", text="Ore")
        self.ts_tree.heading("note", text="Note")
        
        if self.is_admin:
            self.ts_tree.heading("rate", text="Costo h")
            self.ts_tree.heading("cost", text="Costo")
            self.ts_tree.column("user", width=90, anchor="w")
            self.ts_tree.column("client", width=120, anchor="w")
            self.ts_tree.column("project", width=130, anchor="w")
            self.ts_tree.column("activity", width=130, anchor="w")
            self.ts_tree.column("hours", width=70, anchor="e")
            self.ts_tree.column("rate", width=80, anchor="e")
            self.ts_tree.column("cost", width=90, anchor="e")
            self.ts_tree.column("note", width=240, anchor="w")
        else:
            self.ts_tree.column("user", width=100, anchor="w")
            self.ts_tree.column("client", width=140, anchor="w")
            self.ts_tree.column("project", width=160, anchor="w")
            self.ts_tree.column("activity", width=160, anchor="w")
            self.ts_tree.column("hours", width=80, anchor="e")
            self.ts_tree.column("note", width=300, anchor="w")
        
        self.ts_tree.grid(row=0, column=0, sticky="nsew")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.ts_tree.yview)
        self.ts_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

    def goto_prev_month(self) -> None:
        """Vai al mese precedente."""
        year = int(self.cal_year_combo.get())
        month = int(self.cal_month_combo.get())
        
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1
        
        self.cal_month_combo.set(f"{month:02d}")
        self.cal_year_combo.set(str(year))
        self.render_calendar()
    
    def goto_today(self) -> None:
        """Vai al mese corrente (oggi)."""
        today = date.today()
        self.cal_month_combo.set(f"{today.month:02d}")
        self.cal_year_combo.set(str(today.year))
        self.selected_date = today
        self.render_calendar()
    
    def goto_next_month(self) -> None:
        """Vai al mese successivo."""
        year = int(self.cal_year_combo.get())
        month = int(self.cal_month_combo.get())
        
        if month == 12:
            month = 1
            year += 1
        else:
            month += 1
        
        self.cal_month_combo.set(f"{month:02d}")
        self.cal_year_combo.set(str(year))
        self.render_calendar()

    def render_calendar(self) -> None:
        for child in self.calendar_frame.winfo_children():
            child.destroy()

        year = int(self.cal_year_combo.get())
        month = int(self.cal_month_combo.get())
        max_day = calendar.monthrange(year, month)[1]
        selected_day = min(self.selected_date.day, max_day)
        self.selected_date = date(year, month, selected_day)

        # Recupera il sommario delle ore per il mese
        user_id = int(self.current_user["id"]) if self.current_user else None
        hours_summary = self.db.get_month_hours_summary(year, month, user_id)

        weekdays = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        for col, name in enumerate(weekdays):
            label = ctk.CTkLabel(self.calendar_frame, text=name, font=ctk.CTkFont(weight="bold"))
            label.grid(row=0, column=col, padx=4, pady=(8, 4), sticky="nsew")

        month_matrix = calendar.monthcalendar(year, month)
        for week_index, week in enumerate(month_matrix, start=1):
            # Configura righe uniformi per ogni settimana
            self.calendar_frame.grid_rowconfigure(week_index, weight=1, uniform="calweek")
            for col, day_num in enumerate(week):
                # Configura colonne uniformi
                self.calendar_frame.grid_columnconfigure(col, weight=1, uniform="calday")
                if day_num == 0:
                    ctk.CTkLabel(self.calendar_frame, text="").grid(row=week_index, column=col, padx=4, pady=4)
                    continue
                
                is_selected = day_num == self.selected_date.day
                hours = hours_summary.get(day_num, 0)
                has_hours = hours > 0
                is_weekend = col in (5, 6)  # Sabato=5, Domenica=6
                
                # Crea un frame per ogni giorno con colori della palette
                if is_selected:
                    frame_color = self.palette.accent
                elif is_weekend:
                    frame_color = "#FF8C00"  # Arancione per weekend
                elif has_hours:
                    frame_color = self.palette.accent_2
                else:
                    frame_color = self.palette.panel_2
                
                day_frame = ctk.CTkFrame(
                    self.calendar_frame,
                    fg_color=frame_color,
                    corner_radius=6
                )
                day_frame.grid(row=week_index, column=col, padx=4, pady=4, sticky="nsew")
                
                # Pulsante con il numero del giorno
                day_btn = ctk.CTkButton(
                    day_frame,
                    text=str(day_num),
                    width=44,
                    height=28,
                    fg_color="transparent",
                    hover_color=self.palette.selection_bg,
                    font=ctk.CTkFont(size=13, weight="bold" if is_selected else "normal"),
                    text_color=self.palette.fg,
                    command=lambda d=day_num: self.select_calendar_day(d),
                )
                day_btn.pack(fill="x", padx=2, pady=(2, 0))
                
                # Mostra ore se presenti
                if has_hours:
                    hours_label = ctk.CTkLabel(
                        day_frame,
                        text=f"{hours:.1f}h",
                        font=ctk.CTkFont(size=10),
                        fg_color=self.palette.bg if is_selected else self.palette.panel,
                        corner_radius=4,
                        text_color=self.palette.fg
                    )
                    hours_label.pack(fill="x", padx=4, pady=(2, 4))

        self.selected_date_var.set(f"Data selezionata: {self.selected_date.isoformat()}")
        self.refresh_day_entries()

    def select_calendar_day(self, day_num: int) -> None:
        year = int(self.cal_year_combo.get())
        month = int(self.cal_month_combo.get())
        self.selected_date = date(year, month, day_num)
        self.render_calendar()

    def _selected_timesheet_user_id(self) -> int:
        """Restituisce sempre l'ID dell'utente corrente loggato."""
        return int(self.current_user["id"])

    def on_timesheet_client_change(self, _value: str) -> None:
        client_id = self._id_from_option(self.ts_client_combo.get())
        
        # Carica solo commesse del cliente selezionato (filtrando per utente se non admin)
        if client_id:
            user_id = None if self.is_admin else int(self.current_user["id"])
            projects = self.db.list_projects(client_id, only_with_open_schedules=True, user_id=user_id)
            values = [""] + [self._project_option(row) for row in projects]  # "" come prima opzione
            self._set_combo_values(self.ts_project_combo, values)
            self.ts_project_combo.set("")  # Forza selezione vuota
        else:
            self._set_combo_values(self.ts_project_combo, [""])
        
        # Pulisci attività
        self._set_combo_values(self.ts_activity_combo, [""])

    def on_timesheet_project_change(self, _value: str) -> None:
        project_id = self._id_from_option(self.ts_project_combo.get())
        
        # Carica solo attività della commessa selezionata
        if project_id:
            activities = self.db.list_activities(project_id, only_with_open_schedules=True)
            values = [""] + [self._activity_option(row) for row in activities]  # "" come prima opzione
            self._set_combo_values(self.ts_activity_combo, values)
            self.ts_activity_combo.set("")  # Forza selezione vuota
        else:
            self._set_combo_values(self.ts_activity_combo, [""])

    def save_timesheet_entry(self) -> None:
        try:
            user_id = self._selected_timesheet_user_id()
            client_id = self._id_from_option(self.ts_client_combo.get())
            project_id = self._id_from_option(self.ts_project_combo.get())
            activity_id = self._id_from_option(self.ts_activity_combo.get())
            if not (client_id and project_id and activity_id):
                raise ValueError("Seleziona cliente, commessa e attivita.")
            
            # Verifica permessi: utente non-admin deve essere assegnato alla commessa
            if not self.is_admin:
                if not self.db.user_can_access_activity(user_id, project_id, activity_id):
                    raise ValueError("Non hai i permessi per inserire ore su questa attività.")

            hours = self._to_float(self.ts_hours_entry.get().strip(), "Ore")
            if hours <= 0:
                raise ValueError("Ore: il valore deve essere > 0.")

            note = self.ts_note_text.get("1.0", "end").strip()
            self.db.add_timesheet(
                user_id=user_id,
                work_date=self.selected_date.isoformat(),
                client_id=client_id,
                project_id=project_id,
                activity_id=activity_id,
                hours=hours,
                note=note,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Ore giornaliere", str(exc))
            return

        self.ts_hours_entry.delete(0, "end")
        self.ts_note_text.delete("1.0", "end")
        self.refresh_day_entries()
        self.refresh_control_panel()
        messagebox.showinfo("Ore giornaliere", "Inserimento completato.")

    def refresh_day_entries(self) -> None:
        if not hasattr(self, "ts_tree"):
            return

        for item in self.ts_tree.get_children():
            self.ts_tree.delete(item)

        try:
            user_id = self._selected_timesheet_user_id()
        except ValueError:
            user_id = int(self.current_user["id"])

        rows = self.db.list_timesheets_for_day(self.selected_date.isoformat(), user_id=user_id)
        total_hours = 0.0
        total_cost = 0.0
        for row in rows:
            total_hours += float(row["hours"])
            total_cost += float(row["cost"])
            
            if self.is_admin:
                values = (
                    row["username"],
                    row["client_name"],
                    row["project_name"],
                    row["activity_name"],
                    f"{row['hours']:.2f}",
                    f"{row['effective_rate']:.2f}",
                    f"{row['cost']:.2f}",
                    row["note"],
                )
            else:
                values = (
                    row["username"],
                    row["client_name"],
                    row["project_name"],
                    row["activity_name"],
                    f"{row['hours']:.2f}",
                    row["note"],
                )
            
            self.ts_tree.insert("", "end", iid=str(row["id"]), values=values)

        if self.is_admin:
            self.day_total_var.set(f"Totale giornata: {total_hours:.2f} h | {total_cost:.2f} EUR")
        else:
            self.day_total_var.set(f"Totale giornata: {total_hours:.2f} h")

    def delete_selected_timesheet(self) -> None:
        selection = self.ts_tree.selection()
        if not selection:
            messagebox.showwarning("Ore giornaliere", "Seleziona una riga da eliminare.")
            return
        if not messagebox.askyesno("Conferma", "Eliminare la voce selezionata?"):
            return

        entry_id = int(selection[0])
        self.db.delete_timesheet(entry_id, int(self.current_user["id"]), self.is_admin)
        self.refresh_day_entries()
        self.refresh_control_panel()

    def build_project_management_tab(self) -> None:
        """Tab unificata per gestione commesse con pianificazione integrata."""
        # Contenitore principale
        main_container = ctk.CTkFrame(self.tab_master)
        main_container.pack(fill="both", expand=True, padx=8, pady=8)
        
        # ========== SEZIONE 1: SELEZIONE CLIENTE E COMMESSA (fissa in alto) ==========
        selection_frame = ctk.CTkFrame(main_container)
        selection_frame.pack(fill="x", pady=(0, 8))
        selection_frame.grid_columnconfigure(1, weight=1)
        selection_frame.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(selection_frame, text="Cliente:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(10, 5), pady=10, sticky="w"
        )
        self.pm_client_combo = ctk.CTkComboBox(
            selection_frame, state="readonly", command=self.on_pm_client_change, values=[""], width=300
        )
        self.pm_client_combo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        ctk.CTkButton(
            selection_frame, text="🔧 Gestione Clienti", width=150, 
            command=self.open_clients_management
        ).grid(row=0, column=2, padx=5, pady=10)
        
        ctk.CTkLabel(selection_frame, text="Commessa:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=3, padx=(20, 5), pady=10, sticky="w"
        )
        self.pm_project_combo = ctk.CTkComboBox(
            selection_frame, state="readonly", command=self.on_pm_project_change, values=[""], width=300
        )
        self.pm_project_combo.grid(row=0, column=4, padx=5, pady=10, sticky="ew")
        
        ctk.CTkButton(
            selection_frame, text="🔧 Gestione Commessa", width=150,
            command=self.open_project_management
        ).grid(row=0, column=5, padx=5, pady=10)

        # PanedWindow principale verticale per aree ridimensionabili
        paned_vertical = ttk.PanedWindow(main_container, orient="vertical")
        paned_vertical.pack(fill="both", expand=True)

        # ========== PANNELLO 1: DATI COMMESSA + PIANIFICAZIONE ==========
        top_panel = tk.Frame(paned_vertical)
        paned_vertical.add(top_panel, weight=0)
        
        # Contenitore con grid per affiancamento fisso (non ridimensionabile)
        data_container = ctk.CTkFrame(top_panel)
        data_container.pack(fill="both", expand=True, padx=4, pady=4)
        data_container.grid_columnconfigure(0, weight=1)
        data_container.grid_columnconfigure(1, weight=1)
        data_container.grid_rowconfigure(0, weight=1)
        
        # Frame sinistra: dati commessa (scrollable)
        left_data = ctk.CTkScrollableFrame(data_container, height=180)
        left_data.grid(row=0, column=0, padx=(0, 2), pady=0, sticky="nsew")
        
        ctk.CTkLabel(left_data, text="Dati Commessa Selezionata", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(2, 1)
        )
        
        # Nome commessa (readonly) - font aumentato
        ctk.CTkLabel(left_data, text="Nome:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(2, 0))
        self.pm_project_name_label = ctk.CTkLabel(
            left_data, text="Nessuna commessa selezionata", font=ctk.CTkFont(size=13, weight="bold")
        )
        self.pm_project_name_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(left_data, text="Cliente:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_project_client_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_project_client_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(left_data, text="Referente cliente:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_client_referente_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_client_referente_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(left_data, text="Telefono:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_client_telefono_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_client_telefono_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(left_data, text="Email:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_client_email_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_client_email_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        if self.is_admin:
            ctk.CTkLabel(left_data, text="Costo orario (€/h):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
            self.pm_project_rate_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
            self.pm_project_rate_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(left_data, text="Note:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_project_notes_label = ctk.CTkLabel(left_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_project_notes_label.pack(anchor="w", padx=10, pady=(0, 2))
        
        # Frame destra: pianificazione commessa (scrollable)
        right_data = ctk.CTkScrollableFrame(data_container, height=180)
        right_data.grid(row=0, column=1, padx=(2, 0), pady=0, sticky="nsew")
        
        ctk.CTkLabel(right_data, text="Pianificazione Commessa", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(2, 1)
        )
        
        # Alert frame per budget
        self.pm_budget_alert_frame = ctk.CTkFrame(right_data, fg_color="transparent")
        self.pm_budget_alert_frame.pack(fill="x", padx=10, pady=1)
        
        ctk.CTkLabel(right_data, text="Periodo:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_project_dates_label = ctk.CTkLabel(right_data, text="Non pianificata", font=ctk.CTkFont(size=12))
        self.pm_project_dates_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(right_data, text="Ore preventivate:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_project_hours_label = ctk.CTkLabel(right_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_project_hours_label.pack(anchor="w", padx=10, pady=(0, 1))
        
        ctk.CTkLabel(right_data, text="Budget (€):", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(1, 0))
        self.pm_project_budget_label = ctk.CTkLabel(right_data, text="--", font=ctk.CTkFont(size=12))
        self.pm_project_budget_label.pack(anchor="w", padx=10, pady=(0, 2))
        
        # Utenti assegnati (solo admin)
        if self.is_admin:
            ctk.CTkLabel(right_data, text="Utenti assegnati:", font=ctk.CTkFont(size=12, weight="bold")).pack(
                anchor="w", padx=10, pady=(8, 2)
            )
            self.pm_users_frame = ctk.CTkFrame(right_data, fg_color="transparent")
            self.pm_users_frame.pack(fill="x", padx=10, pady=(0, 4))
            # I checkbox verranno popolati dinamicamente in on_pm_project_change
            self.pm_user_checkboxes = {}  # {user_id: CTkCheckBox}

        # ========== PANNELLO 2: GESTIONE ATTIVITÀ ==========
        middle_panel = tk.Frame(paned_vertical)
        paned_vertical.add(middle_panel, weight=0)
        
        activity_frame = ctk.CTkFrame(middle_panel)
        activity_frame.pack(fill="both", expand=True, padx=4, pady=4)
        
        ctk.CTkLabel(
            activity_frame, text="Gestione Attività della Commessa", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).grid(row=0, column=0, columnspan=8, padx=10, pady=(8, 4), sticky="w")
        
        ctk.CTkLabel(activity_frame, text="Nome attività:").grid(row=1, column=0, padx=(10, 5), pady=4, sticky="w")
        self.pm_activity_name_entry = ctk.CTkEntry(activity_frame, placeholder_text="Inserisci nome attività", width=200)
        self.pm_activity_name_entry.grid(row=1, column=1, columnspan=2, padx=5, pady=4, sticky="ew")
        
        ctk.CTkLabel(activity_frame, text="Note:").grid(row=1, column=3, padx=(10, 5), pady=4, sticky="w")
        self.pm_activity_notes_entry = ctk.CTkEntry(activity_frame, placeholder_text="Note opzionali", width=200)
        self.pm_activity_notes_entry.grid(row=1, column=4, columnspan=2, padx=5, pady=4, sticky="ew")
        
        if self.is_admin:
            ctk.CTkLabel(activity_frame, text="Costo (€/h):").grid(row=1, column=6, padx=(10, 5), pady=4, sticky="w")
            self.pm_activity_rate_entry = ctk.CTkEntry(activity_frame, placeholder_text="0", width=80)
            self.pm_activity_rate_entry.grid(row=1, column=7, padx=5, pady=4, sticky="w")
        
        # Pianificazione: tutto su una riga compatta
        ctk.CTkLabel(
            activity_frame, text="Pianificazione:", 
            font=ctk.CTkFont(size=11, weight="bold")
        ).grid(row=2, column=0, padx=(10, 5), pady=(8, 4), sticky="w")
        
        ctk.CTkLabel(activity_frame, text="Da:").grid(row=2, column=1, padx=(5, 2), pady=(8, 4), sticky="e")
        self.pm_activity_start_entry = ctk.CTkEntry(activity_frame, placeholder_text="gg/mm/aaaa", width=90)
        self.pm_activity_start_entry.grid(row=2, column=2, padx=2, pady=(8, 4), sticky="w")
        self.setup_date_entry_helpers(self.pm_activity_start_entry)
        
        ctk.CTkLabel(activity_frame, text="A:").grid(row=2, column=3, padx=(5, 2), pady=(8, 4), sticky="e")
        self.pm_activity_end_entry = ctk.CTkEntry(activity_frame, placeholder_text="gg/mm/aaaa", width=90)
        self.pm_activity_end_entry.grid(row=2, column=4, padx=2, pady=(8, 4), sticky="w")
        self.setup_date_entry_helpers(self.pm_activity_end_entry)
        
        ctk.CTkLabel(activity_frame, text="Ore:").grid(row=2, column=5, padx=(10, 2), pady=(8, 4), sticky="e")
        self.pm_activity_hours_entry = ctk.CTkEntry(activity_frame, placeholder_text="160", width=70)
        self.pm_activity_hours_entry.grid(row=2, column=6, padx=2, pady=(8, 4), sticky="w")
        
        ctk.CTkLabel(activity_frame, text="Budget €:").grid(row=2, column=7, padx=(10, 2), pady=(8, 4), sticky="e")
        self.pm_activity_budget_entry = ctk.CTkEntry(activity_frame, placeholder_text="0", width=80)
        self.pm_activity_budget_entry.grid(row=2, column=8, padx=2, pady=(8, 4), sticky="w")
        
        btn_activity_frame = ctk.CTkFrame(activity_frame, fg_color="transparent")
        btn_activity_frame.grid(row=3, column=0, columnspan=9, padx=10, pady=(8, 10), sticky="ew")
        
        ctk.CTkButton(btn_activity_frame, text="Aggiungi Attività", command=self.pm_add_activity, width=140).pack(
            side="left", padx=(0, 5)
        )
        ctk.CTkButton(btn_activity_frame, text="Modifica Selezionata", command=self.pm_edit_activity, width=140).pack(
            side="left", padx=5
        )
        ctk.CTkButton(btn_activity_frame, text="Elimina Selezionata", command=self.pm_delete_activity, width=140).pack(
            side="left", padx=5
        )
        
        activity_frame.grid_columnconfigure(2, weight=1)
        activity_frame.grid_columnconfigure(4, weight=1)

        # ========== PANNELLO 3: LISTA ATTIVITÀ COMMESSA SELEZIONATA ==========
        bottom_panel = tk.Frame(paned_vertical)
        paned_vertical.add(bottom_panel, weight=1)
        
        tree_frame = ctk.CTkFrame(bottom_panel)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(tree_frame, text="Attività della Commessa Selezionata", 
                    font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 4), sticky="w")

        # Colonne con dati dettagliati
        if self.is_admin:
            columns = ("dates", "planned_hours", "actual_hours", "budget", "actual_cost", "rate")
        else:
            columns = ("dates", "planned_hours", "actual_hours")
        
        self.master_tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings")
        self.master_tree.heading("#0", text="Nome Attività")
        self.master_tree.heading("dates", text="Date (inizio - fine)")
        self.master_tree.heading("planned_hours", text="Ore pianif.")
        self.master_tree.heading("actual_hours", text="Ore effett.")
        
        if self.is_admin:
            self.master_tree.heading("budget", text="Budget €")
            self.master_tree.heading("actual_cost", text="Costo €")
            self.master_tree.heading("rate", text="Tariffa €/h")
            
            self.master_tree.column("#0", width=250, anchor="w")
            self.master_tree.column("dates", width=150, anchor="center")
            self.master_tree.column("planned_hours", width=90, anchor="e")
            self.master_tree.column("actual_hours", width=90, anchor="e")
            self.master_tree.column("budget", width=90, anchor="e")
            self.master_tree.column("actual_cost", width=90, anchor="e")
            self.master_tree.column("rate", width=90, anchor="e")
        else:
            self.master_tree.column("#0", width=350, anchor="w")
            self.master_tree.column("dates", width=180, anchor="center")
            self.master_tree.column("planned_hours", width=110, anchor="e")
            self.master_tree.column("actual_hours", width=110, anchor="e")
        
        self.master_tree.grid(row=1, column=0, sticky="nsew")
        self.master_tree.bind("<<TreeviewSelect>>", self.on_pm_tree_select)

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.master_tree.yview)
        self.master_tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.grid(row=1, column=1, sticky="ns")
        
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.master_tree.xview)
        self.master_tree.configure(xscrollcommand=scroll_x.set)
        scroll_x.grid(row=2, column=0, sticky="ew")
        
        # Variabili per tracciare la commessa selezionata
        self.selected_project_id = None
        self.selected_activity_id = None

    # ========== GESTIONE COMMESSE: Nuove Funzioni ==========
    
    def on_pm_client_change(self, _value: str) -> None:
        """Aggiorna la combo commesse quando cambia il cliente."""
        client_id = self._id_from_option(self.pm_client_combo.get())
        if client_id:
            projects = self.db.list_projects(client_id)
            project_options = [self._project_option(row) for row in projects]
        else:
            project_options = [""]
        
        self._set_combo_values(self.pm_project_combo, project_options)
        self.pm_project_combo.set("")
        self.on_pm_project_change("")
    
    def on_pm_project_change(self, _value: str) -> None:
        """Aggiorna i dati della commessa quando viene selezionata."""
        project_id = self._id_from_option(self.pm_project_combo.get())
        self.selected_project_id = project_id
        
        if not project_id:
            # Nessuna commessa selezionata, pulisci i dati
            self.pm_project_name_label.configure(text="Nessuna commessa selezionata")
            self.pm_project_client_label.configure(text="--")
            self.pm_client_referente_label.configure(text="--")
            self.pm_client_telefono_label.configure(text="--")
            self.pm_client_email_label.configure(text="--")
            if self.is_admin:
                self.pm_project_rate_label.configure(text="--")
            self.pm_project_notes_label.configure(text="--")
            self.pm_project_dates_label.configure(text="Non pianificata")
            self.pm_project_hours_label.configure(text="--")
            self.pm_project_budget_label.configure(text="--")
            self.clear_budget_alert()
            return
        
        # Carica dati commessa
        projects = self.db.list_projects()
        project = next((p for p in projects if p["id"] == project_id), None)
        
        if not project:
            return
        
        self.pm_project_name_label.configure(text=project["name"])
        self.pm_project_client_label.configure(text=project.get("client_name", "--"))
        self.pm_client_referente_label.configure(text=project.get("client_referente", "--") or "--")
        self.pm_client_telefono_label.configure(text=project.get("client_telefono", "--") or "--")
        self.pm_client_email_label.configure(text=project.get("client_email", "--") or "--")
        if self.is_admin:
            self.pm_project_rate_label.configure(text=f"{project['hourly_rate']:.2f} €/h")
        self.pm_project_notes_label.configure(text=project.get("notes", "--") or "--")
        
        # Carica pianificazione commessa
        schedules = self.db.list_schedules()
        project_schedule = next((s for s in schedules if s["project_id"] == project_id and s["activity_id"] is None), None)
        
        if project_schedule:
            start = datetime.strptime(project_schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            end = datetime.strptime(project_schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            self.pm_project_dates_label.configure(text=f"{start} - {end}")
            self.pm_project_hours_label.configure(text=f"{project_schedule['planned_hours']} h")
            self.pm_project_budget_label.configure(text=f"{project_schedule.get('budget', 0):.2f} €")
            
            # Verifica budget attività
            self.check_activities_budget(project_id, project_schedule['planned_hours'], project_schedule.get('budget', 0))
        else:
            self.pm_project_dates_label.configure(text="Non pianificata")
            self.pm_project_hours_label.configure(text="--")
            self.pm_project_budget_label.configure(text="--")
            self.clear_budget_alert()
        
        # Aggiorna checkbox utenti assegnati (solo admin)
        if self.is_admin:
            self.refresh_user_checkboxes()
        
        # Aggiorna lista attività della commessa selezionata
        self.refresh_project_activities_tree()
    
    def refresh_user_checkboxes(self) -> None:
        """Aggiorna i checkbox degli utenti assegnati alla commessa."""
        if not hasattr(self, 'pm_users_frame'):
            return
        
        # Pulisci checkbox esistenti
        for widget in self.pm_users_frame.winfo_children():
            widget.destroy()
        self.pm_user_checkboxes.clear()
        
        if not self.selected_project_id:
            return
        
        # Carica tutti gli utenti attivi
        all_users = self.db.list_users()
        active_users = [u for u in all_users if u["active"] == 1]
        
        # Carica utenti già assegnati
        assigned_users = self.db.list_users_assigned_to_project(self.selected_project_id)
        assigned_ids = {u["id"] for u in assigned_users}
        
        # Crea checkbox per ogni utente
        for user in active_users:
            var = tk.BooleanVar(value=user["id"] in assigned_ids)
            cb = ctk.CTkCheckBox(
                self.pm_users_frame,
                text=f"{user['full_name']} ({user['username']})",
                variable=var,
                command=lambda uid=user["id"], v=var: self.on_user_assignment_toggle(uid, v)
            )
            cb.pack(anchor="w", pady=1)
            self.pm_user_checkboxes[user["id"]] = (cb, var)
    
    def on_user_assignment_toggle(self, user_id: int, var: tk.BooleanVar) -> None:
        """Gestisce il cambio stato di assegnazione utente."""
        if not self.selected_project_id:
            return
        
        try:
            if var.get():
                self.db.assign_user_to_project(user_id, self.selected_project_id)
            else:
                self.db.unassign_user_from_project(user_id, self.selected_project_id)
        except Exception as e:
            messagebox.showerror("Gestione Commesse", f"Errore assegnazione: {e}")
            var.set(not var.get())  # Ripristina stato precedente
    
    def refresh_project_activities_tree(self) -> None:
        """Aggiorna il treeview mostrando solo le attività della commessa selezionata."""
        if not hasattr(self, 'master_tree'):
            return
        
        # Pulisci treeview
        for item in self.master_tree.get_children():
            self.master_tree.delete(item)
        
        # Se non c'è una commessa selezionata, treeview vuoto
        if not self.selected_project_id:
            return
        
        # Carica tutti gli schedule una volta sola
        all_schedules = self.db.list_schedules()
        
        # Mostra solo le attività della commessa selezionata
        activities = self.db.list_activities(self.selected_project_id)
        
        for activity in activities:
            # Cerca pianificazione per l'attività
            dates_text = "--"
            planned_hours = 0.0
            budget = 0.0
            
            for sched in all_schedules:
                if sched["project_id"] == self.selected_project_id and sched["activity_id"] == activity["id"]:
                    start = datetime.strptime(sched["start_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                    end = datetime.strptime(sched["end_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                    dates_text = f"{start} - {end}"
                    planned_hours = float(sched["planned_hours"])
                    budget = float(sched.get("budget", 0))
                    break
            
            # Recupera ore effettive e costi per questa attività
            actual_data = self.db.get_activity_actual_data(self.selected_project_id, activity["id"])
            actual_hours = actual_data["actual_hours"]
            actual_cost = actual_data["actual_cost"]
            
            if self.is_admin:
                values = (
                    dates_text,
                    f"{planned_hours:.1f}" if planned_hours > 0 else "--",
                    f"{actual_hours:.1f}" if actual_hours > 0 else "--",
                    f"{budget:.2f}" if budget > 0 else "--",
                    f"{actual_cost:.2f}" if actual_cost > 0 else "--",
                    f"{activity['hourly_rate']:.2f}"
                )
            else:
                values = (
                    dates_text,
                    f"{planned_hours:.1f}" if planned_hours > 0 else "--",
                    f"{actual_hours:.1f}" if actual_hours > 0 else "--"
                )
                
            self.master_tree.insert(
                "",
                "end",
                text=activity["name"],
                values=values,
                tags=(f"activity_{activity['id']}",),
            )
    
    def check_activities_budget(self, project_id: int, project_hours: float, project_budget: float) -> None:
        """Verifica se le attività superano il budget della commessa."""
        schedules = self.db.list_schedules()
        activities_schedules = [s for s in schedules if s["project_id"] == project_id and s["activity_id"] is not None]
        
        if not activities_schedules:
            self.clear_budget_alert()
            return
        
        total_activity_hours = sum(s["planned_hours"] for s in activities_schedules)
        total_activity_budget = sum(s.get("budget", 0) for s in activities_schedules)
        
        hours_exceeded = total_activity_hours > project_hours
        budget_exceeded = total_activity_budget > project_budget if project_budget > 0 else False
        
        if hours_exceeded or budget_exceeded:
            self.show_budget_alert(hours_exceeded, budget_exceeded, total_activity_hours, project_hours, 
                                   total_activity_budget, project_budget)
        else:
            self.clear_budget_alert()
    
    def show_budget_alert(self, hours_exceeded: bool, budget_exceeded: bool, 
                         total_hours: float, project_hours: float,
                         total_budget: float, project_budget: float) -> None:
        """Mostra alert visivo se i budget sono superati."""
        # Pulisci alert precedente
        for widget in self.pm_budget_alert_frame.winfo_children():
            widget.destroy()
        
        alert_text = "⚠️ ATTENZIONE:"
        details = []
        
        if hours_exceeded:
            details.append(f"Ore attività ({total_hours}h) > Ore commessa ({project_hours}h)")
        if budget_exceeded:
            details.append(f"Budget attività (€{total_budget:.2f}) > Budget commessa (€{project_budget:.2f})")
        
        alert_label = ctk.CTkLabel(
            self.pm_budget_alert_frame, 
            text=alert_text + " " + " | ".join(details),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FF4444"
        )
        alert_label.pack(anchor="w", padx=5, pady=2)
    
    def clear_budget_alert(self) -> None:
        """Rimuove l'alert budget."""
        for widget in self.pm_budget_alert_frame.winfo_children():
            widget.destroy()
    
    def pm_add_activity(self) -> None:
        """Aggiunge un'attività alla commessa selezionata."""
        if not self.selected_project_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona prima una commessa.")
            return
        
        try:
            name = self.pm_activity_name_entry.get().strip()
            if not name:
                raise ValueError("Nome attività obbligatorio.")
            
            if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
                rate = self._to_float(self.pm_activity_rate_entry.get().strip() or "0", "Costo attività")
            else:
                rate = 0.0
            
            notes = self.pm_activity_notes_entry.get().strip()
            
            # Crea l'attività
            activity_id = self.db.add_activity(self.selected_project_id, name, rate, notes)
            
            # Se ci sono dati di pianificazione completi, crea anche uno schedule
            start_date_str = self.pm_activity_start_entry.get().strip()
            end_date_str = self.pm_activity_end_entry.get().strip()
            hours_str = self.pm_activity_hours_entry.get().strip()
            budget_str = self.pm_activity_budget_entry.get().strip()
            
            # Crea schedule solo se ci sono TUTTI i dati necessari (date + ore)
            if start_date_str and end_date_str and hours_str:
                start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                
                if start_date > end_date:
                    raise ValueError("La data di inizio deve essere precedente alla data di fine.")
                
                planned_hours = self._to_float(hours_str, "Ore preventivate")
                if planned_hours <= 0:
                    raise ValueError("Ore preventivate: il valore deve essere > 0.")
                
                budget = self._to_float(budget_str, "Budget") if budget_str else 0.0
                
                self.db.add_schedule(self.selected_project_id, activity_id, start_date, end_date, planned_hours, "", budget)
            
            messagebox.showinfo("Gestione Commesse", "Attività aggiunta con successo.")
            
        except ValueError as exc:
            messagebox.showerror("Gestione Commesse", str(exc))
            return
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                messagebox.showerror("Gestione Commesse", f"Esiste già un'attività con questo nome per questa commessa.\nScegli un nome diverso.")
            else:
                messagebox.showerror("Gestione Commesse", f"Errore database: {exc}")
            return
        
        # Pulisci i campi
        self.pm_activity_name_entry.delete(0, "end")
        if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
            self.pm_activity_rate_entry.delete(0, "end")
        self.pm_activity_notes_entry.delete(0, "end")
        self.pm_activity_start_entry.delete(0, "end")
        self.pm_activity_end_entry.delete(0, "end")
        self.pm_activity_hours_entry.delete(0, "end")
        self.pm_activity_budget_entry.delete(0, "end")
        
        # Ricarica attività e verifica budget
        self.refresh_project_activities_tree()
        self.on_pm_project_change(self.pm_project_combo.get())
        if hasattr(self, 'refresh_control_panel'):
            self.refresh_control_panel()
    
    def pm_edit_activity(self) -> None:
        """Modifica l'attività selezionata nel treeview."""
        if not self.selected_activity_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona un'attività dall'elenco.")
            return
        
        # Recupera project_id dall'attività
        activities = self.db.list_activities()
        project_id = None
        for act in activities:
            if act["id"] == self.selected_activity_id:
                project_id = act["project_id"]
                break
        
        if not project_id:
            messagebox.showerror("Gestione Commesse", "Impossibile trovare la commessa associata.")
            return
        
        try:
            name = self.pm_activity_name_entry.get().strip()
            if not name:
                raise ValueError("Nome attività obbligatorio.")
            
            if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
                rate = self._to_float(self.pm_activity_rate_entry.get().strip() or "0", "Costo attività")
            else:
                rate = 0.0
            
            notes = self.pm_activity_notes_entry.get().strip()
            self.db.update_activity(self.selected_activity_id, name, rate, notes)
            
            # Gestione pianificazione - aggiorna/crea schedule solo se ci sono TUTTI i dati necessari
            start_date_str = self.pm_activity_start_entry.get().strip()
            end_date_str = self.pm_activity_end_entry.get().strip()
            hours_str = self.pm_activity_hours_entry.get().strip()
            budget_str = self.pm_activity_budget_entry.get().strip()
            
            if start_date_str and end_date_str and hours_str:
                # Tutti i dati necessari presenti, gestisci lo schedule
                start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                
                if start_date > end_date:
                    raise ValueError("La data di inizio deve essere precedente alla data di fine.")
                
                planned_hours = self._to_float(hours_str, "Ore preventivate")
                if planned_hours <= 0:
                    raise ValueError("Ore preventivate: il valore deve essere > 0.")
                
                budget = self._to_float(budget_str, "Budget") if budget_str else 0.0
                
                # Cerca schedule esistente per questa attività
                schedules = self.db.list_schedules()
                existing_schedule = None
                for sched in schedules:
                    if sched["project_id"] == project_id and sched["activity_id"] == self.selected_activity_id:
                        existing_schedule = sched
                        break
                
                if existing_schedule:
                    self.db.update_schedule(existing_schedule["id"], project_id, self.selected_activity_id, 
                                          start_date, end_date, planned_hours, "", budget)
                else:
                    self.db.add_schedule(project_id, self.selected_activity_id, start_date, end_date, planned_hours, "", budget)
            elif not start_date_str and not end_date_str and not hours_str:
                # Nessun dato di pianificazione, elimina schedule se esiste
                schedules = self.db.list_schedules()
                for sched in schedules:
                    if sched["project_id"] == project_id and sched["activity_id"] == self.selected_activity_id:
                        self.db.delete_schedule(sched["id"])
                        break
            
            messagebox.showinfo("Gestione Commesse", "Attività modificata con successo.")
            
        except ValueError as exc:
            messagebox.showerror("Gestione Commesse", str(exc))
            return
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                messagebox.showerror("Gestione Commesse", f"Esiste già un'attività con questo nome per questa commessa.\nScegli un nome diverso.")
            else:
                messagebox.showerror("Gestione Commesse", f"Errore database: {exc}")
            return
        
        # Pulisci i campi
        self.pm_activity_name_entry.delete(0, "end")
        if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
            self.pm_activity_rate_entry.delete(0, "end")
        self.pm_activity_notes_entry.delete(0, "end")
        self.pm_activity_start_entry.delete(0, "end")
        self.pm_activity_end_entry.delete(0, "end")
        self.pm_activity_hours_entry.delete(0, "end")
        self.pm_activity_budget_entry.delete(0, "end")
        self.selected_activity_id = None
        
        # Ricarica attività e verifica budget
        self.refresh_project_activities_tree()
        self.on_pm_project_change(self.pm_project_combo.get())
        if hasattr(self, 'refresh_control_panel'):
            self.refresh_control_panel()
    
    def pm_delete_activity(self) -> None:
        """Elimina l'attività selezionata."""
        if not self.selected_activity_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona un'attività dall'elenco.")
            return
        
        if not messagebox.askyesno("Conferma", "Eliminare l'attività selezionata? Verranno eliminati anche i timesheet associati."):
            return
        
        try:
            self.db.delete_activity(self.selected_activity_id)
            messagebox.showinfo("Gestione Commesse", "Attività eliminata.")
            
            # Pulisci i campi
            self.pm_activity_name_entry.delete(0, "end")
            if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
                self.pm_activity_rate_entry.delete(0, "end")
            self.pm_activity_notes_entry.delete(0, "end")
            self.pm_activity_start_entry.delete(0, "end")
            self.pm_activity_end_entry.delete(0, "end")
            self.pm_activity_hours_entry.delete(0, "end")
            self.pm_activity_budget_entry.delete(0, "end")
            self.selected_activity_id = None
            
            # Ricarica attività e verifica budget
            self.refresh_project_activities_tree()
            self.on_pm_project_change(self.pm_project_combo.get())
            if hasattr(self, 'refresh_control_panel'):
                self.refresh_control_panel()
                
        except Exception as exc:
            messagebox.showerror("Gestione Commesse", f"Errore: {exc}")
    
    def on_pm_tree_select(self, _event: tk.Event) -> None:
        """Popola i campi quando viene selezionato un elemento nell'albero."""
        selected = self.master_tree.selection()
        if not selected:
            return
        
        item = selected[0]
        tags = self.master_tree.item(item, "tags")
        
        # Se è un'attività
        if tags and tags[0].startswith("activity_"):
            activity_id = int(tags[0].replace("activity_", ""))
            self.selected_activity_id = activity_id
            activities = self.db.list_activities()
            
            for activity in activities:
                if activity["id"] == activity_id:
                    self.pm_activity_name_entry.delete(0, "end")
                    self.pm_activity_name_entry.insert(0, activity["name"])
                    
                    if self.is_admin and hasattr(self, 'pm_activity_rate_entry'):
                        self.pm_activity_rate_entry.delete(0, "end")
                        self.pm_activity_rate_entry.insert(0, str(activity["hourly_rate"]))
                    
                    self.pm_activity_notes_entry.delete(0, "end")
                    self.pm_activity_notes_entry.insert(0, activity.get("notes", ""))
                    
                    # Carica pianificazione se esiste
                    schedules = self.db.list_schedules()
                    for sched in schedules:
                        if sched["project_id"] == activity["project_id"] and sched["activity_id"] == activity_id:
                            start_date = datetime.strptime(sched["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                            end_date = datetime.strptime(sched["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                            
                            self.pm_activity_start_entry.delete(0, "end")
                            self.pm_activity_start_entry.insert(0, start_date)
                            self.pm_activity_end_entry.delete(0, "end")
                            self.pm_activity_end_entry.insert(0, end_date)
                            self.pm_activity_hours_entry.delete(0, "end")
                            self.pm_activity_hours_entry.insert(0, str(sched["planned_hours"]))
                            self.pm_activity_budget_entry.delete(0, "end")
                            self.pm_activity_budget_entry.insert(0, str(sched.get("budget", 0)))
                            break
                    else:
                        # Nessuna pianificazione, pulisci i campi date
                        self.pm_activity_start_entry.delete(0, "end")
                        self.pm_activity_end_entry.delete(0, "end")
                        self.pm_activity_hours_entry.delete(0, "end")
                        self.pm_activity_budget_entry.delete(0, "end")
                    break
        else:
            # Non è un'attività, pulisci la selezione
            self.selected_activity_id = None
    
    def open_clients_management(self) -> None:
        """Apre finestra popup per gestione completa clienti."""
        popup = ctk.CTkToplevel(self)
        popup.title("Gestione Clienti")
        popup.geometry("800x600")
        popup.transient(self)
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
        
        if self.is_admin:
            ctk.CTkLabel(form_frame, text="Costo orario (€/h):", font=ctk.CTkFont(weight="bold")).grid(
                row=2, column=0, padx=5, pady=5, sticky="w"
            )
            client_rate_entry = ctk.CTkEntry(form_frame, placeholder_text="0.00", width=120)
            client_rate_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(form_frame, text="Note:", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, padx=5, pady=5, sticky="w"
        )
        client_notes_entry = ctk.CTkEntry(form_frame, placeholder_text="Note opzionali")
        client_notes_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Funzioni CRUD
        editing_client_id = [None]  # Lista per permettere modifica da inner function
        
        def add_or_update_client():
            try:
                name = client_name_entry.get().strip()
                if not name:
                    raise ValueError("Nome cliente obbligatorio.")
                
                if self.is_admin:
                    rate = self._to_float(client_rate_entry.get().strip() or "0", "Costo cliente")
                else:
                    rate = 0.0
                
                notes = client_notes_entry.get().strip()
                referente = client_referente_entry.get().strip()
                telefono = client_telefono_entry.get().strip()
                email = client_email_entry.get().strip()
                
                if editing_client_id[0] is None:
                    self.db.add_client(name, rate, notes, referente, telefono, email)
                    messagebox.showinfo("Gestione Clienti", "Cliente aggiunto con successo.")
                else:
                    self.db.update_client(editing_client_id[0], name, rate, notes, referente, telefono, email)
                    messagebox.showinfo("Gestione Clienti", "Cliente modificato con successo.")
                    editing_client_id[0] = None
                    save_btn.configure(text="Aggiungi Cliente")
                
                client_name_entry.delete(0, "end")
                client_referente_entry.delete(0, "end")
                client_telefono_entry.delete(0, "end")
                client_email_entry.delete(0, "end")
                if self.is_admin:
                    client_rate_entry.delete(0, "end")
                client_notes_entry.delete(0, "end")
                
                refresh_clients_list()
                self.refresh_master_data()
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
                
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
            clients = self.db.list_clients()
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
                if self.is_admin:
                    client_rate_entry.delete(0, "end")
                    client_rate_entry.insert(0, str(client["hourly_rate"]))
                client_notes_entry.delete(0, "end")
                client_notes_entry.insert(0, client.get("notes", ""))
                save_btn.configure(text="Salva Modifiche")
        
        def delete_client():
            selected_items = clients_tree.selection()
            if not selected_items:
                messagebox.showinfo("Gestione Clienti", "Seleziona un cliente dall'elenco.")
                return
            
            if not messagebox.askyesno("Conferma", "Eliminare il cliente? Verranno eliminati anche commesse, attività e timesheet associati."):
                return
            
            client_id = int(selected_items[0])
            try:
                self.db.delete_client(client_id)
                messagebox.showinfo("Gestione Clienti", "Cliente eliminato.")
                refresh_clients_list()
                self.refresh_master_data()
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
            except Exception as exc:
                messagebox.showerror("Gestione Clienti", f"Errore: {exc}")
        
        def refresh_clients_list():
            for item in clients_tree.get_children():
                clients_tree.delete(item)
            
            clients = self.db.list_clients()
            for client in clients:
                if self.is_admin:
                    values = (
                        client.get("referente", ""),
                        client.get("telefono", ""),
                        client.get("email", ""),
                        f"{client['hourly_rate']:.2f} €",
                        client.get("notes", "")
                    )
                else:
                    values = (
                        client.get("referente", ""),
                        client.get("telefono", ""),
                        client.get("email", ""),
                        client.get("notes", "")
                    )
                clients_tree.insert("", "end", iid=str(client["id"]), text=client["name"], values=values)
        
        # Pulsanti CRUD
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=4, pady=10)
        
        save_btn = ctk.CTkButton(btn_frame, text="Aggiungi Cliente", command=add_or_update_client, width=120)
        save_btn.pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="Modifica Selezionato", command=load_client_for_edit, width=140).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Elimina Selezionato", command=delete_client, width=140).pack(side="left", padx=5)
        
        # Lista clienti
        list_frame = ctk.CTkFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        if self.is_admin:
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
    
    def open_project_management(self) -> None:
        """Apre finestra popup per gestione completa della commessa (nuova o esistente)."""
        # Modalità: se c'è una commessa selezionata -> modifica, altrimenti -> crea nuova
        is_new = not self.selected_project_id
        
        if is_new:
            # Modalità creazione: serve almeno un cliente selezionato
            client_id = self._id_from_option(self.pm_client_combo.get())
            if not client_id:
                messagebox.showinfo("Gestione Commesse", "Seleziona prima un cliente.")
                return
            
            # Carica dati cliente per la nuova commessa
            clients = self.db.list_clients()
            client = next((c for c in clients if c["id"] == client_id), None)
            if not client:
                messagebox.showerror("Gestione Commesse", "Cliente non trovato.")
                return
            
            project = {
                "name": "",
                "referente_commessa": "",
                "hourly_rate": client["hourly_rate"],  # Eredita dal cliente
                "notes": "",
                "descrizione_commessa": ""
            }
            project_schedule = None
        else:
            # Modalità modifica: carica dati commessa esistente
            projects = self.db.list_projects()
            project = next((p for p in projects if p["id"] == self.selected_project_id), None)
            
            if not project:
                messagebox.showerror("Gestione Commesse", "Commessa non trovata.")
                return
            
            client_id = project["client_id"]
            
            # Carica pianificazione esistente
            schedules = self.db.list_schedules()
            project_schedule = next((s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] is None), None)
        
        popup = ctk.CTkToplevel(self)
        if is_new:
            popup.title("Nuova Commessa")
        else:
            popup.title(f"Gestione Commessa: {project['name']}")
        popup.geometry("800x700")
        popup.transient(self)
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
        
        if self.is_admin:
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
        self.setup_date_entry_helpers(project_start_entry)
        
        ctk.CTkLabel(form_frame, text="Data fine:").grid(row=6, column=2, padx=5, pady=5, sticky="w")
        project_end_entry = ctk.CTkEntry(form_frame, placeholder_text="gg/mm/aaaa", width=120)
        project_end_entry.grid(row=6, column=3, padx=5, pady=5, sticky="w")
        self.setup_date_entry_helpers(project_end_entry)
        
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
                name = project_name_entry.get().strip()
                if not name:
                    raise ValueError("Nome commessa obbligatorio.")
                
                if self.is_admin:
                    rate = self._to_float(project_rate_entry.get().strip() or "0", "Costo commessa")
                else:
                    rate = project["hourly_rate"]
                
                notes = project_notes_entry.get().strip()
                referente_commessa = project_referente_entry.get().strip()
                descrizione_commessa = project_desc_text.get("1.0", "end-1c").strip()
                
                if is_new:
                    # Crea nuova commessa
                    new_project_id = self.db.add_project(client_id, name, rate, notes, referente_commessa, descrizione_commessa)
                    self.selected_project_id = new_project_id
                else:
                    # Aggiorna commessa esistente
                    self.db.update_project(self.selected_project_id, name, rate, notes, referente_commessa, descrizione_commessa)
                
                # Gestione pianificazione - aggiorna/crea schedule solo se ci sono TUTTI i dati necessari
                start_date_str = project_start_entry.get().strip()
                end_date_str = project_end_entry.get().strip()
                hours_str = project_hours_entry.get().strip()
                budget_str = project_budget_entry.get().strip()
                
                if start_date_str and end_date_str and hours_str:
                    # Tutti i dati necessari presenti, gestisci lo schedule
                    start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    
                    if start_date > end_date:
                        raise ValueError("La data di inizio deve essere precedente alla data di fine.")
                    
                    planned_hours = self._to_float(hours_str, "Ore preventivate")
                    if planned_hours <= 0:
                        raise ValueError("Ore preventivate: il valore deve essere > 0.")
                    
                    budget = self._to_float(budget_str, "Budget") if budget_str else 0.0
                    
                    if project_schedule and not is_new:
                        self.db.update_schedule(project_schedule["id"], self.selected_project_id, None,
                                              start_date, end_date, planned_hours, "", budget)
                    else:
                        self.db.add_schedule(self.selected_project_id, None, start_date, end_date, planned_hours, "", budget)
                elif not start_date_str and not end_date_str and not hours_str and project_schedule and not is_new:
                    # Nessun dato di pianificazione e c'era uno schedule, eliminalo
                    self.db.delete_schedule(project_schedule["id"])
                
                if is_new:
                    messagebox.showinfo("Gestione Commesse", "Nuova commessa creata con successo.")
                else:
                    messagebox.showinfo("Gestione Commesse", "Commessa aggiornata con successo.")
                
                popup.destroy()
                self.refresh_master_data()
                
                # Seleziona la nuova/modificata commessa
                projects = self.db.list_projects(client_id)
                project_option = next((self._project_option(p) for p in projects if p["id"] == self.selected_project_id), None)
                if project_option:
                    self.pm_project_combo.set(project_option)
                    self.on_pm_project_change(project_option)
                
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
                
            except ValueError as exc:
                messagebox.showerror("Gestione Commesse", str(exc))
            except sqlite3.IntegrityError as exc:
                if "UNIQUE constraint" in str(exc):
                    messagebox.showerror("Gestione Commesse", "Esiste già una commessa con questo nome per questo cliente.\nScegli un nome diverso.")
                else:
                    messagebox.showerror("Gestione Commesse", f"Errore database: {exc}")
        
        # Pulsanti
        btn_frame = ctk.CTkFrame(main_scroll_frame, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        if is_new:
            ctk.CTkButton(btn_frame, text="Crea Commessa", command=save_project, width=150).pack(side="left", padx=5)
        else:
            ctk.CTkButton(btn_frame, text="Salva Modifiche", command=save_project, width=150).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Chiudi", command=popup.destroy, width=100).pack(side="left", padx=5)

    def add_client(self) -> None:
        # Funzione deprecata - ora si usa open_clients_management
        pass

    def edit_client(self) -> None:
        # Funzione deprecata - ora si usa open_clients_management
        pass

    def add_project(self) -> None:
        # Funzione deprecata - ora si usa open_project_management
        pass

    def edit_project(self) -> None:
        # Funzione deprecata - ora si usa open_project_management
        pass

    def add_activity(self) -> None:
        # Funzione deprecata - ora si usa pm_add_activity
        pass

    def edit_activity(self) -> None:
        # Funzione deprecata - ora si usa pm_edit_activity
        pass

    def on_master_tree_select(self, _event: tk.Event) -> None:
        # Funzione deprecata - ora si usa on_pm_tree_select
        pass

    def on_project_client_change(self, _value: str) -> None:
        # Funzione deprecata - ora si usa on_pm_client_change
        pass

    def refresh_master_data(self) -> None:
        clients = self.db.list_clients()
        client_values = [self._entity_option(row["id"], row["name"]) for row in clients]
        
        # Aggiorna combo solo se le tab corrispondenti sono abilitate
        if hasattr(self, 'ts_client_combo'):
            self._set_combo_values(self.ts_client_combo, client_values)
        if hasattr(self, 'project_client_combo'):
            self._set_combo_values(self.project_client_combo, client_values)
        
        # Nuova tab Project Management
        if hasattr(self, 'pm_client_combo'):
            current_client = self.pm_client_combo.get()
            self._set_combo_values(self.pm_client_combo, client_values)
            if current_client in client_values:
                self.pm_client_combo.set(current_client)
                self.on_pm_client_change(current_client)
            else:
                self.pm_client_combo.set("")
                self.on_pm_client_change("")

        if hasattr(self, 'project_client_combo'):
            selected_client_id = self._id_from_option(self.project_client_combo.get())
            projects_for_client = self.db.list_projects(selected_client_id)
            if hasattr(self, 'activity_project_combo'):
                self._set_combo_values(self.activity_project_combo, [self._project_option(row) for row in projects_for_client])

        if hasattr(self, 'ts_client_combo'):
            self.on_timesheet_client_change(self.ts_client_combo.get())
        if hasattr(self, 'plan_project_combo'):
            self.refresh_programming_options()
        if hasattr(self, 'master_tree'):
            # Per la nuova tab Project Management, aggiorna solo le attività della commessa selezionata
            if hasattr(self, 'pm_client_combo'):
                self.refresh_project_activities_tree()
            else:
                # Vecchia visualizzazione gerarchica (se ancora in uso)
                self.refresh_master_tree()

    def refresh_master_tree(self) -> None:
        if not hasattr(self, 'master_tree'):
            return
        for item in self.master_tree.get_children():
            self.master_tree.delete(item)

        # Carica tutti gli schedule una volta sola
        all_schedules = self.db.list_schedules()

        for client in self.db.list_clients():
            if self.is_admin:
                values = ("Cliente", f"{client['hourly_rate']:.2f}", "")
            else:
                values = ("Cliente", "")
            
            client_node = self.master_tree.insert(
                "",
                "end",
                text=client["name"],
                values=values,
                tags=(f"client_{client['id']}",),
                open=True,
            )
            for project in self.db.list_projects(client["id"]):
                # Cerca pianificazione per la commessa
                planning_info = ""
                for sched in all_schedules:
                    if sched["project_id"] == project["id"] and sched["activity_id"] is None:
                        start = datetime.strptime(sched["start_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                        end = datetime.strptime(sched["end_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                        planning_info = f"{start} - {end}, {sched['planned_hours']}h"
                        if sched.get("budget", 0) > 0:
                            planning_info += f", €{sched['budget']:.0f}"
                        break
                
                if self.is_admin:
                    values = ("Commessa", f"{project['hourly_rate']:.2f}", planning_info)
                else:
                    values = ("Commessa", planning_info)
                    
                project_node = self.master_tree.insert(
                    client_node,
                    "end",
                    text=project["name"],
                    values=values,
                    tags=(f"project_{project['id']}",),
                    open=True,
                )
                for activity in self.db.list_activities(project["id"]):
                    # Cerca pianificazione per l'attività
                    planning_info = ""
                    for sched in all_schedules:
                        if sched["project_id"] == project["id"] and sched["activity_id"] == activity["id"]:
                            start = datetime.strptime(sched["start_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                            end = datetime.strptime(sched["end_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                            planning_info = f"{start} - {end}, {sched['planned_hours']}h"
                            if sched.get("budget", 0) > 0:
                                planning_info += f", €{sched['budget']:.0f}"
                            break
                    
                    if self.is_admin:
                        values = ("Attivita", f"{activity['hourly_rate']:.2f}", planning_info)
                    else:
                        values = ("Attivita", planning_info)
                        
                    self.master_tree.insert(
                        project_node,
                        "end",
                        text=activity["name"],
                        values=values,
                        tags=(f"activity_{activity['id']}",),
                    )

    def build_plan_tab(self) -> None:
        self.tab_plan.grid_columnconfigure(0, weight=1)
        self.tab_plan.grid_rowconfigure(1, weight=1)

        form = ctk.CTkFrame(self.tab_plan)
        form.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        for i in range(6):
            form.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(form, text="Commessa").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.plan_project_combo = ctk.CTkComboBox(
            form, state="readonly", command=self.on_plan_project_change, width=260, values=[""]
        )
        self.plan_project_combo.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Attivita (opzionale)").grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self.plan_activity_combo = ctk.CTkComboBox(form, state="readonly", width=260, values=[""])
        self.plan_activity_combo.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Data inizio (gg/mm/aaaa)").grid(row=0, column=2, padx=8, pady=4, sticky="w")
        self.plan_start_date_entry = ctk.CTkEntry(form, placeholder_text="01/01/2026")
        self.plan_start_date_entry.grid(row=1, column=2, padx=8, pady=4, sticky="ew")
        self.setup_date_entry_helpers(self.plan_start_date_entry)

        ctk.CTkLabel(form, text="Data fine (gg/mm/aaaa)").grid(row=0, column=3, padx=8, pady=4, sticky="w")
        self.plan_end_date_entry = ctk.CTkEntry(form, placeholder_text="31/12/2026")
        self.plan_end_date_entry.grid(row=1, column=3, padx=8, pady=4, sticky="ew")
        self.setup_date_entry_helpers(self.plan_end_date_entry)

        ctk.CTkLabel(form, text="Ore preventivate").grid(row=0, column=4, padx=8, pady=4, sticky="w")
        self.plan_hours_entry = ctk.CTkEntry(form, placeholder_text="160")
        self.plan_hours_entry.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Budget (€)").grid(row=0, column=5, padx=8, pady=4, sticky="w")
        self.plan_budget_entry = ctk.CTkEntry(form, placeholder_text="5000.00")
        self.plan_budget_entry.grid(row=1, column=5, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Note").grid(row=2, column=0, padx=8, pady=4, sticky="w")
        self.plan_note_entry = ctk.CTkEntry(form)
        self.plan_note_entry.grid(row=2, column=1, columnspan=5, padx=8, pady=4, sticky="ew")

        ctk.CTkButton(form, text="Salva programmazione", command=self.add_schedule_entry).grid(
            row=3, column=0, columnspan=1, padx=8, pady=(8, 10), sticky="ew"
        )
        ctk.CTkButton(form, text="Modifica selezionata", command=self.edit_selected_schedule).grid(
            row=3, column=1, padx=8, pady=(8, 10), sticky="ew"
        )
        ctk.CTkButton(form, text="Chiudi/Apri", command=self.toggle_schedule_status).grid(
            row=3, column=2, padx=8, pady=(8, 10), sticky="ew"
        )
        ctk.CTkButton(form, text="Elimina selezionata", command=self.delete_selected_schedule).grid(
            row=3, column=3, padx=8, pady=(8, 10), sticky="ew"
        )

        list_frame = ctk.CTkFrame(self.tab_plan)
        list_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        columns = ("client", "project", "activity", "start_date", "end_date", "hours", "budget", "status", "note")
        self.plan_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.plan_tree.heading("client", text="Cliente")
        self.plan_tree.heading("project", text="Commessa")
        self.plan_tree.heading("activity", text="Attivita")
        self.plan_tree.heading("start_date", text="Data inizio")
        self.plan_tree.heading("end_date", text="Data fine")
        self.plan_tree.heading("hours", text="Ore preventivate")
        self.plan_tree.heading("budget", text="Budget €")
        self.plan_tree.heading("status", text="Stato")
        self.plan_tree.heading("note", text="Note")
        self.plan_tree.column("client", width=120, anchor="w")
        self.plan_tree.column("project", width=150, anchor="w")
        self.plan_tree.column("activity", width=150, anchor="w")
        self.plan_tree.column("start_date", width=90, anchor="center")
        self.plan_tree.column("end_date", width=90, anchor="center")
        self.plan_tree.column("hours", width=100, anchor="e")
        self.plan_tree.column("budget", width=100, anchor="e")
        self.plan_tree.column("status", width=70, anchor="center")
        self.plan_tree.column("note", width=180, anchor="w")
        self.plan_tree.grid(row=0, column=0, sticky="nsew")
        
        # Bind per popolare il form al click
        self.plan_tree.bind("<<TreeviewSelect>>", self.on_schedule_tree_select)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.plan_tree.yview)
        self.plan_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

    def refresh_programming_options(self) -> None:
        if not hasattr(self, "plan_project_combo"):
            return
        projects = self.db.list_projects()
        self._set_combo_values(self.plan_project_combo, [self._project_option(row) for row in projects])
        self.on_plan_project_change(self.plan_project_combo.get())

    def on_plan_project_change(self, _value: str) -> None:
        project_id = self._id_from_option(self.plan_project_combo.get())
        activities = self.db.list_activities(project_id)
        # Aggiungi opzione vuota per "tutta la commessa"
        options = ["(Tutta la commessa)"] + [self._activity_option(row) for row in activities]
        self._set_combo_values(self.plan_activity_combo, options)
        self.plan_activity_combo.set("(Tutta la commessa)")

    def add_schedule_entry(self) -> None:
        try:
            project_id = self._id_from_option(self.plan_project_combo.get())
            if not project_id:
                raise ValueError("Seleziona una commessa.")
            
            # Activity può essere None se selezioniamo "Tutta la commessa"
            activity_str = self.plan_activity_combo.get()
            activity_id = None if activity_str == "(Tutta la commessa)" else self._id_from_option(activity_str)

            # Converti date da dd/mm/yyyy a YYYY-MM-DD
            start_date_str = self.plan_start_date_entry.get().strip()
            end_date_str = self.plan_end_date_entry.get().strip()
            
            start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            
            if start_date > end_date:
                raise ValueError("La data di inizio deve essere precedente alla data di fine.")

            planned_hours = self._to_float(self.plan_hours_entry.get().strip(), "Ore preventivate")
            if planned_hours <= 0:
                raise ValueError("Ore preventivate: il valore deve essere > 0.")

            budget_str = self.plan_budget_entry.get().strip()
            budget = self._to_float(budget_str, "Budget") if budget_str else 0.0

            note = self.plan_note_entry.get().strip()
            self.db.add_schedule(project_id, activity_id, start_date, end_date, planned_hours, note, budget)
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Programmazione", str(exc))
            return

        self.plan_start_date_entry.delete(0, "end")
        self.plan_end_date_entry.delete(0, "end")
        self.plan_hours_entry.delete(0, "end")
        self.plan_budget_entry.delete(0, "end")
        self.plan_note_entry.delete(0, "end")
        self.refresh_schedule_list()
        if hasattr(self, 'refresh_control_panel'):
            self.refresh_control_panel()
        messagebox.showinfo("Programmazione", "Programmazione salvata.")

    def on_schedule_tree_select(self, event) -> None:
        """Popola i campi del form quando si seleziona una programmazione."""
        selection = self.plan_tree.selection()
        if not selection:
            return
        
        schedule_id = int(selection[0])
        schedules = self.db.list_schedules()
        
        for schedule in schedules:
            if schedule["id"] == schedule_id:
                # Imposta il progetto nella combo
                project_option = self._project_option({
                    "id": schedule["project_id"],
                    "name": schedule["project_name"],
                    "client_name": schedule["client_name"]
                })
                self.plan_project_combo.set(project_option)
                self.on_plan_project_change(project_option)
                
                # Imposta l'attività (se presente)
                if schedule["activity_id"] is not None:
                    activities = self.db.list_activities(schedule["project_id"])
                    for act in activities:
                        if act["id"] == schedule["activity_id"]:
                            activity_option = self._activity_option(act)
                            self.plan_activity_combo.set(activity_option)
                            break
                else:
                    self.plan_activity_combo.set("(Tutta la commessa)")
                
                # Imposta le date (converti da YYYY-MM-DD a dd/mm/yyyy)
                try:
                    start_display = datetime.strptime(schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                    end_display = datetime.strptime(schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                except:
                    start_display = schedule["start_date"]
                    end_display = schedule["end_date"]
                
                self.plan_start_date_entry.delete(0, "end")
                self.plan_start_date_entry.insert(0, start_display)
                self.plan_end_date_entry.delete(0, "end")
                self.plan_end_date_entry.insert(0, end_display)
                self.plan_hours_entry.delete(0, "end")
                self.plan_hours_entry.insert(0, str(schedule["planned_hours"]))
                self.plan_budget_entry.delete(0, "end")
                self.plan_budget_entry.insert(0, str(schedule.get("budget", 0.0)))
                self.plan_note_entry.delete(0, "end")
                self.plan_note_entry.insert(0, schedule["note"])
                break

    def edit_selected_schedule(self) -> None:
        """Modifica la programmazione selezionata."""
        selection = self.plan_tree.selection()
        if not selection:
            messagebox.showinfo("Programmazione", "Seleziona una programmazione dall'elenco.")
            return
        
        schedule_id = int(selection[0])
        
        try:
            project_id = self._id_from_option(self.plan_project_combo.get())
            if not project_id:
                raise ValueError("Seleziona una commessa.")
            
            # Activity può essere None se selezioniamo "Tutta la commessa"
            activity_str = self.plan_activity_combo.get()
            activity_id = None if activity_str == "(Tutta la commessa)" else self._id_from_option(activity_str)

            # Converti date da dd/mm/yyyy a YYYY-MM-DD
            start_date_str = self.plan_start_date_entry.get().strip()
            end_date_str = self.plan_end_date_entry.get().strip()
            
            start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
            
            if start_date > end_date:
                raise ValueError("La data di inizio deve essere precedente alla data di fine.")

            planned_hours = self._to_float(self.plan_hours_entry.get().strip(), "Ore preventivate")
            if planned_hours <= 0:
                raise ValueError("Ore preventivate: il valore deve essere > 0.")

            budget_str = self.plan_budget_entry.get().strip()
            budget = self._to_float(budget_str, "Budget") if budget_str else 0.0

            note = self.plan_note_entry.get().strip()
            self.db.update_schedule(schedule_id, project_id, activity_id, start_date, end_date, planned_hours, note, budget)
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Programmazione", str(exc))
            return

        self.refresh_schedule_list()
        if hasattr(self, 'refresh_control_panel'):
            self.refresh_control_panel()
        messagebox.showinfo("Programmazione", "Programmazione aggiornata.")

    def refresh_schedule_list(self) -> None:
        if not hasattr(self, "plan_tree"):
            return

        for item in self.plan_tree.get_children():
            self.plan_tree.delete(item)

        rows = self.db.list_schedules()
        for row in rows:
            # Converti date da YYYY-MM-DD a dd/mm/yyyy per visualizzazione
            try:
                start_display = datetime.strptime(row["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
                end_display = datetime.strptime(row["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                start_display = row["start_date"]
                end_display = row["end_date"]
            
            status_display = "✓" if row.get("status") == "aperta" else "✗"
            
            self.plan_tree.insert(
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

    def delete_selected_schedule(self) -> None:
        selection = self.plan_tree.selection()
        if not selection:
            messagebox.showwarning("Programmazione", "Seleziona una riga da eliminare.")
            return
        if not messagebox.askyesno("Conferma", "Eliminare la programmazione selezionata?"):
            return

        schedule_id = int(selection[0])
        self.db.delete_schedule(schedule_id)
        self.refresh_schedule_list()
    
    def toggle_schedule_status(self) -> None:
        """Apre o chiude una programmazione."""
        selection = self.plan_tree.selection()
        if not selection:
            messagebox.showwarning("Programmazione", "Seleziona una programmazione.")
            return
        
        schedule_id = int(selection[0])
        schedules = self.db.list_schedules()
        schedule = next((s for s in schedules if s["id"] == schedule_id), None)
        
        if not schedule:
            return
        
        current_status = schedule.get("status", "aperta")
        new_status = "chiusa" if current_status == "aperta" else "aperta"
        
        self.db.update_schedule_status(schedule_id, new_status)
        self.refresh_schedule_list()
        
        # Aggiorna anche il calendario ore e il controllo se la schedule era aperta/chiusa
        if hasattr(self, 'ts_client_combo'):
            self.on_timesheet_client_change(self.ts_client_combo.get())
        if hasattr(self, 'ctrl_tree'):
            self.refresh_control_panel()

    def show_schedule_report(self, schedule_id: int) -> None:
        """Mostra finestra report dettagliato per una programmazione."""
        data = self.db.get_schedule_report_data(schedule_id)
        if not data:
            messagebox.showerror("Report", "Programmazione non trovata.")
            return
        
        # Crea finestra popup
        report_win = tk.Toplevel(self)
        report_win.title(f"Report Programmazione - {data['project_name']}")
        report_win.geometry("1200x800")
        report_win.resizable(True, True)
        report_win.transient(self)
        
        # Configura colori in base al tema
        bg_color = "#2b2b2b" if self.is_dark_mode else "#f0f0f0"
        fg_color = "#ffffff" if self.is_dark_mode else "#000000"
        card_bg = "#3a3a3a" if self.is_dark_mode else "#ffffff"
        
        report_win.configure(bg=bg_color)
        
        # Container principale con scrollbar
        main_canvas = tk.Canvas(report_win, bg=bg_color, highlightthickness=0)
        scrollbar = tk.Scrollbar(report_win, orient="vertical", command=main_canvas.yview)
        scrollable_frame = tk.Frame(main_canvas, bg=bg_color)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Header
        header = tk.Frame(scrollable_frame, bg=card_bg, relief="ridge", bd=2)
        header.pack(fill="x", padx=10, pady=10)
        
        tk.Label(
            header,
            text=f"{data['client_name']} > {data['project_name']} > {data['activity_name']}",
            font=("Arial", 16, "bold"),
            bg=card_bg,
            fg=fg_color
        ).pack(side="left", padx=15, pady=10)
        
        try:
            period_start = datetime.strptime(data["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            period_end = datetime.strptime(data["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            period_start = data["start_date"]
            period_end = data["end_date"]
        
        tk.Label(
            header,
            text=f"Periodo: {period_start} - {period_end}",
            font=("Arial", 12),
            bg=card_bg,
            fg=fg_color
        ).pack(side="right", padx=15, pady=10)
        
        # KPI Cards
        kpi_frame = tk.Frame(scrollable_frame, bg=bg_color)
        kpi_frame.pack(fill="x", padx=10, pady=5)
        
        # Calcola metriche
        completion_pct = (data["actual_hours"] / data["planned_hours"] * 100) if data["planned_hours"] > 0 else 0
        budget_pct = (data["actual_cost"] / data["budget"] * 100) if data["budget"] > 0 else 0
        hours_per_day = (data["remaining_hours"] / data["remaining_days"]) if data["remaining_days"] > 0 else 0
        
        # Determina stati
        if data["remaining_hours"] < 0:
            status = "🔴 Ore superate"
            status_color = "#b00020"
        elif data["remaining_days"] < 0:
            status = "⚠️ Scadenza passata"
            status_color = "#f57c00"
        elif completion_pct >= 95:
            status = "✅ Quasi completato"
            status_color = "#4caf50"
        elif data["remaining_days"] < 7:
            status = "⚠️ Scadenza vicina"
            status_color = "#f57c00"
        else:
            status = "✅ In linea"
            status_color = "#4caf50"
        
        kpis = [
            ("Avanzamento Ore", f"{completion_pct:.1f}%", f"{data['actual_hours']:.0f}/{data['planned_hours']:.0f} ore"),
            ("Budget Utilizzato", f"{budget_pct:.1f}%", f"{data['actual_cost']:.2f}€ / {data['budget']:.2f}€"),
            ("Giorni Rimanenti", str(data["remaining_days"]), f"{data['elapsed_days']}/{data['total_days']} giorni trascorsi"),
            ("Ore/Giorno Necessarie", f"{hours_per_day:.1f}", status),
        ]
        
        for idx, (title, value, subtitle) in enumerate(kpis):
            card = tk.Frame(kpi_frame, bg=card_bg, relief="raised", bd=2)
            card.grid(row=0, column=idx, padx=5, pady=5, sticky="nsew")
            kpi_frame.grid_columnconfigure(idx, weight=1)
            
            tk.Label(card, text=title, font=("Arial", 10), bg=card_bg, fg=fg_color).pack(pady=(10, 5))
            
            value_color = status_color if idx == 3 else fg_color
            tk.Label(card, text=value, font=("Arial", 18, "bold"), bg=card_bg, fg=value_color).pack(pady=5)
            tk.Label(card, text=subtitle, font=("Arial", 9), bg=card_bg, fg=fg_color).pack(pady=(5, 10))
        
        # Grafici
        chart_frame = tk.Frame(scrollable_frame, bg=bg_color)
        chart_frame.pack(fill="both", expand=True, padx=10, pady=10)
        chart_frame.grid_columnconfigure(0, weight=1)
        chart_frame.grid_columnconfigure(1, weight=1)
        
        # Configura matplotlib per tema scuro/light
        plt_style = 'dark_background' if self.is_dark_mode else 'default'
        plt.style.use(plt_style)
        
        # Grafico 1: Barre ore
        fig1 = Figure(figsize=(5, 4), dpi=100)
        ax1 = fig1.add_subplot(111)
        
        bars_data = [data["planned_hours"], data["actual_hours"], max(0, data["remaining_hours"])]
        bars_labels = ["Ore Pianificate", "Ore Svolte", "Ore Mancanti"]
        colors = ["#2196f3", "#4caf50", "#ff9800"] if data["remaining_hours"] >= 0 else ["#2196f3", "#b00020", "#ff9800"]
        
        ax1.bar(bars_labels, bars_data, color=colors, alpha=0.8)
        ax1.set_ylabel("Ore")
        ax1.set_title("Distribuzione Ore", fontweight="bold")
        ax1.grid(axis='y', alpha=0.3)
        fig1.tight_layout()
        
        canvas1 = FigureCanvasTkAgg(fig1, master=chart_frame)
        canvas1.draw()
        canvas1.get_tk_widget().grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Grafico 2: Torta distribuzione utenti
        fig2 = Figure(figsize=(5, 4), dpi=100)
        ax2 = fig2.add_subplot(111)
        
        if data["user_hours"]:
            user_labels = [f"{u['username']} ({u['hours']:.1f}h)" for u in data["user_hours"]]
            user_values = [float(u["hours"]) for u in data["user_hours"]]
            ax2.pie(user_values, labels=user_labels, autopct='%1.1f%%', startangle=90)
            ax2.set_title("Distribuzione Ore per Utente", fontweight="bold")
        else:
            ax2.text(0.5, 0.5, "Nessun dato disponibile", ha="center", va="center", fontsize=12)
            ax2.set_xlim(0, 1)
            ax2.set_ylim(0, 1)
            ax2.axis('off')
        
        fig2.tight_layout()
        
        canvas2 = FigureCanvasTkAgg(fig2, master=chart_frame)
        canvas2.draw()
        canvas2.get_tk_widget().grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        # Tabella dettagli
        details_frame = tk.Frame(scrollable_frame, bg=bg_color)
        details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(
            details_frame,
            text="Dettaglio Timesheet",
            font=("Arial", 14, "bold"),
            bg=bg_color,
            fg=fg_color
        ).pack(anchor="w", padx=5, pady=5)
        
        # Treeview per dettagli
        detail_tree = ttk.Treeview(
            details_frame,
            columns=("date", "user", "activity", "hours", "cost", "note"),
            show="headings",
            height=8
        )
        detail_tree.heading("date", text="Data")
        detail_tree.heading("user", text="Utente")
        detail_tree.heading("activity", text="Attività")
        detail_tree.heading("hours", text="Ore")
        detail_tree.heading("cost", text="Costo €")
        detail_tree.heading("note", text="Note")
        
        detail_tree.column("date", width=100, anchor="center")
        detail_tree.column("user", width=120, anchor="w")
        detail_tree.column("activity", width=150, anchor="w")
        detail_tree.column("hours", width=80, anchor="e")
        detail_tree.column("cost", width=100, anchor="e")
        detail_tree.column("note", width=250, anchor="w")
        
        for detail in data["timesheet_details"]:
            try:
                date_display = datetime.strptime(detail["work_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                date_display = detail["work_date"]
            
            activity = detail.get("activity_name", "")
            
            detail_tree.insert("", "end", values=(
                date_display,
                detail["username"],
                activity,
                f"{detail['hours']:.2f}",
                f"{detail['cost']:.2f}",
                detail["note"]
            ))
        
        detail_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Scrollbar per tabella
        detail_scroll = ttk.Scrollbar(details_frame, orient="vertical", command=detail_tree.yview)
        detail_tree.configure(yscrollcommand=detail_scroll.set)
        
        # Pulsante chiudi
        btn_frame = tk.Frame(scrollable_frame, bg=bg_color)
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Button(
            btn_frame,
            text="Chiudi",
            command=report_win.destroy,
            width=15,
            font=("Arial", 11)
        ).pack(side="right", padx=5)
        
        # Pack canvas e scrollbar
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel
        def _on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        report_win.protocol("WM_DELETE_WINDOW", lambda: [main_canvas.unbind_all("<MouseWheel>"), report_win.destroy()])

    def build_control_tab(self) -> None:
        self.tab_control.grid_columnconfigure(0, weight=1)
        self.tab_control.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.tab_control)
        header.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(header, text="Controllo Programmazione", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=10, pady=8
        )
        ctk.CTkButton(header, text="Aggiorna", command=self.refresh_control_panel).pack(side="left", padx=12, pady=8)
        ctk.CTkButton(header, text="📄 Genera Report PDF", command=self.show_pdf_report_dialog).pack(side="left", padx=12, pady=8)

        table_frame = ctk.CTkFrame(self.tab_control)
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
        self.ctrl_tree = ttk.Treeview(table_frame, columns=columns, show="tree headings", selectmode="browse")
        self.ctrl_tree.heading("#0", text="Cliente / Commessa / Attività")
        self.ctrl_tree.heading("status", text="Stato")
        self.ctrl_tree.heading("start_date", text="Inizio")
        self.ctrl_tree.heading("end_date", text="Fine")
        self.ctrl_tree.heading("working_days", text="Gg lav.")
        self.ctrl_tree.heading("remaining_days", text="Gg rest.")
        self.ctrl_tree.heading("planned_hours", text="Ore pianif.")
        self.ctrl_tree.heading("actual_hours", text="Ore effett.")
        self.ctrl_tree.heading("hours_diff", text="Diff. ore")
        self.ctrl_tree.heading("budget", text="Budget €")
        self.ctrl_tree.heading("actual_cost", text="Costo €")
        self.ctrl_tree.heading("budget_remaining", text="Budget rest. €")
        self.ctrl_tree.heading("user", text="Utente")
        self.ctrl_tree.heading("date", text="Data")
        self.ctrl_tree.heading("note", text="Note")
        
        self.ctrl_tree.column("#0", width=250, anchor="w")
        self.ctrl_tree.column("status", width=80, anchor="center")
        self.ctrl_tree.column("start_date", width=80, anchor="center")
        self.ctrl_tree.column("end_date", width=80, anchor="center")
        self.ctrl_tree.column("working_days", width=80, anchor="e")
        self.ctrl_tree.column("remaining_days", width=80, anchor="e")
        self.ctrl_tree.column("planned_hours", width=90, anchor="e")
        self.ctrl_tree.column("actual_hours", width=90, anchor="e")
        self.ctrl_tree.column("hours_diff", width=90, anchor="e")
        self.ctrl_tree.column("budget", width=90, anchor="e")
        self.ctrl_tree.column("actual_cost", width=90, anchor="e")
        self.ctrl_tree.column("budget_remaining", width=110, anchor="e")
        self.ctrl_tree.column("user", width=100, anchor="w")
        self.ctrl_tree.column("date", width=80, anchor="center")
        self.ctrl_tree.column("note", width=150, anchor="w")
        
        self.ctrl_tree.grid(row=0, column=0, sticky="nsew")

        # Tag per colorare i diversi livelli (rimuovo bold dal cliente)
        self.ctrl_tree.tag_configure("client", foreground="#1565c0")
        self.ctrl_tree.tag_configure("project", foreground="#1976d2")
        self.ctrl_tree.tag_configure("activity", foreground="#388e3c")
        self.ctrl_tree.tag_configure("timesheet", foreground="#666666")
        self.ctrl_tree.tag_configure("closed", foreground="#999999")  # Commesse chiuse

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.ctrl_tree.yview)
        self.ctrl_tree.configure(yscrollcommand=scroll_y.set)
        scroll_y.grid(row=0, column=1, sticky="ns")
        
        scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.ctrl_tree.xview)
        self.ctrl_tree.configure(xscrollcommand=scroll_x.set)
        scroll_x.grid(row=1, column=0, sticky="ew")

    def on_control_tree_double_click(self, event) -> None:
        """Gestisce doppio clic sul tree del controllo."""
        selection = self.ctrl_tree.selection()
        if not selection:
            return
        
        item_id = selection[0]
        
        # Espande o collassa l'elemento
        if self.ctrl_tree.get_children(item_id):
            current_state = self.ctrl_tree.item(item_id, "open")
            self.ctrl_tree.item(item_id, open=not current_state)

    def refresh_control_panel(self) -> None:
        if not hasattr(self, "ctrl_tree"):
            return

        for item in self.ctrl_tree.get_children():
            self.ctrl_tree.delete(item)

        data = self.db.get_hierarchical_timesheet_data()
        
        for client in data:
            # Formatta date per il cliente
            client_start = self._format_date_short(client["start_date"]) if client["start_date"] else ""
            client_end = self._format_date_short(client["end_date"]) if client["end_date"] else ""
            
            # Indicatori per il cliente
            client_days_text = self._format_remaining_days(client["remaining_days"], client["start_date"], client["end_date"])
            client_hours_text = self._format_hours_diff(client["hours_diff"], client["planned_hours"])
            client_budget_text = self._format_budget_remaining(client["budget_remaining"], client["budget"])
            
            # Inserisci il cliente
            client_id = f"client_{client['id']}"
            self.ctrl_tree.insert(
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
                project_start = self._format_date_short(project["start_date"]) if project["start_date"] else ""
                project_end = self._format_date_short(project["end_date"]) if project["end_date"] else ""
                
                # Indicatori per la commessa
                project_days_text = self._format_remaining_days(project["remaining_days"], project["start_date"], project["end_date"])
                project_hours_text = self._format_hours_diff(project["hours_diff"], project["planned_hours"])
                project_budget_text = self._format_budget_remaining(project["budget_remaining"], project["budget"])
                
                # Tag: se commessa chiusa, usa tag apposito
                project_tags = ("closed",) if project.get("status") == "chiusa" else ("project",)
                project_status = "✗ Chiusa" if project.get("status") == "chiusa" else "✓ Aperta" if project.get("status") else ""
                
                # Inserisci la commessa sotto il cliente
                project_id = f"project_{project['id']}"
                self.ctrl_tree.insert(
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
                    activity_start = self._format_date_short(activity["start_date"]) if activity["start_date"] else ""
                    activity_end = self._format_date_short(activity["end_date"]) if activity["end_date"] else ""
                    
                    # Indicatori per l'attività
                    activity_days_text = self._format_remaining_days(activity.get("remaining_days", 0), activity["start_date"], activity["end_date"])
                    activity_hours_text = self._format_hours_diff(activity.get("hours_diff", 0), activity.get("planned_hours", 0))
                    activity_budget_text = self._format_budget_remaining(activity.get("budget_remaining", 0), activity.get("budget", 0))
                    
                    # Tag: se attività chiusa, usa tag apposito
                    activity_tags = ("closed",) if activity.get("status") == "chiusa" else ("activity",)
                    activity_status = "✗ Chiusa" if activity.get("status") == "chiusa" else "✓ Aperta" if activity.get("status") else ""
                    
                    # Inserisci l'attività sotto la commessa
                    activity_id = f"activity_{activity['id']}"
                    self.ctrl_tree.insert(
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
                        work_date_display = self._format_date_short(ts["work_date"])
                        
                        timesheet_id = f"timesheet_{ts['id']}"
                        self.ctrl_tree.insert(
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
    
    def _format_date_short(self, date_str: str) -> str:
        """Formatta data da YYYY-MM-DD a DD/MM."""
        if not date_str:
            return ""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%d/%m")
        except:
            return date_str
    
    def _format_remaining_days(self, days: int, start_date: str, end_date: str) -> str:
        """Formatta giorni restanti con indicatori."""
        if not start_date or not end_date:
            return ""
        
        # Calcola il periodo totale per la soglia del 10%
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            total_days = (end - start).days
            threshold_10 = total_days * 0.1
        except:
            total_days = 0
            threshold_10 = 0
        
        if days < 0:
            return f"❌ {days}"
        elif days <= threshold_10 and total_days > 0:
            return f"⚠️ {days}"
        else:
            return str(days)
    
    def _format_hours_diff(self, diff: float, planned: float) -> str:
        """Formatta differenza ore con indicatori."""
        if planned == 0:
            return ""
        
        threshold_10 = planned * 0.1
        
        if diff < 0:
            return f"❌ {diff:.1f}"
        elif diff <= threshold_10:
            return f"⚠️ {diff:.1f}"
        else:
            return f"{diff:.1f}"
    
    def _format_budget_remaining(self, remaining: float, budget: float) -> str:
        """Formatta budget restante con indicatori."""
        if budget == 0:
            return ""
        
        threshold_10 = budget * 0.1
        
        if remaining < 0:
            return f"❌ {remaining:.2f}"
        elif remaining <= threshold_10:
            return f"⚠️ {remaining:.2f}"
        else:
            return f"{remaining:.2f}"

    def build_users_tab(self) -> None:
        self.tab_users.grid_columnconfigure(0, weight=1)
        self.tab_users.grid_rowconfigure(3, weight=1)

        if not self.is_admin:
            ctk.CTkLabel(
                self.tab_users,
                text="Sezione riservata admin.",
                font=ctk.CTkFont(size=18, weight="bold"),
            ).pack(pady=40)
            return

        # Variabile per tracciare se stiamo modificando un utente
        self.editing_user_id = None
        
        form = ctk.CTkFrame(self.tab_users)
        form.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        for i in range(5):
            form.grid_columnconfigure(i, weight=1)

        ctk.CTkLabel(form, text="Username").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        self.new_user_username_entry = ctk.CTkEntry(form)
        self.new_user_username_entry.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Nome completo").grid(row=0, column=1, padx=8, pady=4, sticky="w")
        self.new_user_fullname_entry = ctk.CTkEntry(form)
        self.new_user_fullname_entry.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

        ctk.CTkLabel(form, text="Ruolo").grid(row=0, column=2, padx=8, pady=4, sticky="w")
        self.new_user_role_combo = ctk.CTkComboBox(form, values=["user", "admin"], state="readonly")
        self.new_user_role_combo.grid(row=1, column=2, padx=8, pady=4, sticky="ew")
        self.new_user_role_combo.set("user")

        ctk.CTkLabel(form, text="Password (solo per nuovo)").grid(row=0, column=3, padx=8, pady=4, sticky="w")
        self.new_user_password_entry = ctk.CTkEntry(form)
        self.new_user_password_entry.grid(row=1, column=3, padx=8, pady=4, sticky="ew")

        self.save_user_button = ctk.CTkButton(form, text="Crea utente", command=self.save_user)
        self.save_user_button.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

        # Permessi tab (solo per ruolo user)
        tabs_frame = ctk.CTkFrame(self.tab_users)
        tabs_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="ew")
        
        ctk.CTkLabel(tabs_frame, text="Tab visibili utente selezionato:", font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=(10, 20), pady=8
        )
        
        self.tab_calendar_var = tk.BooleanVar(value=True)
        self.tab_master_var = tk.BooleanVar(value=True)
        self.tab_control_var = tk.BooleanVar(value=True)
        
        ctk.CTkCheckBox(tabs_frame, text="Calendario Ore", variable=self.tab_calendar_var).pack(side="left", padx=8, pady=8)
        ctk.CTkCheckBox(tabs_frame, text="Gestione Commesse", variable=self.tab_master_var).pack(side="left", padx=8, pady=8)
        ctk.CTkCheckBox(tabs_frame, text="Controllo Programmazione", variable=self.tab_control_var).pack(side="left", padx=8, pady=8)
        
        ctk.CTkButton(tabs_frame, text="Salva permessi", command=self.save_user_tabs).pack(side="left", padx=20, pady=8)

        actions = ctk.CTkFrame(self.tab_users)
        actions.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="ew")

        ctk.CTkButton(actions, text="Modifica utente", command=self.load_user_for_edit).pack(side="left", padx=(10, 6), pady=8)
        ctk.CTkButton(actions, text="Annulla modifica", command=self.cancel_user_edit).pack(side="left", padx=6, pady=8)
        ctk.CTkLabel(actions, text="Nuova password utente selezionato").pack(side="left", padx=(20, 6), pady=8)
        self.reset_password_entry = ctk.CTkEntry(actions, width=200)
        self.reset_password_entry.pack(side="left", padx=6, pady=8)
        ctk.CTkButton(actions, text="Reset password", command=self.reset_selected_password).pack(side="left", padx=6, pady=8)
        ctk.CTkButton(actions, text="Attiva/Disattiva", command=self.toggle_selected_user).pack(side="left", padx=6, pady=8)
        ctk.CTkButton(actions, text="Aggiorna", command=self.refresh_users_data).pack(side="left", padx=6, pady=8)

        table = ctk.CTkFrame(self.tab_users)
        table.grid(row=3, column=0, padx=8, pady=(0, 8), sticky="nsew")
        table.grid_rowconfigure(0, weight=1)
        table.grid_columnconfigure(0, weight=1)

        columns = ("id", "username", "fullname", "role", "active")
        self.users_tree = ttk.Treeview(table, columns=columns, show="headings", selectmode="browse")
        self.users_tree.heading("id", text="ID")
        self.users_tree.heading("username", text="Username")
        self.users_tree.heading("fullname", text="Nome")
        self.users_tree.heading("role", text="Ruolo")
        self.users_tree.heading("active", text="Attivo")
        self.users_tree.column("id", width=70, anchor="center")
        self.users_tree.column("username", width=120, anchor="w")
        self.users_tree.column("fullname", width=220, anchor="w")
        self.users_tree.column("role", width=90, anchor="center")
        self.users_tree.column("active", width=90, anchor="center")
        self.users_tree.grid(row=0, column=0, sticky="nsew")
        
        # Bind per popolare i checkbox tab quando si seleziona un utente
        self.users_tree.bind("<<TreeviewSelect>>", self.on_user_select)

        scroll = ttk.Scrollbar(table, orient="vertical", command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

    def on_user_select(self, _event: object) -> None:
        """Popola i checkbox tab quando un utente viene selezionato."""
        selected_items = self.users_tree.selection()
        if not selected_items:
            return
        
        user_id = int(selected_items[0])
        users = self.db.list_users(include_inactive=True)
        selected_user = next((u for u in users if u["id"] == user_id), None)
        
        if selected_user:
            self.tab_calendar_var.set(bool(selected_user.get("tab_calendar", 1)))
            self.tab_master_var.set(bool(selected_user.get("tab_master", 1)))
            self.tab_control_var.set(bool(selected_user.get("tab_control", 1)))

    def save_user_tabs(self) -> None:
        """Salva i permessi tab per l'utente selezionato."""
        selected_items = self.users_tree.selection()
        if not selected_items:
            messagebox.showinfo("Utenti", "Seleziona un utente dall'elenco.")
            return
        
        user_id = int(selected_items[0])
        
        try:
            self.db.update_user_tabs(
                user_id,
                self.tab_calendar_var.get(),
                self.tab_master_var.get(),
                1,
                self.tab_control_var.get()
            )
            messagebox.showinfo("Utenti", "Permessi aggiornati. L'utente deve rifare il login per applicare le modifiche.")
            self.refresh_users_data()
        except Exception as exc:
            messagebox.showerror("Utenti", f"Errore: {exc}")

    def refresh_users_data(self) -> None:
        users = self.db.list_users(include_inactive=True)
        # Programmazione e Controllo: rimosso filtro utente, non più necessario

        if hasattr(self, "users_tree"):
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            for user in users:
                self.users_tree.insert(
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

    def save_user(self) -> None:
        """Salva utente (crea nuovo o modifica esistente)."""
        try:
            username = self.new_user_username_entry.get().strip()
            full_name = self.new_user_fullname_entry.get().strip()
            role = self.new_user_role_combo.get().strip()
            password = self.new_user_password_entry.get().strip()
            
            if not username or not full_name:
                raise ValueError("Compila username e nome.")
            if role not in {"admin", "user"}:
                raise ValueError("Ruolo non valido.")
            
            if self.editing_user_id is None:
                # Modalità creazione
                if not password:
                    raise ValueError("Compila la password per il nuovo utente.")
                
                # Per gli admin tutte le tab sono sempre visibili, per i user usa i checkbox
                if role == "admin":
                    self.db.create_user(username, full_name, role, password, True, True, True, True)
                else:
                    self.db.create_user(
                        username, full_name, role, password,
                        self.tab_calendar_var.get(),
                        self.tab_master_var.get(),
                        1,
                        self.tab_control_var.get()
                    )
                messagebox.showinfo("Utenti", "Utente creato con successo.")
            else:
                # Modalità modifica
                if role == "admin":
                    self.db.update_user(self.editing_user_id, username, full_name, role, True, True, True, True)
                else:
                    self.db.update_user(
                        self.editing_user_id, username, full_name, role,
                        self.tab_calendar_var.get(),
                        self.tab_master_var.get(),
                        1,
                        self.tab_control_var.get()
                    )
                messagebox.showinfo("Utenti", "Utente modificato con successo.")
                
        except (ValueError, sqlite3.IntegrityError) as exc:
            messagebox.showerror("Utenti", str(exc))
            return

        self.cancel_user_edit()
        self.refresh_users_data()
        self.refresh_day_entries()
        self.refresh_schedule_list()
    
    def load_user_for_edit(self) -> None:
        """Carica i dati dell'utente selezionato nel form per la modifica."""
        selected_items = self.users_tree.selection()
        if not selected_items:
            messagebox.showinfo("Utenti", "Seleziona un utente dall'elenco.")
            return
        
        user_id = int(selected_items[0])
        users = self.db.list_users(include_inactive=True)
        selected_user = next((u for u in users if u["id"] == user_id), None)
        
        if not selected_user:
            return
        
        # Imposta modalità modifica
        self.editing_user_id = user_id
        
        # Popola il form
        self.new_user_username_entry.delete(0, "end")
        self.new_user_username_entry.insert(0, selected_user["username"])
        
        self.new_user_fullname_entry.delete(0, "end")
        self.new_user_fullname_entry.insert(0, selected_user["full_name"])
        
        self.new_user_role_combo.set(selected_user["role"])
        
        self.new_user_password_entry.delete(0, "end")
        
        # Aggiorna checkbox
        self.tab_calendar_var.set(bool(selected_user.get("tab_calendar", 1)))
        self.tab_master_var.set(bool(selected_user.get("tab_master", 1)))
        self.tab_control_var.set(bool(selected_user.get("tab_control", 1)))
        
        # Cambia etichetta pulsante
        self.save_user_button.configure(text="Salva modifiche")
    
    def cancel_user_edit(self) -> None:
        """Annulla la modalità modifica e pulisce il form."""
        self.editing_user_id = None
        self.new_user_username_entry.delete(0, "end")
        self.new_user_fullname_entry.delete(0, "end")
        self.new_user_password_entry.delete(0, "end")
        self.new_user_role_combo.set("user")
        self.save_user_button.configure(text="Crea utente")
        
        # Reset checkbox a default
        self.tab_calendar_var.set(True)
        self.tab_master_var.set(True)
        self.tab_control_var.set(True)

    def toggle_selected_user(self) -> None:
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Utenti", "Seleziona un utente.")
            return

        user_id = int(selection[0])
        if user_id == int(self.current_user["id"]):
            messagebox.showwarning("Utenti", "Non puoi disattivare il tuo utente.")
            return

        user_row = [u for u in self.db.list_users(include_inactive=True) if int(u["id"]) == user_id]
        if not user_row:
            return
        current_state = bool(user_row[0]["active"])
        self.db.set_user_active(user_id, not current_state)
        self.refresh_users_data()

    def reset_selected_password(self) -> None:
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Utenti", "Seleziona un utente.")
            return
        new_password = self.reset_password_entry.get().strip()
        if not new_password:
            messagebox.showwarning("Utenti", "Inserisci la nuova password.")
            return

        user_id = int(selection[0])
        self.db.reset_user_password(user_id, new_password)
        self.reset_password_entry.delete(0, "end")
        messagebox.showinfo("Utenti", "Password aggiornata.")

    def show_pdf_report_dialog(self) -> None:
        """Apre finestra di dialogo per selezionare e generare report PDF."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Genera Report PDF")
        dialog.geometry("600x700")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        
        # Container principale con scrollbar
        main_container = ctk.CTkScrollableFrame(dialog)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Titolo
        ctk.CTkLabel(
            main_container, 
            text="Generazione Report PDF", 
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(0, 20))
        
        # Selezione tipo report
        report_frame = ctk.CTkFrame(main_container)
        report_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(report_frame, text="Tipo Report:", font=ctk.CTkFont(size=14, weight="bold")).pack(
            anchor="w", padx=10, pady=(10, 5)
        )
        
        report_types = [
            "Programmazione Singola",
            "Report Cliente",
            "Report Commessa",
            "Report Periodo",
            "Report Utente",
            "Report Generale"
        ]
        
        report_type_var = ctk.StringVar(value=report_types[0])
        report_combo = ctk.CTkComboBox(
            report_frame,
            variable=report_type_var,
            values=report_types,
            width=500,
            state="readonly"
        )
        report_combo.pack(padx=10, pady=(0, 10))
        
        # Frame per filtri dinamici
        filters_frame = ctk.CTkFrame(main_container)
        filters_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Widgets che cambiano in base al tipo di report
        filter_widgets = {}
        
        def update_filters(*args):
            """Aggiorna i filtri visualizzati in base al tipo di report selezionato."""
            # Pulisci frame
            for widget in filters_frame.winfo_children():
                widget.destroy()
            filter_widgets.clear()
            
            selected_type = report_type_var.get()
            
            ctk.CTkLabel(
                filters_frame, 
                text="Filtri:", 
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(anchor="w", padx=10, pady=(10, 10))
            
            # Programmazione Singola - Selezione programmazione
            if selected_type == "Programmazione Singola":
                schedules = self.db.list_schedules()
                schedule_options = [
                    f"{s['id']} - {s['client_name']} / {s['project_name']} / {s['activity_name']}"
                    for s in schedules
                ]
                
                ctk.CTkLabel(filters_frame, text="Programmazione:").pack(anchor="w", padx=10, pady=(5, 2))
                schedule_combo = ctk.CTkComboBox(
                    filters_frame,
                    values=schedule_options if schedule_options else ["Nessuna programmazione disponibile"],
                    width=500,
                    state="readonly"
                )
                schedule_combo.pack(padx=10, pady=(0, 10))
                if schedule_options:
                    schedule_combo.set(schedule_options[0])
                filter_widgets['schedule'] = schedule_combo
            
            # Report Cliente
            elif selected_type == "Report Cliente":
                clients = self.db.list_clients()
                client_options = [f"{c['id']} - {c['name']}" for c in clients]
                
                ctk.CTkLabel(filters_frame, text="Cliente:").pack(anchor="w", padx=10, pady=(5, 2))
                client_combo = ctk.CTkComboBox(
                    filters_frame,
                    values=client_options if client_options else ["Nessun cliente disponibile"],
                    width=500,
                    state="readonly"
                )
                client_combo.pack(padx=10, pady=(0, 10))
                if client_options:
                    client_combo.set(client_options[0])
                filter_widgets['client'] = client_combo
                
                # Periodo opzionale
                ctk.CTkLabel(filters_frame, text="Periodo (opzionale):").pack(anchor="w", padx=10, pady=(10, 2))
                
                date_frame = ctk.CTkFrame(filters_frame)
                date_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(date_frame, text="Da:").pack(side="left", padx=(10, 5))
                start_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                start_entry.pack(side="left", padx=5)
                
                ctk.CTkLabel(date_frame, text="A:").pack(side="left", padx=(10, 5))
                end_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                end_entry.pack(side="left", padx=5)
                
                filter_widgets['start_date'] = start_entry
                filter_widgets['end_date'] = end_entry
            
            # Report Commessa
            elif selected_type == "Report Commessa":
                projects = self.db.list_projects()
                project_options = [
                    f"{p['id']} - {p['client_name']} / {p['name']}"
                    for p in projects
                ]
                
                ctk.CTkLabel(filters_frame, text="Commessa:").pack(anchor="w", padx=10, pady=(5, 2))
                project_combo = ctk.CTkComboBox(
                    filters_frame,
                    values=project_options if project_options else ["Nessuna commessa disponibile"],
                    width=500,
                    state="readonly"
                )
                project_combo.pack(padx=10, pady=(0, 10))
                if project_options:
                    project_combo.set(project_options[0])
                filter_widgets['project'] = project_combo
            
            # Report Periodo
            elif selected_type == "Report Periodo":
                ctk.CTkLabel(filters_frame, text="Periodo:").pack(anchor="w", padx=10, pady=(5, 2))
                
                date_frame = ctk.CTkFrame(filters_frame)
                date_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(date_frame, text="Da:").pack(side="left", padx=(10, 5))
                start_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                start_entry.pack(side="left", padx=5)
                
                ctk.CTkLabel(date_frame, text="A:").pack(side="left", padx=(10, 5))
                end_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                end_entry.pack(side="left", padx=5)
                
                filter_widgets['start_date'] = start_entry
                filter_widgets['end_date'] = end_entry
                
                # Filtri opzionali
                ctk.CTkLabel(filters_frame, text="Filtri aggiuntivi (opzionali):").pack(anchor="w", padx=10, pady=(10, 2))
                
                # Cliente
                clients = self.db.list_clients()
                client_options = ["Tutti i clienti"] + [f"{c['id']} - {c['name']}" for c in clients]
                
                ctk.CTkLabel(filters_frame, text="Cliente:").pack(anchor="w", padx=10, pady=(5, 2))
                client_combo = ctk.CTkComboBox(filters_frame, values=client_options, width=500, state="readonly")
                client_combo.set(client_options[0])
                client_combo.pack(padx=10, pady=(0, 10))
                filter_widgets['period_client'] = client_combo
                
                # Commessa
                projects = self.db.list_projects()
                project_options = ["Tutte le commesse"] + [
                    f"{p['id']} - {p['client_name']} / {p['name']}"
                    for p in projects
                ]
                
                ctk.CTkLabel(filters_frame, text="Commessa:").pack(anchor="w", padx=10, pady=(5, 2))
                project_combo = ctk.CTkComboBox(filters_frame, values=project_options, width=500, state="readonly")
                project_combo.set(project_options[0])
                project_combo.pack(padx=10, pady=(0, 10))
                filter_widgets['period_project'] = project_combo
                
                # Utente
                users = self.db.list_users()
                user_options = ["Tutti gli utenti"] + [f"{u['id']} - {u['full_name']}" for u in users]
                
                ctk.CTkLabel(filters_frame, text="Utente:").pack(anchor="w", padx=10, pady=(5, 2))
                user_combo = ctk.CTkComboBox(filters_frame, values=user_options, width=500, state="readonly")
                user_combo.set(user_options[0])
                user_combo.pack(padx=10, pady=(0, 10))
                filter_widgets['period_user'] = user_combo
            
            # Report Utente
            elif selected_type == "Report Utente":
                users = self.db.list_users()
                user_options = [f"{u['id']} - {u['full_name']}" for u in users]
                
                ctk.CTkLabel(filters_frame, text="Utente:").pack(anchor="w", padx=10, pady=(5, 2))
                user_combo = ctk.CTkComboBox(
                    filters_frame,
                    values=user_options if user_options else ["Nessun utente disponibile"],
                    width=500,
                    state="readonly"
                )
                user_combo.pack(padx=10, pady=(0, 10))
                if user_options:
                    user_combo.set(user_options[0])
                filter_widgets['user'] = user_combo
                
                # Periodo
                ctk.CTkLabel(filters_frame, text="Periodo:").pack(anchor="w", padx=10, pady=(10, 2))
                
                date_frame = ctk.CTkFrame(filters_frame)
                date_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(date_frame, text="Da:").pack(side="left", padx=(10, 5))
                start_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                start_entry.pack(side="left", padx=5)
                
                ctk.CTkLabel(date_frame, text="A:").pack(side="left", padx=(10, 5))
                end_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                end_entry.pack(side="left", padx=5)
                
                filter_widgets['start_date'] = start_entry
                filter_widgets['end_date'] = end_entry
            
            # Report Generale
            elif selected_type == "Report Generale":
                ctk.CTkLabel(
                    filters_frame, 
                    text="Il report generale mostra una panoramica completa di tutte le programmazioni.",
                    wraplength=500
                ).pack(padx=10, pady=10)
                
                # Periodo opzionale
                ctk.CTkLabel(filters_frame, text="Periodo (opzionale - lasciare vuoto per tutte):").pack(
                    anchor="w", padx=10, pady=(10, 2)
                )
                
                date_frame = ctk.CTkFrame(filters_frame)
                date_frame.pack(fill="x", padx=10, pady=5)
                
                ctk.CTkLabel(date_frame, text="Da:").pack(side="left", padx=(10, 5))
                start_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                start_entry.pack(side="left", padx=5)
                
                ctk.CTkLabel(date_frame, text="A:").pack(side="left", padx=(10, 5))
                end_entry = ctk.CTkEntry(date_frame, placeholder_text="YYYY-MM-DD", width=120)
                end_entry.pack(side="left", padx=5)
                
                filter_widgets['start_date'] = start_entry
                filter_widgets['end_date'] = end_entry
        
        # Bind per cambiamento tipo report
        report_type_var.trace_add("write", update_filters)
        update_filters()  # Inizializza filtri
        
        # Pulsanti azione
        button_frame = ctk.CTkFrame(dialog)
        button_frame.pack(fill="x", padx=10, pady=10)
        
        def generate_pdf():
            """Genera il PDF in base alla selezione."""
            try:
                selected_type = report_type_var.get()
                generator = PDFReportGenerator()
                
                # Programmazione Singola
                if selected_type == "Programmazione Singola":
                    schedule_id = self._id_from_option(filter_widgets['schedule'].get())
                    if not schedule_id:
                        messagebox.showerror("Errore", "Seleziona una programmazione valida.")
                        return
                    
                    data = self.db.get_schedule_report_data(schedule_id)
                    output_path = generator.generate_schedule_report(data)
                
                # Report Cliente
                elif selected_type == "Report Cliente":
                    client_id = self._id_from_option(filter_widgets['client'].get())
                    if not client_id:
                        messagebox.showerror("Errore", "Seleziona un cliente valido.")
                        return
                    
                    start_date = filter_widgets['start_date'].get().strip() or None
                    end_date = filter_widgets['end_date'].get().strip() or None
                    dates = (start_date, end_date) if start_date and end_date else None
                    
                    data = self.db.get_report_client_data(client_id, dates)
                    output_path = generator.generate_client_report(data)
                
                # Report Commessa
                elif selected_type == "Report Commessa":
                    project_id = self._id_from_option(filter_widgets['project'].get())
                    if not project_id:
                        messagebox.showerror("Errore", "Seleziona una commessa valida.")
                        return
                    
                    data = self.db.get_report_project_data(project_id)
                    output_path = generator.generate_project_report(data)
                
                # Report Periodo
                elif selected_type == "Report Periodo":
                    start_date = filter_widgets['start_date'].get().strip()
                    end_date = filter_widgets['end_date'].get().strip()
                    
                    if not start_date or not end_date:
                        messagebox.showerror("Errore", "Inserisci periodo valido (da - a).")
                        return
                    
                    # Filtri opzionali
                    filters = {}
                    
                    client_val = filter_widgets['period_client'].get()
                    if not client_val.startswith("Tutti"):
                        filters['client_id'] = self._id_from_option(client_val)
                    
                    project_val = filter_widgets['period_project'].get()
                    if not project_val.startswith("Tutte"):
                        filters['project_id'] = self._id_from_option(project_val)
                    
                    user_val = filter_widgets['period_user'].get()
                    if not user_val.startswith("Tutti"):
                        filters['user_id'] = self._id_from_option(user_val)
                    
                    data = self.db.get_report_period_data(start_date, end_date, filters)
                    output_path = generator.generate_period_report(data)
                
                # Report Utente
                elif selected_type == "Report Utente":
                    user_id = self._id_from_option(filter_widgets['user'].get())
                    if not user_id:
                        messagebox.showerror("Errore", "Seleziona un utente valido.")
                        return
                    
                    start_date = filter_widgets['start_date'].get().strip()
                    end_date = filter_widgets['end_date'].get().strip()
                    
                    if not start_date or not end_date:
                        messagebox.showerror("Errore", "Inserisci periodo valido (da - a).")
                        return
                    
                    data = self.db.get_report_user_data(user_id, (start_date, end_date))
                    output_path = generator.generate_user_report(data)
                
                # Report Generale
                elif selected_type == "Report Generale":
                    start_date = filter_widgets['start_date'].get().strip() or None
                    end_date = filter_widgets['end_date'].get().strip() or None
                    dates = (start_date, end_date) if start_date and end_date else None
                    
                    data = self.db.get_report_general_data(dates)
                    output_path = generator.generate_general_report(data)
                
                # Successo
                messagebox.showinfo(
                    "Report Generato",
                    f"Report PDF generato con successo:\n{output_path.name}\n\nCartella: {output_path.parent}"
                )
                dialog.destroy()
                
            except Exception as e:
                messagebox.showerror("Errore", f"Errore durante la generazione del report:\n{str(e)}")
        
        ctk.CTkButton(
            button_frame,
            text="Genera PDF",
            command=generate_pdf,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=(10, 5), pady=10)
        
        ctk.CTkButton(
            button_frame,
            text="Annulla",
            command=dialog.destroy,
            width=100,
            height=40
        ).pack(side="left", padx=5, pady=10)

    def on_close(self) -> None:
        if self.backup_job_id:
            try:
                self.after_cancel(self.backup_job_id)
            except Exception:
                pass
            self.backup_job_id = None
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = TimesheetApp()
    app.mainloop()
