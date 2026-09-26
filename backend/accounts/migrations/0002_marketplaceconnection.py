import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_marketplace_connections(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    MarketplaceConnection = apps.get_model("accounts", "MarketplaceConnection")
    marketplaces = ("vinted", "depop", "ebay")
    rows = []
    for user in User.objects.all().iterator():
        existing = set(
            MarketplaceConnection.objects.filter(user=user).values_list(
                "marketplace", flat=True
            )
        )
        for marketplace in marketplaces:
            if marketplace in existing:
                continue
            rows.append(
                MarketplaceConnection(
                    user=user,
                    marketplace=marketplace,
                    status="not_connected",
                )
            )
    if rows:
        MarketplaceConnection.objects.bulk_create(rows)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarketplaceConnection",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("not_connected", "Not connected"),
                            ("connected", "Connected"),
                            ("needs_login", "Needs login"),
                            ("failed", "Failed"),
                        ],
                        default="not_connected",
                        max_length=16,
                    ),
                ),
                ("external_username", models.CharField(blank=True, max_length=255)),
                ("connected_at", models.DateTimeField(blank=True, null=True)),
                ("last_checked_at", models.DateTimeField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="marketplace_connections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="marketplaceconnection",
            constraint=models.UniqueConstraint(
                fields=("user", "marketplace"),
                name="unique_user_marketplace_connection",
            ),
        ),
        migrations.RunPython(
            backfill_marketplace_connections, migrations.RunPython.noop
        ),
    ]
