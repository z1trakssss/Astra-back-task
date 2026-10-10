"""Behavior checks for filtering, aggregation, permissions and report content."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import load_workbook
from .models import MacroWeek, Sale


class SalesInterfaceTests(TestCase):
    """Exercise the public read API and the staff-only export."""

    @classmethod
    def setUpTestData(cls):
        """Create two weeks and two distinct product categories."""
        for day in (7, 14):
            MacroWeek.objects.create(week=date(2019, 1, day), housing_starts_index=100,
                lumber_price_index=400, mortgage_rate=4, season_factor=Decimal("0.600"))
        Sale.objects.create(source_row=1, week_id=date(2019, 1, 7), region="Pacific",
            product_category="lumber", sku="L-1", channel="pro_dealer", customer_type="contractor",
            units=2, unit_price=Decimal("10.00"), revenue=Decimal("20.00"))
        Sale.objects.create(source_row=2, week_id=date(2019, 1, 14), region="Mountain",
            product_category="roofing", sku="R-1", channel="big_box_diy", customer_type="homeowner_diy",
            units=3, unit_price=Decimal("5.00"), revenue=Decimal("15.00"))

    def test_sales_filter_macro_and_bounds(self):
        """Return only the selected region and reject invalid pagination."""
        result = self.client.get("/api/v1/sales/", {"region": "Pacific"}).json()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["macro"]["season_factor"], "0.600")
        self.assertEqual(self.client.get("/api/v1/sales/", {"page_size": 201}).status_code, 400)

    def test_aggregate_uses_same_filters(self):
        """Keep units and revenue aligned with the filtered fact set."""
        result = self.client.get("/api/v1/sales/aggregate/", {"region": "Pacific", "group_by": "product_category"}).json()
        self.assertEqual(result["results"][0]["revenue"], "20")
        self.assertEqual(result["results"][0]["units"], 2)
        self.assertEqual(self.client.get("/api/v1/sales/aggregate/", {"group_by": "password"}).status_code, 400)

    def test_export_requires_staff_and_respects_admin_filter(self):
        """Report contents follow changelist filters and require admin access."""
        url = "/admin/sales/sale/export/?region__exact=Pacific"
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_superuser("admin", "a@example.test", "test-password")
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        rows = list(load_workbook(BytesIO(response.content), read_only=True).active.values)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][:3], ("lumber", 1, 2))
