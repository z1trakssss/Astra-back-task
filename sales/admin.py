from django.contrib import admin
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.urls import path
from openpyxl import Workbook
from unfold.admin import ModelAdmin

from .models import MacroWeek, Sale


@admin.register(MacroWeek)
class MacroWeekAdmin(ModelAdmin):
    """Просмотр недельных макроэкономических показателей."""

    list_display = (
        "week",
        "housing_starts_index",
        "lumber_price_index",
        "mortgage_rate",
        "season_factor",
    )
    list_filter = ("week",)
    search_fields = ("=week",)


@admin.register(Sale)
class SaleAdmin(ModelAdmin):
    """Просмотр продаж и выгрузка сводного отчёта."""

    change_list_template = "admin/sales/sale/change_list.html"
    list_display = (
        "source_row",
        "week",
        "region",
        "product_category",
        "sku",
        "channel",
        "customer_type",
        "units",
        "revenue",
    )
    list_filter = ("region", "product_category", "channel", "customer_type", "week")
    search_fields = ("sku", "=source_row")
    list_select_related = ("week",)
    list_per_page = 50
    readonly_fields = (
        "source_row",
        "week",
        "region",
        "product_category",
        "sku",
        "channel",
        "customer_type",
        "units",
        "unit_price",
        "revenue",
    )

    def has_add_permission(self, request):
        """Запрещает ручное добавление импортируемых строк."""
        return False

    def get_urls(self):
        """Добавляет маршрут выгрузки отчёта."""
        return [
            path(
                "export/",
                self.admin_site.admin_view(self.export_xlsx),
                name="sales_sale_export",
            )
        ] + super().get_urls()

    def export_xlsx(self, request):
        """Выгружает сводку по текущим фильтрам списка продаж."""
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        queryset = self.get_changelist_instance(request).queryset
        book = Workbook(write_only=True)
        sheet = book.create_sheet("Продажи по категориям")
        sheet.append(["Категория", "Транзакций", "Единиц", "Выручка, USD"])
        grouped = (
            queryset.order_by()
            .values("product_category")
            .annotate(
                transactions=Count("id"), units=Sum("units"), revenue=Sum("revenue")
            )
            .order_by("product_category")
        )
        for row in grouped.iterator():
            sheet.append(
                [
                    row["product_category"],
                    row["transactions"],
                    row["units"],
                    float(row["revenue"]),
                ]
            )
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = 'attachment; filename="sales-summary.xlsx"'
        book.save(response)
        return response
