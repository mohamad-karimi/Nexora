# Generated manually for the storefront's Color / Item Condition filters.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="color",
            field=models.CharField(
                blank=True,
                choices=[
                    ("red", "Red"),
                    ("green", "Green"),
                    ("blue", "Blue"),
                ],
                help_text="Optional; powers the storefront's color filter.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="condition",
            field=models.CharField(
                choices=[
                    ("new", "New"),
                    ("refurbished", "Refurbished"),
                    ("used", "Used"),
                ],
                default="new",
                help_text="Powers the storefront's item-condition filter.",
                max_length=20,
            ),
        ),
    ]
