from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_marketplaceconnection"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="depop_password",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="ebay_password",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="user",
            name="vinted_password",
            field=models.TextField(blank=True),
        ),
    ]
