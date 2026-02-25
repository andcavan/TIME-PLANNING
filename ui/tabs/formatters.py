from __future__ import annotations

from datetime import datetime


def format_date_short(date_str: str) -> str:
    """Formatta data da YYYY-MM-DD a DD/MM."""
    if not date_str:
        return ""
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%d/%m")
    except Exception:
        return date_str


def format_remaining_days(days: int, start_date: str, end_date: str) -> str:
    """Formatta giorni restanti con indicatori."""
    if not start_date or not end_date:
        return ""

    # Calcola il periodo totale per la soglia del 10%
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        total_days = (end - start).days
        threshold_10 = total_days * 0.1
    except Exception:
        total_days = 0
        threshold_10 = 0

    if days < 0:
        return f"❌ {days}"
    if days <= threshold_10 and total_days > 0:
        return f"⚠️ {days}"
    return str(days)


def format_hours_diff(diff: float, planned: float) -> str:
    """Formatta differenza ore con indicatori."""
    if planned == 0:
        return ""

    threshold_10 = planned * 0.1

    if diff < 0:
        return f"❌ {diff:.1f}"
    if diff <= threshold_10:
        return f"⚠️ {diff:.1f}"
    return f"{diff:.1f}"


def format_budget_remaining(remaining: float, budget: float) -> str:
    """Formatta budget restante con indicatori."""
    if budget == 0:
        return ""

    threshold_10 = budget * 0.1

    if remaining < 0:
        return f"❌ {remaining:.2f}"
    if remaining <= threshold_10:
        return f"⚠️ {remaining:.2f}"
    return f"{remaining:.2f}"

