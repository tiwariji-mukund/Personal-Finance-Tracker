from datetime import date
from decimal import Decimal

from django.shortcuts import render
from django.utils import timezone

from .services import dashboard_summary, monthly_trend, outstanding_balances, outstanding_loans, shift_month


def _parse_year_month(request):
    today = timezone.localtime(timezone.now()).date()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        date(year, month, 1)  # raises ValueError for an out-of-range month
    except (TypeError, ValueError):
        year, month = today.year, today.month
    return year, month


def _conic_gradient(category_breakdown):
    if not category_breakdown:
        return None
    stops = []
    cursor = Decimal('0')
    for row in category_breakdown:
        start, cursor = cursor, cursor + row['percentage']
        stops.append(f'{row["color"]} {start:.2f}% {cursor:.2f}%')
    return 'conic-gradient(' + ', '.join(stops) + ')'


def _with_bar_heights(trend):
    max_value = max(
        [row['income'] for row in trend]
        + [row['expense'] for row in trend]
        + [row['invested'] for row in trend]
        + [Decimal('1')]
    )
    for row in trend:
        row['income_pct'] = float(row['income'] / max_value * 100)
        row['expense_pct'] = float(row['expense'] / max_value * 100)
        row['invested_pct'] = float(row['invested'] / max_value * 100)
    return trend


def dashboard(request):
    year, month = _parse_year_month(request)
    summary = dashboard_summary(year, month)
    prev_year, prev_month = shift_month(year, month, -1)
    next_year, next_month = shift_month(year, month, 1)

    context = {
        **summary,
        'month_label': date(year, month, 1).strftime('%B %Y'),
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'pie_gradient': _conic_gradient(summary['category_breakdown']),
        'trend': _with_bar_heights(monthly_trend()),
        'outstanding_balances': [row for row in outstanding_balances() if row['outstanding'] != 0],
        'outstanding_loans': [row for row in outstanding_loans() if row['outstanding'] != 0],
    }
    return render(request, 'finance/dashboard.html', context)
