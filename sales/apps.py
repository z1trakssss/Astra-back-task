"""Sales application configuration."""
from django.apps import AppConfig


class SalesConfig(AppConfig):
    """Register the sales domain with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "sales"
