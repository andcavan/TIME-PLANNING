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


def _runtime_root() -> Path:
    """Ritorna la cartella dell'eseguibile quando frozen, altrimenti la cartella del sorgente."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return BASE_DIR


APP_DIR = _runtime_root()


class PDFReportGenerator:
    """Generatore di report PDF per TIME-PLANNING."""
    
    def __init__(self, output_dir: Path | str = None):
        self.output_dir = Path(output_dir) if output_dir else APP_DIR / "reports"
        self.output_dir.mkdir(exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Configura stili personalizzati per i PDF."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading2',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceBefore=20,
            spaceAfter=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading3',
            parent=self.styles['Heading3'],
            fontSize=14,
            textColor=colors.HexColor('#424242'),
            spaceBefore=15,
            spaceAfter=10
        ))
        
        self.styles.add(ParagraphStyle(
            name='KPI',
            parent=self.styles['Normal'],
            fontSize=28,
            textColor=colors.HexColor('#1976d2'),
            alignment=TA_CENTER,
            spaceBefore=5,
            spaceAfter=5
        ))
        
        self.styles.add(ParagraphStyle(
            name='KPILabel',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=10
        ))
    
    def _format_date(self, date_str: str) -> str:
        """Formatta data da YYYY-MM-DD a dd/mm/YYYY."""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            return date_str
    
    def _create_header(self, c: canvas.Canvas, doc):
        """Crea header per ogni pagina."""
        c.saveState()
        c.setFont('Helvetica-Bold', 10)
        c.setFillColor(colors.HexColor('#1976d2'))
        c.drawString(2*cm, A4[1] - 1.5*cm, "TIME-PLANNING - Report")
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.grey)
        c.drawRightString(A4[0] - 2*cm, A4[1] - 1.5*cm, f"Generato il: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        c.setStrokeColor(colors.HexColor('#1976d2'))
        c.setLineWidth(2)
        c.line(2*cm, A4[1] - 1.8*cm, A4[0] - 2*cm, A4[1] - 1.8*cm)
        c.restoreState()
    
    def _create_footer(self, c: canvas.Canvas, doc):
        """Crea footer per ogni pagina."""
        c.saveState()
        c.setFont('Helvetica', 8)
        c.setFillColor(colors.grey)
        c.drawCentredString(A4[0] / 2, 1*cm, f"Pagina {doc.page}")
        c.restoreState()
    
    def _build_kpi_table(self, kpis: list[tuple[str, str]]) -> Table:
        """Crea tabella KPI."""
        data = []
        row = []
        for label, value in kpis:
            cell = [
                Paragraph(value, self.styles['KPI']),
                Paragraph(label, self.styles['KPILabel'])
            ]
            row.append(cell)
        
        data.append(row)
        
        table = Table(data, colWidths=[A4[0] / len(kpis) - 1*cm] * len(kpis))
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#e3f2fd')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bbdefb')),
        ]))
        
        return table
    
    def generate_schedule_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per singola programmazione."""
        if not filename:
            filename = f"Report_Programmazione_{data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = f"Report Programmazione"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.3*cm))
        
        # Info programmazione
        info_text = f"<b>{data['client_name']}</b> > {data['project_name']} > {data['activity_name']}"
        story.append(Paragraph(info_text, self.styles['CustomHeading3']))
        
        period_text = f"Periodo: {self._format_date(data['start_date'])} - {self._format_date(data['end_date'])}"
        story.append(Paragraph(period_text, self.styles['Normal']))
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        completion_pct = (data['actual_hours'] / data['planned_hours'] * 100) if data['planned_hours'] > 0 else 0
        budget_pct = (data['actual_cost'] / data['budget'] * 100) if data['budget'] > 0 else 0
        
        kpis = [
            ("Avanzamento Ore", f"{completion_pct:.1f}%"),
            ("Budget Utilizzato", f"{budget_pct:.1f}%"),
            ("Giorni Rimanenti", str(data['remaining_days'])),
            ("Ore Mancanti", f"{data['remaining_hours']:.1f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Riepilogo numerico
        story.append(Paragraph("Riepilogo", self.styles['CustomHeading2']))
        
        summary_data = [
            ['Descrizione', 'Pianificato', 'Effettivo', 'Scostamento'],
            ['Ore', f"{data['planned_hours']:.2f}", f"{data['actual_hours']:.2f}", f"{data['remaining_hours']:.2f}"],
            ['Budget €', f"{data['budget']:.2f}", f"{data['actual_cost']:.2f}", f"{data['remaining_budget']:.2f}"],
            ['Giorni', str(data['total_days']), str(data['elapsed_days']), str(data['remaining_days'])]
        ]
        
        summary_table = Table(summary_data, colWidths=[7*cm, 3.5*cm, 3.5*cm, 3.5*cm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione ore per utente
        if data['user_hours']:
            story.append(Paragraph("Distribuzione Ore per Utente", self.styles['CustomHeading2']))
            
            user_data = [['Utente', 'Ore', 'Costo €']]
            for u in data['user_hours']:
                user_data.append([
                    u['full_name'],
                    f"{float(u['hours']):.2f}",
                    f"{float(u['cost']):.2f}"
                ])
            
            user_table = Table(user_data, colWidths=[10*cm, 3.5*cm, 4*cm])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(user_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Dettaglio timesheet
        if data['timesheet_details']:
            story.append(Paragraph("Dettaglio Timesheet", self.styles['CustomHeading2']))
            
            timesheet_data = [['Data', 'Utente', 'Ore', 'Costo €', 'Note']]
            for detail in data['timesheet_details'][:50]:  # Limita a 50 per non appesantire
                timesheet_data.append([
                    self._format_date(detail['work_date']),
                    detail['username'],
                    f"{float(detail['hours']):.2f}",
                    f"{float(detail['cost']):.2f}",
                    detail.get('note', '')[:30]  # Limita lunghezza note
                ])
            
            timesheet_table = Table(timesheet_data, colWidths=[2.5*cm, 3.5*cm, 2*cm, 2.5*cm, 6.5*cm])
            timesheet_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ]))
            
            story.append(timesheet_table)
        
        # Note
        if data.get('note'):
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("Note", self.styles['CustomHeading3']))
            story.append(Paragraph(data['note'], self.styles['Normal']))
        
        # Build PDF
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
    
    def generate_client_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per cliente."""
        if not filename:
            client_name = data['client']['name'].replace(' ', '_')
            filename = f"Report_Cliente_{client_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = f"Report Cliente: {data['client']['name']}"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        kpis = [
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive", f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale", f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Programmazioni del cliente
        story.append(Paragraph("Programmazioni", self.styles['CustomHeading2']))
        
        schedule_data = [['Commessa', 'Attività', 'Periodo', 'Ore Pianif.', 'Ore Svolte', 'Budget €', 'Costo €']]
        for sched in data['schedules']:
            schedule_data.append([
                sched['project_name'],
                sched['activity_name'],
                f"{self._format_date(sched['start_date'])}\n{self._format_date(sched['end_date'])}",
                f"{sched['planned_hours']:.1f}",
                f"{sched['actual_hours']:.1f}",
                f"{sched['budget']:.2f}",
                f"{sched['actual_cost']:.2f}"
            ])
        
        schedule_table = Table(schedule_data, colWidths=[4*cm, 3.5*cm, 2.5*cm, 2*cm, 2*cm, 2*cm, 2*cm])
        schedule_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(schedule_table)
        
        # Note cliente
        if data['client'].get('notes'):
            story.append(Spacer(1, 0.5*cm))
            story.append(Paragraph("Note Cliente", self.styles['CustomHeading3']))
            story.append(Paragraph(data['client']['notes'], self.styles['Normal']))
        
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
    
    def generate_project_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per commessa."""
        if not filename:
            project_name = data['project']['name'].replace(' ', '_')
            filename = f"Report_Commessa_{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = f"Report Commessa: {data['project']['name']}"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        
        subtitle = f"Cliente: {data['project']['client_name']}"
        story.append(Paragraph(subtitle, self.styles['CustomHeading3']))
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        kpis = [
            ("Ore Pianificate", f"{data['total_planned_hours']:.1f}"),
            ("Ore Effettive", f"{data['total_actual_hours']:.1f}"),
            ("Budget Totale", f"€ {data['total_budget']:.2f}"),
            ("Costo Effettivo", f"€ {data['total_actual_cost']:.2f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione per attività
        if data['activities_summary']:
            story.append(Paragraph("Distribuzione per Attività", self.styles['CustomHeading2']))
            
            activity_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary']:
                activity_data.append([
                    act['activity_name'],
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}"
                ])
            
            activity_table = Table(activity_data, colWidths=[10*cm, 3.5*cm, 4*cm])
            activity_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(activity_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione per utente
        if data['users_summary']:
            story.append(Paragraph("Distribuzione per Utente", self.styles['CustomHeading2']))
            
            user_data = [['Utente', 'Ore Totali', 'Costo €']]
            for user in data['users_summary']:
                user_data.append([
                    user['full_name'],
                    f"{float(user['total_hours']):.2f}",
                    f"{float(user['total_cost']):.2f}"
                ])
            
            user_table = Table(user_data, colWidths=[10*cm, 3.5*cm, 4*cm])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(user_table)
        
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
    
    def generate_period_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per periodo."""
        if not filename:
            filename = f"Report_Periodo_{data['start_date']}_{data['end_date']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = "Report Periodo"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        
        period = f"Dal {self._format_date(data['start_date'])} al {self._format_date(data['end_date'])}"
        story.append(Paragraph(period, self.styles['CustomHeading3']))
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        avg_cost_per_hour = data['total_cost'] / data['total_hours'] if data['total_hours'] > 0 else 0
        num_entries = len(data['timesheets'])
        
        kpis = [
            ("Ore Totali", f"{data['total_hours']:.1f}"),
            ("Costo Totale", f"€ {data['total_cost']:.2f}"),
            ("Inserimenti", str(num_entries)),
            ("Costo Medio/h", f"€ {avg_cost_per_hour:.2f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Riepilogo per cliente
        if data['clients_summary']:
            story.append(Paragraph("Riepilogo per Cliente", self.styles['CustomHeading2']))
            
            client_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for client in data['clients_summary']:
                pct = (float(client['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                client_data.append([
                    client['client_name'],
                    f"{float(client['total_hours']):.2f}",
                    f"{float(client['total_cost']):.2f}",
                    f"{pct:.1f}%"
                ])
            
            client_table = Table(client_data, colWidths=[8*cm, 3*cm, 3.5*cm, 2.5*cm])
            client_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(client_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Top 10 commesse
        if data['projects_summary']:
            story.append(Paragraph("Top 10 Commesse", self.styles['CustomHeading2']))
            
            project_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for proj in data['projects_summary'][:10]:
                project_data.append([
                    proj['client_name'],
                    proj['project_name'],
                    f"{float(proj['total_hours']):.2f}",
                    f"{float(proj['total_cost']):.2f}"
                ])
            
            project_table = Table(project_data, colWidths=[4.5*cm, 5.5*cm, 3*cm, 4*cm])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(project_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Riepilogo per utente
        if data['users_summary']:
            story.append(Paragraph("Riepilogo per Utente", self.styles['CustomHeading2']))
            
            user_data = [['Utente', 'Ore Totali', 'Costo €', '% Ore']]
            for user in data['users_summary']:
                pct = (float(user['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                user_data.append([
                    user['full_name'],
                    f"{float(user['total_hours']):.2f}",
                    f"{float(user['total_cost']):.2f}",
                    f"{pct:.1f}%"
                ])
            
            user_table = Table(user_data, colWidths=[8*cm, 3*cm, 3.5*cm, 2.5*cm])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(user_table)
        
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
    
    def generate_user_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report per utente."""
        if not filename:
            username = data['user']['username'].replace(' ', '_')
            filename = f"Report_Utente_{username}_{data['start_date']}_{data['end_date']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = f"Report Utente: {data['user']['full_name']}"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        
        period = f"Dal {self._format_date(data['start_date'])} al {self._format_date(data['end_date'])}"
        story.append(Paragraph(period, self.styles['CustomHeading3']))
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        kpis = [
            ("Ore Totali", f"{data['total_hours']:.1f}"),
            ("Costo Totale", f"€ {data['total_cost']:.2f}"),
            ("Giorni Lavorativi", str(data['work_days'])),
            ("Media Ore/Giorno", f"{data['avg_hours_per_day']:.1f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione per cliente
        if data['clients_summary']:
            story.append(Paragraph("Distribuzione per Cliente", self.styles['CustomHeading2']))
            
            client_data = [['Cliente', 'Ore Totali', 'Costo €', '% Ore']]
            for client in data['clients_summary']:
                pct = (float(client['total_hours']) / data['total_hours'] * 100) if data['total_hours'] > 0 else 0
                client_data.append([
                    client['client_name'],
                    f"{float(client['total_hours']):.2f}",
                    f"{float(client['total_cost']):.2f}",
                    f"{pct:.1f}%"
                ])
            
            client_table = Table(client_data, colWidths=[8*cm, 3*cm, 3.5*cm, 2.5*cm])
            client_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(client_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione per commessa
        if data['projects_summary']:
            story.append(Paragraph("Distribuzione per Commessa", self.styles['CustomHeading2']))
            
            project_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for proj in data['projects_summary']:
                project_data.append([
                    proj['client_name'],
                    proj['project_name'],
                    f"{float(proj['total_hours']):.2f}",
                    f"{float(proj['total_cost']):.2f}"
                ])
            
            project_table = Table(project_data, colWidths=[4.5*cm, 5.5*cm, 3*cm, 4*cm])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(project_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Distribuzione per attività
        if data['activities_summary']:
            story.append(Paragraph("Distribuzione per Attività", self.styles['CustomHeading2']))
            
            activity_data = [['Attività', 'Ore Totali', 'Costo €']]
            for act in data['activities_summary'][:15]:  # Top 15
                activity_data.append([
                    act['activity_name'],
                    f"{float(act['total_hours']):.2f}",
                    f"{float(act['total_cost']):.2f}"
                ])
            
            activity_table = Table(activity_data, colWidths=[10*cm, 3.5*cm, 3.5*cm])
            activity_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(activity_table)
        
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
    
    def generate_general_report(self, data: dict[str, Any], filename: str = None) -> Path:
        """Genera report generale/riepiloga tivo."""
        if not filename:
            filename = f"Report_Generale_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_path = self.output_dir / filename
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.5*cm,
            bottomMargin=2*cm
        )
        
        story = []
        
        # Titolo
        title = "Report Generale Programmazioni"
        story.append(Paragraph(title, self.styles['CustomTitle']))
        
        if data.get('start_date') and data.get('end_date'):
            period = f"Periodo: {self._format_date(data['start_date'])} - {self._format_date(data['end_date'])}"
            story.append(Paragraph(period, self.styles['CustomHeading3']))
        else:
            story.append(Paragraph("Tutte le programmazioni", self.styles['CustomHeading3']))
        
        story.append(Spacer(1, 0.5*cm))
        
        # KPI
        kpis = [
            ("Programmazioni Attive", str(data['num_active_schedules'])),
            ("A Rischio", str(data['num_at_risk'])),
            ("Ore Totali", f"{data['total_hours']:.1f}"),
            ("Costo Totale", f"€ {data['total_cost']:.2f}")
        ]
        
        story.append(self._build_kpi_table(kpis))
        story.append(Spacer(1, 0.8*cm))
        
        # Programmazioni a rischio
        if data['schedules_at_risk']:
            story.append(Paragraph("⚠️ Programmazioni a Rischio", self.styles['CustomHeading2']))
            
            risk_data = [['Cliente/Commessa/Attività', 'Periodo', 'Ore Manc.', 'Gg Manc.']]
            for sched in data['schedules_at_risk'][:10]:  # Top 10
                name = f"{sched['client_name']} > {sched['project_name']} > {sched['activity_name']}"
                risk_data.append([
                    name[:50],  # Limita lunghezza
                    f"{self._format_date(sched['start_date'])}\n{self._format_date(sched['end_date'])}",
                    f"{sched['remaining_hours']:.1f}",
                    str(sched['remaining_days'])
                ])
            
            risk_table = Table(risk_data, colWidths=[9*cm, 3*cm, 2.5*cm, 2.5*cm])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d32f2f')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('TOPPADDING', (0, 1), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(risk_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Top clienti per fatturato
        if data['clients_summary']:
            story.append(Paragraph("Top Clienti per Fatturato", self.styles['CustomHeading2']))
            
            client_data = [['Cliente', 'Ore Totali', 'Costo €']]
            for client in data['clients_summary'][:10]:
                client_data.append([
                    client['client_name'],
                    f"{float(client['total_hours']):.2f}",
                    f"{float(client['total_cost']):.2f}"
                ])
            
            client_table = Table(client_data, colWidths=[10*cm, 3.5*cm, 3.5*cm])
            client_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(client_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Top commesse
        if data['projects_summary']:
            story.append(Paragraph("Top 10 Commesse", self.styles['CustomHeading2']))
            
            project_data = [['Cliente', 'Commessa', 'Ore', 'Costo €']]
            for proj in data['projects_summary'][:10]:
                project_data.append([
                    proj['client_name'],
                    proj['project_name'],
                    f"{float(proj['total_hours']):.2f}",
                    f"{float(proj['total_cost']):.2f}"
                ])
            
            project_table = Table(project_data, colWidths=[4.5*cm, 5.5*cm, 3*cm, 4*cm])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(project_table)
            story.append(Spacer(1, 0.8*cm))
        
        # Riepilogo utenti
        if data['users_summary']:
            story.append(Paragraph("Riepilogo Utenti", self.styles['CustomHeading2']))
            
            user_data = [['Utente', 'Ore Totali', 'Costo €']]
            for user in data['users_summary']:
                user_data.append([
                    user['full_name'],
                    f"{float(user['total_hours']):.2f}",
                    f"{float(user['total_cost']):.2f}"
                ])
            
            user_table = Table(user_data, colWidths=[10*cm, 3.5*cm, 3.5*cm])
            user_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(user_table)
        
        doc.build(story, onFirstPage=self._create_header, onLaterPages=self._create_header)
        
        return output_path
