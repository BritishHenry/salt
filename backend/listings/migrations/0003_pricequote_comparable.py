import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0002_item_proposals"),
    ]

    operations = [
        migrations.CreateModel(
            name="PriceQuote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "Running"),
                            ("ready", "Ready"),
                            ("failed", "Failed"),
                        ],
                        default="running",
                        max_length=16,
                    ),
                ),
                (
                    "price_minor",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("currency", models.CharField(default="gbp", max_length=3)),
                ("rationale", models.TextField(blank=True)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_quotes",
                        to="listings.item",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Comparable",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "marketplace",
                    models.CharField(
                        choices=[
                            ("vinted", "Vinted"),
                            ("depop", "Depop"),
                            ("ebay", "eBay"),
                        ],
                        max_length=16,
                    ),
                ),
                ("title", models.CharField(blank=True, max_length=255)),
                ("price_minor", models.PositiveIntegerField()),
                ("currency", models.CharField(default="gbp", max_length=3)),
                ("condition", models.CharField(blank=True, max_length=64)),
                ("size", models.CharField(blank=True, max_length=64)),
                ("url", models.URLField(max_length=500)),
                ("sold", models.BooleanField(default=False)),
                (
                    "similarity",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("high", "High"),
                            ("medium", "Medium"),
                            ("low", "Low"),
                        ],
                        max_length=16,
                    ),
                ),
                ("reason", models.TextField(blank=True)),
                (
                    "quote",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comps",
                        to="listings.pricequote",
                    ),
                ),
            ],
        ),
    ]
