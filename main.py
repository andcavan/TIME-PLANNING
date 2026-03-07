from __future__ import annotations

import calendar
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QDate, QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication,
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QTableView,
)

from db import AUTO_BACKUP_INTERVAL_MINUTES, CFG_DIR, Database
from pdf_reports import PDFReportGenerator

BASE_DIR = Path(__file__).resolve().parent
APP_VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()

DARK_THEME = """
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #1e1e2e; }
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #45475a; border-color: #89b4fa; }
QPushButton#btn_primary { background-color: #89b4fa; color: #1e1e2e; font-weight: bold; }
QPushButton#btn_warning { background-color: #fab387; color: #1e1e2e; font-weight: bold; }
QPushButton#btn_danger { background-color: #f38ba8; color: #1e1e2e; font-weight: bold; }
QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateEdit:focus { border-color: #89b4fa; }
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    border: 1px solid #45475a;
    selection-background-color: #45475a;
}
QTableWidget, QTreeWidget {
    background-color: #181825;
    alternate-background-color: #1e1e2e;
    border: 1px solid #313244;
    gridline-color: #313244;
}
QHeaderView::section {
    background-color: #181825;
    color: #89b4fa;
    font-weight: bold;
    border: 1px solid #313244;
    padding: 6px;
}
QTabWidget::pane { border: 1px solid #313244; background: #1e1e2e; }
QTabBar::tab {
    background-color: #181825;
    border: 1px solid #313244;
    padding: 8px 12px;
    color: #a6adc8;
}
QTabBar::tab:selected { background-color: #313244; color: #cdd6f4; font-weight: bold; }
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    color: #89b4fa;
    font-weight: bold;
}
QGroupBox::title { left: 10px; padding: 0 4px; }
"""

LIGHT_THEME = """
QWidget {
    background-color: #f5f7fb;
    color: #1f2937;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QMainWindow, QDialog { background-color: #f5f7fb; }
QPushButton {
    background-color: #e2e8f0;
    color: #111827;
    border: 1px solid #cbd5e1;
    border-radius: 5px;
    padding: 6px 14px;
}
QPushButton:hover { background-color: #dbe3ef; border-color: #2563eb; }
QPushButton#btn_primary { background-color: #2563eb; color: #ffffff; font-weight: bold; }
QPushButton#btn_warning { background-color: #f59e0b; color: #111827; font-weight: bold; }
QPushButton#btn_danger { background-color: #ef4444; color: #ffffff; font-weight: bold; }
QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 8px;
    color: #111827;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QDateEdit:focus { border-color: #2563eb; }
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    selection-background-color: #dbeafe;
}
QTableWidget, QTreeWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    gridline-color: #e2e8f0;
}
QHeaderView::section {
    background-color: #eef2ff;
    color: #1e40af;
    font-weight: bold;
    border: 1px solid #cbd5e1;
    padding: 6px;
}
QTabWidget::pane { border: 1px solid #cbd5e1; background: #ffffff; }
QTabBar::tab {
    background-color: #e2e8f0;
    border: 1px solid #cbd5e1;
    padding: 8px 12px;
    color: #334155;
}
QTabBar::tab:selected { background-color: #ffffff; color: #0f172a; font-weight: bold; }
QGroupBox {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 8px;
    color: #1e40af;
    font-weight: bold;
}
QGroupBox::title { left: 10px; padding: 0 4px; }
"""


def _readonly_item(text: Any) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _to_qdate(dt: date) -> QDate:
    return QDate(dt.year, dt.month, dt.day)


