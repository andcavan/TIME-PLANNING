from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

BASE_DIR = Path(__file__).resolve().parent

# Palette colori
_C_PRIMARY   = colors.HexColor('#1565C0')   # blu scuro intestazioni
_C_PRIMARY_L = colors.HexColor('#E3F2FD')   # azzurro chiarissimo KPI sfondo
_C_PRIMARY_B = colors.HexColor('#BBDEFB')   # bordo KPI
_C_ROW_ALT   = colors.HexColor('#F5F5F5')   # grigio zebra righe pari
_C_RISK_HDR  = colors.HexColor('#C62828')   # rosso intestazione rischio
_C_GRAY_LINE = colors.HexColor('#BDBDBD')   # bordo tabelle dati
_C_HDR_TXT   = colors.white


def _runtime_root() -> Path:
    """Ritorna la cartella dell'eseguibile quando frozen, altrimenti la cartella del sorgente."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return BASE_DIR


APP_DIR = _runtime_root()


class PDFReportGenerator:
    """Generatore di report PDF per TIME-PLANNING."""

    def __init__(self, output_dir: Path | str = None, company_name: str = "TIME-PLANNING"):
        self.output_dir = Path(output_dir) if output_dir else APP_DIR / "reports"
        self.output_dir.mkdir(exist_ok=True)
        self.company_name = company_name
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Configura stili personalizzati per i PDF."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=22,
            textColor=_C_PRIMARY,
            spaceAfter=6,
            spaceBefore=0,
            alignment=TA_CENTER,
            leading=26,
        ))

        self.styles.add(ParagraphStyle(
            name='CustomSubtitle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#546E7A'),
            spaceAfter=16,
            alignment=TA_CENTER,
        ))

        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=13,
            textColor=_C_PRIMARY,
            spaceBefore=14,
            spaceAfter=6,
            borderPad=(0, 0, 2, 0),
        ))

        self.styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=self.styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#424242'),
            spaceBefore=10,
            spaceAfter=6,
        ))

        self.styles.add(ParagraphStyle(
            name='KPIValue',
            parent=self.styles['Normal'],
            fontSize=24,
            textColor=_C_PRIMARY,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=2,
            leading=28,
        ))

        self.styles.add(ParagraphStyle(
            name='KPILabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=4,
        ))

        self.styles.add(ParagraphStyle(
            name='NoteText',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#424242'),
            leading=13,
            wordWrap='LTR',
        ))

    # ------------------------------------------------------------------ #
    #  Utility                                                             #
    # ------------------------------------------------------------------ #

    def _format_date(self, date_str: str) -> str:
        """Formatta data da YYYY-MM-DD a dd/mm/YYYY."""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            return date_str or ""

    def _on_page(self, c: canvas.Canvas, doc):
        """Header + footer su ogni pagina."""
        w, h = A4
        c.saveState()

        # --- Header ---
        # Sfondo blu leggero
        c.setFillColor(colors.HexColor('#E8F0FE'))
        c.rect(0, h - 1.6*cm, w, 1.6*cm, fill=1, stroke=0)

        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(_C_PRIMARY)
        c.drawString(1.8*cm, h - 1.1*cm, self.company_name)

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#546E7A'))
        c.drawRightString(w - 1.8*cm, h - 1.1*cm,
                          f"Generato il {datetime.now().strftime('%d/%m/%Y  %H:%M')}")

        # Linea separatrice
        c.setStrokeColor(_C_PRIMARY)
        c.setLineWidth(1.5)
        c.line(1.8*cm, h - 1.6*cm, w - 1.8*cm, h - 1.6*cm)

        # --- Footer ---
        c.setStrokeColor(_C_GRAY_LINE)
        c.setLineWidth(0.5)
        c.line(1.8*cm, 1.4*cm, w - 1.8*cm, 1.4*cm)

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#78909C'))
        c.drawCentredString(w / 2, 0.8*cm, f"Pagina {doc.page}")

        c.restoreState()

    def _build_doc(self, output_path: Path, landscape_mode: bool = False) -> SimpleDocTemplate:
        """Crea SimpleDocTemplate con margini standard."""
        ps = landscape(A4) if landscape_mode else A4
        return SimpleDocTemplate(
            str(output_path),
            pagesize=ps,
            rightMargin=1.8*cm,
            leftMargin=1.8*cm,
            topMargin=2.2*cm,
            bottomMargin=2*cm,
        )

    def _table_style(self, header_color=None, risk: bool = False) -> TableStyle:
        """Stile tabella standard con zebra striping."""
        hdr = header_color or (_C_RISK_HDR if risk else _C_PRIMARY)
        return TableStyle([
            # Intestazione
            ('BACKGROUND',    (0, 0), (-1, 0),  hdr),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  _C_HDR_TXT),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0),  9),
            ('TOPPADDING',    (0, 0), (-1, 0),  9),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  9),
            ('LEFTPADDING',   (0, 0), (-1, 0),  8),
            ('RIGHTPADDING',  (0, 0), (-1, 0),  8),
            # Righe dati
            ('FONTSIZE',      (0, 1), (-1, -1), 9),
            ('TOPPADDING',    (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('LEFTPADDING',   (0, 1), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, _C_ROW_ALT]),
            # Bordi
            ('LINEBELOW',     (0, 0), (-1, 0),  0.8, _C_PRIMARY),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.3, _C_GRAY_LINE),
            ('LINEBEFORE',    (0, 0), (0, -1),  0.3, _C_GRAY_LINE),
            ('LINEAFTER',     (-1, 0), (-1, -1), 0.3, _C_GRAY_LINE),
            # Allineamento
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ])

    def _add_right_align(self, style: TableStyle, col_start: int, col_end: int) -> TableStyle:
        """Aggiunge allineamento a destra per colonne numeriche."""
        style.add('ALIGN', (col_start, 0), (col_end, -1), 'RIGHT')
        return style

    def _build_kpi_table(self, kpis: list[tuple[str, str]]) -> Table:
        """Crea tabella KPI orizzontale con valore grande + etichetta."""
        n = len(kpis)
        usable = A4[0] - 3.6*cm
        col_w = usable / n

        row = []
        for label, value in kpis:
            cell = [
                Paragraph(value, self.styles['KPIValue']),
                Paragraph(label, self.styles['KPILabel']),
            ]
            row.append(cell)

        table = Table([row], colWidths=[col_w] * n)
        table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), _C_PRIMARY_L),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('TOPPADDING',    (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('BOX',           (0, 0), (-1, -1), 1,   _C_PRIMARY_B),
            ('INNERGRID',     (0, 0), (-1, -1), 0.5, _C_PRIMARY_B),
            ('ROUNDEDCORNERS', [4]),
        ]))
        return table

    def _section_header(self, title: str, risk: bool = False) -> Paragraph:
        """Paragrafo intestazione sezione."""
        return Paragraph(title, self.styles['CustomHeading2'])
    
    # ------------------------------------------------------------------ #
    #  Report Programmazione                                               #
    # ------------------------------------------------------------------ #

    def generate_schedule_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per singola programmazione."""
        if not filename:
            filename = f"Report_Programmazione_{data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        # Titolo + breadcrumb
        story.append(Paragraph("Report Programmazione", self.styles['CustomTitle']))
        breadcrumb = f"{data['client_name']}  ›  {data['project_name']}  ›  {data['activity_name']}"
        story.append(Paragraph(breadcrumb, self.styles['CustomSubtitle']))
        period_text = (
            f"Periodo: {self._format_date(data['start_date'])} — {self._format_date(data['end_date'])}"
        )
        story.append(Paragraph(period_text, self.styles['CustomHeading3']))
        story.append(Spacer(1, 0.4*cm))

        # KPI
        completion_pct = (data['actual_hours'] / data['planned_hours'] * 100) if data['planned_hours'] > 0 else 0
        budget_pct = (data['actual_cost'] / data['budget'] * 100) if data['budget'] > 0 else 0
        story.append(self._build_kpi_table([
            ("Avanzamento Ore",   f"{completion_pct:.1f}%"),
            ("Budget Utilizzato", f"{budget_pct:.1f}%"),
            ("Giorni Rimasti",    str(data['remaining_days'])),
            ("Ore Mancanti",      f"{data['remaining_hours']:.1f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        # Riepilogo numerico
        story.append(self._section_header("Riepilogo"))
        summary_data = [
            ['',        'Pianificato',             'Effettivo',              'Scostamento'],
            ['Ore',     f"{data['planned_hours']:.2f}",   f"{data['actual_hours']:.2f}",   f"{data['remaining_hours']:.2f}"],
            ['Budget €',f"{data['budget']:.2f}",          f"{data['actual_cost']:.2f}",    f"{data['remaining_budget']:.2f}"],
            ['Giorni',  str(data['total_days']),           str(data['elapsed_days']),       str(data['remaining_days'])],
        ]
        ts = self._table_style()
        self._add_right_align(ts, 1, 3)
        summary_table = Table(summary_data, colWidths=[5*cm, 3.8*cm, 3.8*cm, 3.8*cm])
        summary_table.setStyle(ts)
        story.append(summary_table)
        story.append(Spacer(1, 0.6*cm))

        # Distribuzione ore per utente
        if data.get('user_hours'):
            story.append(self._section_header("Distribuzione Ore per Utente"))
            user_data = [['Utente', 'Ore', 'Costo €']]
            for u in data['user_hours']:
                user_data.append([
                    u['full_name'],
                    f"{float(u['hours']):.2f}",
                    f"{float(u['cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 1, 2)
            user_table = Table(user_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            user_table.setStyle(ts2)
            story.append(user_table)
            story.append(Spacer(1, 0.6*cm))

        # Dettaglio timesheet
        if data.get('timesheet_details'):
            story.append(self._section_header("Dettaglio Timesheet"))
            ts_rows = [['Data', 'Utente', 'Ore', 'Costo €', 'Note']]
            for detail in data['timesheet_details'][:100]:
                ts_rows.append([
                    self._format_date(detail['work_date']),
                    detail.get('username', ''),
                    f"{float(detail['hours']):.2f}",
                    f"{float(detail['cost']):.2f}",
                    Paragraph(detail.get('note', '') or '', self.styles['NoteText']),
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 2, 3)
            timesheet_table = Table(ts_rows, colWidths=[2.4*cm, 3.2*cm, 2*cm, 2.4*cm, 6.4*cm])
            timesheet_table.setStyle(ts3)
            story.append(timesheet_table)

        # Note
        if data.get('note'):
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph("Note", self.styles['CustomHeading3']))
            story.append(Paragraph(data['note'], self.styles['NoteText']))

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path
    
    # ------------------------------------------------------------------ #
    #  Report Cliente                                                      #
    # ------------------------------------------------------------------ #

    def generate_client_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per cliente."""
        if not filename:
            client_name = data['client']['name'].replace(' ', '_')
            filename = f"Report_Cliente_{client_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph(f"Report Cliente", self.styles['CustomTitle']))
        story.append(Paragraph(data['client']['name'], self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.4*cm))

        story.append(self._build_kpi_table([
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive",   f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale",   f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        story.append(self._section_header("Programmazioni"))
        sched_data = [['Commessa', 'Attività', 'Periodo', 'Ore Pian.', 'Ore Svolte', 'Budget €', 'Costo €']]
        for s in data['schedules']:
            sched_data.append([
                s['project_name'],
                s['activity_name'],
                f"{self._format_date(s['start_date'])}\n{self._format_date(s['end_date'])}",
                f"{s['planned_hours']:.1f}",
                f"{s['actual_hours']:.1f}",
                f"{s['budget']:.2f}",
                f"{s['actual_cost']:.2f}",
            ])
        ts = self._table_style()
        self._add_right_align(ts, 3, 6)
        sched_table = Table(sched_data, colWidths=[3.8*cm, 3.2*cm, 2.4*cm, 2*cm, 2*cm, 2*cm, 2*cm])
        sched_table.setStyle(ts)
        story.append(sched_table)

        if data['client'].get('notes'):
            story.append(Spacer(1, 0.4*cm))
            story.append(Paragraph("Note Cliente", self.styles['CustomHeading3']))
            story.append(Paragraph(data['client']['notes'], self.styles['NoteText']))

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path
    
    # ------------------------------------------------------------------ #
    #  Report Commessa                                                     #
    # ------------------------------------------------------------------ #

    def generate_project_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per commessa."""
        if not filename:
            project_name = data['project']['name'].replace(' ', '_')
            filename = f"Report_Commessa_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph("Report Commessa", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"{data['project']['name']}  ·  Cliente: {data['project']['client_name']}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.4*cm))

        story.append(self._build_kpi_table([
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive",   f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale",   f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        if data.get('activities_summary'):
            story.append(self._section_header("Distribuzione per Attività"))
            act_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary']:
                act_data.append([
                    act['activity_name'],
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 2)
            act_table = Table(act_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            act_table.setStyle(ts)
            story.append(act_table)
            story.append(Spacer(1, 0.6*cm))

        if data.get('users_summary'):
            story.append(self._section_header("Distribuzione per Utente"))
            usr_data = [['Utente', 'Ore Totali', 'Costo €']]
            for u in data['users_summary']:
                usr_data.append([
                    u['full_name'],
                    f"{float(u['total_hours']):.2f}",
                    f"{float(u['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 1, 2)
            usr_table = Table(usr_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            usr_table.setStyle(ts2)
            story.append(usr_table)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

    # ------------------------------------------------------------------ #
    #  Report Periodo                                                      #
    # ------------------------------------------------------------------ #

    def generate_period_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per periodo."""
        if not filename:
            filename = f"Report_Periodo_{data['start_date']}_{data['end_date']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph("Report Periodo", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"Dal {self._format_date(data['start_date'])} al {self._format_date(data['end_date'])}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.4*cm))

        avg_cph = data['total_cost'] / data['total_hours'] if data['total_hours'] > 0 else 0
        num_entries = len(data['timesheets'])
        story.append(self._build_kpi_table([
            ("Ore Totali",     f"{data['total_hours']:.1f}"),
            ("Costo Totale",   f"€ {data['total_cost']:.2f}"),
            ("Inserimenti",    str(num_entries)),
            ("Costo Medio/h",  f"€ {avg_cph:.2f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Riepilogo per Cliente"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for cl in data['clients_summary']:
                pct = (float(cl['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                c_data.append([cl['client_name'], f"{float(cl['total_hours']):.2f}",
                                f"{float(cl['total_cost']):.2f}", f"{pct:.1f}%"])
            ts = self._table_style()
            self._add_right_align(ts, 1, 3)
            ct = Table(c_data, colWidths=[8*cm, 2.8*cm, 3.2*cm, 2.4*cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6*cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Top 10 Commesse"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary'][:10]:
                p_data.append([pr['client_name'], pr['project_name'],
                                f"{float(pr['total_hours']):.2f}", f"{float(pr['total_cost']):.2f}"])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[4.4*cm, 5.4*cm, 2.8*cm, 3.8*cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6*cm))

        if data.get('users_summary'):
            story.append(self._section_header("Riepilogo per Utente"))
            u_data = [['Utente', 'Ore Totali', 'Costo €', '% Ore']]
            for us in data['users_summary']:
                pct = (float(us['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                u_data.append([us['full_name'], f"{float(us['total_hours']):.2f}",
                                f"{float(us['total_cost']):.2f}", f"{pct:.1f}%"])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 3)
            ut = Table(u_data, colWidths=[8*cm, 2.8*cm, 3.2*cm, 2.4*cm])
            ut.setStyle(ts3)
            story.append(ut)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

    # ------------------------------------------------------------------ #
    #  Report Utente                                                       #
    # ------------------------------------------------------------------ #

    def generate_user_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per utente."""
        if not filename:
            username = data['user']['username'].replace(' ', '_')
            filename = (
                f"Report_Utente_{username}_{data['start_date']}_{data['end_date']}"
                f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph("Report Utente", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"{data['user']['full_name']}  ·  "
            f"Dal {self._format_date(data['start_date'])} al {self._format_date(data['end_date'])}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.4*cm))

        story.append(self._build_kpi_table([
            ("Ore Totali",       f"{data['total_hours']:.1f}"),
            ("Costo Totale",     f"€ {data['total_cost']:.2f}"),
            ("Giorni Lavorativi",str(data['work_days'])),
            ("Media Ore/Giorno", f"{data['avg_hours_per_day']:.1f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Distribuzione per Cliente"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for cl in data['clients_summary']:
                pct = (float(cl['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                c_data.append([cl['client_name'], f"{float(cl['total_hours']):.2f}",
                                f"{float(cl['total_cost']):.2f}", f"{pct:.1f}%"])
            ts = self._table_style()
            self._add_right_align(ts, 1, 3)
            ct = Table(c_data, colWidths=[8*cm, 2.8*cm, 3.2*cm, 2.4*cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6*cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Distribuzione per Commessa"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary']:
                p_data.append([pr['client_name'], pr['project_name'],
                                f"{float(pr['total_hours']):.2f}", f"{float(pr['total_cost']):.2f}"])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[4.4*cm, 5.4*cm, 2.8*cm, 3.8*cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6*cm))

        if data.get('activities_summary'):
            story.append(self._section_header("Distribuzione per Attività"))
            a_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary'][:20]:
                a_data.append([act['activity_name'], f"{float(act['total_hours']):.2f}",
                                f"{float(act['total_cost']):.2f}"])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 2)
            at = Table(a_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            at.setStyle(ts3)
            story.append(at)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

    # ------------------------------------------------------------------ #
    #  Report Generale                                                     #
    # ------------------------------------------------------------------ #

    def generate_general_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report generale/riepilogativo."""
        if not filename:
            filename = f"Report_Generale_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph("Report Generale Programmazioni", self.styles['CustomTitle']))
        if data.get('start_date') and data.get('end_date'):
            sub = f"Periodo: {self._format_date(data['start_date'])} — {self._format_date(data['end_date'])}"
        else:
            sub = "Tutte le programmazioni"
        story.append(Paragraph(sub, self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.4*cm))

        story.append(self._build_kpi_table([
            ("Programmazioni Attive", str(data['num_active_schedules'])),
            ("A Rischio",             str(data['num_at_risk'])),
            ("Ore Totali",            f"{data['total_hours']:.1f}"),
            ("Costo Totale",          f"€ {data['total_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6*cm))

        if data.get('schedules_at_risk'):
            story.append(self._section_header("Programmazioni a Rischio"))
            r_data = [['Cliente / Commessa / Attività', 'Periodo', 'Ore Manc.', 'Gg Manc.']]
            for s in data['schedules_at_risk'][:10]:
                name = f"{s['client_name']} › {s['project_name']} › {s['activity_name']}"
                r_data.append([
                    Paragraph(name, self.styles['NoteText']),
                    f"{self._format_date(s['start_date'])}\n{self._format_date(s['end_date'])}",
                    f"{s['remaining_hours']:.1f}",
                    str(s['remaining_days']),
                ])
            ts_risk = self._table_style(risk=True)
            self._add_right_align(ts_risk, 2, 3)
            rt = Table(r_data, colWidths=[8.8*cm, 3*cm, 2.4*cm, 2.2*cm])
            rt.setStyle(ts_risk)
            story.append(rt)
            story.append(Spacer(1, 0.6*cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Top Clienti per Fatturato"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €']]
            for cl in data['clients_summary'][:10]:
                c_data.append([cl['client_name'], f"{float(cl['total_hours']):.2f}",
                                f"{float(cl['total_cost']):.2f}"])
            ts = self._table_style()
            self._add_right_align(ts, 1, 2)
            ct = Table(c_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6*cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Top 10 Commesse"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary'][:10]:
                p_data.append([pr['client_name'], pr['project_name'],
                                f"{float(pr['total_hours']):.2f}", f"{float(pr['total_cost']):.2f}"])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[4.4*cm, 5.4*cm, 2.8*cm, 3.8*cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6*cm))

        if data.get('users_summary'):
            story.append(self._section_header("Riepilogo Utenti"))
            u_data = [['Utente', 'Ore Totali', 'Costo €']]
            for us in data['users_summary']:
                u_data.append([us['full_name'], f"{float(us['total_hours']):.2f}",
                                f"{float(us['total_cost']):.2f}"])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 2)
            ut = Table(u_data, colWidths=[10.4*cm, 3*cm, 3*cm])
            ut.setStyle(ts3)
            story.append(ut)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

