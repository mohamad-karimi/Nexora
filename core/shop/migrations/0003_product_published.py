# Adds the admin-only `published` flag that now gates public storefront
# visibility (see 0004 for the data migration that backfills existing
# rows so already-live products don't disappear from the Shop).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0002_product_color_condition"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="published",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Controls public storefront visibility (Shop, "
                    "category/list pages, search, related products, and "
                    "the public Product API). Only staff/admin can set "
                    "this to True, from Django Admin -- vendors cannot "
                    "publish their own products. The owning vendor and "
                    "staff can still view/manage the product before "
                    "it's published; everyone else cannot."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["published"], name="shop_product_published_idx"
            ),
        ),
    ]
