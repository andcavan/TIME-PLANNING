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

from db import AUTO_BACKUP_INTERVAL_MINUTES, CFG_DIR, Database
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
        
        # Inizializza cache per filtri di ricerca
        self._projects_data = []
        self._activities_data = []
        
        # Tracking per ordinamento colonne
        self._projects_sort_col = None
        self._projects_sort_reverse = False
        self._activities_sort_col = None
        self._activities_sort_reverse = False

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
        _last_user_file = CFG_DIR / "last_user.txt"
        _last_user = _last_user_file.read_text(encoding="utf-8").strip() if _last_user_file.exists() else "admin"
        self.login_username_entry.insert(0, _last_user)

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
        try:
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            (CFG_DIR / "last_user.txt").write_text(username, encoding="utf-8")
        except Exception:
            pass
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
            form, state="readonly", command=self.on_timesheet_client_change, width=300, values=[""]
        )
        self.ts_client_combo.grid(row=1, column=1, padx=10, pady=4, sticky="w")

        ctk.CTkLabel(form, text="Commessa").grid(row=2, column=0, padx=10, pady=4, sticky="w")
        self.ts_project_combo = ctk.CTkComboBox(
            form, state="readonly", command=self.on_timesheet_project_change, width=300, values=[""]
        )
        self.ts_project_combo.grid(row=2, column=1, padx=10, pady=4, sticky="w")

        ctk.CTkLabel(form, text="Attivita").grid(row=3, column=0, padx=10, pady=4, sticky="w")
        self.ts_activity_combo = ctk.CTkComboBox(form, state="readonly", width=300, values=[""])
        self.ts_activity_combo.grid(row=3, column=1, padx=10, pady=4, sticky="w")

        ctk.CTkLabel(form, text="Ore").grid(row=4, column=0, padx=10, pady=4, sticky="w")
        self.ts_hours_entry = ctk.CTkEntry(form, width=150)
        self.ts_hours_entry.grid(row=4, column=1, padx=10, pady=4, sticky="w")

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
        
        # Carica solo commesse del cliente selezionato che sono già iniziate (filtrando per utente se non admin)
        if client_id:
            user_id = None if self.is_admin else int(self.current_user["id"])
            today = date.today().isoformat()
            projects = self.db.list_projects(client_id, only_with_open_schedules=True, user_id=user_id, available_from_date=today)
            values = [""] + [self._project_option(row) for row in projects]  # "" come prima opzione
            self._set_combo_values(self.ts_project_combo, values)
            self.ts_project_combo.set("")  # Forza selezione vuota
        else:
            self._set_combo_values(self.ts_project_combo, [""])
        
        # Pulisci attività
        self._set_combo_values(self.ts_activity_combo, [""])

    def on_timesheet_project_change(self, _value: str) -> None:
        project_id = self._id_from_option(self.ts_project_combo.get())
        
        # Carica solo attività della commessa selezionata che sono già iniziate
        if project_id:
            today = date.today().isoformat()
            activities = self.db.list_activities(project_id, only_with_open_schedules=True, available_from_date=today)
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
        """Tab semplificata con elenchi commesse e attività affiancati."""
        main_container = ctk.CTkFrame(self.tab_master)
        main_container.pack(fill="both", expand=True, padx=8, pady=8)
        
        # ========== SEZIONE 1: SELEZIONE CLIENTE (fissa in alto) ==========
        selection_frame = ctk.CTkFrame(main_container)
        selection_frame.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(selection_frame, text="Cliente:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(10, 5), pady=10, sticky="w"
        )
        self.pm_client_combo = ctk.CTkComboBox(
            selection_frame, state="readonly", command=self.on_pm_client_change, values=[""], width=250
        )
        self.pm_client_combo.grid(row=0, column=1, padx=5, pady=10, sticky="w")
        
        ctk.CTkButton(
            selection_frame, text="🔧 Gestione Clienti", width=150, 
            command=self.open_clients_management
        ).grid(row=0, column=2, padx=(5, 10), pady=10, sticky="w")
        
        # ========== SEZIONE 2: ELENCHI AFFIANCATI (Commesse | Attività) ==========
        # Usa PanedWindow per ridimensionamento dinamico
        lists_paned = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        lists_paned.pack(fill="both", expand=True, pady=(0, 8))
        
        # Frame per elenco commesse con PanedWindow verticale
        projects_container = ctk.CTkFrame(lists_paned)
        projects_paned_v = ttk.PanedWindow(projects_container, orient=tk.VERTICAL)
        projects_paned_v.pack(fill="both", expand=True)
        
        # Frame superiore: treeview commesse
        projects_frame = ctk.CTkFrame(projects_paned_v)
        projects_frame.grid_rowconfigure(3, weight=1)
        projects_frame.grid_columnconfigure(0, weight=1)
        
        # Header e pulsanti commesse
        header_projects = ctk.CTkFrame(projects_frame, fg_color="transparent")
        header_projects.grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="ew")
        
        ctk.CTkLabel(
            header_projects, text="Commesse del Cliente", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")
        
        # Pulsanti gestione commesse
        buttons_projects = ctk.CTkFrame(projects_frame, fg_color="transparent")
        buttons_projects.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")
        
        ctk.CTkButton(
            buttons_projects, text="➕ Nuova", width=100,
            command=self.pm_new_project
        ).pack(side="left", padx=(0, 5))
        
        ctk.CTkButton(
            buttons_projects, text="✏️ Modifica", width=100,
            command=self.pm_edit_project
        ).pack(side="left", padx=(0, 10))
        
        # Switch per mostrare commesse chiuse
        ctk.CTkLabel(buttons_projects, text="Mostra chiuse:").pack(side="left", padx=(10, 5))
        self.show_closed_projects = tk.BooleanVar(value=False)
        self.closed_switch = ctk.CTkSwitch(
            buttons_projects, text="", variable=self.show_closed_projects,
            command=self.refresh_projects_tree, width=50
        )
        self.closed_switch.pack(side="left")
        
        # Campo di ricerca per commesse
        search_projects_frame = ctk.CTkFrame(projects_frame, fg_color="transparent")
        search_projects_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=(4, 4), sticky="ew")
        search_projects_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_projects_frame, text="🔍 Filtra:").grid(row=0, column=0, padx=(0, 5))
        self.project_search_var = tk.StringVar()
        self.project_search_var.trace("w", lambda *args: self.filter_projects_tree())
        self.project_search_entry = ctk.CTkEntry(search_projects_frame, textvariable=self.project_search_var, placeholder_text="Cerca commessa...")
        self.project_search_entry.grid(row=0, column=1, sticky="ew")
        
        # Treeview commesse con colonne visibili (aggiunta colonna stato)
        projects_columns = ("stato", "referente", "dates", "hours", "budget")
        self.projects_tree = ttk.Treeview(projects_frame, columns=projects_columns, show="tree headings")
        self.projects_tree.heading("#0", text="Nome Commessa")
        self.projects_tree.heading("stato", text="Stato")
        self.projects_tree.heading("referente", text="Referente")
        self.projects_tree.heading("dates", text="Date (inizio - fine)")
        self.projects_tree.heading("hours", text="Ore pianif.")
        self.projects_tree.heading("budget", text="Budget €")
        
        self.projects_tree.column("#0", width=180, anchor="w")
        self.projects_tree.column("stato", width=70, anchor="center")
        self.projects_tree.column("referente", width=110, anchor="w")
        self.projects_tree.column("dates", width=120, anchor="center")
        self.projects_tree.column("hours", width=75, anchor="e")
        self.projects_tree.column("budget", width=85, anchor="e")
        
        self.projects_tree.grid(row=3, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self.projects_tree.bind("<<TreeviewSelect>>", self.on_pm_projects_tree_select)
        self.projects_tree.bind("<Double-Button-1>", self.on_projects_tree_double_click)
        
        # Abilita ordinamento per le colonne delle commesse
        for col in ["#0"] + list(projects_columns):
            self.projects_tree.heading(col, command=lambda c=col: self.sort_projects_tree(c))
        
        scroll_projects_y = ttk.Scrollbar(projects_frame, orient="vertical", command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=scroll_projects_y.set)
        scroll_projects_y.grid(row=3, column=1, sticky="ns", pady=(0, 8))
        
        # Aggiungi frame treeview al paned window verticale
        projects_paned_v.add(projects_frame, weight=3)
        
        # Box riepilogo commessa selezionata (frame inferiore)
        project_info_frame = ctk.CTkFrame(projects_paned_v)
        
        ctk.CTkLabel(
            project_info_frame, text="📋 Riepilogo Commessa", 
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=8, pady=(8, 4))
        
        self.project_info_text = ctk.CTkTextbox(project_info_frame, height=100, wrap="word")
        self.project_info_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.project_info_text.configure(state="disabled")
        
        # Aggiungi box info al paned window verticale
        projects_paned_v.add(project_info_frame, weight=1)
        
        # Aggiungi il container delle commesse al paned window orizzontale
        lists_paned.add(projects_container, weight=1)
        
        # Frame per elenco attività con PanedWindow verticale
        activities_container = ctk.CTkFrame(lists_paned)
        activities_paned_v = ttk.PanedWindow(activities_container, orient=tk.VERTICAL)
        activities_paned_v.pack(fill="both", expand=True)
        
        # Frame superiore: treeview attività
        activities_frame = ctk.CTkFrame(activities_paned_v)
        activities_frame.grid_rowconfigure(3, weight=1)
        activities_frame.grid_columnconfigure(0, weight=1)
        
        # Header e pulsanti attività
        header_activities = ctk.CTkFrame(activities_frame, fg_color="transparent")
        header_activities.grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="ew")
        
        ctk.CTkLabel(
            header_activities, text="Attività della Commessa", 
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")
        
        # Pulsanti gestione attività
        buttons_activities = ctk.CTkFrame(activities_frame, fg_color="transparent")
        buttons_activities.grid(row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")
        
        self.pm_new_activity_btn = ctk.CTkButton(
            buttons_activities, text="➕ Nuova", width=100,
            command=self.pm_new_activity
        )
        self.pm_new_activity_btn.pack(side="left", padx=(0, 5))
        
        self.pm_edit_activity_btn = ctk.CTkButton(
            buttons_activities, text="✏️ Modifica", width=100,
            command=self.pm_edit_activity_window
        )
        self.pm_edit_activity_btn.pack(side="left")
        
        # Campo di ricerca per attività
        search_activities_frame = ctk.CTkFrame(activities_frame, fg_color="transparent")
        search_activities_frame.grid(row=2, column=0, columnspan=2, padx=8, pady=(4, 4), sticky="ew")
        search_activities_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(search_activities_frame, text="🔍 Filtra:").grid(row=0, column=0, padx=(0, 5))
        self.activity_search_var = tk.StringVar()
        self.activity_search_var.trace("w", lambda *args: self.filter_activities_tree())
        self.activity_search_entry = ctk.CTkEntry(search_activities_frame, textvariable=self.activity_search_var, placeholder_text="Cerca attività...")
        self.activity_search_entry.grid(row=0, column=1, sticky="ew")
        
        # Treeview attività con colonne visibili (senza ore effettive)
        activities_columns = ("dates", "planned_hours", "budget", "rate")
        self.activities_tree = ttk.Treeview(activities_frame, columns=activities_columns, show="tree headings")
        self.activities_tree.heading("#0", text="Nome Attività")
        self.activities_tree.heading("dates", text="Date (inizio - fine)")
        self.activities_tree.heading("planned_hours", text="Ore pianif.")
        self.activities_tree.heading("budget", text="Budget €")
        self.activities_tree.heading("rate", text="Tariffa €/h")
        
        self.activities_tree.column("#0", width=200, anchor="w")
        self.activities_tree.column("dates", width=150, anchor="center")
        self.activities_tree.column("planned_hours", width=90, anchor="e")
        self.activities_tree.column("budget", width=90, anchor="e")
        self.activities_tree.column("rate", width=90, anchor="e")
        
        self.activities_tree.grid(row=3, column=0, sticky="nsew", padx=(8, 0), pady=(0, 8))
        self.activities_tree.bind("<<TreeviewSelect>>", self.on_pm_activities_tree_select)
        self.activities_tree.bind("<Double-Button-1>", self.on_activities_tree_double_click)
        
        # Abilita ordinamento per le colonne delle attività
        for col in ["#0"] + list(activities_columns):
            self.activities_tree.heading(col, command=lambda c=col: self.sort_activities_tree(c))
        
        scroll_activities_y = ttk.Scrollbar(activities_frame, orient="vertical", command=self.activities_tree.yview)
        self.activities_tree.configure(yscrollcommand=scroll_activities_y.set)
        scroll_activities_y.grid(row=3, column=1, sticky="ns", pady=(0, 8))
        
        # Aggiungi frame treeview al paned window verticale
        activities_paned_v.add(activities_frame, weight=3)
        
        # Box riepilogo attività selezionata (frame inferiore)
        activity_info_frame = ctk.CTkFrame(activities_paned_v)
        
        ctk.CTkLabel(
            activity_info_frame, text="📋 Riepilogo Attività", 
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=8, pady=(8, 4))
        
        self.activity_info_text = ctk.CTkTextbox(activity_info_frame, height=80, wrap="word")
        self.activity_info_text.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.activity_info_text.configure(state="disabled")
        
        # Gestione utenti assegnati all'attività
        user_selection_frame = ctk.CTkFrame(activity_info_frame, fg_color="transparent")
        user_selection_frame.pack(fill="both", expand=True, padx=8, pady=(4, 8))
        
        ctk.CTkLabel(user_selection_frame, text="👥 Utenti assegnati:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        
        users_list_frame = ctk.CTkFrame(user_selection_frame, fg_color="transparent")
        users_list_frame.pack(fill="both", expand=True)
        
        self.activity_users_listbox = tk.Listbox(users_list_frame, height=4, selectmode=tk.SINGLE, font=("Arial", 12))
        self.activity_users_listbox.pack(side="left", fill="both", expand=True)
        
        users_scroll = ttk.Scrollbar(users_list_frame, orient="vertical", command=self.activity_users_listbox.yview)
        self.activity_users_listbox.configure(yscrollcommand=users_scroll.set)
        users_scroll.pack(side="left", fill="y")
        
        users_buttons_frame = ctk.CTkFrame(user_selection_frame, fg_color="transparent")
        users_buttons_frame.pack(fill="x", pady=(4, 0))
        
        ctk.CTkButton(users_buttons_frame, text="➕ Aggiungi", width=100, command=self.add_user_to_activity).pack(side="left", padx=(0, 4))
        ctk.CTkButton(users_buttons_frame, text="➖ Rimuovi", width=100, command=self.remove_user_from_activity).pack(side="left")
        
        # Aggiungi box info al paned window verticale
        activities_paned_v.add(activity_info_frame, weight=1)
        
        # Aggiungi il container delle attività al paned window orizzontale
        lists_paned.add(activities_container, weight=1)
        
        # Variabili per tracciare selezioni
        self.selected_project_id = None
        self.selected_activity_id = None
        
        # Inizializza i box informativi
        self.clear_project_info_box()
        self.clear_activity_info_box()

    # ========== GESTIONE COMMESSE: Nuove Funzioni ==========
    
    def on_pm_client_change(self, _value: str) -> None:
        """Aggiorna l'elenco commesse quando cambia il cliente selezionato."""
        self.refresh_projects_tree()
        self.refresh_activities_tree()  # Pulisce attività quando cambia cliente
    
    def refresh_projects_tree(self) -> None:
        """Aggiorna l'elenco delle commesse del cliente selezionato."""
        if not hasattr(self, 'projects_tree'):
            return
        
        # Configura tag per commesse chiuse
        self.projects_tree.tag_configure("closed_project", foreground="gray60")
        
        # Pulisci treeview
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        
        client_id = self._id_from_option(self.pm_client_combo.get())
        if not client_id:
            self._projects_data = []
            return
        
        # Carica commesse del cliente
        projects = self.db.list_projects(client_id)
        schedules = self.db.list_schedules()
        
        # Controlla se mostrare le commesse chiuse
        show_closed = self.show_closed_projects.get() if hasattr(self, 'show_closed_projects') else True
        
        # Salva dati per il filtro
        self._projects_data = []
        
        for project in projects:
            # Trova la schedule del progetto per determinare lo stato
            project_schedule = next((s for s in schedules if s["project_id"] == project["id"] and s["activity_id"] is None), None)
            
            # Verifica se è chiusa: controlla sia schedule che campo closed
            is_closed = False
            if project_schedule:
                # Ha una schedule: usa il suo status
                is_closed = project_schedule.get("status", "aperta") == "chiusa"
            else:
                # Non ha schedule: usa il campo closed
                is_closed = project.get("closed", 0) == 1
            
            # Filtra commesse chiuse se necessario
            if is_closed and not show_closed:
                continue
            
            # Determina lo stato
            stato_text = "Chiusa" if is_closed else "Aperta"
            
            # Cerca pianificazione per la commessa
            dates_text = "--"
            planned_hours = "--"
            budget = "--"
            referente = project.get("referente_commessa", "--") or "--"
            
            if project_schedule:
                start = datetime.strptime(project_schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                end = datetime.strptime(project_schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                dates_text = f"{start} - {end}"
                planned_hours = f"{project_schedule['planned_hours']:.0f}"
                budget = f"{project_schedule.get('budget', 0):.2f}"
            
            values = (stato_text, referente, dates_text, planned_hours, budget)
            tags = ("closed_project",) if is_closed else ()
            
            # Salva i dati
            self._projects_data.append({
                'id': str(project["id"]),
                'text': project["name"],
                'values': values,
                'tags': tags
            })
        
        # Applica il filtro di ricerca se presente
        self.filter_projects_tree()
    
    def refresh_activities_tree(self) -> None:
        """Aggiorna l'elenco delle attività della commessa selezionata."""
        if not hasattr(self, 'activities_tree'):
            return
        
        # Pulisci treeview
        for item in self.activities_tree.get_children():
            self.activities_tree.delete(item)
        
        if not self.selected_project_id:
            self._activities_data = []
            return
        
        # Carica attività della commessa
        activities = self.db.list_activities(self.selected_project_id)
        schedules = self.db.list_schedules()
        
        # Salva dati per il filtro
        self._activities_data = []
        
        for activity in activities:
            # Cerca pianificazione per l'attività
            dates_text = "--"
            planned_hours = "--"
            budget = "--"
            
            for sched in schedules:
                if sched["project_id"] == self.selected_project_id and sched["activity_id"] == activity["id"]:
                    start = datetime.strptime(sched["start_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                    end = datetime.strptime(sched["end_date"], "%Y-%m-%d").strftime("%d/%m/%y")
                    dates_text = f"{start} - {end}"
                    planned_hours = f"{sched['planned_hours']:.1f}"
                    budget = f"{sched.get('budget', 0):.2f}"
                    break
            
            values = (dates_text, planned_hours, budget, f"{activity['hourly_rate']:.2f}")
            
            # Salva i dati
            self._activities_data.append({
                'id': str(activity["id"]),
                'text': activity["name"],
                'values': values
            })
        
        # Applica il filtro di ricerca se presente
        self.filter_activities_tree()
    
    def filter_projects_tree(self) -> None:
        """Filtra la visualizzazione delle commesse in base al testo di ricerca."""
        if not hasattr(self, 'projects_tree') or not hasattr(self, '_projects_data'):
            return
        
        # Ottieni il testo di ricerca
        search_text = ""
        if hasattr(self, 'project_search_var'):
            search_text = self.project_search_var.get().lower().strip()
        
        # Salva la selezione corrente
        current_selection = self.projects_tree.selection()
        
        # Pulisci il tree
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        
        # Reinserisci solo gli item che corrispondono al filtro
        for project_data in self._projects_data:
            # Se non c'è filtro, mostra tutto
            if not search_text:
                self.projects_tree.insert("", "end", 
                                         iid=project_data['id'],
                                         text=project_data['text'], 
                                         values=project_data['values'],
                                         tags=project_data['tags'])
            else:
                # Verifica se il testo di ricerca è contenuto nel nome o nei valori
                item_text = project_data['text'].lower()
                item_values = [str(v).lower() for v in project_data['values']]
                
                if search_text in item_text or any(search_text in v for v in item_values):
                    self.projects_tree.insert("", "end", 
                                             iid=project_data['id'],
                                             text=project_data['text'], 
                                             values=project_data['values'],
                                             tags=project_data['tags'])
        
        # Ripristina la selezione se l'item è ancora visibile
        if current_selection:
            try:
                if self.projects_tree.exists(current_selection[0]):
                    self.projects_tree.selection_set(current_selection[0])
            except:
                pass
    
    def filter_activities_tree(self) -> None:
        """Filtra la visualizzazione delle attività in base al testo di ricerca."""
        if not hasattr(self, 'activities_tree') or not hasattr(self, '_activities_data'):
            return
        
        # Ottieni il testo di ricerca
        search_text = ""
        if hasattr(self, 'activity_search_var'):
            search_text = self.activity_search_var.get().lower().strip()
        
        # Salva la selezione corrente
        current_selection = self.activities_tree.selection()
        
        # Pulisci il tree
        for item in self.activities_tree.get_children():
            self.activities_tree.delete(item)
        
        # Reinserisci solo gli item che corrispondono al filtro
        for activity_data in self._activities_data:
            # Se non c'è filtro, mostra tutto
            if not search_text:
                self.activities_tree.insert("", "end", 
                                           iid=activity_data['id'],
                                           text=activity_data['text'], 
                                           values=activity_data['values'])
            else:
                # Verifica se il testo di ricerca è contenuto nel nome o nei valori
                item_text = activity_data['text'].lower()
                item_values = [str(v).lower() for v in activity_data['values']]
                
                if search_text in item_text or any(search_text in v for v in item_values):
                    self.activities_tree.insert("", "end", 
                                               iid=activity_data['id'],
                                               text=activity_data['text'], 
                                               values=activity_data['values'])
        
        # Ripristina la selezione se l'item è ancora visibile
        if current_selection:
            try:
                if self.activities_tree.exists(current_selection[0]):
                    self.activities_tree.selection_set(current_selection[0])
            except:
                pass
    
    def sort_projects_tree(self, col: str) -> None:
        """Ordina la treeview delle commesse per la colonna selezionata."""
        if not hasattr(self, '_projects_data') or not self._projects_data:
            return
        
        # Determina la direzione di ordinamento
        if self._projects_sort_col == col:
            self._projects_sort_reverse = not self._projects_sort_reverse
        else:
            self._projects_sort_col = col
            self._projects_sort_reverse = False
        
        # Mappa delle colonne agli indici
        col_map = {
            "#0": "text",
            "stato": 0,
            "referente": 1,
            "dates": 2,
            "hours": 3,
            "budget": 4
        }
        
        # Funzione di chiave per ordinamento
        def sort_key(item):
            if col == "#0":
                return item["text"].lower()
            else:
                idx = col_map[col]
                value = item["values"][idx]
                # Prova a convertire in numero per ore e budget
                if col in ("hours", "budget"):
                    try:
                        return float(value.replace(",", ".")) if value != "--" else -1
                    except:
                        return -1
                return str(value).lower()
        
        # Ordina i dati
        self._projects_data.sort(key=sort_key, reverse=self._projects_sort_reverse)
        
        # Riapplica il filtro (che ricarica il tree)
        self.filter_projects_tree()
        
        # Aggiorna l'header per mostrare la direzione
        for c in ["#0", "stato", "referente", "dates", "hours", "budget"]:
            text = self.projects_tree.heading(c)["text"]
            # Rimuovi frecce esistenti
            text = text.replace(" ▲", "").replace(" ▼", "")
            if c == col:
                text += " ▼" if self._projects_sort_reverse else " ▲"
            self.projects_tree.heading(c, text=text)
    
    def sort_activities_tree(self, col: str) -> None:
        """Ordina la treeview delle attività per la colonna selezionata."""
        if not hasattr(self, '_activities_data') or not self._activities_data:
            return
        
        # Determina la direzione di ordinamento
        if self._activities_sort_col == col:
            self._activities_sort_reverse = not self._activities_sort_reverse
        else:
            self._activities_sort_col = col
            self._activities_sort_reverse = False
        
        # Mappa delle colonne agli indici
        col_map = {
            "#0": "text",
            "dates": 0,
            "planned_hours": 1,
            "budget": 2,
            "rate": 3
        }
        
        # Funzione di chiave per ordinamento
        def sort_key(item):
            if col == "#0":
                return item["text"].lower()
            else:
                idx = col_map[col]
                value = item["values"][idx]
                # Prova a convertire in numero per ore, budget e tariffa
                if col in ("planned_hours", "budget", "rate"):
                    try:
                        return float(value.replace(",", ".")) if value != "--" else -1
                    except:
                        return -1
                return str(value).lower()
        
        # Ordina i dati
        self._activities_data.sort(key=sort_key, reverse=self._activities_sort_reverse)
        
        # Riapplica il filtro (che ricarica il tree)
        self.filter_activities_tree()
        
        # Aggiorna l'header per mostrare la direzione
        for c in ["#0", "dates", "planned_hours", "budget", "rate"]:
            text = self.activities_tree.heading(c)["text"]
            # Rimuovi frecce esistenti
            text = text.replace(" ▲", "").replace(" ▼", "")
            if c == col:
                text += " ▼" if self._activities_sort_reverse else " ▲"
            self.activities_tree.heading(c, text=text)
    
    def on_pm_projects_tree_select(self, _event: tk.Event) -> None:
        """Gestisce la selezione di una commessa nell'elenco."""
        selected = self.projects_tree.selection()
        if selected:
            self.selected_project_id = int(selected[0])
            
            # Controlla se la commessa ha una schedule chiusa e disabilita i pulsanti di gestione attività
            schedules = self.db.list_schedules()
            project_schedule = next((s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] is None), None)
            
            # Verifica se è chiusa: controlla sia schedule che campo closed del progetto
            project = self.db.get_project(self.selected_project_id)
            is_closed = False
            if project_schedule:
                is_closed = project_schedule.get("status", "aperta") == "chiusa"
            elif project:
                is_closed = project.get("closed", 0) == 1
            
            if is_closed:
                # Commessa chiusa: disabilita pulsanti attività
                if hasattr(self, 'pm_new_activity_btn'):
                    self.pm_new_activity_btn.configure(state="disabled")
                if hasattr(self, 'pm_edit_activity_btn'):
                    self.pm_edit_activity_btn.configure(state="disabled")
            else:
                # Commessa aperta: abilita pulsanti attività
                if hasattr(self, 'pm_new_activity_btn'):
                    self.pm_new_activity_btn.configure(state="normal")
                if hasattr(self, 'pm_edit_activity_btn'):
                    self.pm_edit_activity_btn.configure(state="normal")
            
            # Aggiorna il box riepilogo commessa
            self.update_project_info_box(project, project_schedule, is_closed)
        else:
            self.selected_project_id = None
            self.clear_project_info_box()
        
        self.refresh_activities_tree()
    
    def on_pm_activities_tree_select(self, _event: tk.Event) -> None:
        """Gestisce la selezione di un'attività nell'elenco."""
        selected = self.activities_tree.selection()
        if selected:
            self.selected_activity_id = int(selected[0])
            # Aggiorna il box riepilogo attività
            self.update_activity_info_box()
        else:
            self.selected_activity_id = None
            self.clear_activity_info_box()
    
    def on_projects_tree_double_click(self, _event: tk.Event) -> None:
        """Apre la finestra di modifica commessa con doppio click."""
        if self.selected_project_id:
            self.pm_edit_project()
    
    def on_activities_tree_double_click(self, _event: tk.Event) -> None:
        """Apre la finestra di modifica attività con doppio click."""
        if self.selected_activity_id:
            self.pm_edit_activity_window()
    
    def update_project_info_box(self, project: dict, schedule: dict | None, is_closed: bool) -> None:
        """Aggiorna il box informativo della commessa selezionata."""
        if not hasattr(self, 'project_info_text'):
            return
        
        self.project_info_text.configure(state="normal")
        self.project_info_text.delete("1.0", "end")
        
        if project:
            info = f"🏢 Nome: {project['name']}\n"
            info += f"📊 Stato: {'Chiusa' if is_closed else 'Aperta'}\n"
            info += f"👤 Referente: {project.get('referente_commessa', 'Non specificato')}\n"
            
            descrizione = project.get('descrizione_commessa', '').strip()
            if descrizione:
                info += f"📝 Descrizione: {descrizione}\n"
            
            if schedule:
                info += f"📅 Inizio: {datetime.strptime(schedule['start_date'], '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
                info += f"📅 Fine: {datetime.strptime(schedule['end_date'], '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
                info += f"⏱️ Ore pianificate: {schedule['planned_hours']:.1f}\n"
                info += f"💰 Budget: €{schedule.get('budget', 0):.2f}\n"
            else:
                info += "⚠️ Nessuna pianificazione impostata\n"
            
            notes = project.get('notes', '').strip()
            if notes:
                info += f"📄 Note: {notes}"
            
            self.project_info_text.insert("1.0", info)
        
        self.project_info_text.configure(state="disabled")
    
    def clear_project_info_box(self) -> None:
        """Pulisce il box informativo della commessa."""
        if hasattr(self, 'project_info_text'):
            self.project_info_text.configure(state="normal")
            self.project_info_text.delete("1.0", "end")
            self.project_info_text.insert("1.0", "Nessuna commessa selezionata")
            self.project_info_text.configure(state="disabled")
    
    def update_activity_info_box(self) -> None:
        """Aggiorna il box informativo dell'attività selezionata."""
        if not hasattr(self, 'activity_info_text') or not self.selected_activity_id:
            return
        
        activity = self.db.get_activity(self.selected_activity_id)
        if not activity:
            self.clear_activity_info_box()
            return
        
        self.activity_info_text.configure(state="normal")
        self.activity_info_text.delete("1.0", "end")
        
        info = f"⚙️ Nome: {activity['name']}\n"
        info += f"💵 Tariffa oraria: €{activity['hourly_rate']:.2f}/h\n"
        
        notes = activity.get('notes', '').strip()
        if notes:
            info += f"📄 Note: {notes}\n"
        
        # Cerca la pianificazione
        schedules = self.db.list_schedules()
        activity_schedule = next((s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] == self.selected_activity_id), None)
        
        if activity_schedule:
            info += f"📅 Inizio: {datetime.strptime(activity_schedule['start_date'], '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
            info += f"📅 Fine: {datetime.strptime(activity_schedule['end_date'], '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
            info += f"⏱️ Ore pianificate: {activity_schedule['planned_hours']:.1f}\n"
            info += f"💰 Budget: €{activity_schedule.get('budget', 0):.2f}"
        else:
            info += "⚠️ Nessuna pianificazione impostata"
        
        self.activity_info_text.insert("1.0", info)
        self.activity_info_text.configure(state="disabled")
        
        # Carica gli utenti e l'utente assegnato
        self.load_activity_users()
    
    def clear_activity_info_box(self) -> None:
        """Pulisce il box informativo dell'attività."""
        if hasattr(self, 'activity_info_text'):
            self.activity_info_text.configure(state="normal")
            self.activity_info_text.delete("1.0", "end")
            self.activity_info_text.insert("1.0", "Nessuna attività selezionata")
            self.activity_info_text.configure(state="disabled")
        
        if hasattr(self, 'activity_users_listbox'):
            self.activity_users_listbox.delete(0, tk.END)
    
    def load_activity_users(self) -> None:
        """Carica la lista degli utenti assegnati all'attività selezionata."""
        if not hasattr(self, 'activity_users_listbox'):
            return
        
        # Pulisci la listbox
        self.activity_users_listbox.delete(0, tk.END)
        
        # Carica gli utenti assegnati (se presente)
        if self.selected_project_id and self.selected_activity_id:
            assignments = self.db.get_user_project_assignments(self.selected_project_id)
            # Filtra solo le assegnazioni specifiche a questa attività
            assigned_users = [a for a in assignments if a.get("activity_id") is not None and a.get("activity_id") == self.selected_activity_id]
            
            for user in assigned_users:
                display_name = f"{user['full_name']} ({user['username']})"
                self.activity_users_listbox.insert(tk.END, display_name)
    
    def add_user_to_activity(self) -> None:
        """Apre una finestra per aggiungere un utente all'attività."""
        if not self.selected_project_id or not self.selected_activity_id:
            messagebox.showwarning("Assegnazione", "Seleziona prima un'attività.")
            return
        
        # Finestra di selezione utente
        dialog = ctk.CTkToplevel(self)
        dialog.title("Aggiungi Utente")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Seleziona utente da aggiungere:", font=ctk.CTkFont(weight="bold")).pack(padx=20, pady=(20, 10))
        
        # Lista utenti disponibili
        users = self.db.list_users()
        assignments = self.db.get_user_project_assignments(self.selected_project_id)
        # Filtra solo le assegnazioni specifiche a questa attività
        assigned_user_ids = [a['user_id'] for a in assignments if a.get("activity_id") is not None and a.get("activity_id") == self.selected_activity_id]
        
        available_users = [u for u in users if u['id'] not in assigned_user_ids]
        
        if not available_users:
            messagebox.showinfo("Assegnazione", "Tutti gli utenti sono già assegnati a questa attività.")
            dialog.destroy()
            return
        
        user_listbox = tk.Listbox(dialog, height=10, font=("Arial", 12))
        user_listbox.pack(fill="both", expand=True, padx=20, pady=10)
        
        user_map = {}
        for user in available_users:
            display = f"{user['full_name']} ({user['username']})"
            user_listbox.insert(tk.END, display)
            user_map[user_listbox.size() - 1] = user['id']
        
        def confirm_add():
            selection = user_listbox.curselection()
            if not selection:
                messagebox.showwarning("Selezione", "Seleziona un utente.")
                return
            
            user_id = user_map[selection[0]]
            self.db.add_user_project_assignment(user_id, self.selected_project_id, self.selected_activity_id)
            self.load_activity_users()
            dialog.destroy()
            messagebox.showinfo("Assegnazione", "Utente aggiunto con successo.")
        
        ctk.CTkButton(dialog, text="Aggiungi", command=confirm_add).pack(pady=(0, 20))
    
    def remove_user_from_activity(self) -> None:
        """Rimuove l'utente selezionato dall'attività."""
        if not self.selected_project_id or not self.selected_activity_id:
            return
        
        if not hasattr(self, 'activity_users_listbox'):
            return
        
        selection = self.activity_users_listbox.curselection()
        if not selection:
            messagebox.showwarning("Rimozione", "Seleziona un utente da rimuovere.")
            return
        
        # Ottieni l'utente dalla listbox
        selected_text = self.activity_users_listbox.get(selection[0])
        
        # Trova l'user_id corrispondente
        assignments = self.db.get_user_project_assignments(self.selected_project_id)
        # Filtra solo le assegnazioni specifiche a questa attività
        assigned_users = [a for a in assignments if a.get("activity_id") is not None and a.get("activity_id") == self.selected_activity_id]
        
        selected_user = None
        for user in assigned_users:
            display_name = f"{user['full_name']} ({user['username']})"
            if display_name == selected_text:
                selected_user = user
                break
        
        if not selected_user:
            messagebox.showerror("Errore", "Impossibile identificare l'utente selezionato.")
            return
        
        if messagebox.askyesno("Conferma", f"Rimuovere {selected_user['full_name']} dall'attività?"):
            # Rimuovi l'assegnazione specifica
            self.db.conn.execute(
                "DELETE FROM user_project_assignments WHERE user_id = ? AND project_id = ? AND activity_id = ?",
                (selected_user['user_id'], self.selected_project_id, self.selected_activity_id)
            )
            self.db.conn.commit()
            self.load_activity_users()
            messagebox.showinfo("Rimozione", "Utente rimosso con successo.")
    
    def pm_new_project(self) -> None:
        """Crea una nuova commessa. Richiede la selezione di un cliente."""
        client_id = self._id_from_option(self.pm_client_combo.get())
        if not client_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona prima un cliente.")
            return
        
        # Resetta selected_project_id per indicare creazione nuova
        self.selected_project_id = None
        self.open_project_management()
        
        # Dopo la chiusura della finestra, ricarica
        self.refresh_projects_tree()
    
    def pm_edit_project(self) -> None:
        """Modifica la commessa selezionata."""
        if not self.selected_project_id:
            messagebox.showinfo("Gestione Commesse", "Seleziona una commessa dall'elenco.")
            return
        
        self.open_project_management()
        
        # Dopo la chiusura della finestra, ricarica
        self.refresh_projects_tree()
        self.refresh_activities_tree()
    
    def pm_new_activity(self) -> None:
        """Apre finestra per creare una nuova attività."""
        if not self.selected_project_id:
            messagebox.showinfo("Gestione Attività", "Seleziona prima una commessa dall'elenco.")
            return
        
        # Resetta selected_activity_id per indicare creazione nuova
        self.selected_activity_id = None
        self.open_activity_management()
        
        # Dopo la chiusura della finestra, ricarica
        self.refresh_activities_tree()
    
    def pm_edit_activity_window(self) -> None:
        """Apre finestra per modificare l'attività selezionata."""
        if not self.selected_activity_id:
            messagebox.showinfo("Gestione Attività", "Seleziona un'attività dall'elenco.")
            return
        
        self.open_activity_management()
        
        # Dopo la chiusura della finestra, ricarica
        self.refresh_activities_tree()
    
    def open_activity_management(self) -> None:
        """Apre finestra popup per gestione completa dell'attività (nuova o esistente)."""
        is_new = not self.selected_activity_id
        
        if is_new:
            # Modalità creazione
            if not self.selected_project_id:
                messagebox.showinfo("Gestione Attività", "Seleziona prima una commessa.")
                return
            
            activity = {
                "name": "",
                "hourly_rate": 0.0,
                "notes": "",
                "project_id": self.selected_project_id
            }
            activity_schedule = None
        else:
            # Modalità modifica: carica dati attività esistente
            activities = self.db.list_activities()
            activity = next((a for a in activities if a["id"] == self.selected_activity_id), None)
            
            if not activity:
                messagebox.showerror("Gestione Attività", "Attività non trovata.")
                return
            
            # Carica pianificazione esistente - usa activity["id"] per sicurezza
            schedules = self.db.list_schedules()
            activity_schedule = next((s for s in schedules if s["project_id"] == activity["project_id"] and s["activity_id"] == activity["id"]), None)
        
        # Ottieni il nome della commessa e del cliente
        projects = self.db.list_projects()
        project = next((p for p in projects if p["id"] == activity["project_id"]), None)
        project_info = ""
        is_project_closed = False
        if project:
            project_info = f"{project.get('client_name', '')} / {project['name']}"
            # Verifica se la schedule del progetto è chiusa o se il campo closed è 1
            schedules = self.db.list_schedules()
            project_schedule = next((s for s in schedules if s["project_id"] == project["id"] and s["activity_id"] is None), None)
            if project_schedule:
                is_project_closed = project_schedule.get("status", "aperta") == "chiusa"
            else:
                is_project_closed = project.get("closed", 0) == 1
        
        popup = ctk.CTkToplevel(self)
        if is_new:
            popup.title("Nuova Attività")
        else:
            popup.title(f"Gestione Attività: {activity['name']}")
        popup.geometry("700x550")
        popup.transient(self)
        popup.grab_set()
        
        # Frame con scrollbar
        main_scroll_frame = ctk.CTkScrollableFrame(popup)
        main_scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Form modifica dati attività
        form_frame = ctk.CTkFrame(main_scroll_frame)
        form_frame.pack(fill="x", pady=(0, 10))
        form_frame.grid_columnconfigure(1, weight=1)
        
        # Mostra commessa
        ctk.CTkLabel(form_frame, text="Commessa:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(form_frame, text=project_info, font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w"
        )
        
        ctk.CTkLabel(form_frame, text="Nome attività:", font=ctk.CTkFont(weight="bold")).grid(
            row=1, column=0, padx=5, pady=5, sticky="w"
        )
        activity_name_entry = ctk.CTkEntry(form_frame, placeholder_text="Inserisci nome attività")
        activity_name_entry.insert(0, activity["name"])
        activity_name_entry.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        ctk.CTkLabel(form_frame, text="Tariffa oraria (€/h):", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, padx=5, pady=5, sticky="w"
        )
        activity_rate_entry = ctk.CTkEntry(form_frame, width=120)
        activity_rate_entry.insert(0, str(activity["hourly_rate"]))
        activity_rate_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(form_frame, text="Note:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        activity_notes_entry = ctk.CTkEntry(form_frame)
        activity_notes_entry.insert(0, activity.get("notes", ""))
        activity_notes_entry.grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="ew")
        
        # Pianificazione
        ctk.CTkLabel(form_frame, text="Pianificazione", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=4, column=0, columnspan=4, padx=5, pady=(15, 5), sticky="w"
        )
        
        ctk.CTkLabel(form_frame, text="Data inizio:").grid(row=5, column=0, padx=5, pady=5, sticky="w")
        activity_start_entry = ctk.CTkEntry(form_frame, placeholder_text="gg/mm/aaaa", width=120)
        activity_start_entry.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.setup_date_entry_helpers(activity_start_entry)
        
        ctk.CTkLabel(form_frame, text="Data fine:").grid(row=5, column=2, padx=5, pady=5, sticky="w")
        activity_end_entry = ctk.CTkEntry(form_frame, placeholder_text="gg/mm/aaaa", width=120)
        activity_end_entry.grid(row=5, column=3, padx=5, pady=5, sticky="w")
        self.setup_date_entry_helpers(activity_end_entry)
        
        ctk.CTkLabel(form_frame, text="Ore preventivate:").grid(row=6, column=0, padx=5, pady=5, sticky="w")
        activity_hours_entry = ctk.CTkEntry(form_frame, width=120)
        activity_hours_entry.grid(row=6, column=1, padx=5, pady=5, sticky="w")
        
        ctk.CTkLabel(form_frame, text="Budget (€):").grid(row=6, column=2, padx=5, pady=5, sticky="w")
        activity_budget_entry = ctk.CTkEntry(form_frame, width=120)
        activity_budget_entry.grid(row=6, column=3, padx=5, pady=5, sticky="w")
        
        # Carica pianificazione esistente (solo se modifica)
        if activity_schedule:
            start = datetime.strptime(activity_schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            end = datetime.strptime(activity_schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            activity_start_entry.insert(0, start)
            activity_end_entry.insert(0, end)
            activity_hours_entry.insert(0, str(activity_schedule["planned_hours"]))
            activity_budget_entry.insert(0, str(activity_schedule.get("budget", 0)))
        elif is_new and project_schedule:
            # Nuova attività: pre-compila le date dalla commessa (se presente)
            start = datetime.strptime(project_schedule["start_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            end = datetime.strptime(project_schedule["end_date"], "%Y-%m-%d").strftime("%d/%m/%Y")
            activity_start_entry.insert(0, start)
            activity_end_entry.insert(0, end)
        
        # Non disabilitiamo più i campi per commesse chiuse - solo i pulsanti
        # Questo permette di leggere i valori anche se la commessa è chiusa
        
        def save_activity():
            try:
                # Salva gli ID corretti all'inizio
                current_project_id = self.selected_project_id if is_new else activity["project_id"]
                current_activity_id = None if is_new else activity["id"]
                
                name = activity_name_entry.get().strip()
                if not name:
                    raise ValueError("Nome attività obbligatorio.")
                
                rate = self._to_float(activity_rate_entry.get().strip() or "0", "Tariffa attività")
                notes = activity_notes_entry.get().strip()
                
                # VALIDAZIONE PIANIFICAZIONE PRIMA DI SALVARE L'ATTIVITÀ
                start_date_str = activity_start_entry.get().strip()
                end_date_str = activity_end_entry.get().strip()
                hours_str = activity_hours_entry.get().strip()
                budget_str = activity_budget_entry.get().strip()
                
                # Crea schedule se ci sono date O se ci sono ore/budget
                has_any_planning = any([start_date_str, end_date_str, hours_str, budget_str])
                
                # Variabili per schedule
                start_date = None
                end_date = None
                planned_hours = 0
                budget = 0
                warnings = []
                
                if has_any_planning:
                    # Converti ore e budget (senza validazioni)
                    planned_hours = self._to_float(hours_str, "Ore preventivate") if hours_str else 0
                    budget = self._to_float(budget_str, "Budget") if budget_str else 0
                    
                    # Gestisci date
                    if start_date_str and end_date_str:
                        # Usa le date inserite dall'utente
                        start_date = datetime.strptime(start_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                        end_date = datetime.strptime(end_date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                        
                        if start_date > end_date:
                            raise ValueError("La data di inizio deve essere precedente alla data di fine.")
                    elif project_schedule:
                        # Usa le date dalla commessa come default
                        start_date = project_schedule["start_date"]
                        end_date = project_schedule["end_date"]
                    else:
                        # Usa date default dell'anno corrente se non ci sono date della commessa
                        current_year = datetime.now().year
                        start_date = f"{current_year}-01-01"
                        end_date = f"{current_year}-12-31"
                    
                    # CONTROLLI RISPETTO AI LIMITI DELLA COMMESSA
                    schedules = self.db.list_schedules()
                    project_schedule_check = next((s for s in schedules if s["project_id"] == current_project_id and s["activity_id"] is None), None)
                    
                    if project_schedule_check:
                        project_end_date = project_schedule_check["end_date"]
                        project_planned_hours = project_schedule_check["planned_hours"]
                        project_budget = project_schedule_check.get("budget", 0)
                        
                        # Verifica data fine attività
                        if end_date > project_end_date:
                            warnings.append(f"⚠ Data fine attività ({datetime.strptime(end_date, '%Y-%m-%d').strftime('%d/%m/%Y')}) supera la data fine commessa ({datetime.strptime(project_end_date, '%Y-%m-%d').strftime('%d/%m/%Y')})")
                        
                        # Calcola totali attività (esclusa quella corrente se è modifica)
                        activity_schedules = [s for s in schedules if s["project_id"] == current_project_id and s["activity_id"] is not None]
                        
                        total_hours = 0
                        total_budget = 0
                        for s in activity_schedules:
                            # Escludi l'attività corrente se è una modifica
                            if not is_new and s["activity_id"] == current_activity_id:
                                continue
                            total_hours += s.get("planned_hours", 0)
                            total_budget += s.get("budget", 0)
                        
                        # Aggiungi i valori della attività corrente
                        total_hours += planned_hours
                        total_budget += budget
                        
                        # Verifica ore
                        if project_planned_hours > 0 and total_hours > project_planned_hours:
                            warnings.append(f"⚠ Ore totali attività ({total_hours:.1f}h) superano le ore preventivate della commessa ({project_planned_hours:.1f}h)")
                        
                        # Verifica budget
                        if project_budget > 0 and total_budget > project_budget:
                            warnings.append(f"⚠ Budget totale attività ({total_budget:.2f}€) supera il budget della commessa ({project_budget:.2f}€)")
                
                # VALIDAZIONE SUPERATA - ORA SALVA L'ATTIVITÀ
                if is_new:
                    # Crea nuova attività
                    new_activity_id = self.db.add_activity(current_project_id, name, rate, notes)
                    current_activity_id = new_activity_id
                    self.selected_activity_id = new_activity_id
                else:
                    # Aggiorna attività esistente
                    self.db.update_activity(current_activity_id, name, rate, notes)
                
                # GESTIONE SCHEDULE
                if has_any_planning:
                    # Salva schedule
                    if activity_schedule and not is_new:
                        self.db.update_schedule(activity_schedule["id"], current_project_id, current_activity_id,
                                              start_date, end_date, planned_hours, "", budget)
                    else:
                        self.db.add_schedule(current_project_id, current_activity_id, start_date, end_date, 
                                           planned_hours, "", budget)
                    
                    # Mostra avvertimenti se presenti
                    if warnings:
                        warning_msg = "Attività salvata, ma attenzione:\n\n" + "\n".join(warnings)
                        messagebox.showwarning("Gestione Attività", warning_msg)
                    else:
                        messagebox.showinfo("Gestione Attività", "Attività salvata con successo.")
                elif not has_any_planning and activity_schedule and not is_new:
                    # L'utente ha cancellato tutti i dati di pianificazione e c'è uno schedule esistente -> elimina lo schedule
                    if messagebox.askyesno("Conferma", "Vuoi eliminare la pianificazione di questa attività?"):
                        self.db.delete_schedule(activity_schedule["id"])
                        messagebox.showinfo("Gestione Attività", "Attività salvata. Pianificazione eliminata.")
                    else:
                        messagebox.showinfo("Gestione Attività", "Attività salvata. Pianificazione mantenuta.")
                else:
                    # Nessuna pianificazione e nessuno schedule esistente -> ok
                    messagebox.showinfo("Gestione Attività", "Attività salvata con successo.")
                
                popup.destroy()
                
                # Ricarica dati
                self.refresh_activities_tree()
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
                
            except ValueError as exc:
                messagebox.showerror("Gestione Attività", str(exc))
            except sqlite3.IntegrityError as exc:
                if "UNIQUE constraint" in str(exc):
                    messagebox.showerror("Gestione Attività", "Esiste già un'attività con questo nome per questa commessa.")
                else:
                    messagebox.showerror("Gestione Attività", f"Errore database: {exc}")
            except Exception as exc:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Gestione Attività", f"Errore generico: {exc}")
        
        def delete_activity():
            if is_new:
                return
            
            if not messagebox.askyesno("Conferma", "Eliminare l'attività? Verranno eliminati anche i timesheet associati."):
                return
            
            try:
                activity_id_to_delete = activity["id"]
                self.db.delete_activity(activity_id_to_delete)
                messagebox.showinfo("Gestione Attività", "Attività eliminata.")
                popup.destroy()
                
                self.selected_activity_id = None
                self.refresh_activities_tree()
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
            except Exception as exc:
                messagebox.showerror("Gestione Attività", f"Errore: {exc}")
        
        # Pulsanti
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.grid(row=7, column=0, columnspan=4, pady=20)
        
        save_btn = ctk.CTkButton(btn_frame, text="Salva", command=save_activity, width=120)
        save_btn.pack(side="left", padx=5)
        if is_project_closed:
            save_btn.configure(state="disabled")
        
        if not is_new:
            delete_btn = ctk.CTkButton(btn_frame, text="Elimina Attività", command=delete_activity, width=120, 
                         fg_color="#D32F2F")
            delete_btn.pack(side="left", padx=5)
            if is_project_closed:
                delete_btn.configure(state="disabled")
        
        ctk.CTkButton(btn_frame, text="Annulla", command=popup.destroy, width=120).pack(side="left", padx=5)
    
    # ========== FUNZIONI VECCHIE DA RIMUOVERE O ADATTARE ==========
    
    def on_pm_project_change(self, _value: str) -> None:
        """Funzione legacy - non più utilizzata nel nuovo layout."""
        pass
    
    def refresh_user_checkboxes(self) -> None:
        """Funzione legacy - non più utilizzata nel nuovo layout."""
        pass
    
    def on_user_assignment_toggle(self, user_id: int, var: tk.BooleanVar) -> None:
        """Funzione legacy - non più utilizzata nel nuovo layout."""
        pass
    
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
                # Salva il project_id corretto all'inizio (in caso di modifica)
                current_project_id = self.selected_project_id if is_new else project["id"]
                
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
                    planned_hours = self._to_float(hours_str, "Ore preventivate") if hours_str else 0
                    budget = self._to_float(budget_str, "Budget") if budget_str else 0
                    
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
                    new_project_id = self.db.add_project(client_id, name, rate, notes, referente_commessa, descrizione_commessa)
                    current_project_id = new_project_id
                    self.selected_project_id = new_project_id
                else:
                    # Aggiorna commessa esistente
                    self.db.update_project(current_project_id, name, rate, notes, referente_commessa, descrizione_commessa)
                
                # GESTIONE SCHEDULE
                if has_any_planning:
                    # Salva schedule
                    if project_schedule and not is_new:
                        self.db.update_schedule(project_schedule["id"], current_project_id, None,
                                              start_date, end_date, planned_hours, "", budget)
                    else:
                        self.db.add_schedule(current_project_id, None, start_date, end_date, planned_hours, "", budget)
                elif not has_any_planning and project_schedule and not is_new:
                    # L'utente ha cancellato tutti i dati di pianificazione e c'è uno schedule esistente -> elimina lo schedule
                    if messagebox.askyesno("Conferma", "Vuoi eliminare la pianificazione di questa commessa?"):
                        self.db.delete_schedule(project_schedule["id"])
                
                if is_new:
                    messagebox.showinfo("Gestione Commesse", "Nuova commessa creata con successo.")
                else:
                    messagebox.showinfo("Gestione Commesse", "Commessa aggiornata con successo.")
                
                # Aggiorna self.selected_project_id per sincronizzazione
                self.selected_project_id = current_project_id
                
                popup.destroy()
                self.refresh_master_data()
                self.refresh_projects_tree()
                
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
                
            except ValueError as exc:
                messagebox.showerror("Gestione Commesse", str(exc))
            except sqlite3.IntegrityError as exc:
                if "UNIQUE constraint" in str(exc):
                    messagebox.showerror("Gestione Commesse", "Esiste già una commessa con questo nome per questo cliente.\nScegli un nome diverso.")
                else:
                    messagebox.showerror("Gestione Commesse", f"Errore database: {exc}")
            except Exception as exc:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Gestione Commesse", f"Errore generico: {exc}")
        
        def delete_project():
            if is_new:
                return
            
            if not messagebox.askyesno("Conferma", "Eliminare la commessa? Verranno eliminati anche attività, pianificazioni e timesheet associati."):
                return
            
            try:
                project_id_to_delete = project["id"]
                self.db.delete_project(project_id_to_delete)
                messagebox.showinfo("Gestione Commesse", "Commessa eliminata.")
                popup.destroy()
                
                self.selected_project_id = None
                self.selected_activity_id = None
                self.refresh_master_data()
                if hasattr(self, 'refresh_control_panel'):
                    self.refresh_control_panel()
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
            save_btn.pack(side="left", padx=5)
            if is_closed:
                save_btn.configure(state="disabled")
            
            delete_btn = ctk.CTkButton(btn_frame, text="🗑️ Elimina Commessa", command=delete_project, width=150, 
                         fg_color="#D32F2F")
            delete_btn.pack(side="left", padx=5)
            if is_closed:
                delete_btn.configure(state="disabled")
            
            # Definisco le funzioni close/open DOPO aver creato i pulsanti
            def close_project_action():
                try:
                    project_id_to_close = project["id"]
                    self.db.close_project(project_id_to_close)
                    messagebox.showinfo("Gestione Commesse", "Commessa chiusa con successo.")
                    
                    # Aggiorna pulsanti senza disabilitare i campi
                    save_btn.configure(state="disabled")
                    delete_btn.configure(state="disabled")
                    close_btn.configure(state="disabled")
                    open_btn.configure(state="normal")
                    
                    self.refresh_master_data()
                    self.refresh_projects_tree()
                    if hasattr(self, 'refresh_control_panel'):
                        self.refresh_control_panel()
                except Exception as exc:
                    messagebox.showerror("Gestione Commesse", f"Errore: {exc}")
            
            def open_project_action():
                try:
                    project_id_to_open = project["id"]
                    self.db.open_project(project_id_to_open)
                    messagebox.showinfo("Gestione Commesse", "Commessa riaperta con successo.")
                    
                    # Aggiorna pulsanti senza abilitare i campi
                    save_btn.configure(state="normal")
                    delete_btn.configure(state="normal")
                    close_btn.configure(state="normal")
                    open_btn.configure(state="disabled")
                    
                    self.refresh_master_data()
                    self.refresh_projects_tree()
                    if hasattr(self, 'refresh_control_panel'):
                        self.refresh_control_panel()
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
        if hasattr(self, 'projects_tree'):
            # Per la nuova tab Project Management, aggiorna gli elenchi
            self.refresh_projects_tree()
            self.refresh_activities_tree()
        elif hasattr(self, 'master_tree'):
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
