"""Read-only JSON endpoints for transactions and their weekly context."""
from datetime import date
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Avg, Count, Sum
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .filters import FIELDS, filtered_sales
from .models import MacroWeek


def _error(message):
    """Return a uniform client error."""
    return JsonResponse({"error": message}, status=400)


def _positive_int(value, default, maximum):
    """Parse a bounded pagination parameter."""
    number = int(value) if value is not None else default
    if not 1 <= number <= maximum:
        raise ValueError
    return number


@require_GET
def health(request):
    """Report process and database readiness."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok"})


@require_GET
def sales_list(request):
    """Return one bounded page of filtered sales with weekly macro indicators."""
    try:
        page = _positive_int(request.GET.get("page"), 1, 10000000)
        page_size = _positive_int(request.GET.get("page_size"), 50, 200)
        queryset = filtered_sales(request.GET)
    except (ValueError, ValidationError) as exc:
        return _error(str(exc))
    total = queryset.count()
    rows = queryset.order_by("source_row")[(page - 1) * page_size:page * page_size]
    return JsonResponse({"count": total, "page": page, "page_size": page_size, "results": [{
        "id": row.id, "date": row.week_id, "region": row.region,
        "product_category": row.product_category, "sku": row.sku,
        "channel": row.channel, "customer_type": row.customer_type,
        "units": row.units, "unit_price": str(row.unit_price), "revenue": str(row.revenue),
        "macro": {"housing_starts_index": str(row.week.housing_starts_index),
                  "lumber_price_index": str(row.week.lumber_price_index),
                  "mortgage_rate": str(row.week.mortgage_rate), "season_factor": str(row.week.season_factor)},
    } for row in rows]})


@require_GET
def sales_aggregate(request):
    """Aggregate the same filtered fact set by one explicitly allowed dimension."""
    group = request.GET.get("group_by", "month")
    if group not in (*FIELDS, "week", "month"):
        return _error("Недопустимое значение group_by.")
    try:
        queryset = filtered_sales(request.GET)
    except ValidationError as exc:
        return _error(str(exc))
    if group == "month":
        from django.db.models.functions import TruncMonth
        queryset = queryset.annotate(bucket=TruncMonth("week_id"))
        key = "bucket"
    elif group == "week":
        key = "week_id"
    else:
        key = group
    rows = queryset.order_by().values(key).annotate(transactions=Count("id"), units=Sum("units"),
        revenue=Sum("revenue"), average_unit_price=Avg("unit_price")).order_by(key)
    return JsonResponse({"group_by": group, "results": [{"value": str(row[key]),
        "transactions": row["transactions"], "units": row["units"],
        "revenue": str(row["revenue"]), "average_unit_price": str(row["average_unit_price"])} for row in rows]})


@require_GET
def macro_list(request):
    """Return weekly exogenous series, optionally restricted by date."""
    rows = MacroWeek.objects.all()
    for param, lookup in (("date_from", "week__gte"), ("date_to", "week__lte")):
        value = request.GET.get(param)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError:
                return _error(f"{param}: ожидается дата YYYY-MM-DD.")
            rows = rows.filter(**{lookup: value})
    return JsonResponse({"results": [{"week": row.week.isoformat(),
        "housing_starts_index": str(row.housing_starts_index),
        "lumber_price_index": str(row.lumber_price_index), "mortgage_rate": str(row.mortgage_rate),
        "season_factor": str(row.season_factor)} for row in rows]})
