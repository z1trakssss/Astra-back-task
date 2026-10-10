from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth

from .models import Sale


def _bars(rows, label_key, limit=12):
    """Подготавливает значения для столбчатой диаграммы."""
    items = list(rows[:limit])
    top = max((row["revenue"] or 0 for row in items), default=0)
    return [
        {
            "label": str(row[label_key]),
            "revenue": row["revenue"],
            "width": round(100 * row["revenue"] / top, 1) if top else 0,
        }
        for row in items
    ]


def dashboard_callback(request, context):
    """Формирует показатели для главной страницы админки."""
    if not request.user.has_perm("sales.view_sale"):
        return context
    totals = Sale.objects.aggregate(
        count=Count("id"), revenue=Sum("revenue"), units=Sum("units")
    )
    monthly = (
        Sale.objects.annotate(month=TruncMonth("week_id"))
        .order_by()
        .values("month")
        .annotate(revenue=Sum("revenue"))
        .order_by("-month")
    )
    regions = (
        Sale.objects.order_by()
        .values("region")
        .annotate(revenue=Sum("revenue"))
        .order_by("-revenue")
    )
    categories = (
        Sale.objects.order_by()
        .values("product_category")
        .annotate(revenue=Sum("revenue"))
        .order_by("-revenue")
    )
    context.update(
        {
            "kpi": totals,
            "months": _bars(list(monthly[:12])[::-1], "month"),
            "regions": _bars(regions, "region", 9),
            "categories": _bars(categories, "product_category", 10),
        }
    )
    return context
