"""Unfold admin lists, filters, search, and XLSX summary export."""
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseBadRequest
from django.urls import path
from openpyxl import Workbook
from unfold.admin import ModelAdmin
from .filters import filtered_sales
from .models import MacroWeek, Sale


@admin.register(MacroWeek)
class MacroWeekAdmin(ModelAdmin):
    """Inspect weekly economic indicators separately from the sale facts."""

    list_display = ("week", "housing_starts_index", "lumber_price_index", "mortgage_rate", "season_factor")
    list_filter = ("week",)
    search_fields = ("=week",)


@admin.register(Sale)
class SaleAdmin(ModelAdmin):
    """Browse sales and export a filtered category summary as XLSX."""

    change_list_template = "admin/sales/sale/change_list.html"
    list_display = ("source_row", "week", "region", "product_category", "sku", "channel", "customer_type", "units", "revenue")
    list_filter = ("region", "product_category", "channel", "customer_type", "week")
    search_fields = ("sku", "=source_row")
    list_select_related = ("week",)
    list_per_page = 50
    readonly_fields = ("source_row", "week", "region", "product_category", "sku", "channel", "customer_type", "units", "unit_price", "revenue")

    def has_add_permission(self, request):
        """Preserve the identity of imported source rows."""
        return False

    def get_urls(self):
        """Expose an authenticated report download adjacent to the sale list."""
        return [path("export/", self.admin_site.admin_view(self.export_xlsx), name="sales_sale_export")] + super().get_urls()

    def export_xlsx(self, request):
        """Stream a grouped workbook using the same explicit dimension filters as the API."""
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        params = request.GET.copy()
        for field in ("region", "product_category", "channel", "customer_type"):
            if params.get(f"{field}__exact"):
                params[field] = params[f"{field}__exact"]
        if params.get("week__gte"):
            params["date_from"] = params["week__gte"]
        if params.get("week__lte"):
            params["date_to"] = params["week__lte"]
        try:
            queryset = filtered_sales(params)
        except ValidationError as exc:
            return HttpResponseBadRequest(str(exc))
        if request.GET.get("q"):
            from django.db.models import Q
            term = request.GET["q"]
            query = Q(sku__icontains=term)
            if term.isdigit():
                query |= Q(source_row=int(term))
            queryset = queryset.filter(query)
        book = Workbook(write_only=True)
        sheet = book.create_sheet("Продажи по категориям")
        sheet.append(["Категория", "Транзакций", "Единиц", "Выручка, USD"])
        grouped = queryset.order_by().values("product_category").annotate(
            transactions=Count("id"), units=Sum("units"), revenue=Sum("revenue")).order_by("product_category")
        for row in grouped.iterator():
            sheet.append([row["product_category"], row["transactions"], row["units"], float(row["revenue"])])
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="sales-summary.xlsx"'
        book.save(response)
        return response
