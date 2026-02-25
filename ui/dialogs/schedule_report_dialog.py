from __future__ import annotations

from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


def show_schedule_report_dialog(app, schedule_id: int) -> None:
    """Mostra finestra report dettagliato per una programmazione."""
    data = app.db.get_schedule_report_data(schedule_id)
    if not data:
        messagebox.showerror("Report", "Programmazione non trovata.")
        return

    # Crea finestra popup
    report_win = tk.Toplevel(app)
    report_win.title(f"Report Programmazione - {data['project_name']}")
    report_win.geometry("1200x800")
    report_win.resizable(True, True)
    report_win.transient(app)

    # Configura colori in base al tema
    bg_color = "#2b2b2b" if app.is_dark_mode else "#f0f0f0"
    fg_color = "#ffffff" if app.is_dark_mode else "#000000"
    card_bg = "#3a3a3a" if app.is_dark_mode else "#ffffff"

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
    except Exception:
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
    plt_style = "dark_background" if app.is_dark_mode else "default"
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
    ax1.grid(axis="y", alpha=0.3)
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
        ax2.pie(user_values, labels=user_labels, autopct="%1.1f%%", startangle=90)
        ax2.set_title("Distribuzione Ore per Utente", fontweight="bold")
    else:
        ax2.text(0.5, 0.5, "Nessun dato disponibile", ha="center", va="center", fontsize=12)
        ax2.set_xlim(0, 1)
        ax2.set_ylim(0, 1)
        ax2.axis("off")

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
        except Exception:
            date_display = detail["work_date"]

        activity = detail.get("activity_name", "")

        detail_tree.insert("", "end", values=(
            date_display,
            detail["username"],
            activity,
            f"{detail['hours']:.2f}",
            f"{detail['cost']:.2f}",
            detail["note"],
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
        main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    main_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    report_win.protocol("WM_DELETE_WINDOW", lambda: [main_canvas.unbind_all("<MouseWheel>"), report_win.destroy()])