class HoursCalendarWidget(QCalendarWidget):
    def __init__(self, dark_mode: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_dark_mode = dark_mode
        self._hours_by_day: dict[int, float] = {}
        self.setGridVisible(True)
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
        self._apply_calendar_style()
        self.currentPageChanged.connect(lambda _y, _m: QTimer.singleShot(0, self._tune_headers))
        QTimer.singleShot(0, self._tune_headers)

    def set_theme_mode(self, dark_mode: bool) -> None:
        self._is_dark_mode = dark_mode
        self._apply_calendar_style()
        self.updateCells()
        QTimer.singleShot(0, self._tune_headers)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        QTimer.singleShot(0, self._tune_headers)

    def set_hours_map(self, hours_by_day: dict[int, float]) -> None:
        self._hours_by_day = {int(k): float(v) for k, v in hours_by_day.items()}
        self.updateCells()

    def _tune_headers(self) -> None:
        table = self.findChild(QTableView, "qt_calendar_calendarview")
        if table is None:
            return

        model = table.model()
        if model is None:
            return

        rows = model.rowCount()
        cols = model.columnCount()
        if rows < 2 or cols < 2:
            return

        # La vista interna usa Stretch; forziamo dimensioni fisse della riga giorni e colonna settimane.
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        viewport_w = max(1, table.viewport().width())
        viewport_h = max(1, table.viewport().height())

        day_cols = cols - 1
        day_rows = rows - 1

        day_col_w = max(36, int(viewport_w / (day_cols + 0.5)))
        week_col_w = max(14, int(day_col_w * 0.5))
        used_w = week_col_w + (day_cols - 1) * day_col_w
        last_day_col_w = max(36, viewport_w - used_w)

        table.setColumnWidth(0, week_col_w)
        for c in range(1, cols - 1):
            table.setColumnWidth(c, day_col_w)
        table.setColumnWidth(cols - 1, last_day_col_w)

        day_row_h = max(24, int(viewport_h / (day_rows + 0.5)))
        header_row_h = max(10, int(day_row_h * 0.5))
        used_h = header_row_h + (day_rows - 1) * day_row_h
        last_day_row_h = max(20, viewport_h - used_h)

        table.setRowHeight(0, header_row_h)
        for r in range(1, rows - 1):
            table.setRowHeight(r, day_row_h)
        table.setRowHeight(rows - 1, last_day_row_h)

    def _apply_calendar_style(self) -> None:
        if self._is_dark_mode:
            calendar_bg = "#181825"
            weekday_bg = "#4b5563"
            weeknum_bg = "#4b5563"
            header_fg = "#ffffff"
            border = "#6b7280"
        else:
            calendar_bg = "#ffffff"
            weekday_bg = "#4b5563"
            weeknum_bg = "#4b5563"
            header_fg = "#ffffff"
            border = "#6b7280"

        self.setStyleSheet(
            f"""
QCalendarWidget QTableView {{
    background-color: {calendar_bg};
    selection-background-color: transparent;
}}
QCalendarWidget QTableView#qt_calendar_calendarview {{
    background-color: {weekday_bg};
    color: {header_fg};
    font-size: 13px;
    font-weight: 800;
    gridline-color: {border};
}}
QCalendarWidget QTableView#qt_calendar_calendarview::item {{
    background-color: {weekday_bg};
    color: {header_fg};
}}
QCalendarWidget QTableView QHeaderView::section:horizontal {{
    background-color: {weekday_bg};
    color: {header_fg};
    border: 1px solid {border};
    padding: 0px;
    min-height: 9px;
    max-height: 9px;
    font-size: 13px;
    font-weight: 800;
}}
QCalendarWidget QTableView QHeaderView::section:vertical {{
    background-color: {weeknum_bg};
    color: {header_fg};
    border: 1px solid {border};
    padding: 0px;
    min-width: 16px;
    max-width: 16px;
    font-size: 13px;
    font-weight: 800;
}}
"""
        )

    def paintCell(self, painter, rect, qdate) -> None:  # type: ignore[override]
        in_current_month = qdate.year() == self.yearShown() and qdate.month() == self.monthShown()
        is_today = qdate == QDate.currentDate()
        is_selected = qdate == self.selectedDate()
        is_weekend = qdate.dayOfWeek() in (6, 7)

        if self._is_dark_mode:
            base_bg = QColor("#181825" if in_current_month else "#121221")
            base_fg = QColor("#cdd6f4" if in_current_month else "#6b7280")
            border = QColor("#313244")
            weekend_bg = QColor("#8b1d1d")
            weekend_fg = QColor("#fee2e2")
            default_badge_bg = QColor("#1d4ed8")
            default_badge_fg = QColor("#dbeafe")
            default_badge_border = QColor("#60a5fa")
        else:
            base_bg = QColor("#ffffff" if in_current_month else "#f3f4f6")
            base_fg = QColor("#1f2937" if in_current_month else "#9ca3af")
            border = QColor("#d1d5db")
            weekend_bg = QColor("#ef4444")
            weekend_fg = QColor("#ffffff")
            default_badge_bg = QColor("#1d4ed8")
            default_badge_fg = QColor("#ffffff")
            default_badge_border = QColor("#1e40af")

        # Priorita colori: selezione (giallo) > oggi (blu) > weekend (rosso).
        if is_selected:
            bg = QColor("#facc15")
            fg = QColor("#111827")
            badge_bg = QColor("#92400e")
            badge_fg = QColor("#fef3c7")
            badge_border = QColor("#78350f")
        elif is_today:
            bg = QColor("#2563eb")
            fg = QColor("#ffffff")
            badge_bg = QColor("#dbeafe")
            badge_fg = QColor("#1e3a8a")
            badge_border = QColor("#93c5fd")
        elif is_weekend and in_current_month:
            bg = weekend_bg
            fg = weekend_fg
            badge_bg = QColor("#7f1d1d")
            badge_fg = QColor("#fee2e2")
            badge_border = QColor("#991b1b")
        else:
            bg = base_bg
            fg = base_fg
            badge_bg = default_badge_bg
            badge_fg = default_badge_fg
            badge_border = default_badge_border

        painter.save()
        painter.fillRect(rect.adjusted(1, 1, -1, -1), bg)
        painter.setPen(border)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        num_font = painter.font()
        num_font.setBold(is_today or is_selected or (is_weekend and in_current_month))
        painter.setFont(num_font)
        painter.setPen(fg)
        top_rect = rect.adjusted(4, 2, -4, -rect.height() // 2)
        painter.drawText(top_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), str(qdate.day()))

        if in_current_month:
            hours = float(self._hours_by_day.get(qdate.day(), 0.0) or 0.0)
            if hours > 0:
                bottom_rect = rect.adjusted(4, rect.height() - 15, -4, -3)
                painter.fillRect(bottom_rect, badge_bg)
                painter.setPen(badge_border)
                painter.drawRect(bottom_rect.adjusted(0, 0, -1, -1))

                hours_font = painter.font()
                hours_font.setBold(True)
                hours_font.setPointSize(max(8, hours_font.pointSize() - 1))
                painter.setFont(hours_font)
                painter.setPen(badge_fg)
                painter.drawText(
                    bottom_rect,
                    int(Qt.AlignmentFlag.AlignCenter),
                    f"{hours:.1f} h",
                )

        painter.restore()


class LoginDialog(QDialog):
    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.user: dict[str, Any] | None = None
        self.setWindowTitle(f"APP Timesheet v{APP_VERSION} - Accesso")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel(f"APP Timesheet v{APP_VERSION}")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)
        layout.addLayout(form)

        last_user_file = CFG_DIR / "last_user.txt"
        last_user = "admin"
        if last_user_file.exists():
            try:
                last_user = last_user_file.read_text(encoding="utf-8").strip() or "admin"
            except Exception:
                last_user = "admin"
        self.username_edit.setText(last_user)
        self.password_edit.setFocus()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Accedi")
        buttons.accepted.connect(self._do_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _do_login(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        user = self.db.authenticate(username, password)
        if not user:
            QMessageBox.critical(self, "Accesso", "Credenziali non valide o utente disattivato.")
            return

        try:
            CFG_DIR.mkdir(parents=True, exist_ok=True)
            (CFG_DIR / "last_user.txt").write_text(username, encoding="utf-8")
        except Exception:
            pass

        self.user = user
        self.accept()


class ClientDialog(QDialog):
    def __init__(self, initial: dict[str, Any] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cliente")
        self.setModal(True)
        self.setMinimumWidth(540)
        self._build_ui(initial or {})

    def _build_ui(self, initial: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(initial.get("name", ""))
        self.referente_edit = QLineEdit(initial.get("referente", ""))
        self.telefono_edit = QLineEdit(initial.get("telefono", ""))
        self.email_edit = QLineEdit(initial.get("email", ""))
        self.rate_edit = QLineEdit(str(initial.get("hourly_rate", "")))
        self.notes_edit = QLineEdit(initial.get("notes", ""))

        form.addRow("Nome cliente", self.name_edit)
        form.addRow("Referente", self.referente_edit)
        form.addRow("Telefono", self.telefono_edit)
        form.addRow("Email", self.email_edit)
        form.addRow("Costo orario (EUR/h)", self.rate_edit)
        form.addRow("Note", self.notes_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Salva")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "name": self.name_edit.text().strip(),
            "referente": self.referente_edit.text().strip(),
            "telefono": self.telefono_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "hourly_rate": self.rate_edit.text().strip(),
            "notes": self.notes_edit.text().strip(),
        }


class ProjectDialog(QDialog):
    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        schedule: dict[str, Any] | None = None,
        is_new: bool = False,
        client_name: str = "",
        allow_save: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._allow_save = allow_save
        self.setWindowTitle("Nuova commessa" if is_new else "Gestione commessa")
        self.setModal(True)
        self.setMinimumWidth(640)
        self._build_ui(initial or {}, schedule, client_name)

    @staticmethod
    def _iso_to_ui(value: str) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return value

    def _build_ui(self, initial: dict[str, Any], schedule: dict[str, Any] | None, client_name: str) -> None:
        layout = QVBoxLayout(self)
        form = QGridLayout()

        row = 0
        if client_name:
            form.addWidget(QLabel("Cliente"), row, 0)
            client_label = QLabel(client_name)
            client_label.setStyleSheet("font-weight:bold;")
            form.addWidget(client_label, row, 1, 1, 3)
            row += 1

        form.addWidget(QLabel("Nome commessa"), row, 0)
        self.name_edit = QLineEdit(initial.get("name", ""))
        form.addWidget(self.name_edit, row, 1, 1, 3)
        row += 1

        form.addWidget(QLabel("Referente commessa"), row, 0)
        self.referente_edit = QLineEdit(initial.get("referente_commessa", ""))
        form.addWidget(self.referente_edit, row, 1, 1, 3)
        row += 1

        form.addWidget(QLabel("Costo orario (EUR/h)"), row, 0)
        self.rate_edit = QLineEdit(str(initial.get("hourly_rate", "")))
        form.addWidget(self.rate_edit, row, 1)
        row += 1

        form.addWidget(QLabel("Note"), row, 0)
        self.notes_edit = QLineEdit(initial.get("notes", ""))
        form.addWidget(self.notes_edit, row, 1, 1, 3)
        row += 1

        form.addWidget(QLabel("Descrizione"), row, 0)
        self.desc_edit = QTextEdit(initial.get("descrizione_commessa", ""))
        self.desc_edit.setFixedHeight(96)
        form.addWidget(self.desc_edit, row, 1, 1, 3)
        row += 1

        planning_title = QLabel("Pianificazione")
        planning_title.setStyleSheet("font-weight:bold;")
        form.addWidget(planning_title, row, 0, 1, 4)
        row += 1

        form.addWidget(QLabel("Data inizio (gg/mm/aaaa)"), row, 0)
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("gg/mm/aaaa")
        form.addWidget(self.start_date_edit, row, 1)

        form.addWidget(QLabel("Data fine (gg/mm/aaaa)"), row, 2)
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("gg/mm/aaaa")
        form.addWidget(self.end_date_edit, row, 3)
        row += 1

        form.addWidget(QLabel("Ore preventivate"), row, 0)
        self.hours_edit = QLineEdit()
        form.addWidget(self.hours_edit, row, 1)

        form.addWidget(QLabel("Budget (EUR)"), row, 2)
        self.budget_edit = QLineEdit()
        form.addWidget(self.budget_edit, row, 3)
        layout.addLayout(form)

        if schedule:
            self.start_date_edit.setText(self._iso_to_ui(schedule.get("start_date", "")))
            self.end_date_edit.setText(self._iso_to_ui(schedule.get("end_date", "")))
            self.hours_edit.setText(str(schedule.get("planned_hours", "")))
            self.budget_edit.setText(str(schedule.get("budget", "")))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        save_button.setText("Salva")
        save_button.setEnabled(self._allow_save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "name": self.name_edit.text().strip(),
            "referente_commessa": self.referente_edit.text().strip(),
            "hourly_rate": self.rate_edit.text().strip(),
            "notes": self.notes_edit.text().strip(),
            "descrizione_commessa": self.desc_edit.toPlainText().strip(),
            "start_date": self.start_date_edit.text().strip(),
            "end_date": self.end_date_edit.text().strip(),
            "planned_hours": self.hours_edit.text().strip(),
            "budget": self.budget_edit.text().strip(),
        }


class ActivityDialog(QDialog):
    def __init__(
        self,
        initial: dict[str, Any] | None = None,
        schedule: dict[str, Any] | None = None,
        is_new: bool = False,
        project_label: str = "",
        project_schedule: dict[str, Any] | None = None,
        allow_save: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._allow_save = allow_save
        self.setWindowTitle("Nuova attivita" if is_new else "Gestione attivita")
        self.setModal(True)
        self.setMinimumWidth(620)
        self._build_ui(initial or {}, schedule, is_new, project_label, project_schedule)

    @staticmethod
    def _iso_to_ui(value: str) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return value

    def _build_ui(
        self,
        initial: dict[str, Any],
        schedule: dict[str, Any] | None,
        is_new: bool,
        project_label: str,
        project_schedule: dict[str, Any] | None,
    ) -> None:
        layout = QVBoxLayout(self)
        form = QGridLayout()

        row = 0
        if project_label:
            form.addWidget(QLabel("Commessa"), row, 0)
            project_info = QLabel(project_label)
            project_info.setStyleSheet("font-weight:bold;")
            form.addWidget(project_info, row, 1, 1, 3)
            row += 1

        form.addWidget(QLabel("Nome attivita"), row, 0)
        self.name_edit = QLineEdit(initial.get("name", ""))
        form.addWidget(self.name_edit, row, 1, 1, 3)
        row += 1

        form.addWidget(QLabel("Tariffa oraria (EUR/h)"), row, 0)
        self.rate_edit = QLineEdit(str(initial.get("hourly_rate", "")))
        form.addWidget(self.rate_edit, row, 1)
        row += 1

        form.addWidget(QLabel("Note"), row, 0)
        self.notes_edit = QLineEdit(initial.get("notes", ""))
        form.addWidget(self.notes_edit, row, 1, 1, 3)
        row += 1

        planning_title = QLabel("Pianificazione")
        planning_title.setStyleSheet("font-weight:bold;")
        form.addWidget(planning_title, row, 0, 1, 4)
        row += 1

        form.addWidget(QLabel("Data inizio (gg/mm/aaaa)"), row, 0)
        self.start_date_edit = QLineEdit()
        self.start_date_edit.setPlaceholderText("gg/mm/aaaa")
        form.addWidget(self.start_date_edit, row, 1)

        form.addWidget(QLabel("Data fine (gg/mm/aaaa)"), row, 2)
        self.end_date_edit = QLineEdit()
        self.end_date_edit.setPlaceholderText("gg/mm/aaaa")
        form.addWidget(self.end_date_edit, row, 3)
        row += 1

        form.addWidget(QLabel("Ore preventivate"), row, 0)
        self.hours_edit = QLineEdit()
        form.addWidget(self.hours_edit, row, 1)

        form.addWidget(QLabel("Budget (EUR)"), row, 2)
        self.budget_edit = QLineEdit()
        form.addWidget(self.budget_edit, row, 3)
        layout.addLayout(form)

        if schedule:
            self.start_date_edit.setText(self._iso_to_ui(schedule.get("start_date", "")))
            self.end_date_edit.setText(self._iso_to_ui(schedule.get("end_date", "")))
            self.hours_edit.setText(str(schedule.get("planned_hours", "")))
            self.budget_edit.setText(str(schedule.get("budget", "")))
        elif is_new and project_schedule:
            self.start_date_edit.setText(self._iso_to_ui(project_schedule.get("start_date", "")))
            self.end_date_edit.setText(self._iso_to_ui(project_schedule.get("end_date", "")))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        save_button.setText("Salva")
        save_button.setEnabled(self._allow_save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "name": self.name_edit.text().strip(),
            "hourly_rate": self.rate_edit.text().strip(),
            "notes": self.notes_edit.text().strip(),
            "start_date": self.start_date_edit.text().strip(),
            "end_date": self.end_date_edit.text().strip(),
            "planned_hours": self.hours_edit.text().strip(),
            "budget": self.budget_edit.text().strip(),
        }

class DiaryEditorDialog(QDialog):
    def __init__(self, app: "TimesheetWindow", entry_id: int | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.entry_id = entry_id
        self.entry = app.db.get_diary_entry(entry_id) if entry_id else None
        self.setWindowTitle("Modifica Nota" if entry_id else "Nuova Nota")
        self.setModal(True)
        self.setMinimumSize(660, 540)
        self._build_ui()
        self._load_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.client_combo = QComboBox()
        self.project_combo = QComboBox()
        self.activity_combo = QComboBox()
        self.reminder_edit = QLineEdit()
        self.priority_check = QCheckBox("Priorita alta")
        self.content_edit = QTextEdit()
        self.content_edit.setMinimumHeight(180)

        form.addRow("Cliente", self.client_combo)
        form.addRow("Commessa", self.project_combo)
        form.addRow("Attivita", self.activity_combo)
        form.addRow("Promemoria (YYYY-MM-DD)", self.reminder_edit)
        form.addRow("", self.priority_check)
        form.addRow("Contenuto", self.content_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.client_combo.currentTextChanged.connect(self._on_client_change)
        self.project_combo.currentTextChanged.connect(self._on_project_change)

    def _load_data(self) -> None:
        clients = self.app.db.list_clients()
        client_opts = ["-- Nessuno --"] + [f"{c['id']} - {c['name']}" for c in clients]
        self.client_combo.addItems(client_opts)
        self.project_combo.addItem("-- Nessuna --")
        self.activity_combo.addItem("-- Nessuna --")

        if not self.entry:
            self.client_combo.setCurrentIndex(0)
            self.project_combo.setCurrentIndex(0)
            self.activity_combo.setCurrentIndex(0)
            return

        self.priority_check.setChecked(bool(self.entry.get("priority", 0)))
        self.reminder_edit.setText(self.entry.get("reminder_date", "") or "")
        self.content_edit.setPlainText(self.entry.get("content", "") or "")

        if self.entry.get("client_id"):
            target = f"{self.entry['client_id']} -"
            for i in range(self.client_combo.count()):
                txt = self.client_combo.itemText(i)
                if txt.startswith(target):
                    self.client_combo.setCurrentIndex(i)
                    break
        self._on_client_change()

        if self.entry.get("project_id"):
            target = f"{self.entry['project_id']} -"
            for i in range(self.project_combo.count()):
                txt = self.project_combo.itemText(i)
                if txt.startswith(target):
                    self.project_combo.setCurrentIndex(i)
                    break
        self._on_project_change()

        if self.entry.get("activity_id"):
            target = f"{self.entry['activity_id']} -"
            for i in range(self.activity_combo.count()):
                txt = self.activity_combo.itemText(i)
                if txt.startswith(target):
                    self.activity_combo.setCurrentIndex(i)
                    break

    def _on_client_change(self) -> None:
        client_id = self.app._id_from_option(self.client_combo.currentText())
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        if client_id:
            projects = self.app.db.list_projects(client_id=client_id)
            self.project_combo.addItems(["-- Nessuna --"] + [f"{p['id']} - {p['name']}" for p in projects])
        else:
            self.project_combo.addItem("-- Nessuna --")
        self.project_combo.setCurrentIndex(0)
        self.project_combo.blockSignals(False)
        self._on_project_change()

    def _on_project_change(self) -> None:
        project_id = self.app._id_from_option(self.project_combo.currentText())
        self.activity_combo.clear()
        if project_id:
            activities = self.app.db.list_activities(project_id=project_id)
            self.activity_combo.addItems(["-- Nessuna --"] + [f"{a['id']} - {a['name']}" for a in activities])
        else:
            self.activity_combo.addItem("-- Nessuna --")
        self.activity_combo.setCurrentIndex(0)

    def _save(self) -> None:
        client_id = self.app._id_from_option(self.client_combo.currentText())
        project_id = self.app._id_from_option(self.project_combo.currentText())
        activity_id = self.app._id_from_option(self.activity_combo.currentText())
        reminder = self.reminder_edit.text().strip() or None
        content = self.content_edit.toPlainText().strip()
        priority = 1 if self.priority_check.isChecked() else 0

        if not content:
            QMessageBox.warning(self, "Errore", "Il contenuto non puo essere vuoto.")
            return
        if not client_id and not project_id and not activity_id:
            QMessageBox.warning(self, "Errore", "Seleziona almeno un cliente, commessa o attivita.")
            return

        try:
            if self.entry_id is None:
                self.app.db.create_diary_entry(
                    user_id=int(self.app.current_user["id"]),
                    content=content,
                    client_id=client_id,
                    project_id=project_id,
                    activity_id=activity_id,
                    reminder_date=reminder,
                    priority=priority,
                )
            else:
                self.app.db.update_diary_entry(
                    self.entry_id,
                    content=content,
                    client_id=client_id or 0,
                    project_id=project_id or 0,
                    activity_id=activity_id or 0,
                    reminder_date=reminder or "",
                    priority=priority,
                )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Errore", str(exc))


class PDFReportDialog(QDialog):
    def __init__(self, app: "TimesheetWindow", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Genera Report PDF")
        self.setModal(True)
        self.setMinimumWidth(650)
        self._build_ui()
        self._load_options()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.client_combo = QComboBox()
        self.project_combo = QComboBox()
        self.activity_combo = QComboBox()
        self.user_combo = QComboBox()
        self.start_edit = QLineEdit()
        self.end_edit = QLineEdit()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["sintetica", "dettagliata", "gerarchica"])

        self.start_edit.setPlaceholderText("YYYY-MM-DD")
        self.end_edit.setPlaceholderText("YYYY-MM-DD")

        form.addRow("Cliente", self.client_combo)
        form.addRow("Commessa", self.project_combo)
        form.addRow("Attivita", self.activity_combo)
        form.addRow("Utente", self.user_combo)
        form.addRow("Data inizio", self.start_edit)
        form.addRow("Data fine", self.end_edit)
        form.addRow("Tipo report", self.mode_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Genera PDF")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.client_combo.currentTextChanged.connect(self._on_client_change)
        self.project_combo.currentTextChanged.connect(self._on_project_change)

    def _load_options(self) -> None:
        self.all_clients = self.app.db.list_clients()
        self.all_projects = self.app.db.list_projects()
        self.all_activities = self.app.db.list_activities()
        self.all_users = self.app.db.list_users(include_inactive=False)

        self.client_combo.addItems(["Tutti i clienti"] + [f"{c['id']} - {c['name']}" for c in self.all_clients])
        self.project_combo.addItems(
            ["Tutte le commesse"] + [f"{p['id']} - {p['client_name']} / {p['name']}" for p in self.all_projects]
        )
        self.activity_combo.addItems(["Tutte le attivita"] + [f"{a['id']} - {a['name']}" for a in self.all_activities])
        self.user_combo.addItems(["Tutti gli utenti"] + [f"{u['id']} - {u['full_name']}" for u in self.all_users])

    def _on_client_change(self) -> None:
        cid = self.app._id_from_option(self.client_combo.currentText())
        if cid:
            projects = self.app.db.list_projects(client_id=cid)
            options = ["Tutte le commesse"] + [f"{p['id']} - {p['client_name']} / {p['name']}" for p in projects]
        else:
            options = ["Tutte le commesse"] + [f"{p['id']} - {p['client_name']} / {p['name']}" for p in self.all_projects]
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItems(options)
        self.project_combo.setCurrentIndex(0)
        self.project_combo.blockSignals(False)
        self._on_project_change()

    def _on_project_change(self) -> None:
        pid = self.app._id_from_option(self.project_combo.currentText())
        if pid:
            activities = self.app.db.list_activities(project_id=pid)
            options = ["Tutte le attivita"] + [f"{a['id']} - {a['name']}" for a in activities]
        else:
            options = ["Tutte le attivita"] + [f"{a['id']} - {a['name']}" for a in self.all_activities]
        self.activity_combo.clear()
        self.activity_combo.addItems(options)
        self.activity_combo.setCurrentIndex(0)

    def _generate(self) -> None:
        try:
            client_id = self.app._id_from_option(self.client_combo.currentText())
            project_id = self.app._id_from_option(self.project_combo.currentText())
            activity_id = self.app._id_from_option(self.activity_combo.currentText())
            user_id = self.app._id_from_option(self.user_combo.currentText())
            start_date = self.start_edit.text().strip() or None
            end_date = self.end_edit.text().strip() or None
            mode = self.mode_combo.currentText()

            data = self.app.db.get_report_filtered_data(
                client_id=client_id,
                project_id=project_id,
                activity_id=activity_id,
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )
            if not data.get("timesheets"):
                QMessageBox.warning(self, "Nessun dato", "Nessun inserimento trovato con i filtri selezionati.")
                return

            parts: list[str] = []
            if client_id:
                parts.append(self.client_combo.currentText().split(" - ", 1)[-1])
            if project_id:
                raw = self.project_combo.currentText().split(" - ", 1)[-1]
                parts.append(raw.split(" / ")[-1] if " / " in raw else raw)
            if activity_id:
                parts.append(self.activity_combo.currentText().split(" - ", 1)[-1])
            if user_id:
                parts.append("Utente: " + self.user_combo.currentText().split(" - ", 1)[-1])
            if start_date and end_date:
                parts.append(f"Dal {start_date} al {end_date}")
            subtitle = " > ".join(parts) if parts else "Tutti i dati"

            title_mode = "Dettagliato" if mode == "dettagliata" else ("Gerarchico" if mode == "gerarchica" else "Sintetico")
            title = f"Report {title_mode}"

            generator = PDFReportGenerator()
            if mode == "gerarchica":
                output = generator.generate_hierarchical_report(data=data, title=title, subtitle=subtitle)
            else:
                output = generator.generate_filtered_report(data=data, mode=mode, title=title, subtitle=subtitle)

            QMessageBox.information(self, "Report generato", f"PDF generato:\n{output}")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Errore durante la generazione del report:\n{exc}")

class TimesheetWindow(QMainWindow):
    def __init__(self, db: Database, user: dict[str, Any]) -> None:
        super().__init__()
        self.db = db
        self.current_user = user
        self.selected_date = date.today()
        self.is_dark_mode = True
        self._timesheet_rows_by_id: dict[int, dict[str, Any]] = {}
        self._projects_data: list[dict[str, Any]] = []
        self._activities_data: list[dict[str, Any]] = []
        self.selected_project_id: int | None = None
        self.selected_activity_id: int | None = None
        self.editing_user_id: int | None = None
        self._diary_tab_index: int | None = None

        self.setWindowTitle(f"APP Timesheet v{APP_VERSION}")
        self.setMinimumSize(1280, 820)

        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self._run_periodic_backup)

        self._apply_theme()
        self._build_ui()
        self._backup_now_and_schedule()

    @property
    def is_admin(self) -> bool:
        return bool(self.current_user and self.current_user.get("role") == "admin")

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(DARK_THEME if self.is_dark_mode else LIGHT_THEME)
        if hasattr(self, "qt_calendar") and isinstance(self.qt_calendar, HoursCalendarWidget):
            self.qt_calendar.set_theme_mode(self.is_dark_mode)

    def _build_ui(self) -> None:
        existing = self.centralWidget()
        if existing is not None:
            existing.deleteLater()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        topbar = QHBoxLayout()
        title = QLabel(f"APP Timesheet v{APP_VERSION}")
        title.setStyleSheet("font-size:16px;font-weight:bold;")
        topbar.addWidget(title)
        topbar.addStretch(1)
        self.user_label = QLabel()
        topbar.addWidget(self.user_label)
        self._update_user_label()

        theme_btn = QPushButton("Tema")
        theme_btn.clicked.connect(self.toggle_theme)
        topbar.addWidget(theme_btn)

        logout_btn = QPushButton("Logout")
        logout_btn.clicked.connect(self.logout)
        topbar.addWidget(logout_btn)

        root.addLayout(topbar)

        self.tabview = QTabWidget()
        self.tabview.setTabPosition(QTabWidget.TabPosition.West)
        root.addWidget(self.tabview, 1)

        if self._tab_enabled("tab_calendar"):
            self.tab_calendar = QWidget()
            self.tabview.addTab(self.tab_calendar, "Calendario Ore")
            self.build_calendar_tab()

        if self._tab_enabled("tab_master"):
            self.tab_master = QWidget()
            self.tabview.addTab(self.tab_master, "Gestione Commesse")
            self.build_project_management_tab()

        if self._tab_enabled("tab_control"):
            self.tab_control = QWidget()
            self.tabview.addTab(self.tab_control, "Controllo")
            self.build_control_tab()

        self.tab_diary = QWidget()
        self._diary_tab_index = self.tabview.addTab(self.tab_diary, "Diario")
        self.build_diary_tab()

        self.tab_users = QWidget()
        self.tabview.addTab(self.tab_users, "Utenti")
        self.build_users_tab()

        self.refresh_master_data()
        self.refresh_day_entries()
        self.refresh_schedule_list()
        self.refresh_control_panel()
        self.refresh_diary_data()
        self.refresh_users_data()
        self.update_diary_alert()

    def _tab_enabled(self, key: str) -> bool:
        if self.is_admin:
            return True
        return bool(self.current_user.get(key, 1))

    def _update_user_label(self) -> None:
        self.user_label.setText(
            f"Utente: {self.current_user.get('full_name', self.current_user.get('username', ''))} "
            f"({self.current_user.get('role', '')})"
        )

    def _to_float(self, value: str, field_name: str) -> float:
        try:
            parsed = float(value.replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"{field_name}: valore non valido.") from exc
        if parsed < 0:
            raise ValueError(f"{field_name}: valore non puo essere negativo.")
        return parsed

    @staticmethod
    def _entity_option(entity_id: int, name: str) -> str:
        return f"{entity_id} - {name}"

    @staticmethod
    def _project_option(row: dict[str, Any]) -> str:
        return f"{row['id']} - {row['client_name']} / {row['name']}"

    @staticmethod
    def _activity_option(row: dict[str, Any]) -> str:
        project_name = row.get("project_name", "")
        prefix = f"{project_name} / " if project_name else ""
        return f"{row['id']} - {prefix}{row['name']}"

    @staticmethod
    def _id_from_option(value: str) -> int | None:
        if not value or " - " not in value:
            return None
        try:
            return int(value.split("-", 1)[0].strip())
        except Exception:
            return None

    def _set_combo_values(self, combo: QComboBox, values: list[str]) -> None:
        safe_values = values or [""]
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(safe_values)
        if current in safe_values:
            combo.setCurrentText(current)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _selected_table_id(self, table: QTableWidget) -> int | None:
        selected = table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        cell = table.item(row, 0)
        if not cell:
            return None
        try:
            return int(cell.text())
        except ValueError:
            return None

    def _backup_now_and_schedule(self) -> None:
        try:
            self.db.create_backup()
        except Exception as exc:
            print(f"[backup] Errore creazione backup: {exc}")
        interval_ms = AUTO_BACKUP_INTERVAL_MINUTES * 60 * 1000
        self.backup_timer.start(interval_ms)

    def _run_periodic_backup(self) -> None:
        try:
            self.db.create_backup()
        except Exception as exc:
            print(f"[backup] Errore backup periodico: {exc}")

    def _set_button_role(self, button: QPushButton, role: str) -> None:
        button.setObjectName(role)
        button.style().unpolish(button)
        button.style().polish(button)

    def apply_edit_button_style(self, button: QPushButton) -> None:
        self._set_button_role(button, "btn_warning")

    def apply_delete_button_style(self, button: QPushButton) -> None:
        self._set_button_role(button, "btn_danger")

    def toggle_theme(self) -> None:
        self.is_dark_mode = not self.is_dark_mode
        self._apply_theme()

    def logout(self) -> None:
        dlg = LoginDialog(self.db, self)
        if dlg.exec() != QDialog.DialogCode.Accepted or dlg.user is None:
            self.close()
            return
        self.current_user = dlg.user
        self.selected_date = date.today()
        self._build_ui()

    def format_date_ui(self, value: str) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return value

    def _format_date_short(self, value: str) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m")
        except Exception:
            return value

    def _format_remaining_days(self, days: int, start_date: str, end_date: str) -> str:
        if not start_date or not end_date:
            return ""
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            total = (end - start).days
            threshold = total * 0.1
        except Exception:
            total = 0
            threshold = 0
        if days < 0:
            return f"X {days}"
        if total > 0 and days <= threshold:
            return f"! {days}"
        return str(days)

    def _format_hours_diff(self, diff: float, planned: float) -> str:
        if planned == 0:
            return ""
        threshold = planned * 0.1
        if diff < 0:
            return f"X {diff:.1f}"
        if diff <= threshold:
            return f"! {diff:.1f}"
        return f"{diff:.1f}"

    def _format_budget_remaining(self, remaining: float, budget: float) -> str:
        if budget == 0:
            return ""
        threshold = budget * 0.1
        if remaining < 0:
            return f"X {remaining:.2f}"
        if remaining <= threshold:
            return f"! {remaining:.2f}"
        return f"{remaining:.2f}"

    def _ensure_combo_option(self, combo: QComboBox, value: str) -> None:
        if not value:
            return
        for i in range(combo.count()):
            if combo.itemText(i) == value:
                return
        combo.addItem(value)

    def _parse_ui_date(self, value: str, field_name: str) -> str:
        try:
            return datetime.strptime(value.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{field_name}: formato non valido (usa gg/mm/aaaa).") from exc

    def _build_planning_payload(
        self,
        start_date_text: str,
        end_date_text: str,
        hours_text: str,
        budget_text: str,
        default_start: str | None = None,
        default_end: str | None = None,
    ) -> dict[str, Any]:
        has_any_planning = any([start_date_text, end_date_text, hours_text, budget_text])
        if not has_any_planning:
            return {
                "has_any_planning": False,
                "start_date": None,
                "end_date": None,
                "planned_hours": 0.0,
                "budget": 0.0,
            }

        planned_hours = self._to_float(hours_text, "Ore preventivate") if hours_text else 0.0
        budget = self._to_float(budget_text, "Budget") if budget_text else 0.0

        if start_date_text and end_date_text:
            start_date = self._parse_ui_date(start_date_text, "Data inizio")
            end_date = self._parse_ui_date(end_date_text, "Data fine")
        else:
            if not (default_start and default_end):
                current_year = datetime.now().year
                default_start = f"{current_year}-01-01"
                default_end = f"{current_year}-12-31"
            start_date = default_start
            end_date = default_end

        if start_date > end_date:
            raise ValueError("La data di inizio deve essere precedente alla data di fine.")

        return {
            "has_any_planning": True,
            "start_date": start_date,
            "end_date": end_date,
            "planned_hours": planned_hours,
            "budget": budget,
        }

    # Calendario Ore
    def build_calendar_tab(self) -> None:
        layout = QVBoxLayout(self.tab_calendar)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel("Mese"))
        self.cal_month_combo = QComboBox()
        self.cal_month_combo.addItems([calendar.month_name[i].title() for i in range(1, 13)])
        header.addWidget(self.cal_month_combo)

        header.addWidget(QLabel("Anno"))
        self.cal_year_combo = QComboBox()
        current_year = date.today().year
        self.cal_year_combo.addItems([str(y) for y in range(current_year - 5, current_year + 6)])
        header.addWidget(self.cal_year_combo)

        btn_show = QPushButton("Mostra")
        btn_show.clicked.connect(self.show_selected_month)
        header.addWidget(btn_show)
        btn_prev = QPushButton("<")
        btn_prev.clicked.connect(self.goto_prev_month)
        header.addWidget(btn_prev)
        btn_today = QPushButton("Oggi")
        btn_today.clicked.connect(self.goto_today)
        header.addWidget(btn_today)
        btn_next = QPushButton(">")
        btn_next.clicked.connect(self.goto_next_month)
        header.addWidget(btn_next)
        header.addStretch(1)
        layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        self.qt_calendar = HoursCalendarWidget(dark_mode=self.is_dark_mode)
        self.qt_calendar.setSelectedDate(_to_qdate(self.selected_date))
        self.qt_calendar.selectionChanged.connect(self._on_calendar_selected)
        self.qt_calendar.currentPageChanged.connect(self._on_calendar_page_changed)
        left_layout.addWidget(self.qt_calendar)
        self.month_hours_label = QLabel("Totale mese: 0.00 h")
        left_layout.addWidget(self.month_hours_label)
        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        form = QGridLayout()

        self.selected_date_label = QLabel("")
        self.selected_date_label.setStyleSheet("font-weight:bold;")
        form.addWidget(self.selected_date_label, 0, 0, 1, 2)

        form.addWidget(QLabel("Cliente"), 1, 0)
        self.ts_client_combo = QComboBox()
        self.ts_client_combo.currentTextChanged.connect(self.on_timesheet_client_change)
        form.addWidget(self.ts_client_combo, 1, 1)

        form.addWidget(QLabel("Commessa"), 2, 0)
        self.ts_project_combo = QComboBox()
        self.ts_project_combo.currentTextChanged.connect(self.on_timesheet_project_change)
        form.addWidget(self.ts_project_combo, 2, 1)

        form.addWidget(QLabel("Attivita"), 3, 0)
        self.ts_activity_combo = QComboBox()
        form.addWidget(self.ts_activity_combo, 3, 1)

        form.addWidget(QLabel("Ore"), 4, 0)
        self.ts_hours_entry = QLineEdit()
        form.addWidget(self.ts_hours_entry, 4, 1)

        form.addWidget(QLabel("Note"), 5, 0)
        self.ts_note_text = QTextEdit()
        self.ts_note_text.setFixedHeight(80)
        form.addWidget(self.ts_note_text, 5, 1)
        right_layout.addLayout(form)

        actions = QHBoxLayout()
        self.ts_save_button = QPushButton("Salva ore")
        self._set_button_role(self.ts_save_button, "btn_primary")
        self.ts_save_button.clicked.connect(self.save_timesheet_entry)
        actions.addWidget(self.ts_save_button)

        self.ts_edit_button = QPushButton("Modifica selezionata")
        self.apply_edit_button_style(self.ts_edit_button)
        self.ts_edit_button.clicked.connect(self.edit_selected_timesheet)
        actions.addWidget(self.ts_edit_button)

        self.ts_delete_button = QPushButton("Elimina selezionata")
        self.apply_delete_button_style(self.ts_delete_button)
        self.ts_delete_button.clicked.connect(self.delete_selected_timesheet)
        actions.addWidget(self.ts_delete_button)
        actions.addStretch(1)
        right_layout.addLayout(actions)

        self.day_total_label = QLabel("Totale giornata: 0.00 h")
        right_layout.addWidget(self.day_total_label)

        self.ts_table = QTableWidget(0, 9 if self.is_admin else 7)
        headers = (
            ["ID", "Utente", "Cliente", "Commessa", "Attivita", "Ore", "Tariffa", "Costo", "Note"]
            if self.is_admin
            else ["ID", "Utente", "Cliente", "Commessa", "Attivita", "Ore", "Note"]
        )
        self.ts_table.setHorizontalHeaderLabels(headers)
        self.ts_table.setAlternatingRowColors(True)
        self.ts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.ts_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.ts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ts_table.itemSelectionChanged.connect(self.on_timesheet_table_select)
        self.ts_table.setColumnHidden(0, True)
        right_layout.addWidget(self.ts_table, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([430, 850])

        self._sync_month_year_from_date(self.selected_date)
        self._set_calendar_date(self.selected_date)

    def _on_calendar_selected(self) -> None:
        qd = self.qt_calendar.selectedDate()
        self._set_calendar_date(date(qd.year(), qd.month(), qd.day()))

    def _on_calendar_page_changed(self, year: int, month: int) -> None:
        self.cal_year_combo.setCurrentText(str(year))
        self.cal_month_combo.setCurrentIndex(month - 1)
        self._refresh_month_hours()

    def _sync_month_year_from_date(self, d: date) -> None:
        self.cal_year_combo.setCurrentText(str(d.year))
        self.cal_month_combo.setCurrentIndex(d.month - 1)

    def _set_calendar_date(self, new_date: date) -> None:
        self.selected_date = new_date
        self.qt_calendar.setSelectedDate(_to_qdate(new_date))
        self.selected_date_label.setText(f"Data selezionata: {new_date.isoformat()}")
        self._clear_timesheet_form()
        self.refresh_day_entries()
        self._refresh_month_hours()

    def _refresh_month_hours(self) -> None:
        year = self.qt_calendar.yearShown()
        month = self.qt_calendar.monthShown()
        user_id = int(self.current_user["id"])
        summary = self.db.get_month_hours_summary(year, month, user_id=user_id)
        total = sum(float(v) for v in summary.values())
        self.month_hours_label.setText(f"Totale mese: {total:.2f} h")
        self.qt_calendar.set_hours_map(summary)

    def _clear_timesheet_form(self) -> None:
        if hasattr(self, "ts_client_combo"):
            self.ts_client_combo.setCurrentIndex(0)
        if hasattr(self, "ts_project_combo"):
            self.ts_project_combo.setCurrentIndex(0)
        if hasattr(self, "ts_activity_combo"):
            self.ts_activity_combo.setCurrentIndex(0)
        if hasattr(self, "ts_hours_entry"):
            self.ts_hours_entry.clear()
        if hasattr(self, "ts_note_text"):
            self.ts_note_text.clear()

    def show_selected_month(self) -> None:
        month = self.cal_month_combo.currentIndex() + 1
        try:
            year = int(self.cal_year_combo.currentText())
        except ValueError:
            year = date.today().year
        self.qt_calendar.setCurrentPage(year, month)
        self._set_calendar_date(date(year, month, 1))

    def goto_prev_month(self) -> None:
        self.qt_calendar.showPreviousMonth()
        self._refresh_month_hours()

    def goto_today(self) -> None:
        self._set_calendar_date(date.today())

    def goto_next_month(self) -> None:
        self.qt_calendar.showNextMonth()
        self._refresh_month_hours()

    def _selected_timesheet_user_id(self) -> int:
        return int(self.current_user["id"])

    def on_timesheet_client_change(self, _value: str) -> None:
        client_id = self._id_from_option(self.ts_client_combo.currentText())
        if client_id:
            user_id = None if self.is_admin else int(self.current_user["id"])
            today = date.today().isoformat()
            projects = self.db.list_projects(
                client_id=client_id,
                only_with_open_schedules=True,
                user_id=user_id,
                available_from_date=today,
            )
            self._set_combo_values(self.ts_project_combo, [""] + [self._project_option(p) for p in projects])
            self.ts_project_combo.setCurrentIndex(0)
        else:
            self._set_combo_values(self.ts_project_combo, [""])
        self._set_combo_values(self.ts_activity_combo, [""])

    def on_timesheet_project_change(self, _value: str) -> None:
        project_id = self._id_from_option(self.ts_project_combo.currentText())
        if project_id:
            today = date.today().isoformat()
            activities = self.db.list_activities(
                project_id=project_id,
                only_with_open_schedules=True,
                available_from_date=today,
            )
            self._set_combo_values(self.ts_activity_combo, [""] + [self._activity_option(a) for a in activities])
            self.ts_activity_combo.setCurrentIndex(0)
        else:
            self._set_combo_values(self.ts_activity_combo, [""])

    def save_timesheet_entry(self) -> None:
        try:
            user_id = self._selected_timesheet_user_id()
            client_id = self._id_from_option(self.ts_client_combo.currentText())
            project_id = self._id_from_option(self.ts_project_combo.currentText())
            activity_id = self._id_from_option(self.ts_activity_combo.currentText())
            if not (client_id and project_id and activity_id):
                raise ValueError("Seleziona cliente, commessa e attivita.")

            if not self.is_admin and not self.db.user_can_access_activity(user_id, project_id, activity_id):
                raise ValueError("Non hai i permessi per inserire ore su questa attivita.")

            hours = self._to_float(self.ts_hours_entry.text().strip(), "Ore")
            if hours <= 0:
                raise ValueError("Ore: il valore deve essere > 0.")

            note = self.ts_note_text.toPlainText().strip()
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
            QMessageBox.critical(self, "Ore giornaliere", str(exc))
            return

        self.ts_hours_entry.clear()
        self.ts_note_text.clear()
        self.refresh_day_entries()
        self._refresh_month_hours()
        self.refresh_control_panel()
        QMessageBox.information(self, "Ore giornaliere", "Inserimento completato.")

    def refresh_day_entries(self) -> None:
        if not hasattr(self, "ts_table"):
            return

        self._timesheet_rows_by_id = {}
        self.ts_table.setRowCount(0)

        user_id = int(self.current_user["id"])
        rows = self.db.list_timesheets_for_day(self.selected_date.isoformat(), user_id=user_id)
        total_hours = 0.0
        total_cost = 0.0

        for row in rows:
            entry_id = int(row["id"])
            self._timesheet_rows_by_id[entry_id] = row
            total_hours += float(row["hours"])
            total_cost += float(row["cost"])

            idx = self.ts_table.rowCount()
            self.ts_table.insertRow(idx)
            if self.is_admin:
                data = [
                    entry_id,
                    row["username"],
                    row["client_name"],
                    row["project_name"],
                    row["activity_name"],
                    f"{row['hours']:.2f}",
                    f"{row['effective_rate']:.2f}",
                    f"{row['cost']:.2f}",
                    row["note"] or "",
                ]
            else:
                data = [
                    entry_id,
                    row["username"],
                    row["client_name"],
                    row["project_name"],
                    row["activity_name"],
                    f"{row['hours']:.2f}",
                    row["note"] or "",
                ]
            for col, value in enumerate(data):
                self.ts_table.setItem(idx, col, _readonly_item(value))

        if self.is_admin:
            self.day_total_label.setText(f"Totale giornata: {total_hours:.2f} h | {total_cost:.2f} EUR")
        else:
            self.day_total_label.setText(f"Totale giornata: {total_hours:.2f} h")

    def on_timesheet_table_select(self) -> None:
        entry_id = self._selected_table_id(self.ts_table)
        if not entry_id:
            return
        row = self._timesheet_rows_by_id.get(entry_id)
        if not row:
            return

        client_option = self._entity_option(row["client_id"], row["client_name"])
        self._ensure_combo_option(self.ts_client_combo, client_option)
        self.ts_client_combo.setCurrentText(client_option)
        self.on_timesheet_client_change(client_option)

        project_option = self._project_option(
            {"id": row["project_id"], "client_name": row["client_name"], "name": row["project_name"]}
        )
        self._ensure_combo_option(self.ts_project_combo, project_option)
        self.ts_project_combo.setCurrentText(project_option)
        self.on_timesheet_project_change(project_option)

        activity_option = self._activity_option(
            {"id": row["activity_id"], "project_name": row["project_name"], "name": row["activity_name"]}
        )
        self._ensure_combo_option(self.ts_activity_combo, activity_option)
        self.ts_activity_combo.setCurrentText(activity_option)

        self.ts_hours_entry.setText(f"{float(row['hours']):.2f}")
        self.ts_note_text.setPlainText(row.get("note", "") or "")

    def edit_selected_timesheet(self) -> None:
        entry_id = self._selected_table_id(self.ts_table)
        if not entry_id:
            QMessageBox.warning(self, "Ore giornaliere", "Seleziona una riga da modificare.")
            return
        try:
            user_id = self._selected_timesheet_user_id()
            client_id = self._id_from_option(self.ts_client_combo.currentText())
            project_id = self._id_from_option(self.ts_project_combo.currentText())
            activity_id = self._id_from_option(self.ts_activity_combo.currentText())
            if not (client_id and project_id and activity_id):
                raise ValueError("Seleziona cliente, commessa e attivita.")

            if not self.is_admin and not self.db.user_can_access_activity(user_id, project_id, activity_id):
                raise ValueError("Non hai i permessi per modificare ore su questa attivita.")

            hours = self._to_float(self.ts_hours_entry.text().strip(), "Ore")
            if hours <= 0:
                raise ValueError("Ore: il valore deve essere > 0.")
            note = self.ts_note_text.toPlainText().strip()

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
            QMessageBox.critical(self, "Ore giornaliere", str(exc))
            return

        self.refresh_day_entries()
        self._refresh_month_hours()
        self.refresh_control_panel()
        QMessageBox.information(self, "Ore giornaliere", "Voce aggiornata.")

    def delete_selected_timesheet(self) -> None:
        entry_id = self._selected_table_id(self.ts_table)
        if not entry_id:
            QMessageBox.warning(self, "Ore giornaliere", "Seleziona una riga da eliminare.")
            return
        if QMessageBox.question(self, "Conferma", "Eliminare la voce selezionata?") != QMessageBox.StandardButton.Yes:
            return

        self.db.delete_timesheet(entry_id, int(self.current_user["id"]), self.is_admin)
        self.refresh_day_entries()
        self._refresh_month_hours()
        self.refresh_control_panel()

    # Gestione Commesse
    def build_project_management_tab(self) -> None:
        layout = QVBoxLayout(self.tab_master)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.addWidget(QLabel("Cliente"))
        self.pm_client_combo = QComboBox()
        self.pm_client_combo.currentTextChanged.connect(self.on_pm_client_change)
        top.addWidget(self.pm_client_combo)

        btn_add_client = QPushButton("Nuovo cliente")
        btn_add_client.clicked.connect(self.add_client)
        top.addWidget(btn_add_client)
        btn_edit_client = QPushButton("Modifica cliente")
        self.apply_edit_button_style(btn_edit_client)
        btn_edit_client.clicked.connect(self.edit_client)
        top.addWidget(btn_edit_client)
        btn_del_client = QPushButton("Elimina cliente")
        self.apply_delete_button_style(btn_del_client)
        btn_del_client.clicked.connect(self.delete_client)
        top.addWidget(btn_del_client)
        top.addStretch(1)
        layout.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        project_panel = QWidget()
        project_layout = QVBoxLayout(project_panel)
        project_actions = QHBoxLayout()

        self.project_search_entry = QLineEdit()
        self.project_search_entry.setPlaceholderText("Filtra commesse...")
        self.project_search_entry.textChanged.connect(self.filter_projects_tree)
        project_actions.addWidget(self.project_search_entry)

        self.show_closed_projects = QCheckBox("Mostra chiuse")
        self.show_closed_projects.setChecked(False)
        self.show_closed_projects.stateChanged.connect(self.refresh_projects_tree)
        project_actions.addWidget(self.show_closed_projects)

        btn_new_project = QPushButton("Nuova commessa")
        btn_new_project.clicked.connect(self.pm_new_project)
        project_actions.addWidget(btn_new_project)
        btn_edit_project = QPushButton("Modifica")
        self.apply_edit_button_style(btn_edit_project)
        btn_edit_project.clicked.connect(self.pm_edit_project)
        project_actions.addWidget(btn_edit_project)
        btn_del_project = QPushButton("Elimina")
        self.apply_delete_button_style(btn_del_project)
        btn_del_project.clicked.connect(self.pm_delete_project)
        project_actions.addWidget(btn_del_project)
        self.btn_close_project = QPushButton("Chiudi")
        self.btn_close_project.clicked.connect(self.pm_close_project)
        project_actions.addWidget(self.btn_close_project)
        self.btn_open_project = QPushButton("Apri")
        self.btn_open_project.clicked.connect(self.pm_open_project)
        project_actions.addWidget(self.btn_open_project)
        project_layout.addLayout(project_actions)

        self.projects_table = QTableWidget(0, 7)
        self.projects_table.setHorizontalHeaderLabels(["ID", "Commessa", "Stato", "Referente", "Periodo", "Ore", "Budget"])
        self.projects_table.setColumnHidden(0, True)
        self.projects_table.setAlternatingRowColors(True)
        self.projects_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.projects_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.projects_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.projects_table.itemSelectionChanged.connect(self.on_pm_projects_tree_select)
        self.projects_table.itemDoubleClicked.connect(self.on_projects_table_double_click)
        project_layout.addWidget(self.projects_table, 1)

        project_info_group = QGroupBox("Riepilogo commessa")
        project_info_layout = QVBoxLayout(project_info_group)
        self.project_info_text = QPlainTextEdit()
        self.project_info_text.setReadOnly(True)
        project_info_layout.addWidget(self.project_info_text)
        project_layout.addWidget(project_info_group)
        splitter.addWidget(project_panel)

        activity_panel = QWidget()
        activity_layout = QVBoxLayout(activity_panel)
        activity_actions = QHBoxLayout()

        self.activity_search_entry = QLineEdit()
        self.activity_search_entry.setPlaceholderText("Filtra attivita...")
        self.activity_search_entry.textChanged.connect(self.filter_activities_tree)
        activity_actions.addWidget(self.activity_search_entry)

        self.pm_new_activity_btn = QPushButton("Nuova attivita")
        self.pm_new_activity_btn.clicked.connect(self.pm_new_activity)
        activity_actions.addWidget(self.pm_new_activity_btn)
        self.pm_edit_activity_btn = QPushButton("Modifica")
        self.apply_edit_button_style(self.pm_edit_activity_btn)
        self.pm_edit_activity_btn.clicked.connect(self.pm_edit_activity_window)
        activity_actions.addWidget(self.pm_edit_activity_btn)
        btn_del_activity = QPushButton("Elimina")
        self.apply_delete_button_style(btn_del_activity)
        btn_del_activity.clicked.connect(self.pm_delete_activity)
        activity_actions.addWidget(btn_del_activity)
        activity_layout.addLayout(activity_actions)

        self.activities_table = QTableWidget(0, 6)
        self.activities_table.setHorizontalHeaderLabels(["ID", "Attivita", "Periodo", "Ore", "Budget", "Tariffa"])
        self.activities_table.setColumnHidden(0, True)
        self.activities_table.setAlternatingRowColors(True)
        self.activities_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.activities_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.activities_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.activities_table.itemSelectionChanged.connect(self.on_pm_activities_tree_select)
        self.activities_table.itemDoubleClicked.connect(self.on_activities_table_double_click)
        activity_layout.addWidget(self.activities_table, 1)

        activity_info_group = QGroupBox("Riepilogo attivita")
        activity_info_layout = QVBoxLayout(activity_info_group)
        self.activity_info_text = QPlainTextEdit()
        self.activity_info_text.setReadOnly(True)
        activity_info_layout.addWidget(self.activity_info_text)

        assign_actions = QHBoxLayout()
        btn_add_user = QPushButton("Assegna utente")
        btn_add_user.clicked.connect(self.add_user_to_activity)
        assign_actions.addWidget(btn_add_user)
        btn_remove_user = QPushButton("Rimuovi utente")
        btn_remove_user.clicked.connect(self.remove_user_from_activity)
        assign_actions.addWidget(btn_remove_user)
        assign_actions.addStretch(1)
        activity_info_layout.addLayout(assign_actions)

        self.activity_users_list = QListWidget()
        activity_info_layout.addWidget(self.activity_users_list)
        activity_layout.addWidget(activity_info_group)
        splitter.addWidget(activity_panel)
        splitter.setSizes([680, 680])

        self.clear_project_info_box()
        self.clear_activity_info_box()

    def on_pm_client_change(self, _value: str) -> None:
        self.selected_project_id = None
        self.selected_activity_id = None
        self.refresh_projects_tree()
        self.refresh_activities_tree()

    def refresh_projects_tree(self) -> None:
        if not hasattr(self, "projects_table"):
            return

        client_id = self._id_from_option(self.pm_client_combo.currentText())
        self._projects_data = []
        if not client_id:
            self.filter_projects_tree()
            return

        projects = self.db.list_projects(client_id=client_id)
        schedules = self.db.list_schedules()
        show_closed = self.show_closed_projects.isChecked()

        for project in projects:
            project_schedule = next((s for s in schedules if s["project_id"] == project["id"] and s["activity_id"] is None), None)
            if project_schedule:
                is_closed = project_schedule.get("status", "aperta") == "chiusa"
            else:
                is_closed = bool(project.get("closed", 0))

            if is_closed and not show_closed:
                continue

            state_text = "Chiusa" if is_closed else "Aperta"
            period = "--"
            planned_hours = "--"
            budget = "--"
            referente = project.get("referente_commessa", "--") or "--"
            if project_schedule:
                start = self.format_date_ui(project_schedule["start_date"])
                end = self.format_date_ui(project_schedule["end_date"])
                period = f"{start} - {end}"
                planned_hours = f"{project_schedule['planned_hours']:.1f}"
                budget = f"{project_schedule.get('budget', 0.0):.2f}"

            self._projects_data.append(
                {
                    "id": int(project["id"]),
                    "name": project["name"],
                    "state": state_text,
                    "referente": referente,
                    "period": period,
                    "hours": planned_hours,
                    "budget": budget,
                    "is_closed": is_closed,
                }
            )
        self.filter_projects_tree()

    def filter_projects_tree(self) -> None:
        if not hasattr(self, "projects_table"):
            return
        text = self.project_search_entry.text().strip().lower() if hasattr(self, "project_search_entry") else ""
        current_id = self._selected_table_id(self.projects_table)

        self.projects_table.setRowCount(0)
        for row in self._projects_data:
            haystack = f"{row['name']} {row['state']} {row['referente']} {row['period']} {row['hours']} {row['budget']}".lower()
            if text and text not in haystack:
                continue
            idx = self.projects_table.rowCount()
            self.projects_table.insertRow(idx)
            values = [row["id"], row["name"], row["state"], row["referente"], row["period"], row["hours"], row["budget"]]
            for col, value in enumerate(values):
                item = _readonly_item(value)
                if row["is_closed"]:
                    item.setForeground(QColor("gray"))
                self.projects_table.setItem(idx, col, item)

        if current_id:
            for r in range(self.projects_table.rowCount()):
                cell = self.projects_table.item(r, 0)
                if cell and cell.text() == str(current_id):
                    self.projects_table.selectRow(r)
                    break

    def refresh_activities_tree(self) -> None:
        if not hasattr(self, "activities_table"):
            return
        self._activities_data = []
        if not self.selected_project_id:
            self.filter_activities_tree()
            return

        activities = self.db.list_activities(self.selected_project_id)
        schedules = self.db.list_schedules()

        for activity in activities:
            period = "--"
            planned_hours = "--"
            budget = "--"
            schedule = next((s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] == activity["id"]), None)
            if schedule:
                period = f"{self.format_date_ui(schedule['start_date'])} - {self.format_date_ui(schedule['end_date'])}"
                planned_hours = f"{schedule['planned_hours']:.1f}"
                budget = f"{schedule.get('budget', 0.0):.2f}"

            self._activities_data.append(
                {
                    "id": int(activity["id"]),
                    "name": activity["name"],
                    "period": period,
                    "hours": planned_hours,
                    "budget": budget,
                    "rate": f"{float(activity['hourly_rate']):.2f}",
                }
            )
        self.filter_activities_tree()

    def filter_activities_tree(self) -> None:
        if not hasattr(self, "activities_table"):
            return
        text = self.activity_search_entry.text().strip().lower() if hasattr(self, "activity_search_entry") else ""
        current_id = self._selected_table_id(self.activities_table)

        self.activities_table.setRowCount(0)
        for row in self._activities_data:
            haystack = f"{row['name']} {row['period']} {row['hours']} {row['budget']} {row['rate']}".lower()
            if text and text not in haystack:
                continue
            idx = self.activities_table.rowCount()
            self.activities_table.insertRow(idx)
            values = [row["id"], row["name"], row["period"], row["hours"], row["budget"], row["rate"]]
            for col, value in enumerate(values):
                self.activities_table.setItem(idx, col, _readonly_item(value))

        if current_id:
            for r in range(self.activities_table.rowCount()):
                cell = self.activities_table.item(r, 0)
                if cell and cell.text() == str(current_id):
                    self.activities_table.selectRow(r)
                    break

    def on_pm_projects_tree_select(self) -> None:
        project_id = self._selected_table_id(self.projects_table)
        self.selected_project_id = project_id
        self.selected_activity_id = None
        if not project_id:
            self.clear_project_info_box()
            self.clear_activity_info_box()
            self.refresh_activities_tree()
            return

        project = self.db.get_project(project_id)
        schedules = self.db.list_schedules()
        project_schedule = next((s for s in schedules if s["project_id"] == project_id and s["activity_id"] is None), None)
        is_closed = False
        if project_schedule:
            is_closed = project_schedule.get("status", "aperta") == "chiusa"
        elif project:
            is_closed = bool(project.get("closed", 0))

        self.pm_new_activity_btn.setEnabled(not is_closed)
        self.pm_edit_activity_btn.setEnabled(not is_closed)
        self.update_project_info_box(project, project_schedule, is_closed)
        self.refresh_activities_tree()
        self.clear_activity_info_box()

    def on_pm_activities_tree_select(self) -> None:
        self.selected_activity_id = self._selected_table_id(self.activities_table)
        if self.selected_activity_id:
            self.update_activity_info_box()
        else:
            self.clear_activity_info_box()

    def on_projects_table_double_click(self, _item: QTableWidgetItem) -> None:
        if self.selected_project_id:
            self.pm_edit_project()

    def on_activities_table_double_click(self, _item: QTableWidgetItem) -> None:
        if self.selected_activity_id:
            self.pm_edit_activity_window()

    def update_project_info_box(self, project: dict[str, Any] | None, schedule: dict[str, Any] | None, is_closed: bool) -> None:
        if not project:
            self.clear_project_info_box()
            return
        lines = [
            f"Nome: {project['name']}",
            f"Stato: {'Chiusa' if is_closed else 'Aperta'}",
            f"Referente: {project.get('referente_commessa', 'Non specificato') or 'Non specificato'}",
        ]
        descrizione = (project.get("descrizione_commessa") or "").strip()
        if descrizione:
            lines.append(f"Descrizione: {descrizione}")
        if schedule:
            lines.extend(
                [
                    f"Inizio: {self.format_date_ui(schedule['start_date'])}",
                    f"Fine: {self.format_date_ui(schedule['end_date'])}",
                    f"Ore pianificate: {float(schedule['planned_hours']):.1f}",
                    f"Budget: EUR {float(schedule.get('budget', 0.0)):.2f}",
                ]
            )
        else:
            lines.append("Nessuna pianificazione impostata")
        notes = (project.get("notes") or "").strip()
        if notes:
            lines.append(f"Note: {notes}")
        self.project_info_text.setPlainText("\n".join(lines))

    def clear_project_info_box(self) -> None:
        if hasattr(self, "project_info_text"):
            self.project_info_text.setPlainText("Nessuna commessa selezionata")

    def update_activity_info_box(self) -> None:
        if not self.selected_activity_id or not self.selected_project_id:
            self.clear_activity_info_box()
            return
        activity = self.db.get_activity(self.selected_activity_id)
        if not activity:
            self.clear_activity_info_box()
            return
        lines = [
            f"Nome: {activity['name']}",
            f"Tariffa oraria: EUR {float(activity['hourly_rate']):.2f}/h",
        ]
        notes = (activity.get("notes") or "").strip()
        if notes:
            lines.append(f"Note: {notes}")
        schedules = self.db.list_schedules()
        schedule = next((s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] == self.selected_activity_id), None)
        if schedule:
            lines.extend(
                [
                    f"Inizio: {self.format_date_ui(schedule['start_date'])}",
                    f"Fine: {self.format_date_ui(schedule['end_date'])}",
                    f"Ore pianificate: {float(schedule['planned_hours']):.1f}",
                    f"Budget: EUR {float(schedule.get('budget', 0.0)):.2f}",
                ]
            )
        else:
            lines.append("Nessuna pianificazione impostata")
        self.activity_info_text.setPlainText("\n".join(lines))
        self.load_activity_users()

    def clear_activity_info_box(self) -> None:
        if hasattr(self, "activity_info_text"):
            self.activity_info_text.setPlainText("Nessuna attivita selezionata")
        if hasattr(self, "activity_users_list"):
            self.activity_users_list.clear()

    def load_activity_users(self) -> None:
        if not (self.selected_project_id and self.selected_activity_id):
            self.activity_users_list.clear()
            return
        self.activity_users_list.clear()
        assignments = self.db.get_user_project_assignments(self.selected_project_id)
        for assignment in assignments:
            if assignment.get("activity_id") == self.selected_activity_id:
                item = QListWidgetItem(f"{assignment['full_name']} ({assignment['username']})")
                item.setData(Qt.ItemDataRole.UserRole, int(assignment["user_id"]))
                self.activity_users_list.addItem(item)

    def add_user_to_activity(self) -> None:
        if not (self.selected_project_id and self.selected_activity_id):
            QMessageBox.warning(self, "Assegnazione", "Seleziona prima un'attivita.")
            return

        all_users = self.db.list_users(include_inactive=False)
        assignments = self.db.get_user_project_assignments(self.selected_project_id)
        assigned_ids = {int(a["user_id"]) for a in assignments if a.get("activity_id") == self.selected_activity_id}
        options = [u for u in all_users if int(u["id"]) not in assigned_ids]
        if not options:
            QMessageBox.information(self, "Assegnazione", "Tutti gli utenti sono gia assegnati a questa attivita.")
            return

        labels = [f"{u['id']} - {u['full_name']} ({u['username']})" for u in options]
        choice, ok = QInputDialog.getItem(self, "Assegna utente", "Seleziona utente", labels, editable=False)
        if not ok:
            return
        user_id = self._id_from_option(choice)
        if not user_id:
            return
        self.db.add_user_project_assignment(user_id, self.selected_project_id, self.selected_activity_id)
        self.load_activity_users()
        QMessageBox.information(self, "Assegnazione", "Utente aggiunto con successo.")

    def remove_user_from_activity(self) -> None:
        if not (self.selected_project_id and self.selected_activity_id):
            QMessageBox.warning(self, "Rimozione", "Seleziona prima un'attivita.")
            return
        item = self.activity_users_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Rimozione", "Seleziona un utente da rimuovere.")
            return
        user_id = item.data(Qt.ItemDataRole.UserRole)
        if not user_id:
            return
        if QMessageBox.question(self, "Conferma", "Rimuovere l'utente selezionato dall'attivita?") != QMessageBox.StandardButton.Yes:
            return
        self.db.remove_user_project_assignment(int(user_id), self.selected_project_id, self.selected_activity_id)
        self.load_activity_users()
        QMessageBox.information(self, "Rimozione", "Utente rimosso con successo.")

    def _current_client_id(self) -> int | None:
        return self._id_from_option(self.pm_client_combo.currentText())

    def add_client(self) -> None:
        dialog = ClientDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome cliente obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Costo orario")
            self.db.add_client(name=name, hourly_rate=rate, notes=values["notes"], referente=values["referente"], telefono=values["telefono"], email=values["email"])
            self.refresh_master_data()
            QMessageBox.information(self, "Clienti", "Cliente aggiunto con successo.")
        except Exception as exc:
            QMessageBox.critical(self, "Clienti", str(exc))

    def edit_client(self) -> None:
        client_id = self._current_client_id()
        if not client_id:
            QMessageBox.information(self, "Clienti", "Seleziona prima un cliente.")
            return
        client = next((c for c in self.db.list_clients() if c["id"] == client_id), None)
        if not client:
            QMessageBox.critical(self, "Clienti", "Cliente non trovato.")
            return
        dialog = ClientDialog(initial=client, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome cliente obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Costo orario")
            self.db.update_client(client_id=client_id, name=name, hourly_rate=rate, notes=values["notes"], referente=values["referente"], telefono=values["telefono"], email=values["email"])
            self.refresh_master_data()
            self.pm_client_combo.setCurrentText(self._entity_option(client_id, name))
            QMessageBox.information(self, "Clienti", "Cliente aggiornato.")
        except Exception as exc:
            QMessageBox.critical(self, "Clienti", str(exc))

    def delete_client(self) -> None:
        client_id = self._current_client_id()
        if not client_id:
            QMessageBox.information(self, "Clienti", "Seleziona prima un cliente.")
            return
        if QMessageBox.question(self, "Conferma", "Eliminare il cliente? Verranno eliminati anche commesse, attivita e timesheet associati.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_client(client_id)
            self.refresh_master_data()
            QMessageBox.information(self, "Clienti", "Cliente eliminato.")
        except Exception as exc:
            QMessageBox.critical(self, "Clienti", str(exc))

    def pm_new_project(self) -> None:
        client_id = self._current_client_id()
        if not client_id:
            QMessageBox.information(self, "Commesse", "Seleziona prima un cliente.")
            return

        client = next((c for c in self.db.list_clients() if c["id"] == client_id), None)
        if not client:
            QMessageBox.critical(self, "Commesse", "Cliente non trovato.")
            return

        initial = {
            "name": "",
            "referente_commessa": "",
            "hourly_rate": client.get("hourly_rate", 0.0),
            "notes": "",
            "descrizione_commessa": "",
        }
        dialog = ProjectDialog(
            initial=initial,
            schedule=None,
            is_new=True,
            client_name=client.get("name", ""),
            allow_save=True,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome commessa obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Costo orario")

            planning = self._build_planning_payload(
                start_date_text=values["start_date"],
                end_date_text=values["end_date"],
                hours_text=values["planned_hours"],
                budget_text=values["budget"],
            )

            project_id = self.db.add_project(
                client_id=client_id,
                name=name,
                hourly_rate=rate,
                notes=values["notes"],
                referente_commessa=values["referente_commessa"],
                descrizione_commessa=values["descrizione_commessa"],
            )
            self.selected_project_id = project_id

            if planning["has_any_planning"]:
                self.db.add_schedule(
                    project_id=project_id,
                    activity_id=None,
                    start_date=planning["start_date"],
                    end_date=planning["end_date"],
                    planned_hours=planning["planned_hours"],
                    note="",
                    budget=planning["budget"],
                )

            self.refresh_master_data()
            self.refresh_projects_tree()
            self.refresh_control_panel()
            QMessageBox.information(self, "Commesse", "Commessa creata.")
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                QMessageBox.critical(self, "Commesse", "Esiste gia una commessa con questo nome per il cliente selezionato.")
            else:
                QMessageBox.critical(self, "Commesse", f"Errore database: {exc}")
        except ValueError as exc:
            QMessageBox.critical(self, "Commesse", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Commesse", f"Errore: {exc}")

    def pm_edit_project(self) -> None:
        project_id = self._selected_table_id(self.projects_table)
        if not project_id:
            QMessageBox.information(self, "Commesse", "Seleziona una commessa.")
            return

        project = self.db.get_project(project_id)
        if not project:
            QMessageBox.critical(self, "Commesse", "Commessa non trovata.")
            return

        schedules = self.db.list_schedules()
        project_schedule = next(
            (s for s in schedules if s["project_id"] == project_id and s["activity_id"] is None),
            None,
        )
        is_closed = False
        if project_schedule:
            is_closed = project_schedule.get("status", "aperta") == "chiusa"
        else:
            is_closed = bool(project.get("closed", 0))

        dialog = ProjectDialog(
            initial=project,
            schedule=project_schedule,
            is_new=False,
            client_name=project.get("client_name", ""),
            allow_save=not is_closed,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome commessa obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Costo orario")

            planning = self._build_planning_payload(
                start_date_text=values["start_date"],
                end_date_text=values["end_date"],
                hours_text=values["planned_hours"],
                budget_text=values["budget"],
            )

            self.db.update_project(
                project_id=project_id,
                name=name,
                hourly_rate=rate,
                notes=values["notes"],
                referente_commessa=values["referente_commessa"],
                descrizione_commessa=values["descrizione_commessa"],
            )

            if planning["has_any_planning"]:
                if project_schedule:
                    self.db.update_schedule(
                        schedule_id=int(project_schedule["id"]),
                        project_id=project_id,
                        activity_id=None,
                        start_date=planning["start_date"],
                        end_date=planning["end_date"],
                        planned_hours=planning["planned_hours"],
                        note="",
                        budget=planning["budget"],
                    )
                else:
                    self.db.add_schedule(
                        project_id=project_id,
                        activity_id=None,
                        start_date=planning["start_date"],
                        end_date=planning["end_date"],
                        planned_hours=planning["planned_hours"],
                        note="",
                        budget=planning["budget"],
                    )
            elif project_schedule:
                answer = QMessageBox.question(
                    self,
                    "Commesse",
                    "Vuoi eliminare la pianificazione di questa commessa?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.db.delete_schedule(int(project_schedule["id"]))

            self.refresh_master_data()
            self.refresh_projects_tree()
            self.refresh_control_panel()
            QMessageBox.information(self, "Commesse", "Commessa aggiornata.")
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                QMessageBox.critical(self, "Commesse", "Esiste gia una commessa con questo nome per il cliente selezionato.")
            else:
                QMessageBox.critical(self, "Commesse", f"Errore database: {exc}")
        except ValueError as exc:
            QMessageBox.critical(self, "Commesse", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Commesse", f"Errore: {exc}")

    def pm_delete_project(self) -> None:
        project_id = self._selected_table_id(self.projects_table)
        if not project_id:
            QMessageBox.information(self, "Commesse", "Seleziona una commessa.")
            return
        if QMessageBox.question(self, "Conferma", "Eliminare la commessa? Verranno eliminati anche attivita, pianificazioni e timesheet associati.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_project(project_id)
            self.selected_project_id = None
            self.selected_activity_id = None
            self.refresh_master_data()
            QMessageBox.information(self, "Commesse", "Commessa eliminata.")
        except Exception as exc:
            QMessageBox.critical(self, "Commesse", str(exc))

    def pm_close_project(self) -> None:
        project_id = self._selected_table_id(self.projects_table)
        if not project_id:
            QMessageBox.information(self, "Commesse", "Seleziona una commessa.")
            return
        try:
            self.db.close_project(project_id)
            self.refresh_master_data()
            self.refresh_projects_tree()
            QMessageBox.information(self, "Commesse", "Commessa chiusa.")
        except Exception as exc:
            QMessageBox.critical(self, "Commesse", str(exc))

    def pm_open_project(self) -> None:
        project_id = self._selected_table_id(self.projects_table)
        if not project_id:
            QMessageBox.information(self, "Commesse", "Seleziona una commessa.")
            return
        try:
            self.db.open_project(project_id)
            self.refresh_master_data()
            self.refresh_projects_tree()
            QMessageBox.information(self, "Commesse", "Commessa riaperta.")
        except Exception as exc:
            QMessageBox.critical(self, "Commesse", str(exc))

    def pm_new_activity(self) -> None:
        if not self.selected_project_id:
            QMessageBox.information(self, "Attivita", "Seleziona prima una commessa.")
            return

        project = self.db.get_project(self.selected_project_id)
        if not project:
            QMessageBox.critical(self, "Attivita", "Commessa non trovata.")
            return

        schedules = self.db.list_schedules()
        project_schedule = next(
            (s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] is None),
            None,
        )
        is_project_closed = False
        if project_schedule:
            is_project_closed = project_schedule.get("status", "aperta") == "chiusa"
        else:
            is_project_closed = bool(project.get("closed", 0))

        initial = {
            "name": "",
            "hourly_rate": 0.0,
            "notes": "",
            "project_id": self.selected_project_id,
        }
        dialog = ActivityDialog(
            initial=initial,
            schedule=None,
            is_new=True,
            project_label=f"{project.get('client_name', '')} / {project.get('name', '')}",
            project_schedule=project_schedule,
            allow_save=not is_project_closed,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome attivita obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Tariffa oraria")

            planning = self._build_planning_payload(
                start_date_text=values["start_date"],
                end_date_text=values["end_date"],
                hours_text=values["planned_hours"],
                budget_text=values["budget"],
                default_start=project_schedule.get("start_date") if project_schedule else None,
                default_end=project_schedule.get("end_date") if project_schedule else None,
            )

            warnings: list[str] = []
            if planning["has_any_planning"]:
                project_schedule_check = next(
                    (s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] is None),
                    None,
                )
                if project_schedule_check:
                    project_end_date = project_schedule_check["end_date"]
                    project_planned_hours = float(project_schedule_check.get("planned_hours", 0.0))
                    project_budget = float(project_schedule_check.get("budget", 0.0))

                    if planning["end_date"] > project_end_date:
                        warnings.append(
                            "Data fine attivita oltre la data fine della commessa "
                            f"({self.format_date_ui(planning['end_date'])} > {self.format_date_ui(project_end_date)})."
                        )

                    activity_schedules = [
                        s for s in schedules if s["project_id"] == self.selected_project_id and s["activity_id"] is not None
                    ]
                    total_hours = sum(float(s.get("planned_hours", 0.0)) for s in activity_schedules)
                    total_budget = sum(float(s.get("budget", 0.0)) for s in activity_schedules)
                    total_hours += planning["planned_hours"]
                    total_budget += planning["budget"]

                    if project_planned_hours > 0 and total_hours > project_planned_hours:
                        warnings.append(
                            f"Ore totali attivita ({total_hours:.1f}h) superiori alle ore commessa ({project_planned_hours:.1f}h)."
                        )
                    if project_budget > 0 and total_budget > project_budget:
                        warnings.append(
                            f"Budget totale attivita ({total_budget:.2f} EUR) superiore al budget commessa ({project_budget:.2f} EUR)."
                        )

            new_activity_id = self.db.add_activity(
                project_id=self.selected_project_id,
                name=name,
                hourly_rate=rate,
                notes=values["notes"],
            )
            self.selected_activity_id = new_activity_id

            if planning["has_any_planning"]:
                self.db.add_schedule(
                    project_id=self.selected_project_id,
                    activity_id=new_activity_id,
                    start_date=planning["start_date"],
                    end_date=planning["end_date"],
                    planned_hours=planning["planned_hours"],
                    note="",
                    budget=planning["budget"],
                )

            self.refresh_activities_tree()
            self.refresh_master_data()
            self.refresh_control_panel()
            if warnings:
                QMessageBox.warning(self, "Attivita", "Attivita salvata, ma attenzione:\n\n" + "\n".join(warnings))
            else:
                QMessageBox.information(self, "Attivita", "Attivita creata.")
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                QMessageBox.critical(self, "Attivita", "Esiste gia un'attivita con questo nome per la commessa selezionata.")
            else:
                QMessageBox.critical(self, "Attivita", f"Errore database: {exc}")
        except ValueError as exc:
            QMessageBox.critical(self, "Attivita", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Attivita", f"Errore: {exc}")

    def pm_edit_activity_window(self) -> None:
        if not self.selected_activity_id:
            QMessageBox.information(self, "Attivita", "Seleziona un'attivita.")
            return

        activity = self.db.get_activity(self.selected_activity_id)
        if not activity:
            QMessageBox.critical(self, "Attivita", "Attivita non trovata.")
            return

        project_id = int(activity["project_id"])
        project = self.db.get_project(project_id)
        schedules = self.db.list_schedules()
        project_schedule = next((s for s in schedules if s["project_id"] == project_id and s["activity_id"] is None), None)
        activity_schedule = next(
            (s for s in schedules if s["project_id"] == project_id and s["activity_id"] == self.selected_activity_id),
            None,
        )

        is_project_closed = False
        if project_schedule:
            is_project_closed = project_schedule.get("status", "aperta") == "chiusa"
        elif project:
            is_project_closed = bool(project.get("closed", 0))

        project_label = ""
        if project:
            project_label = f"{project.get('client_name', '')} / {project.get('name', '')}"

        dialog = ActivityDialog(
            initial=activity,
            schedule=activity_schedule,
            is_new=False,
            project_label=project_label,
            project_schedule=project_schedule,
            allow_save=not is_project_closed,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        try:
            name = values["name"]
            if not name:
                raise ValueError("Nome attivita obbligatorio.")
            rate = self._to_float(values["hourly_rate"] or "0", "Tariffa oraria")

            planning = self._build_planning_payload(
                start_date_text=values["start_date"],
                end_date_text=values["end_date"],
                hours_text=values["planned_hours"],
                budget_text=values["budget"],
                default_start=project_schedule.get("start_date") if project_schedule else None,
                default_end=project_schedule.get("end_date") if project_schedule else None,
            )

            warnings: list[str] = []
            if planning["has_any_planning"]:
                project_schedule_check = next(
                    (s for s in schedules if s["project_id"] == project_id and s["activity_id"] is None),
                    None,
                )
                if project_schedule_check:
                    project_end_date = project_schedule_check["end_date"]
                    project_planned_hours = float(project_schedule_check.get("planned_hours", 0.0))
                    project_budget = float(project_schedule_check.get("budget", 0.0))

                    if planning["end_date"] > project_end_date:
                        warnings.append(
                            "Data fine attivita oltre la data fine della commessa "
                            f"({self.format_date_ui(planning['end_date'])} > {self.format_date_ui(project_end_date)})."
                        )

                    activity_schedules = [s for s in schedules if s["project_id"] == project_id and s["activity_id"] is not None]
                    total_hours = 0.0
                    total_budget = 0.0
                    for sched in activity_schedules:
                        if int(sched["activity_id"]) == int(self.selected_activity_id):
                            continue
                        total_hours += float(sched.get("planned_hours", 0.0))
                        total_budget += float(sched.get("budget", 0.0))

                    total_hours += planning["planned_hours"]
                    total_budget += planning["budget"]

                    if project_planned_hours > 0 and total_hours > project_planned_hours:
                        warnings.append(
                            f"Ore totali attivita ({total_hours:.1f}h) superiori alle ore commessa ({project_planned_hours:.1f}h)."
                        )
                    if project_budget > 0 and total_budget > project_budget:
                        warnings.append(
                            f"Budget totale attivita ({total_budget:.2f} EUR) superiore al budget commessa ({project_budget:.2f} EUR)."
                        )

            self.db.update_activity(
                activity_id=self.selected_activity_id,
                name=name,
                hourly_rate=rate,
                notes=values["notes"],
            )

            if planning["has_any_planning"]:
                if activity_schedule:
                    self.db.update_schedule(
                        schedule_id=int(activity_schedule["id"]),
                        project_id=project_id,
                        activity_id=self.selected_activity_id,
                        start_date=planning["start_date"],
                        end_date=planning["end_date"],
                        planned_hours=planning["planned_hours"],
                        note="",
                        budget=planning["budget"],
                    )
                else:
                    self.db.add_schedule(
                        project_id=project_id,
                        activity_id=self.selected_activity_id,
                        start_date=planning["start_date"],
                        end_date=planning["end_date"],
                        planned_hours=planning["planned_hours"],
                        note="",
                        budget=planning["budget"],
                    )
            elif activity_schedule:
                answer = QMessageBox.question(
                    self,
                    "Attivita",
                    "Vuoi eliminare la pianificazione di questa attivita?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.db.delete_schedule(int(activity_schedule["id"]))

            self.selected_project_id = project_id
            self.refresh_activities_tree()
            self.refresh_master_data()
            self.refresh_control_panel()
            self.update_activity_info_box()
            if warnings:
                QMessageBox.warning(self, "Attivita", "Attivita salvata, ma attenzione:\n\n" + "\n".join(warnings))
            else:
                QMessageBox.information(self, "Attivita", "Attivita aggiornata.")
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint" in str(exc):
                QMessageBox.critical(self, "Attivita", "Esiste gia un'attivita con questo nome per la commessa selezionata.")
            else:
                QMessageBox.critical(self, "Attivita", f"Errore database: {exc}")
        except ValueError as exc:
            QMessageBox.critical(self, "Attivita", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Attivita", f"Errore: {exc}")

    def pm_delete_activity(self) -> None:
        if not self.selected_activity_id:
            QMessageBox.information(self, "Attivita", "Seleziona un'attivita.")
            return
        if QMessageBox.question(self, "Conferma", "Eliminare l'attivita? Verranno eliminati anche i timesheet associati.") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.delete_activity(self.selected_activity_id)
            self.selected_activity_id = None
            self.refresh_activities_tree()
            self.refresh_master_data()
            self.clear_activity_info_box()
            QMessageBox.information(self, "Attivita", "Attivita eliminata.")
        except Exception as exc:
            QMessageBox.critical(self, "Attivita", str(exc))

    # Programmazione
    def build_plan_tab(self) -> None:
        layout = QVBoxLayout(self.tab_plan)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        form = QGridLayout()
        form.addWidget(QLabel("Commessa"), 0, 0)
        self.plan_project_combo = QComboBox()
        self.plan_project_combo.currentTextChanged.connect(self.on_plan_project_change)
        form.addWidget(self.plan_project_combo, 1, 0)

        form.addWidget(QLabel("Attivita (opzionale)"), 0, 1)
        self.plan_activity_combo = QComboBox()
        form.addWidget(self.plan_activity_combo, 1, 1)

        form.addWidget(QLabel("Data inizio"), 0, 2)
        self.plan_start_date_edit = QDateEdit()
        self.plan_start_date_edit.setCalendarPopup(True)
        self.plan_start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.plan_start_date_edit.setDate(_to_qdate(date.today()))
        form.addWidget(self.plan_start_date_edit, 1, 2)

        form.addWidget(QLabel("Data fine"), 0, 3)
        self.plan_end_date_edit = QDateEdit()
        self.plan_end_date_edit.setCalendarPopup(True)
        self.plan_end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.plan_end_date_edit.setDate(_to_qdate(date.today()))
        form.addWidget(self.plan_end_date_edit, 1, 3)

        form.addWidget(QLabel("Ore preventivate"), 0, 4)
        self.plan_hours_entry = QLineEdit()
        form.addWidget(self.plan_hours_entry, 1, 4)

        form.addWidget(QLabel("Budget (EUR)"), 0, 5)
        self.plan_budget_entry = QLineEdit()
        form.addWidget(self.plan_budget_entry, 1, 5)

        form.addWidget(QLabel("Note"), 2, 0)
        self.plan_note_entry = QLineEdit()
        form.addWidget(self.plan_note_entry, 2, 1, 1, 5)
        layout.addLayout(form)

        actions = QHBoxLayout()
        btn_save = QPushButton("Salva programmazione")
        self._set_button_role(btn_save, "btn_primary")
        btn_save.clicked.connect(self.add_schedule_entry)
        actions.addWidget(btn_save)
        btn_edit = QPushButton("Modifica selezionata")
        self.apply_edit_button_style(btn_edit)
        btn_edit.clicked.connect(self.edit_selected_schedule)
        actions.addWidget(btn_edit)
        btn_toggle = QPushButton("Chiudi/Apri")
        btn_toggle.clicked.connect(self.toggle_schedule_status)
        actions.addWidget(btn_toggle)
        btn_delete = QPushButton("Elimina selezionata")
        self.apply_delete_button_style(btn_delete)
        btn_delete.clicked.connect(self.delete_selected_schedule)
        actions.addWidget(btn_delete)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.plan_table = QTableWidget(0, 10)
        self.plan_table.setHorizontalHeaderLabels(["ID", "Cliente", "Commessa", "Attivita", "Data inizio", "Data fine", "Ore", "Budget", "Stato", "Note"])
        self.plan_table.setColumnHidden(0, True)
        self.plan_table.setAlternatingRowColors(True)
        self.plan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.plan_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.plan_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.plan_table.itemSelectionChanged.connect(self.on_schedule_table_select)
        layout.addWidget(self.plan_table, 1)

    def refresh_programming_options(self) -> None:
        if not hasattr(self, "plan_project_combo"):
            return
        projects = self.db.list_projects()
        self._set_combo_values(self.plan_project_combo, [self._project_option(p) for p in projects])
        self.on_plan_project_change(self.plan_project_combo.currentText())

    def on_plan_project_change(self, _value: str) -> None:
        if not hasattr(self, "plan_activity_combo"):
            return
        project_id = self._id_from_option(self.plan_project_combo.currentText())
        activities = self.db.list_activities(project_id)
        options = ["(Tutta la commessa)"] + [self._activity_option(a) for a in activities]
        self._set_combo_values(self.plan_activity_combo, options)
        self.plan_activity_combo.setCurrentText("(Tutta la commessa)")

    def _plan_dates_iso(self) -> tuple[str, str]:
        return (
            self.plan_start_date_edit.date().toString("yyyy-MM-dd"),
            self.plan_end_date_edit.date().toString("yyyy-MM-dd"),
        )

    def add_schedule_entry(self) -> None:
        try:
            project_id = self._id_from_option(self.plan_project_combo.currentText())
            if not project_id:
                raise ValueError("Seleziona una commessa.")
            activity_str = self.plan_activity_combo.currentText()
            activity_id = None if activity_str == "(Tutta la commessa)" else self._id_from_option(activity_str)
            start_date, end_date = self._plan_dates_iso()
            if start_date > end_date:
                raise ValueError("La data di inizio deve essere precedente alla data di fine.")
            planned_hours = self._to_float(self.plan_hours_entry.text().strip(), "Ore preventivate")
            if planned_hours <= 0:
                raise ValueError("Ore preventivate: il valore deve essere > 0.")
            budget_str = self.plan_budget_entry.text().strip()
            budget = self._to_float(budget_str, "Budget") if budget_str else 0.0
            note = self.plan_note_entry.text().strip()
            self.db.add_schedule(project_id, activity_id, start_date, end_date, planned_hours, note, budget)
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.critical(self, "Programmazione", str(exc))
            return

        self.plan_hours_entry.clear()
        self.plan_budget_entry.clear()
        self.plan_note_entry.clear()
        self.refresh_schedule_list()
        self.refresh_control_panel()
        QMessageBox.information(self, "Programmazione", "Programmazione salvata.")

    def on_schedule_table_select(self) -> None:
        schedule_id = self._selected_table_id(self.plan_table)
        if not schedule_id:
            return
        schedules = self.db.list_schedules()
        schedule = next((s for s in schedules if s["id"] == schedule_id), None)
        if not schedule:
            return

        project_option = self._project_option({"id": schedule["project_id"], "name": schedule["project_name"], "client_name": schedule["client_name"]})
        self._ensure_combo_option(self.plan_project_combo, project_option)
        self.plan_project_combo.setCurrentText(project_option)
        self.on_plan_project_change(project_option)

        if schedule["activity_id"] is not None:
            activities = self.db.list_activities(schedule["project_id"])
            for activity in activities:
                if activity["id"] == schedule["activity_id"]:
                    option = self._activity_option(activity)
                    self._ensure_combo_option(self.plan_activity_combo, option)
                    self.plan_activity_combo.setCurrentText(option)
                    break
        else:
            self.plan_activity_combo.setCurrentText("(Tutta la commessa)")

        start_q = QDate.fromString(schedule["start_date"], "yyyy-MM-dd")
        end_q = QDate.fromString(schedule["end_date"], "yyyy-MM-dd")
        if start_q.isValid():
            self.plan_start_date_edit.setDate(start_q)
        if end_q.isValid():
            self.plan_end_date_edit.setDate(end_q)

        self.plan_hours_entry.setText(str(schedule["planned_hours"]))
        self.plan_budget_entry.setText(str(schedule.get("budget", 0.0)))
        self.plan_note_entry.setText(schedule.get("note", "") or "")

    def edit_selected_schedule(self) -> None:
        schedule_id = self._selected_table_id(self.plan_table)
        if not schedule_id:
            QMessageBox.information(self, "Programmazione", "Seleziona una programmazione dall'elenco.")
            return
        try:
            project_id = self._id_from_option(self.plan_project_combo.currentText())
            if not project_id:
                raise ValueError("Seleziona una commessa.")
            activity_str = self.plan_activity_combo.currentText()
            activity_id = None if activity_str == "(Tutta la commessa)" else self._id_from_option(activity_str)
            start_date, end_date = self._plan_dates_iso()
            if start_date > end_date:
                raise ValueError("La data di inizio deve essere precedente alla data di fine.")
            planned_hours = self._to_float(self.plan_hours_entry.text().strip(), "Ore preventivate")
            if planned_hours <= 0:
                raise ValueError("Ore preventivate: il valore deve essere > 0.")
            budget_str = self.plan_budget_entry.text().strip()
            budget = self._to_float(budget_str, "Budget") if budget_str else 0.0
            note = self.plan_note_entry.text().strip()
            self.db.update_schedule(schedule_id, project_id, activity_id, start_date, end_date, planned_hours, note, budget)
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.critical(self, "Programmazione", str(exc))
            return

        self.refresh_schedule_list()
        self.refresh_control_panel()
        QMessageBox.information(self, "Programmazione", "Programmazione aggiornata.")

    def refresh_schedule_list(self) -> None:
        if not hasattr(self, "plan_table"):
            return
        self.plan_table.setRowCount(0)
        rows = self.db.list_schedules()
        for row in rows:
            idx = self.plan_table.rowCount()
            self.plan_table.insertRow(idx)
            status_display = "Aperta" if row.get("status") == "aperta" else "Chiusa"
            values = [
                row["id"],
                row["client_name"],
                row["project_name"],
                row["activity_name"] or "(Tutta la commessa)",
                self.format_date_ui(row["start_date"]),
                self.format_date_ui(row["end_date"]),
                f"{row['planned_hours']:.2f}",
                f"{row.get('budget', 0.0):.2f}",
                status_display,
                row["note"] or "",
            ]
            for col, value in enumerate(values):
                self.plan_table.setItem(idx, col, _readonly_item(value))

    def delete_selected_schedule(self) -> None:
        schedule_id = self._selected_table_id(self.plan_table)
        if not schedule_id:
            QMessageBox.warning(self, "Programmazione", "Seleziona una riga da eliminare.")
            return
        if QMessageBox.question(self, "Conferma", "Eliminare la programmazione selezionata?") != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_schedule(schedule_id)
        self.refresh_schedule_list()
        self.refresh_control_panel()

    def toggle_schedule_status(self) -> None:
        schedule_id = self._selected_table_id(self.plan_table)
        if not schedule_id:
            QMessageBox.warning(self, "Programmazione", "Seleziona una programmazione.")
            return
        schedules = self.db.list_schedules()
        schedule = next((s for s in schedules if s["id"] == schedule_id), None)
        if not schedule:
            return
        current = schedule.get("status", "aperta")
        new_status = "chiusa" if current == "aperta" else "aperta"
        self.db.update_schedule_status(schedule_id, new_status)
        self.refresh_schedule_list()
        if hasattr(self, "ts_client_combo"):
            self.on_timesheet_client_change(self.ts_client_combo.currentText())
        self.refresh_control_panel()

    # Controllo
    def build_control_tab(self) -> None:
        layout = QVBoxLayout(self.tab_control)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Controllo Programmazione")
        title.setStyleSheet("font-size:16px;font-weight:bold;")
        header.addWidget(title)
        btn_refresh = QPushButton("Aggiorna")
        btn_refresh.clicked.connect(self.refresh_control_panel)
        header.addWidget(btn_refresh)
        btn_pdf = QPushButton("Genera Report PDF")
        btn_pdf.clicked.connect(self.show_pdf_report_dialog)
        header.addWidget(btn_pdf)
        header.addStretch(1)
        layout.addLayout(header)

        self.ctrl_tree = QTreeWidget()
        self.ctrl_tree.setColumnCount(15)
        self.ctrl_tree.setHeaderLabels(
            [
                "Cliente / Commessa / Attivita",
                "Stato",
                "Inizio",
                "Fine",
                "Gg lav.",
                "Gg rest.",
                "Ore pianif.",
                "Ore effett.",
                "Diff. ore",
                "Budget EUR",
                "Costo EUR",
                "Budget rest. EUR",
                "Utente",
                "Data",
                "Note",
            ]
        )
        self.ctrl_tree.itemDoubleClicked.connect(lambda item, _col: item.setExpanded(not item.isExpanded()))
        layout.addWidget(self.ctrl_tree, 1)

    def refresh_control_panel(self) -> None:
        if not hasattr(self, "ctrl_tree"):
            return
        self.ctrl_tree.clear()
        data = self.db.get_hierarchical_timesheet_data()

        for client in data:
            client_item = QTreeWidgetItem(
                [
                    client["name"],
                    "",
                    self._format_date_short(client["start_date"]) if client["start_date"] else "",
                    self._format_date_short(client["end_date"]) if client["end_date"] else "",
                    str(client.get("working_days", 0)) if client.get("working_days", 0) > 0 else "",
                    self._format_remaining_days(client["remaining_days"], client["start_date"], client["end_date"]),
                    f"{client['planned_hours']:.1f}" if client["planned_hours"] > 0 else "",
                    f"{client['actual_hours']:.1f}",
                    self._format_hours_diff(client["hours_diff"], client["planned_hours"]),
                    f"{client['budget']:.2f}" if client["budget"] > 0 else "",
                    f"{client['actual_cost']:.2f}",
                    self._format_budget_remaining(client["budget_remaining"], client["budget"]),
                    "",
                    "",
                    "",
                ]
            )
            client_item.setForeground(0, QColor("#4ea1ff"))
            self.ctrl_tree.addTopLevelItem(client_item)

            for project in client["projects"]:
                is_closed = project.get("status") == "chiusa"
                project_status = "Chiusa" if is_closed else ("Aperta" if project.get("status") else "")
                project_item = QTreeWidgetItem(
                    [
                        project["name"],
                        project_status,
                        self._format_date_short(project["start_date"]) if project["start_date"] else "",
                        self._format_date_short(project["end_date"]) if project["end_date"] else "",
                        str(project.get("working_days", 0)) if project.get("working_days", 0) > 0 else "",
                        self._format_remaining_days(project["remaining_days"], project["start_date"], project["end_date"]),
                        f"{project['planned_hours']:.1f}" if project["planned_hours"] > 0 else "",
                        f"{project['actual_hours']:.1f}",
                        self._format_hours_diff(project["hours_diff"], project["planned_hours"]),
                        f"{project['budget']:.2f}" if project["budget"] > 0 else "",
                        f"{project['actual_cost']:.2f}",
                        self._format_budget_remaining(project["budget_remaining"], project["budget"]),
                        "",
                        "",
                        "",
                    ]
                )
                project_item.setForeground(0, QColor("#8f8f8f") if is_closed else QColor("#70b8ff"))
                client_item.addChild(project_item)

                for activity in project["activities"]:
                    activity_closed = activity.get("status") == "chiusa"
                    activity_status = "Chiusa" if activity_closed else ("Aperta" if activity.get("status") else "")
                    activity_item = QTreeWidgetItem(
                        [
                            activity["name"],
                            activity_status,
                            self._format_date_short(activity["start_date"]) if activity["start_date"] else "",
                            self._format_date_short(activity["end_date"]) if activity["end_date"] else "",
                            str(activity.get("working_days", 0)) if activity.get("working_days", 0) > 0 else "",
                            self._format_remaining_days(activity.get("remaining_days", 0), activity["start_date"], activity["end_date"]),
                            f"{activity.get('planned_hours', 0):.1f}" if activity.get("planned_hours", 0) > 0 else "",
                            f"{activity['actual_hours']:.1f}",
                            self._format_hours_diff(activity.get("hours_diff", 0), activity.get("planned_hours", 0)),
                            f"{activity.get('budget', 0):.2f}" if activity.get("budget", 0) > 0 else "",
                            f"{activity['actual_cost']:.2f}",
                            self._format_budget_remaining(activity.get("budget_remaining", 0), activity.get("budget", 0)),
                            "",
                            "",
                            activity.get("schedule_note", "") or "",
                        ]
                    )
                    activity_item.setForeground(0, QColor("#7ed6a8") if not activity_closed else QColor("#8f8f8f"))
                    project_item.addChild(activity_item)

                    for ts in activity["timesheets"]:
                        ts_item = QTreeWidgetItem(
                            [
                                f"Voce ore #{ts['id']}",
                                "",
                                "",
                                "",
                                "",
                                "",
                                "",
                                f"{ts['hours']:.1f}",
                                "",
                                "",
                                f"{ts['cost']:.2f}",
                                "",
                                ts["username"],
                                self._format_date_short(ts["work_date"]),
                                ts.get("note", "") or "",
                            ]
                        )
                        ts_item.setForeground(0, QColor("#9aa1af"))
                        activity_item.addChild(ts_item)

        self.ctrl_tree.expandToDepth(0)

    # Diario
    def build_diary_tab(self) -> None:
        layout = QVBoxLayout(self.tab_diary)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Cliente"))
        self.diary_client_combo = QComboBox()
        self.diary_client_combo.currentTextChanged.connect(self._diary_on_client_change)
        filters.addWidget(self.diary_client_combo)

        filters.addWidget(QLabel("Commessa"))
        self.diary_project_combo = QComboBox()
        self.diary_project_combo.currentTextChanged.connect(self._diary_on_project_change)
        filters.addWidget(self.diary_project_combo)

        filters.addWidget(QLabel("Attivita"))
        self.diary_activity_combo = QComboBox()
        filters.addWidget(self.diary_activity_combo)

        self.diary_show_completed = QCheckBox("Mostra completati")
        self.diary_show_completed.setChecked(True)
        self.diary_show_completed.stateChanged.connect(self.refresh_diary_data)
        filters.addWidget(self.diary_show_completed)

        btn_filter = QPushButton("Filtra")
        btn_filter.clicked.connect(self.refresh_diary_data)
        filters.addWidget(btn_filter)

        btn_new = QPushButton("Nuova nota")
        self._set_button_role(btn_new, "btn_primary")
        btn_new.clicked.connect(self._diary_new_entry)
        filters.addWidget(btn_new)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.diary_table = QTableWidget(0, 9)
        self.diary_table.setHorizontalHeaderLabels(["ID", "Alert", "Prio", "Riferimento", "Contenuto", "Promemoria", "Stato", "Autore", "Creato"])
        self.diary_table.setAlternatingRowColors(True)
        self.diary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.diary_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.diary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.diary_table.doubleClicked.connect(lambda *_: self._diary_edit_entry())
        layout.addWidget(self.diary_table, 1)

        actions = QHBoxLayout()
        btn_toggle = QPushButton("Completa / Riapri")
        btn_toggle.clicked.connect(self._diary_toggle_completed)
        actions.addWidget(btn_toggle)
        btn_edit = QPushButton("Modifica")
        self.apply_edit_button_style(btn_edit)
        btn_edit.clicked.connect(self._diary_edit_entry)
        actions.addWidget(btn_edit)
        btn_delete = QPushButton("Elimina")
        self.apply_delete_button_style(btn_delete)
        btn_delete.clicked.connect(self._diary_delete_entry)
        actions.addWidget(btn_delete)
        actions.addStretch(1)
        layout.addLayout(actions)

        self._diary_populate_combos()

    def _diary_populate_combos(self) -> None:
        clients = self.db.list_clients()
        self.diary_client_combo.blockSignals(True)
        self.diary_client_combo.clear()
        self.diary_client_combo.addItems(["Tutti"] + [f"{c['id']} - {c['name']}" for c in clients])
        self.diary_client_combo.setCurrentText("Tutti")
        self.diary_client_combo.blockSignals(False)

        self.diary_project_combo.clear()
        self.diary_project_combo.addItem("Tutte")
        self.diary_activity_combo.clear()
        self.diary_activity_combo.addItem("Tutte")

    def _diary_on_client_change(self) -> None:
        client_id = self._id_from_option(self.diary_client_combo.currentText())
        self.diary_project_combo.blockSignals(True)
        self.diary_project_combo.clear()
        if client_id:
            projects = self.db.list_projects(client_id)
            self.diary_project_combo.addItems(["Tutte"] + [f"{p['id']} - {p['name']}" for p in projects])
        else:
            self.diary_project_combo.addItem("Tutte")
        self.diary_project_combo.setCurrentIndex(0)
        self.diary_project_combo.blockSignals(False)
        self._diary_on_project_change()

    def _diary_on_project_change(self) -> None:
        project_id = self._id_from_option(self.diary_project_combo.currentText())
        self.diary_activity_combo.clear()
        if project_id:
            activities = self.db.list_activities(project_id)
            self.diary_activity_combo.addItems(["Tutte"] + [f"{a['id']} - {a['name']}" for a in activities])
        else:
            self.diary_activity_combo.addItem("Tutte")
        self.diary_activity_combo.setCurrentIndex(0)

    def refresh_diary_data(self) -> None:
        if not hasattr(self, "diary_table"):
            return

        self.diary_table.setRowCount(0)
        client_id = self._id_from_option(self.diary_client_combo.currentText())
        project_id = self._id_from_option(self.diary_project_combo.currentText())
        activity_id = self._id_from_option(self.diary_activity_combo.currentText())
        show_completed = self.diary_show_completed.isChecked()

        entries = self.db.list_diary_entries(
            client_id=client_id,
            project_id=project_id,
            activity_id=activity_id,
            show_completed=show_completed,
        )

        today = date.today().isoformat()
        for entry in entries:
            ref_parts = []
            if entry.get("client_name"):
                ref_parts.append(entry["client_name"])
            if entry.get("project_name"):
                ref_parts.append(entry["project_name"])
            if entry.get("activity_name"):
                ref_parts.append(entry["activity_name"])
            ref_str = " > ".join(ref_parts) if ref_parts else "-"

            alert = ""
            if entry.get("reminder_date") and not entry.get("is_completed"):
                if entry["reminder_date"] <= today:
                    alert = "!"

            priority = "H" if entry.get("priority") else ""
            status = "SI" if entry.get("is_completed") else "NO"
            reminder = self._format_date_display(entry.get("reminder_date") or "")
            created = (entry.get("created_at") or "")[:10]
            content = entry.get("content") or ""
            if len(content) > 80:
                content = content[:80] + "..."

            idx = self.diary_table.rowCount()
            self.diary_table.insertRow(idx)
            values = [entry["id"], alert, priority, ref_str, content, reminder, status, entry.get("user_name", ""), created]
            for col, value in enumerate(values):
                self.diary_table.setItem(idx, col, _readonly_item(value))

    def _format_date_display(self, date_str: str) -> str:
        if not date_str:
            return ""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return date_str

    def update_diary_alert(self) -> None:
        count = self.db.count_pending_reminders()
        if self._diary_tab_index is None:
            return
        label = "Diario"
        if count > 0:
            label = f"Diario !{count}"
        self.tabview.setTabText(self._diary_tab_index, label)

    def _diary_get_selected_id(self) -> int | None:
        entry_id = self._selected_table_id(self.diary_table)
        if not entry_id:
            QMessageBox.warning(self, "Selezione", "Seleziona una nota.")
            return None
        return entry_id

    def _diary_toggle_completed(self) -> None:
        entry_id = self._diary_get_selected_id()
        if not entry_id:
            return
        self.db.toggle_diary_completed(entry_id)
        self.refresh_diary_data()
        self.update_diary_alert()

    def _diary_delete_entry(self) -> None:
        entry_id = self._diary_get_selected_id()
        if not entry_id:
            return
        if QMessageBox.question(self, "Conferma", "Eliminare questa nota?") != QMessageBox.StandardButton.Yes:
            return
        self.db.delete_diary_entry(entry_id)
        self.refresh_diary_data()
        self.update_diary_alert()

    def _diary_new_entry(self) -> None:
        self._diary_open_editor(None)

    def _diary_edit_entry(self) -> None:
        entry_id = self._diary_get_selected_id()
        if entry_id:
            self._diary_open_editor(entry_id)

    def _diary_open_editor(self, entry_id: int | None) -> None:
        dlg = DiaryEditorDialog(self, entry_id, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refresh_diary_data()
            self.update_diary_alert()

    # Utenti
    def build_users_tab(self) -> None:
        layout = QVBoxLayout(self.tab_users)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        if not self.is_admin:
            label = QLabel("Sezione riservata admin.")
            label.setStyleSheet("font-size:18px;font-weight:bold;")
            layout.addWidget(label)
            layout.addStretch(1)
            return

        form = QGridLayout()
        form.addWidget(QLabel("Username"), 0, 0)
        self.new_user_username_entry = QLineEdit()
        form.addWidget(self.new_user_username_entry, 1, 0)

        form.addWidget(QLabel("Nome completo"), 0, 1)
        self.new_user_fullname_entry = QLineEdit()
        form.addWidget(self.new_user_fullname_entry, 1, 1)

        form.addWidget(QLabel("Ruolo"), 0, 2)
        self.new_user_role_combo = QComboBox()
        self.new_user_role_combo.addItems(["user", "admin"])
        form.addWidget(self.new_user_role_combo, 1, 2)

        form.addWidget(QLabel("Password (solo nuovo)"), 0, 3)
        self.new_user_password_entry = QLineEdit()
        self.new_user_password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        form.addWidget(self.new_user_password_entry, 1, 3)

        self.save_user_button = QPushButton("Crea utente")
        self._set_button_role(self.save_user_button, "btn_primary")
        self.save_user_button.clicked.connect(self.save_user)
        form.addWidget(self.save_user_button, 1, 4)
        layout.addLayout(form)

        tabs_row = QHBoxLayout()
        tabs_row.addWidget(QLabel("Tab visibili utente selezionato:"))
        self.tab_calendar_check = QCheckBox("Calendario Ore")
        self.tab_calendar_check.setChecked(True)
        tabs_row.addWidget(self.tab_calendar_check)
        self.tab_master_check = QCheckBox("Gestione Commesse")
        self.tab_master_check.setChecked(True)
        tabs_row.addWidget(self.tab_master_check)
        self.tab_control_check = QCheckBox("Controllo")
        self.tab_control_check.setChecked(True)
        tabs_row.addWidget(self.tab_control_check)
        btn_tabs = QPushButton("Salva permessi")
        btn_tabs.clicked.connect(self.save_user_tabs)
        tabs_row.addWidget(btn_tabs)
        tabs_row.addStretch(1)
        layout.addLayout(tabs_row)

        actions = QHBoxLayout()
        btn_edit = QPushButton("Modifica utente")
        self.apply_edit_button_style(btn_edit)
        btn_edit.clicked.connect(self.load_user_for_edit)
        actions.addWidget(btn_edit)
        btn_cancel = QPushButton("Annulla modifica")
        btn_cancel.clicked.connect(self.cancel_user_edit)
        actions.addWidget(btn_cancel)
        actions.addWidget(QLabel("Nuova password"))
        self.reset_password_entry = QLineEdit()
        self.reset_password_entry.setEchoMode(QLineEdit.EchoMode.Password)
        actions.addWidget(self.reset_password_entry)
        btn_reset = QPushButton("Reset password")
        btn_reset.clicked.connect(self.reset_selected_password)
        actions.addWidget(btn_reset)
        btn_toggle = QPushButton("Attiva/Disattiva")
        btn_toggle.clicked.connect(self.toggle_selected_user)
        actions.addWidget(btn_toggle)
        btn_refresh = QPushButton("Aggiorna")
        btn_refresh.clicked.connect(self.refresh_users_data)
        actions.addWidget(btn_refresh)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.users_table = QTableWidget(0, 5)
        self.users_table.setHorizontalHeaderLabels(["ID", "Username", "Nome", "Ruolo", "Attivo"])
        self.users_table.setAlternatingRowColors(True)
        self.users_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.users_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.users_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.users_table.itemSelectionChanged.connect(self.on_user_select)
        layout.addWidget(self.users_table, 1)

    def on_user_select(self) -> None:
        if not self.is_admin or not hasattr(self, "users_table"):
            return
        user_id = self._selected_table_id(self.users_table)
        if not user_id:
            return
        users = self.db.list_users(include_inactive=True)
        selected = next((u for u in users if int(u["id"]) == user_id), None)
        if not selected:
            return
        self.tab_calendar_check.setChecked(bool(selected.get("tab_calendar", 1)))
        self.tab_master_check.setChecked(bool(selected.get("tab_master", 1)))
        self.tab_control_check.setChecked(bool(selected.get("tab_control", 1)))

    def save_user_tabs(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        if not user_id:
            QMessageBox.information(self, "Utenti", "Seleziona un utente dall'elenco.")
            return
        try:
            self.db.update_user_tabs(
                user_id,
                self.tab_calendar_check.isChecked(),
                self.tab_master_check.isChecked(),
                True,
                self.tab_control_check.isChecked(),
            )
            self.refresh_users_data()
            QMessageBox.information(self, "Utenti", "Permessi aggiornati. L'utente deve rifare il login per applicare le modifiche.")
        except Exception as exc:
            QMessageBox.critical(self, "Utenti", str(exc))

    def refresh_users_data(self) -> None:
        if not self.is_admin or not hasattr(self, "users_table"):
            return
        users = self.db.list_users(include_inactive=True)
        self.users_table.setRowCount(0)
        for user in users:
            idx = self.users_table.rowCount()
            self.users_table.insertRow(idx)
            values = [user["id"], user["username"], user["full_name"], user["role"], "SI" if user["active"] else "NO"]
            for col, value in enumerate(values):
                self.users_table.setItem(idx, col, _readonly_item(value))

    def save_user(self) -> None:
        try:
            username = self.new_user_username_entry.text().strip()
            full_name = self.new_user_fullname_entry.text().strip()
            role = self.new_user_role_combo.currentText().strip()
            password = self.new_user_password_entry.text().strip()

            if not username or not full_name:
                raise ValueError("Compila username e nome.")
            if role not in {"admin", "user"}:
                raise ValueError("Ruolo non valido.")

            if self.editing_user_id is None:
                if not password:
                    raise ValueError("Compila la password per il nuovo utente.")
                if role == "admin":
                    self.db.create_user(username, full_name, role, password, True, True, True, True)
                else:
                    self.db.create_user(username, full_name, role, password, self.tab_calendar_check.isChecked(), self.tab_master_check.isChecked(), True, self.tab_control_check.isChecked())
                QMessageBox.information(self, "Utenti", "Utente creato con successo.")
            else:
                if role == "admin":
                    self.db.update_user(self.editing_user_id, username, full_name, role, True, True, True, True)
                else:
                    self.db.update_user(self.editing_user_id, username, full_name, role, self.tab_calendar_check.isChecked(), self.tab_master_check.isChecked(), True, self.tab_control_check.isChecked())
                QMessageBox.information(self, "Utenti", "Utente modificato con successo.")
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.critical(self, "Utenti", str(exc))
            return

        self.cancel_user_edit()
        self.refresh_users_data()
        self.refresh_day_entries()
        self.refresh_schedule_list()

    def load_user_for_edit(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        if not user_id:
            QMessageBox.information(self, "Utenti", "Seleziona un utente dall'elenco.")
            return
        users = self.db.list_users(include_inactive=True)
        selected = next((u for u in users if int(u["id"]) == user_id), None)
        if not selected:
            return

        self.editing_user_id = user_id
        self.new_user_username_entry.setText(selected["username"])
        self.new_user_fullname_entry.setText(selected["full_name"])
        self.new_user_role_combo.setCurrentText(selected["role"])
        self.new_user_password_entry.clear()
        self.tab_calendar_check.setChecked(bool(selected.get("tab_calendar", 1)))
        self.tab_master_check.setChecked(bool(selected.get("tab_master", 1)))
        self.tab_control_check.setChecked(bool(selected.get("tab_control", 1)))
        self.save_user_button.setText("Salva modifiche")
        self.apply_edit_button_style(self.save_user_button)

    def cancel_user_edit(self) -> None:
        self.editing_user_id = None
        self.new_user_username_entry.clear()
        self.new_user_fullname_entry.clear()
        self.new_user_password_entry.clear()
        self.new_user_role_combo.setCurrentText("user")
        self.tab_calendar_check.setChecked(True)
        self.tab_master_check.setChecked(True)
        self.tab_control_check.setChecked(True)
        self.save_user_button.setText("Crea utente")
        self._set_button_role(self.save_user_button, "btn_primary")

    def toggle_selected_user(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        if not user_id:
            QMessageBox.warning(self, "Utenti", "Seleziona un utente.")
            return
        if user_id == int(self.current_user["id"]):
            QMessageBox.warning(self, "Utenti", "Non puoi disattivare il tuo utente.")
            return
        users = self.db.list_users(include_inactive=True)
        selected = next((u for u in users if int(u["id"]) == user_id), None)
        if not selected:
            return
        current_state = bool(selected["active"])
        self.db.set_user_active(user_id, not current_state)
        self.refresh_users_data()

    def reset_selected_password(self) -> None:
        user_id = self._selected_table_id(self.users_table)
        if not user_id:
            QMessageBox.warning(self, "Utenti", "Seleziona un utente.")
            return
        new_password = self.reset_password_entry.text().strip()
        if not new_password:
            QMessageBox.warning(self, "Utenti", "Inserisci la nuova password.")
            return
        self.db.reset_user_password(user_id, new_password)
        self.reset_password_entry.clear()
        QMessageBox.information(self, "Utenti", "Password aggiornata.")

    # Utility comuni
    def refresh_master_data(self) -> None:
        clients = self.db.list_clients()
        client_values = [self._entity_option(c["id"], c["name"]) for c in clients]

        if hasattr(self, "ts_client_combo"):
            self._set_combo_values(self.ts_client_combo, [""] + client_values)
            self.on_timesheet_client_change(self.ts_client_combo.currentText())
        if hasattr(self, "pm_client_combo"):
            current = self.pm_client_combo.currentText()
            self._set_combo_values(self.pm_client_combo, client_values)
            if current in client_values:
                self.pm_client_combo.setCurrentText(current)
            self.refresh_projects_tree()
            self.refresh_activities_tree()
        if hasattr(self, "plan_project_combo"):
            self.refresh_programming_options()
        if hasattr(self, "diary_client_combo"):
            self._diary_populate_combos()
        self.refresh_day_entries()
        self.refresh_schedule_list()
        self.refresh_control_panel()
        self.refresh_diary_data()
        self.update_diary_alert()

    def show_pdf_report_dialog(self) -> None:
        dlg = PDFReportDialog(self, self)
        dlg.exec()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.backup_timer.stop()
        super().closeEvent(event)


def main() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("APP Timesheet")

    db = Database()
    try:
        login = LoginDialog(db)
        if login.exec() != QDialog.DialogCode.Accepted or login.user is None:
            return 0
        window = TimesheetWindow(db=db, user=login.user)
        window.show()
        return qt_app.exec()
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
