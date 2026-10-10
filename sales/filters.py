"""Validated filters shared by the API and XLSX export."""
from datetime import date
from django.core.exceptions import ValidationError
from .models import Sale

FIELDS = ("region", "product_category", "sku", "channel", "customer_type")


def filtered_sales(params):
    """Apply exact dimension filters and an inclusive week interval."""
    queryset = Sale.objects.select_related("week")
    for field in FIELDS:
        value = params.get(field)
        if value:
            queryset = queryset.filter(**{field: value})
    for param, lookup in (("date_from", "week_id__gte"), ("date_to", "week_id__lte")):
        value = params.get(param)
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise ValidationError({param: "Ожидается дата YYYY-MM-DD."}) from exc
            queryset = queryset.filter(**{lookup: value})
    return queryset
