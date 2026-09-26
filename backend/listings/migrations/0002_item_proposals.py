from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="proposals",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="item",
            name="confirmed_fields",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
