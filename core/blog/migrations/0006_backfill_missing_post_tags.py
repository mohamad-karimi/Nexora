from django.db import migrations
from django.utils.text import slugify

# slug -> tag names to add, only applied to posts that currently have
# zero tags (idempotent + doesn't touch posts an editor already tagged).
TAG_ASSIGNMENTS = {
    "classic-sourdough-bread-from-scratch": ["Bread", "Baking"],
    "one-pot-creamy-tomato-pasta": ["Pasta", "Food"],
    "knife-skills-every-home-cook-should-know": ["Knife Skills"],
    "how-to-organize-a-small-pantry": ["Pantry", "Organization"],
    "simple-swaps-to-cut-added-sugar": ["Swaps", "Sugar"],
    "local-farmers-market-season-kicks-off-early-this-year": ["Farmers", "Market"],
    "how-to-read-nutrition-labels-like-a-pro": ["Nutrition", "Labels"],
    "choosing-the-best-olive-oil-a-buyers-guide": ["Olive Oil", "Shopping"],
}


def backfill_tags(apps, schema_editor):
    Post = apps.get_model("blog", "Post")
    Tag = apps.get_model("blog", "Tag")

    for slug, tag_names in TAG_ASSIGNMENTS.items():
        try:
            post = Post.objects.get(slug=slug)
        except Post.DoesNotExist:
            continue
        if post.tags.exists():
            continue  # already tagged (by an editor, or a re-run) - leave it alone
        for name in tag_names:
            tag, _created = Tag.objects.get_or_create(
                name=name, defaults={"slug": slugify(name)}
            )
            post.tags.add(tag)


def noop_reverse(apps, schema_editor):
    # Intentionally not removing tags on reverse: they may have been
    # reused/edited since, and Tag rows are shared across posts.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0005_postlike"),
    ]

    operations = [
        migrations.RunPython(backfill_tags, noop_reverse),
    ]
