import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("listings", "0003_pricequote_comparable"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BuyerThread",
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
                ("marketplace", models.CharField(max_length=16)),
                ("external_thread_id", models.CharField(max_length=255)),
                ("buyer_name", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("needs_seller", "Needs seller"),
                            ("closed", "Closed"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="buyer_threads",
                        to="listings.item",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="buyer_threads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="BuyerMessage",
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
                    "direction",
                    models.CharField(
                        choices=[("buyer", "Buyer"), ("seller", "Seller")],
                        max_length=16,
                    ),
                ),
                ("body", models.TextField()),
                ("offer_minor", models.PositiveIntegerField(blank=True, null=True)),
                ("external_id", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="agents.buyerthread",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="buyerthread",
            constraint=models.UniqueConstraint(
                fields=("user", "marketplace", "external_thread_id"),
                name="unique_buyer_thread",
            ),
        ),
        migrations.AddConstraint(
            model_name="buyermessage",
            constraint=models.UniqueConstraint(
                fields=("thread", "external_id"),
                name="unique_buyer_message",
            ),
        ),
    ]
