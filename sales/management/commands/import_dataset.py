"""Load the original Kaggle ZIP into normalized, idempotent database tables."""
import csv
import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from sales.models import MacroWeek, Sale


class Command(BaseCommand):
    """Import weekly drivers first, then stream transaction batches from a ZIP."""

    help = "Import the Kaggle source archive; repeated runs keep the same source rows."

    def add_arguments(self, parser):
        """Register archive path and optional test limit."""
        parser.add_argument("--source", type=Path, default=Path("data/source.zip"))
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        """Validate source fields and insert data in bounded batches."""
        source = options["source"]
        if not source.exists():
            raise CommandError(f"Archive missing: {source}")
        limit = options["limit"]
        if limit is not None and limit < 1:
            raise CommandError("--limit must be positive")
        try:
            with zipfile.ZipFile(source) as archive:
                with archive.open("macro_drivers_weekly.csv") as raw:
                    reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                    macro = {}
                    for row in reader:
                        week = date.fromisoformat(row["week"])
                        macro[week] = MacroWeek(week=week,
                            housing_starts_index=Decimal(row["housing_starts_index"]),
                            lumber_price_index=Decimal(row["lumber_price_index"]),
                            mortgage_rate=Decimal(row["mortgage_rate"]),
                            season_factor=Decimal(row["season_factor"]))
                    MacroWeek.objects.bulk_create(macro.values(), ignore_conflicts=True, batch_size=1000)

                count = 0
                batch = []
                with archive.open("building_materials_transactions.csv") as raw:
                    reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))
                    for source_row, row in enumerate(reader, start=1):
                        if limit and source_row > limit:
                            break
                        week = date.fromisoformat(row["date"])
                        if week not in macro:
                            raise CommandError(f"Row {source_row}: no macro observation for {week}")
                        if int(row["year"]) != week.year or int(row["month"]) != week.month or int(row["week_of_year"]) != week.isocalendar().week:
                            raise CommandError(f"Row {source_row}: inconsistent calendar fields")
                        for field in ("housing_starts_index", "lumber_price_index", "mortgage_rate"):
                            if Decimal(row[field]) != getattr(macro[week], field):
                                raise CommandError(f"Row {source_row}: {field} differs from weekly table")
                        units = int(row["units"])
                        price = Decimal(row["unit_price"])
                        revenue = Decimal(row["revenue"])
                        if units < 0 or price < 0 or revenue < 0 or (units * price).quantize(Decimal("0.01")) != revenue:
                            raise CommandError(f"Row {source_row}: invalid amounts")
                        batch.append(Sale(source_row=source_row, week_id=week, region=row["region"],
                            product_category=row["product_category"], sku=row["sku"], channel=row["channel"],
                            customer_type=row["customer_type"], units=units, unit_price=price, revenue=revenue))
                        if len(batch) >= 2000:
                            Sale.objects.bulk_create(batch, ignore_conflicts=True, batch_size=2000)
                            count += len(batch)
                            batch.clear()
                    if batch:
                        Sale.objects.bulk_create(batch, ignore_conflicts=True, batch_size=2000)
                        count += len(batch)
        except (KeyError, ValueError, zipfile.BadZipFile) as exc:
            raise CommandError(f"Invalid source archive: {exc}") from exc
        self.stdout.write(self.style.SUCCESS(f"Read {count} transactions and {len(macro)} macro weeks; total stored: {Sale.objects.count()}"))
