# Data migration for the new `published` flag (see 0003).
#
# `published` defaults to False for *new* rows, which is exactly what
# we want for products a vendor creates from now on. But existing
# products that were already status="published" (and therefore already
# visible in the Shop) must keep working after this change ships --
# otherwise every live product in the marketplace would disappear from
# the storefront the moment this migration runs. So: backfill
# `published=True` for exactly the rows that were already public under
# the old status-based check, and leave everything else (draft/archived)
# as published=False, matching the previous visibility rules exactly.

from django.db import migrations


def backfill_published(apps, schema_editor):
    Product = apps.get_model("shop", "Product")
    Product.objects.filter(status="published").update(published=True)


def unset_published(apps, schema_editor):
    # Reversing this migration only undoes what it did -- it does not
    # touch rows an admin has since published by hand.
    Product = apps.get_model("shop", "Product")
    Product.objects.filter(status="published", published=True).update(published=False)


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0003_product_published"),
    ]

    operations = [
        migrations.RunPython(backfill_published, unset_published),
    ]
