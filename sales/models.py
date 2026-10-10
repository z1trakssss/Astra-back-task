from django.db import models


class MacroWeek(models.Model):
    """Макроэкономические показатели за одну неделю."""

    week = models.DateField(primary_key=True)
    housing_starts_index = models.DecimalField(max_digits=9, decimal_places=2)
    lumber_price_index = models.DecimalField(max_digits=9, decimal_places=2)
    mortgage_rate = models.DecimalField(max_digits=6, decimal_places=2)
    season_factor = models.DecimalField(max_digits=6, decimal_places=3)

    class Meta:
        ordering = ["week"]
        verbose_name = "недельный показатель"
        verbose_name_plural = "Недельные показатели"

    def __str__(self):
        """Возвращает дату наблюдения."""
        return self.week.isoformat()


class Sale(models.Model):
    """Транзакция из исходного файла."""

    source_row = models.PositiveIntegerField(unique=True)
    week = models.ForeignKey(
        MacroWeek,
        to_field="week",
        db_column="week",
        on_delete=models.PROTECT,
        related_name="sales",
    )
    region = models.CharField(max_length=50, db_index=True)
    product_category = models.CharField(max_length=50, db_index=True)
    sku = models.CharField(max_length=40, db_index=True)
    channel = models.CharField(max_length=30, db_index=True)
    customer_type = models.CharField(max_length=30, db_index=True)
    units = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)
    revenue = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["source_row"]
        indexes = [
            models.Index(fields=["week", "region"]),
            models.Index(fields=["week", "product_category"]),
        ]
        verbose_name = "продажа"
        verbose_name_plural = "Продажи"

    def __str__(self):
        """Возвращает номер строки и артикул."""
        return f"#{self.source_row}: {self.sku}"
