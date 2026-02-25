from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import copy
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

# Colori livelli gerarchici
_C_LVL1      = colors.HexColor('#1565C0')   # Cliente  – blu scuro
_C_LVL1_BG   = colors.HexColor('#E3F2FD')   # sfondo riga cliente
_C_LVL2      = colors.HexColor('#0277BD')   # Commessa – blu medio
_C_LVL2_BG   = colors.HexColor('#E1F5FE')   # sfondo riga commessa
_C_LVL3      = colors.HexColor('#00897B')   # Attività – verde acqua
_C_LVL3_BG   = colors.HexColor('#E0F2F1')   # sfondo riga attività
_C_TOTAL_BG  = colors.HexColor('#ECEFF1')   # sfondo righe totale

# Layout landscape A4
_PAGE_LS  = landscape(A4)               # (841.89 pt, 595.27 pt)
_MARGIN   = 1.8 * cm
_USABLE_W = _PAGE_LS[0] - 2 * _MARGIN  # ≈ 26.1 cm


def _runtime_root() -> Path:
    """Ritorna la cartella dell'eseguibile quando frozen, altrimenti la cartella del sorgente."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return BASE_DIR


APP_DIR = _runtime_root()


class PDFReportGenerator:
    """Generatore di report PDF per TIME-PLANNING.

    Layout A4 orizzontale, word-wrap su tutte le celle, vista gerarchica.
    """

    def __init__(self, output_dir: Path | str = None, company_name: str = "TIME-PLANNING"):
        self.output_dir = Path(output_dir) if output_dir else APP_DIR / "reports"
        self.output_dir.mkdir(exist_ok=True)
        self.company_name = company_name
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    # ------------------------------------------------------------------ #
    #  Stili                                                               #
    # ------------------------------------------------------------------ #

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
            fontSize=8,
            textColor=colors.HexColor('#424242'),
            leading=11,
            wordWrap='LTR',
        ))
        # Stile generico per celle tabella con word-wrap
        self.styles.add(ParagraphStyle(
            name='CellText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#212121'),
            leading=11,
            wordWrap='LTR',
            spaceBefore=0,
            spaceAfter=0,
        ))
        # Stili etichette vista gerarchica
        self.styles.add(ParagraphStyle(
            name='HierClient',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=_C_LVL1,
            leading=13,
            fontName='Helvetica-Bold',
            wordWrap='LTR',
        ))
        self.styles.add(ParagraphStyle(
            name='HierProject',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=_C_LVL2,
            leading=12,
            fontName='Helvetica-Bold',
            wordWrap='LTR',
        ))
        self.styles.add(ParagraphStyle(
            name='HierActivity',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=_C_LVL3,
            leading=11,
            fontName='Helvetica-Bold',
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

    def _p(self, text: str, style_name: str = 'CellText') -> Paragraph:
        """Crea Paragraph con word-wrap per celle tabella."""
        return Paragraph(str(text or ''), self.styles[style_name])

    def _on_page(self, c: canvas.Canvas, doc):
        """Header + footer su ogni pagina — funziona sia Portrait che Landscape."""
        w, h = doc.pagesize
        c.saveState()

        # Header
        c.setFillColor(colors.HexColor('#E8F0FE'))
        c.rect(0, h - 1.6 * cm, w, 1.6 * cm, fill=1, stroke=0)

        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(_C_PRIMARY)
        c.drawString(_MARGIN, h - 1.1 * cm, self.company_name)

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#546E7A'))
        c.drawRightString(w - _MARGIN, h - 1.1 * cm,
                          f"Generato il {datetime.now().strftime('%d/%m/%Y  %H:%M')}")

        c.setStrokeColor(_C_PRIMARY)
        c.setLineWidth(1.5)
        c.line(_MARGIN, h - 1.6 * cm, w - _MARGIN, h - 1.6 * cm)

        # Footer
        c.setStrokeColor(_C_GRAY_LINE)
        c.setLineWidth(0.5)
        c.line(_MARGIN, 1.4 * cm, w - _MARGIN, 1.4 * cm)

        c.setFont('Helvetica', 8)
        c.setFillColor(colors.HexColor('#78909C'))
        c.drawCentredString(w / 2, 0.8 * cm, f"Pagina {doc.page}")

        c.restoreState()

    def _build_doc(self, output_path: Path, landscape_mode: bool = True) -> SimpleDocTemplate:
        """Crea SimpleDocTemplate A4 orizzontale (default) con margini standard."""
        ps = landscape(A4) if landscape_mode else A4
        return SimpleDocTemplate(
            str(output_path),
            pagesize=ps,
            rightMargin=_MARGIN,
            leftMargin=_MARGIN,
            topMargin=2.2 * cm,
            bottomMargin=2.0 * cm,
        )

    def _table_style(self, header_color=None, risk: bool = False) -> TableStyle:
        """Stile tabella standard con zebra striping e VALIGN=TOP (word-wrap)."""
        hdr = header_color or (_C_RISK_HDR if risk else _C_PRIMARY)
        return TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  hdr),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  _C_HDR_TXT),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0),  9),
            ('TOPPADDING',    (0, 0), (-1, 0),  9),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  9),
            ('LEFTPADDING',   (0, 0), (-1, 0),  8),
            ('RIGHTPADDING',  (0, 0), (-1, 0),  8),
            # Righe dati
            ('FONTSIZE',      (0, 1), (-1, -1), 8),
            ('TOPPADDING',    (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('LEFTPADDING',   (0, 1), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, _C_ROW_ALT]),
            # Bordi
            ('LINEBELOW',     (0, 0), (-1, 0),  0.8, _C_PRIMARY),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.3, _C_GRAY_LINE),
            ('LINEBEFORE',    (0, 0), (0, -1),  0.3, _C_GRAY_LINE),
            ('LINEAFTER',     (-1, 0), (-1, -1), 0.3, _C_GRAY_LINE),
            # VALIGN TOP → le righe multi-linea non si sovrappongono
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ])

    def _add_right_align(self, style: TableStyle, col_start: int, col_end: int) -> TableStyle:
        """Aggiunge allineamento a destra per colonne numeriche."""
        style.add('ALIGN', (col_start, 0), (col_end, -1), 'RIGHT')
        return style

    def _build_kpi_table(self, kpis: list[tuple[str, str]]) -> Table:
        """Crea riga KPI orizzontale con valore grande + etichetta."""
        n = len(kpis)
        col_w = _USABLE_W / n
        row = []
        for label, value in kpis:
            row.append([
                Paragraph(value, self.styles['KPIValue']),
                Paragraph(label,  self.styles['KPILabel']),
            ])
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

        story.append(Paragraph("Report Programmazione", self.styles['CustomTitle']))
        breadcrumb = f"{data['client_name']}  ›  {data['project_name']}  ›  {data['activity_name']}"
        story.append(Paragraph(breadcrumb, self.styles['CustomSubtitle']))
        story.append(Paragraph(
            f"Periodo: {self._format_date(data['start_date'])} — {self._format_date(data['end_date'])}",
            self.styles['CustomHeading3']
        ))
        story.append(Spacer(1, 0.4 * cm))

        completion_pct = (data['actual_hours'] / data['planned_hours'] * 100) if data['planned_hours'] > 0 else 0
        budget_pct     = (data['actual_cost']  / data['budget']        * 100) if data['budget']        > 0 else 0
        story.append(self._build_kpi_table([
            ("Avanzamento Ore",   f"{completion_pct:.1f}%"),
            ("Budget Utilizzato", f"{budget_pct:.1f}%"),
            ("Giorni Rimasti",    str(data['remaining_days'])),
            ("Ore Mancanti",      f"{data['remaining_hours']:.1f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        story.append(self._section_header("Riepilogo"))
        summary_data = [
            ['',         'Pianificato',                  'Effettivo',                    'Scostamento'],
            ['Ore',      f"{data['planned_hours']:.2f}", f"{data['actual_hours']:.2f}",  f"{data['remaining_hours']:.2f}"],
            ['Budget €', f"{data['budget']:.2f}",        f"{data['actual_cost']:.2f}",   f"{data['remaining_budget']:.2f}"],
            ['Giorni',   str(data['total_days']),         str(data['elapsed_days']),      str(data['remaining_days'])],
        ]
        ts = self._table_style()
        self._add_right_align(ts, 1, 3)
        # totale 26.1 cm
        summary_table = Table(summary_data, colWidths=[7 * cm, 6.4 * cm, 6.4 * cm, 6.3 * cm])
        summary_table.setStyle(ts)
        story.append(summary_table)
        story.append(Spacer(1, 0.6 * cm))

        if data.get('user_hours'):
            story.append(self._section_header("Distribuzione Ore per Utente"))
            user_data = [['Utente', 'Ore', 'Costo €']]
            for u in data['user_hours']:
                user_data.append([
                    self._p(u['full_name']),
                    f"{float(u['hours']):.2f}",
                    f"{float(u['cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 1, 2)
            user_table = Table(user_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
            user_table.setStyle(ts2)
            story.append(user_table)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('timesheet_details'):
            story.append(self._section_header("Dettaglio Timesheet"))
            ts_rows = [['Data', 'Utente', 'Ore', 'Costo €', 'Note']]
            for d in data['timesheet_details'][:200]:
                ts_rows.append([
                    self._format_date(d['work_date']),
                    self._p(d.get('username', '')),
                    f"{float(d['hours']):.2f}",
                    f"{float(d['cost']):.2f}",
                    self._p(d.get('note', '') or '', 'NoteText'),
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 2, 3)
            # 3+5+2.5+3+12.6 = 26.1
            timesheet_table = Table(ts_rows, colWidths=[3 * cm, 5 * cm, 2.5 * cm, 3 * cm, 12.6 * cm],
                                    repeatRows=1)
            timesheet_table.setStyle(ts3)
            story.append(timesheet_table)

        if data.get('note'):
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Note", self.styles['CustomHeading3']))
            story.append(self._p(data['note'], 'NoteText'))

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

        story.append(Paragraph("Report Cliente", self.styles['CustomTitle']))
        story.append(Paragraph(data['client']['name'], self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.4 * cm))

        story.append(self._build_kpi_table([
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive",   f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale",   f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        story.append(self._section_header("Programmazioni"))
        sched_data = [['Commessa', 'Attività', 'Periodo', 'Ore Pian.', 'Ore Svolte', 'Budget €', 'Costo €']]
        for s in data['schedules']:
            sched_data.append([
                self._p(s['project_name']),
                self._p(s['activity_name']),
                self._p(f"{self._format_date(s['start_date'])}\n{self._format_date(s['end_date'])}"),
                f"{s['planned_hours']:.1f}",
                f"{s['actual_hours']:.1f}",
                f"{s['budget']:.2f}",
                f"{s['actual_cost']:.2f}",
            ])
        ts = self._table_style()
        self._add_right_align(ts, 3, 6)
        # 6+5.5+3+3+3+2.8+2.8 = 26.1
        sched_table = Table(sched_data,
                            colWidths=[6 * cm, 5.5 * cm, 3 * cm, 3 * cm, 3 * cm, 2.8 * cm, 2.8 * cm])
        sched_table.setStyle(ts)
        story.append(sched_table)

        if data['client'].get('notes'):
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph("Note Cliente", self.styles['CustomHeading3']))
            story.append(self._p(data['client']['notes'], 'NoteText'))

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
        story.append(Spacer(1, 0.4 * cm))

        story.append(self._build_kpi_table([
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive",   f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale",   f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        if data.get('activities_summary'):
            story.append(self._section_header("Distribuzione per Attività"))
            act_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary']:
                act_data.append([
                    self._p(act['activity_name']),
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 2)
            act_table = Table(act_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
            act_table.setStyle(ts)
            story.append(act_table)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('users_summary'):
            story.append(self._section_header("Distribuzione per Utente"))
            usr_data = [['Utente', 'Ore Totali', 'Costo €']]
            for u in data['users_summary']:
                usr_data.append([
                    self._p(u['full_name']),
                    f"{float(u['total_hours']):.2f}",
                    f"{float(u['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 1, 2)
            usr_table = Table(usr_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
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
            filename = (
                f"Report_Periodo_{data['start_date']}_{data['end_date']}"
                f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph("Report Periodo", self.styles['CustomTitle']))
        story.append(Paragraph(
            f"Dal {self._format_date(data['start_date'])} al {self._format_date(data['end_date'])}",
            self.styles['CustomSubtitle']
        ))
        story.append(Spacer(1, 0.4 * cm))

        avg_cph = data['total_cost'] / data['total_hours'] if data['total_hours'] > 0 else 0
        story.append(self._build_kpi_table([
            ("Ore Totali",    f"{data['total_hours']:.1f}"),
            ("Costo Totale",  f"€ {data['total_cost']:.2f}"),
            ("Inserimenti",   str(len(data['timesheets']))),
            ("Costo Medio/h", f"€ {avg_cph:.2f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Riepilogo per Cliente"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for cl in data['clients_summary']:
                pct = (float(cl['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                c_data.append([
                    self._p(cl['client_name']),
                    f"{float(cl['total_hours']):.2f}",
                    f"{float(cl['total_cost']):.2f}",
                    f"{pct:.1f}%",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 3)
            ct = Table(c_data, colWidths=[14.1 * cm, 4 * cm, 5 * cm, 3 * cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Top 10 Commesse"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary'][:10]:
                p_data.append([
                    self._p(pr['client_name']),
                    self._p(pr['project_name']),
                    f"{float(pr['total_hours']):.2f}",
                    f"{float(pr['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[8.1 * cm, 10 * cm, 4 * cm, 4 * cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('users_summary'):
            story.append(self._section_header("Riepilogo per Utente"))
            u_data = [['Utente', 'Ore Totali', 'Costo €', '% Ore']]
            for us in data['users_summary']:
                pct = (float(us['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                u_data.append([
                    self._p(us['full_name']),
                    f"{float(us['total_hours']):.2f}",
                    f"{float(us['total_cost']):.2f}",
                    f"{pct:.1f}%",
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 3)
            ut = Table(u_data, colWidths=[14.1 * cm, 4 * cm, 5 * cm, 3 * cm])
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
        story.append(Spacer(1, 0.4 * cm))

        story.append(self._build_kpi_table([
            ("Ore Totali",        f"{data['total_hours']:.1f}"),
            ("Costo Totale",      f"€ {data['total_cost']:.2f}"),
            ("Giorni Lavorativi", str(data['work_days'])),
            ("Media Ore/Giorno",  f"{data['avg_hours_per_day']:.1f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Distribuzione per Cliente"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for cl in data['clients_summary']:
                pct = (float(cl['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                c_data.append([
                    self._p(cl['client_name']),
                    f"{float(cl['total_hours']):.2f}",
                    f"{float(cl['total_cost']):.2f}",
                    f"{pct:.1f}%",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 3)
            ct = Table(c_data, colWidths=[14.1 * cm, 4 * cm, 5 * cm, 3 * cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Distribuzione per Commessa"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary']:
                p_data.append([
                    self._p(pr['client_name']),
                    self._p(pr['project_name']),
                    f"{float(pr['total_hours']):.2f}",
                    f"{float(pr['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[8.1 * cm, 10 * cm, 4 * cm, 4 * cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('activities_summary'):
            story.append(self._section_header("Distribuzione per Attività"))
            a_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary'][:20]:
                a_data.append([
                    self._p(act['activity_name']),
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}",
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 2)
            at = Table(a_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
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
        story.append(Spacer(1, 0.4 * cm))

        story.append(self._build_kpi_table([
            ("Programmazioni Attive", str(data['num_active_schedules'])),
            ("A Rischio",             str(data['num_at_risk'])),
            ("Ore Totali",            f"{data['total_hours']:.1f}"),
            ("Costo Totale",          f"€ {data['total_cost']:.2f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        if data.get('schedules_at_risk'):
            story.append(self._section_header("Programmazioni a Rischio"))
            r_data = [['Cliente / Commessa / Attività', 'Periodo', 'Ore Manc.', 'Gg Manc.']]
            for s in data['schedules_at_risk'][:10]:
                name = f"{s['client_name']} › {s['project_name']} › {s['activity_name']}"
                r_data.append([
                    self._p(name, 'NoteText'),
                    self._p(f"{self._format_date(s['start_date'])}\n{self._format_date(s['end_date'])}"),
                    f"{s['remaining_hours']:.1f}",
                    str(s['remaining_days']),
                ])
            ts_risk = self._table_style(risk=True)
            self._add_right_align(ts_risk, 2, 3)
            rt = Table(r_data, colWidths=[14.1 * cm, 4.5 * cm, 4 * cm, 3.5 * cm])
            rt.setStyle(ts_risk)
            story.append(rt)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('clients_summary'):
            story.append(self._section_header("Top Clienti per Fatturato"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €']]
            for cl in data['clients_summary'][:10]:
                c_data.append([
                    self._p(cl['client_name']),
                    f"{float(cl['total_hours']):.2f}",
                    f"{float(cl['total_cost']):.2f}",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 2)
            ct = Table(c_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Top 10 Commesse"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary'][:10]:
                p_data.append([
                    self._p(pr['client_name']),
                    self._p(pr['project_name']),
                    f"{float(pr['total_hours']):.2f}",
                    f"{float(pr['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[8.1 * cm, 10 * cm, 4 * cm, 4 * cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('users_summary'):
            story.append(self._section_header("Riepilogo Utenti"))
            u_data = [['Utente', 'Ore Totali', 'Costo €']]
            for us in data['users_summary']:
                u_data.append([
                    self._p(us['full_name']),
                    f"{float(us['total_hours']):.2f}",
                    f"{float(us['total_cost']):.2f}",
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 2)
            ut = Table(u_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
            ut.setStyle(ts3)
            story.append(ut)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

    # ------------------------------------------------------------------ #
    #  Report Filtrato (sintetico / dettagliato)                          #
    # ------------------------------------------------------------------ #

    def generate_filtered_report(
        self,
        data: dict[str, Any],
        mode: str = "sintetica",
        title: str = "Report",
        subtitle: str = "",
        filename: str = None,
    ) -> Path:
        """Genera report PDF con filtri flessibili.

        Parameters
        ----------
        data    : dict restituito da ``Database.get_report_filtered_data``
        mode    : ``'sintetica'`` → solo totali aggregati;
                  ``'dettagliata'`` → aggiunge tabella inserimenti con data e note
        title   : titolo principale del documento
        subtitle: riga descrittiva sotto il titolo
        """
        if not filename:
            filename = f"Report_{mode.capitalize()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        story.append(Paragraph(title, self.styles['CustomTitle']))
        if subtitle:
            story.append(Paragraph(subtitle, self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.4 * cm))

        avg_cph = data['total_cost'] / data['total_hours'] if data['total_hours'] > 0 else 0
        story.append(self._build_kpi_table([
            ("Ore Totali",    f"{data['total_hours']:.1f}"),
            ("Costo Totale",  f"€ {data['total_cost']:.2f}"),
            ("Inserimenti",   str(len(data['timesheets']))),
            ("Costo Medio/h", f"€ {avg_cph:.2f}"),
        ]))
        story.append(Spacer(1, 0.6 * cm))

        if data.get('clients_summary') and len(data['clients_summary']) > 1:
            story.append(self._section_header("Riepilogo per Cliente"))
            c_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for cl in data['clients_summary']:
                pct = (float(cl['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                c_data.append([
                    self._p(cl['client_name']),
                    f"{float(cl['total_hours']):.2f}",
                    f"{float(cl['total_cost']):.2f}",
                    f"{pct:.1f}%",
                ])
            ts = self._table_style()
            self._add_right_align(ts, 1, 3)
            ct = Table(c_data, colWidths=[14.1 * cm, 4 * cm, 5 * cm, 3 * cm])
            ct.setStyle(ts)
            story.append(ct)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('projects_summary'):
            story.append(self._section_header("Riepilogo per Commessa"))
            p_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for pr in data['projects_summary']:
                p_data.append([
                    self._p(pr['client_name']),
                    self._p(pr['project_name']),
                    f"{float(pr['total_hours']):.2f}",
                    f"{float(pr['total_cost']):.2f}",
                ])
            ts2 = self._table_style()
            self._add_right_align(ts2, 2, 3)
            pt = Table(p_data, colWidths=[8.1 * cm, 10 * cm, 4 * cm, 4 * cm])
            pt.setStyle(ts2)
            story.append(pt)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('activities_summary'):
            story.append(self._section_header("Riepilogo per Attività"))
            a_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary']:
                a_data.append([
                    self._p(act['activity_name']),
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}",
                ])
            ts3 = self._table_style()
            self._add_right_align(ts3, 1, 2)
            at = Table(a_data, colWidths=[18.1 * cm, 4 * cm, 4 * cm])
            at.setStyle(ts3)
            story.append(at)
            story.append(Spacer(1, 0.6 * cm))

        if data.get('users_summary'):
            story.append(self._section_header("Riepilogo per Utente"))
            u_data = [['Utente', 'Ore Totali', 'Costo €', '% Ore']]
            for us in data['users_summary']:
                pct = (float(us['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                u_data.append([
                    self._p(us['full_name']),
                    f"{float(us['total_hours']):.2f}",
                    f"{float(us['total_cost']):.2f}",
                    f"{pct:.1f}%",
                ])
            ts4 = self._table_style()
            self._add_right_align(ts4, 1, 3)
            ut = Table(u_data, colWidths=[14.1 * cm, 4 * cm, 5 * cm, 3 * cm])
            ut.setStyle(ts4)
            story.append(ut)

        if mode == "dettagliata" and data.get('timesheets'):
            story.append(PageBreak())
            story.append(self._section_header("Dettaglio Inserimenti Ore"))
            ts_rows = [['Data', 'Utente', 'Cliente', 'Commessa', 'Attività', 'Ore', 'Costo €', 'Note']]
            for t in data['timesheets']:
                ts_rows.append([
                    self._format_date(t['work_date']),
                    self._p(t.get('full_name', '')),
                    self._p(t.get('client_name', '')),
                    self._p(t.get('project_name', '')),
                    self._p(t.get('activity_name', '')),
                    f"{float(t['hours']):.2f}",
                    f"{float(t['cost']):.2f}",
                    self._p(t.get('note', '') or '', 'NoteText'),
                ])
            ts5 = self._table_style()
            self._add_right_align(ts5, 5, 6)
            # 3+4+4+4.5+4+2+2.5+6.1 = 30.1 → aggiusto a 26.1
            # 2.5+3.5+3.5+4+3.5+2+2.5+4.6 = 26.1
            detail_table = Table(
                ts_rows,
                colWidths=[2.5 * cm, 3.5 * cm, 3.5 * cm, 4 * cm, 3.5 * cm,
                           2 * cm, 2.5 * cm, 4.6 * cm],
                repeatRows=1,
            )
            detail_table.setStyle(ts5)
            story.append(detail_table)

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

    # ------------------------------------------------------------------ #
    #  Report Gerarchico (Cliente > Commessa > Attività > Ore)            #
    # ------------------------------------------------------------------ #

    def generate_hierarchical_report(
        self,
        data: dict[str, Any],
        title: str = "Report Ore — Vista Gerarchica",
        subtitle: str = "",
        filename: str = None,
    ) -> Path:
        """Genera report gerarchico: Cliente › Commessa › Attività › Ore inserite.

        Struttura visiva
        ----------------
        ▶ CLIENTE                          ore tot   costo tot
            ▷ COMMESSA                     ore       costo
                •  ATTIVITÀ                ore       costo
                   Data | Utente | Ore | Costo | Note
                   ...

        Parameters
        ----------
        data    : dict restituito da ``Database.get_report_filtered_data``
        title   : titolo principale
        subtitle: riga sotto il titolo (periodo, filtri, ecc.)
        """
        if not filename:
            filename = f"Report_Gerarchico_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        output_path = self.output_dir / filename
        doc = self._build_doc(output_path)
        story = []

        # ---- Titolo ----
        story.append(Paragraph(title, self.styles['CustomTitle']))
        if subtitle:
            story.append(Paragraph(subtitle, self.styles['CustomSubtitle']))
        story.append(Spacer(1, 0.4 * cm))

        # ---- KPI sommario ----
        avg_cph = data['total_cost'] / data['total_hours'] if data['total_hours'] > 0 else 0
        story.append(self._build_kpi_table([
            ("Ore Totali",    f"{data['total_hours']:.1f}"),
            ("Costo Totale",  f"€ {data['total_cost']:.2f}"),
            ("Inserimenti",   str(len(data.get('timesheets', [])))),
            ("Costo Medio/h", f"€ {avg_cph:.2f}"),
        ]))
        story.append(Spacer(1, 0.8 * cm))

        # ---- Costruzione gerarchia in memoria ----
        # {cliente: {commessa: {attività: [righe]}}}
        hierarchy: dict[str, dict[str, dict[str, list[dict]]]] = {}
        for row in data.get('timesheets', []):
            cl = row.get('client_name',   '—')
            pr = row.get('project_name',  '—')
            ac = row.get('activity_name', '—')
            hierarchy.setdefault(cl, {}).setdefault(pr, {}).setdefault(ac, []).append(row)

        # ---- Larghezze fisse (tot = _USABLE_W ≈ 26.1 cm) ----
# ---- Larghezze fisse (tot = _USABLE_W ≈ 26.1 cm) ----
        # Righe intestazione: nome | ore tot | costo tot
        W_NAME  = _USABLE_W * 0.62
        W_HOURS = _USABLE_W * 0.19
        W_COST  = _USABLE_W * 0.19

        # Tabella ore dettaglio: data | utente | ore | costo | note
        WD_DATE  = 3.0 * cm
        WD_USER  = 4.5 * cm
        WD_HOURS = 2.5 * cm
        WD_COST  = 3.0 * cm
        WD_NOTE  = _USABLE_W - WD_DATE - WD_USER - WD_HOURS - WD_COST  # ≈ 13.1 cm

        # Stile tabella ore dettaglio
        _det_style = TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0),  colors.HexColor('#455A64')),
            ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0), (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0), (-1, 0),  8),
            ('TOPPADDING',    (0, 0), (-1, 0),  5),
            ('BOTTOMPADDING', (0, 0), (-1, 0),  5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('FONTSIZE',      (0, 1), (-1, -1), 8),
            ('TOPPADDING',    (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, _C_ROW_ALT]),
            ('LINEBELOW',     (0, 0), (-1, 0),  0.6, colors.HexColor('#455A64')),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.2, _C_GRAY_LINE),
            ('BOX',           (0, 0), (-1, -1), 0.3, _C_GRAY_LINE),
            ('ALIGN',         (2, 0), (3, -1),  'RIGHT'),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ])

        grand_hours = 0.0
        grand_cost  = 0.0

        for client_name in sorted(hierarchy):
            cl_data  = hierarchy[client_name]
            cl_hours = sum(float(r['hours']) for pr_d in cl_data.values()
                           for rows in pr_d.values() for r in rows)
            cl_cost  = sum(float(r['cost'])  for pr_d in cl_data.values()
                           for rows in pr_d.values() for r in rows)
            grand_hours += cl_hours
            grand_cost  += cl_cost

            # ── CLIENTE ──────────────────────────────────────────────────
            story.append(Table(
                [[
                    Paragraph(f"▶  {client_name}", self.styles['HierClient']),
                    Paragraph(f"{cl_hours:.2f} h",  self.styles['HierClient']),
                    Paragraph(f"€ {cl_cost:.2f}",   self.styles['HierClient']),
                ]],
                colWidths=[W_NAME, W_HOURS, W_COST],
                style=TableStyle([
                    ('BACKGROUND',    (0, 0), (-1, -1), _C_LVL1_BG),
                    ('TOPPADDING',    (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
                    ('LEFTPADDING',   (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
                    ('LINEABOVE',     (0, 0), (-1, 0),  1.8, _C_LVL1),
                    ('LINEBELOW',     (0, 0), (-1, 0),  1.0, _C_LVL1),
                    ('ALIGN',         (1, 0), (2, 0),   'RIGHT'),
                    ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                ]),
            ))

            for project_name in sorted(cl_data):
                pr_data  = cl_data[project_name]
                pr_hours = sum(float(r['hours']) for rows in pr_data.values() for r in rows)
                pr_cost  = sum(float(r['cost'])  for rows in pr_data.values() for r in rows)

                # ── COMMESSA ──────────────────────────────────────────────
                story.append(Table(
                    [[
                        Paragraph(f"    ▷  {project_name}", self.styles['HierProject']),
                        Paragraph(f"{pr_hours:.2f} h", self.styles['HierProject']),
                        Paragraph(f"€ {pr_cost:.2f}",  self.styles['HierProject']),
                    ]],
                    colWidths=[W_NAME, W_HOURS, W_COST],
                    style=TableStyle([
                        ('BACKGROUND',    (0, 0), (-1, -1), _C_LVL2_BG),
                        ('TOPPADDING',    (0, 0), (-1, -1), 7),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                        ('LEFTPADDING',   (0, 0), (-1, -1), 22),
                        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
                        ('LINEBELOW',     (0, 0), (-1, 0),  0.5, _C_LVL2),
                        ('ALIGN',         (1, 0), (2, 0),   'RIGHT'),
                        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                    ]),
                ))

                for activity_name in sorted(pr_data):
                    act_entries = pr_data[activity_name]
                    act_hours   = sum(float(r['hours']) for r in act_entries)
                    act_cost    = sum(float(r['cost'])  for r in act_entries)

                    # ── ATTIVITÀ ─────────────────────────────────────────
                    story.append(Table(
                        [[
                            Paragraph(f"        •  {activity_name}", self.styles['HierActivity']),
                            Paragraph(f"{act_hours:.2f} h", self.styles['HierActivity']),
                            Paragraph(f"€ {act_cost:.2f}",  self.styles['HierActivity']),
                        ]],
                        colWidths=[W_NAME, W_HOURS, W_COST],
                        style=TableStyle([
                            ('BACKGROUND',    (0, 0), (-1, -1), _C_LVL3_BG),
                            ('TOPPADDING',    (0, 0), (-1, -1), 5),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                            ('LEFTPADDING',   (0, 0), (-1, -1), 36),
                            ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
                            ('LINEBELOW',     (0, 0), (-1, 0),  0.4, _C_LVL3),
                            ('ALIGN',         (1, 0), (2, 0),   'RIGHT'),
                            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                        ]),
                    ))

                    # ── ORE INSERITE: Data | Utente | Ore | Costo | Note ──
                    ore_rows = [['Data', 'Utente', 'Ore', 'Costo €', 'Note']]
                    for r in sorted(act_entries, key=lambda x: x.get('work_date', '')):
                        ore_rows.append([
                            self._format_date(r.get('work_date', '')),
                            self._p(r.get('full_name', '') or r.get('username', '')),
                            f"{float(r['hours']):.2f}",
                            f"{float(r['cost']):.2f}",
                            self._p(r.get('note', '') or '', 'NoteText'),
                        ])

                    ore_table = Table(
                        ore_rows,
                        colWidths=[WD_DATE, WD_USER, WD_HOURS, WD_COST, WD_NOTE],
                        repeatRows=1,
                    )
                    ore_table.setStyle(copy.deepcopy(_det_style))
                    story.append(ore_table)
                    story.append(Spacer(1, 0.3 * cm))

                story.append(Spacer(1, 0.3 * cm))

            story.append(Spacer(1, 0.5 * cm))

        # ── TOTALE GENERALE ──────────────────────────────────────────────
        story.append(Table(
            [[
                Paragraph("<b>TOTALE GENERALE</b>", self.styles['CellText']),
                Paragraph(f"<b>{grand_hours:.2f} h</b>", self.styles['CellText']),
                Paragraph(f"<b>€ {grand_cost:.2f}</b>",  self.styles['CellText']),
            ]],
            colWidths=[W_NAME, W_HOURS, W_COST],
            style=TableStyle([
                ('BACKGROUND',    (0, 0), (-1, -1), _C_TOTAL_BG),
                ('TOPPADDING',    (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
                ('LEFTPADDING',   (0, 0), (-1, -1), 10),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
                ('BOX',           (0, 0), (-1, -1), 1.5, _C_PRIMARY),
                ('ALIGN',         (1, 0), (2, 0),   'RIGHT'),
                ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ]),
        ))

        doc.build(story, onFirstPage=self._on_page, onLaterPages=self._on_page)
        return output_path

