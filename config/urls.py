from django.contrib import admin
from django.urls import path

from sales import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/sales/", api.sales_list, name="sales-list"),
    path("api/v1/sales/aggregate/", api.sales_aggregate, name="sales-aggregate"),
    path("api/v1/macro/", api.macro_list, name="macro-list"),
    path("health/", api.health, name="health"),
]
