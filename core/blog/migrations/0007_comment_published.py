from django.db import migrations, models


def backfill_published(apps, schema_editor):
    """
    Existing comments were gated by is_approved (default False, i.e.
    hidden until moderated). Mirror that into the new published flag
    so nothing that was previously hidden suddenly becomes visible,
    and nothing that was already approved/visible gets hidden.
    """
    Comment = apps.get_model("blog", "Comment")
    Comment.objects.filter(is_approved=False).update(published=False)
    Comment.objects.filter(is_approved=True).update(published=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0006_backfill_missing_post_tags"),
    ]

    operations = [
        migrations.AddField(
            model_name="comment",
            name="published",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Visible on the site when checked. Uncheck to hide "
                    "this comment from every visitor without deleting it."
                ),
            ),
        ),
        migrations.RunPython(backfill_published, noop_reverse),
    ]
