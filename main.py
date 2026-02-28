from __future__ import annotations

import calendar
import sqlite3
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from db import AUTO_BACKUP_INTERVAL_MINUTES, CFG_DIR, Database
from style import ui_style as mystyle
from style.ui_ttk import configure_treeview_style
from ui.dialogs.clients_dialog import open_clients_management_dialog
from ui.dialogs.pdf_report_dialog import show_pdf_report_dialog
from ui.dialogs.project_management_dialog import open_project_management_dialog
from ui.dialogs.schedule_report_dialog import show_schedule_report_dialog
from ui.tabs.diary_tab import (
    build_diary_tab as build_diary_tab_impl,
    diary_delete_entry as diary_delete_entry_impl,
    diary_edit_entry as diary_edit_entry_impl,
    diary_get_selected_id as diary_get_selected_id_impl,
    diary_new_entry as diary_new_entry_impl,
    diary_on_client_change as diary_on_client_change_impl,
    diary_on_project_change as diary_on_project_change_impl,
    diary_open_editor as diary_open_editor_impl,
    diary_populate_combos as diary_populate_combos_impl,
    diary_toggle_completed as diary_toggle_completed_impl,
    format_date_display as format_date_display_impl,
    refresh_diary_data as refresh_diary_data_impl,
    update_diary_alert as update_diary_alert_impl,
)
from ui.tabs.control_tab import (
    build_control_tab as build_control_tab_impl,
    on_control_tree_double_click as on_control_tree_double_click_impl,
    refresh_control_panel as refresh_control_panel_impl,
)
from ui.tabs.plan_tab import (
    add_schedule_entry as add_schedule_entry_impl,
    build_plan_tab as build_plan_tab_impl,
    delete_selected_schedule as delete_selected_schedule_impl,
    edit_selected_schedule as edit_selected_schedule_impl,
    on_plan_project_change as on_plan_project_change_impl,
    on_schedule_tree_select as on_schedule_tree_select_impl,
    refresh_programming_options as refresh_programming_options_impl,
    refresh_schedule_list as refresh_schedule_list_impl,
    toggle_schedule_status as toggle_schedule_status_impl,
)
from ui.tabs.users_tab import (
    build_users_tab as build_users_tab_impl,
    cancel_user_edit as cancel_user_edit_impl,
    load_user_for_edit as load_user_for_edit_impl,
    on_user_select as on_user_select_impl,
    refresh_users_data as refresh_users_data_impl,
    reset_selected_password as reset_selected_password_impl,
    save_user as save_user_impl,
    save_user_tabs as save_user_tabs_impl,
    toggle_selected_user as toggle_selected_user_impl,
)

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
        self._timesheet_rows_by_id: dict[int, dict] = {}

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

    def _get_edit_button_colors(self) -> dict[str, str]:
        if self.is_dark_mode:
            return {"fg_color": "#f59e0b", "hover_color": "#d97706"}
        return {"fg_color": "#d97706", "hover_color": "#b45309"}

    def _get_delete_button_colors(self) -> dict[str, str]:
        if self.is_dark_mode:
            return {"fg_color": "#ef4444", "hover_color": "#dc2626"}
        return {"fg_color": "#dc2626", "hover_color": "#b91c1c"}

    def apply_edit_button_style(self, button: ctk.CTkButton) -> None:
        button.configure(**self._get_edit_button_colors())

    def apply_delete_button_style(self, button: ctk.CTkButton) -> None:
        button.configure(**self._get_delete_button_colors())

    def _ensure_combo_option(self, combo: ctk.CTkComboBox, value: str) -> None:
        if not value:
            return
        values = list(combo.cget("values"))
        if value not in values:
            values.append(value)
            combo.configure(values=values)

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

        # Tab Diario sempre visibile per tutti
        self.tab_diary = self.tabview.add("Diario")
            
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
        self.build_diary_tab()
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
        self.refresh_diary_data()
        self.update_diary_alert()

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
        self.ts_save_button = ctk.CTkButton(button_row, text="Salva ore", command=self.save_timesheet_entry)
        self.ts_save_button.pack(side="left", padx=(0, 8))
        self.ts_edit_button = ctk.CTkButton(button_row, text="Modifica selezionata", command=self.edit_selected_timesheet)
        self.apply_edit_button_style(self.ts_edit_button)
        self.ts_edit_button.pack(side="left", padx=(0, 8))
        self.ts_delete_button = ctk.CTkButton(button_row, text="Elimina selezionata", command=self.delete_selected_timesheet)
        self.apply_delete_button_style(self.ts_delete_button)
        self.ts_delete_button.pack(side="left")

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
        self.ts_tree.bind("<<TreeviewSelect>>", self.on_timesheet_tree_select)

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

        self._timesheet_rows_by_id = {}
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
            self._timesheet_rows_by_id[int(row["id"])] = row
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

    def on_timesheet_tree_select(self, _event: object) -> None:
        selection = self.ts_tree.selection()
        if not selection:
            return

        entry_id = int(selection[0])
        row = self._timesheet_rows_by_id.get(entry_id)
        if not row:
            return

        client_option = self._entity_option(row["client_id"], row["client_name"])
        self._ensure_combo_option(self.ts_client_combo, client_option)
        self.ts_client_combo.set(client_option)
        self.on_timesheet_client_change(client_option)

        project_option = self._project_option(
            {
                "id": row["project_id"],
                "client_name": row["client_name"],
                "name": row["project_name"],
            }
        )
        self._ensure_combo_option(self.ts_project_combo, project_option)
        self.ts_project_combo.set(project_option)
        self.on_timesheet_project_change(project_option)

        activity_option = self._activity_option(
            {
                "id": row["activity_id"],
                "project_name": row["project_name"],
                "name": row["activity_name"],
            }
        )
        self._ensure_combo_option(self.ts_activity_combo, activity_option)
        self.ts_activity_combo.set(activity_option)

        self.ts_hours_entry.delete(0, "end")
        self.ts_hours_entry.insert(0, f"{float(row['hours']):.2f}")
        self.ts_note_text.delete("1.0", "end")
        self.ts_note_text.insert("1.0", row["note"] or "")

    def edit_selected_timesheet(self) -> None:
        selection = self.ts_tree.selection()
        if not selection:
            messagebox.showwarning("Ore giornaliere", "Seleziona una riga da modificare.")
            return

        entry_id = int(selection[0])
        try:
            user_id = self._selected_timesheet_user_id()
            client_id = self._id_from_option(self.ts_client_combo.get())
            project_id = self._id_from_option(self.ts_project_combo.get())
            activity_id = self._id_from_option(self.ts_activity_combo.get())
            if not (client_id and project_id and activity_id):
                raise ValueError("Seleziona cliente, commessa e attivita.")

            if not self.is_admin:
                if not self.db.user_can_access_activity(user_id, project_id, activity_id):
                    raise ValueError("Non hai i permessi per modificare ore su questa attività.")

            hours = self._to_float(self.ts_hours_entry.get().strip(), "Ore")
            if hours <= 0:
                raise ValueError("Ore: il valore deve essere > 0.")

            note = self.ts_note_text.get("1.0", "end").strip()
            self.db.update_timesheet(
                entry_id=entry_id,
                user_id=user_id,
                is_admin=self.is_admin,
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

        self.refresh_day_entries()
        self.refresh_control_panel()
        messagebox.showinfo("Ore giornaliere", "Voce aggiornata.")

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
        
        self.pm_edit_project_btn = ctk.CTkButton(
            buttons_projects, text="✏️ Modifica", width=100,
            command=self.pm_edit_project
        )
        self.apply_edit_button_style(self.pm_edit_project_btn)
        self.pm_edit_project_btn.pack(side="left", padx=(0, 10))
        
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
        self.apply_edit_button_style(self.pm_edit_activity_btn)
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
            delete_btn = ctk.CTkButton(
                btn_frame,
                text="Elimina Attività",
                command=delete_activity,
                width=120,
            )
            self.apply_delete_button_style(delete_btn)
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
        open_clients_management_dialog(self)
    
    def open_project_management(self) -> None:
        open_project_management_dialog(self)

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
        build_plan_tab_impl(self)

    def refresh_programming_options(self) -> None:
        refresh_programming_options_impl(self)

    def on_plan_project_change(self, _value: str) -> None:
        on_plan_project_change_impl(self, _value)

    def add_schedule_entry(self) -> None:
        add_schedule_entry_impl(self)

    def on_schedule_tree_select(self, event) -> None:
        on_schedule_tree_select_impl(self, event)

    def edit_selected_schedule(self) -> None:
        edit_selected_schedule_impl(self)

    def refresh_schedule_list(self) -> None:
        refresh_schedule_list_impl(self)

    def delete_selected_schedule(self) -> None:
        delete_selected_schedule_impl(self)
    
    def toggle_schedule_status(self) -> None:
        toggle_schedule_status_impl(self)

    def show_schedule_report(self, schedule_id: int) -> None:
        show_schedule_report_dialog(self, schedule_id)

    def build_control_tab(self) -> None:
        build_control_tab_impl(self)

    def on_control_tree_double_click(self, event) -> None:
        on_control_tree_double_click_impl(self, event)

    def refresh_control_panel(self) -> None:
        refresh_control_panel_impl(self)
    
    # ══════════════════════════════════════════════════════════════════════════
    # TAB DIARIO
    # ══════════════════════════════════════════════════════════════════════════

    def build_diary_tab(self) -> None:
        build_diary_tab_impl(self)

    def _diary_populate_combos(self) -> None:
        diary_populate_combos_impl(self)

    def _diary_on_client_change(self) -> None:
        diary_on_client_change_impl(self)

    def _diary_on_project_change(self) -> None:
        diary_on_project_change_impl(self)

    def refresh_diary_data(self) -> None:
        refresh_diary_data_impl(self)

    def _format_date_display(self, date_str: str) -> str:
        return format_date_display_impl(date_str)

    def update_diary_alert(self) -> None:
        update_diary_alert_impl(self)

    def _diary_get_selected_id(self) -> int | None:
        return diary_get_selected_id_impl(self)

    def _diary_toggle_completed(self) -> None:
        diary_toggle_completed_impl(self)

    def _diary_delete_entry(self) -> None:
        diary_delete_entry_impl(self)

    def _diary_new_entry(self) -> None:
        diary_new_entry_impl(self)

    def _diary_edit_entry(self) -> None:
        diary_edit_entry_impl(self)

    def _diary_open_editor(self, entry_id: int | None) -> None:
        diary_open_editor_impl(self, entry_id)

    def build_users_tab(self) -> None:
        build_users_tab_impl(self)

    def on_user_select(self, _event: object) -> None:
        on_user_select_impl(self, _event)

    def save_user_tabs(self) -> None:
        save_user_tabs_impl(self)

    def refresh_users_data(self) -> None:
        refresh_users_data_impl(self)

    def save_user(self) -> None:
        save_user_impl(self)
    
    def load_user_for_edit(self) -> None:
        load_user_for_edit_impl(self)
    
    def cancel_user_edit(self) -> None:
        cancel_user_edit_impl(self)

    def toggle_selected_user(self) -> None:
        toggle_selected_user_impl(self)

    def reset_selected_password(self) -> None:
        reset_selected_password_impl(self)

    def show_pdf_report_dialog(self) -> None:
        show_pdf_report_dialog(self)

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
