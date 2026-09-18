"""
Seed the database with realistic demo data for the blog app (Category,
Post), so the blog listing page and its sidebar - both of which read
from /api/v1/blog/... - have something real to show.

Usage:
    python manage.py seed_blog            # seed (skips if already seeded)
    python manage.py seed_blog --flush     # wipe existing seed data, reseed

Notes:
- Mirrors the style of orders/management/commands/seed_store.py: image
  fields are filled with small generated placeholder PNGs (via Pillow),
  and everything this command creates is tagged by a fixed set of
  usernames/titles, so `--flush` can remove exactly what it added.
- Post.created_date is `auto_now_add`, so realistic/varied publish
  dates are applied with a bulk `.update()` right after creation
  (the ORM's `save()` can't set it directly).
"""

import random
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from blog.models import Category, Post

User = get_user_model()

SEED_PASSWORD = "Passw0rd!123"

AUTHOR_USERNAMES = ["emma_hart", "daniel_cho"]

PLACEHOLDER_COLORS = [
    "8bc34a",
    "ff7043",
    "26a69a",
    "ab47bc",
    "5c6bc0",
    "ffa726",
]


def placeholder_image(label, size=(700, 450)):
    """A tiny in-memory PNG so ImageFields have a real file to point to."""
    from PIL import Image, ImageDraw

    color = "#" + random.choice(PLACEHOLDER_COLORS)
    img = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(img)
    draw.text((16, 16), label[:40], fill="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    safe_name = "".join(c if c.isalnum() else "_" for c in label.lower())[:40]
    return ContentFile(buffer.getvalue(), name=f"{safe_name}.png")


AUTHOR_DATA = [
    {
        "username": "emma_hart",
        "email": "emma.hart@nexora.test",
        "first_name": "Emma",
        "last_name": "Hart",
        "description": "Food writer covering recipes and healthy eating.",
    },
    {
        "username": "daniel_cho",
        "email": "daniel.cho@nexora.test",
        "first_name": "Daniel",
        "last_name": "Cho",
        "description": "Kitchen tips, shopping guides and food news.",
    },
]

CATEGORY_DATA = [
    "Recipes",
    "Kitchen Tips",
    "Healthy Eating",
    "Food News",
    "Shopping Guides",
]

# Each post: category, title, excerpt, content, status, author username,
# and days_ago (used to back-date created_date for a realistic, varied
# "-created_date" ordering on the listing page).
POST_DATA = [
    dict(
        category="Recipes",
        title="Five-Minute Weeknight Stir-Fry",
        excerpt=(
            "A fast, pantry-friendly stir-fry that comes together before the "
            "rice is even done."
        ),
        content=(
            "Some nights call for dinner in the time it takes to boil rice. "
            "This "
            "stir-fry leans on whatever vegetables are in the crisper drawer "
            "and a "
            "simple soy-garlic sauce that clings to everything in the pan. "
            "Keep the "
            "heat high, keep the pieces small, and keep stirring - that's "
            "really "
            "the whole recipe."
        ),
        status=Post.Status.PUBLISHED,
        author="emma_hart",
        days_ago=2,
    ),
    dict(
        category="Recipes",
        title="Classic Sourdough Bread From Scratch",
        excerpt=(
            "Everything you need to bake a crackly-crusted sourdough loaf at "
            "home, starter included."
        ),
        content=(
            "A good sourdough loaf rewards patience more than skill. This "
            "walkthrough "
            "covers building a starter from flour and water, reading the "
            "dough at "
            "each stage, and getting a proper oven spring without any special "
            "equipment beyond a heavy pot."
        ),
        status=Post.Status.PUBLISHED,
        author="daniel_cho",
        days_ago=10,
    ),
    dict(
        category="Recipes",
        title="One-Pot Creamy Tomato Pasta",
        excerpt=(
            "A weeknight pasta that only dirties one pot, finished with a "
            "spoonful of cream."
        ),
        content=(
            "The pasta cooks directly in the tomato sauce, releasing starch "
            "that "
            "thickens everything as it goes. A splash of cream at the end "
            "rounds "
            "out the acidity, and dinner is ready in about twenty minutes "
            "with a "
            "single pot to wash."
        ),
        status=Post.Status.PUBLISHED,
        author="emma_hart",
        days_ago=25,
    ),
    dict(
        category="Kitchen Tips",
        title="Knife Skills Every Home Cook Should Know",
        excerpt=(
            "The handful of cuts that cover almost every recipe, explained "
            "step by step."
        ),
        content=(
            "You don't need a drawer full of knives to cook well - you need "
            "one "
            "sharp chef's knife and a few reliable cuts. This guide breaks "
            "down the "
            "dice, the julienne, and the chiffonade, plus how to keep your "
            "fingers "
            "safely out of the way."
        ),
        status=Post.Status.PUBLISHED,
        author="daniel_cho",
        days_ago=5,
    ),
    dict(
        category="Kitchen Tips",
        title="How to Organize a Small Pantry",
        excerpt=(
            "A simple system for keeping a compact pantry tidy, visible and "
            "easy to shop from."
        ),
        content=(
            "Small pantries stay useful when everything has a fixed "
            "spot and a clear label. Grouping by how you cook - grains, "
            "baking, canned goods, "
            "snacks - makes it obvious at a glance what's running low before "
            "you "
            "head to the store."
        ),
        status=Post.Status.PUBLISHED,
        author="emma_hart",
        days_ago=18,
    ),
    dict(
        category="Healthy Eating",
        title="Building a Balanced Plate Without Counting Calories",
        excerpt=(
            "A simple visual method for balanced meals that doesn't involve a "
            "food scale."
        ),
        content=(
            "Splitting a plate roughly into vegetables, protein and whole "
            "grains "
            "gets most meals into a healthy range without tracking a single "
            "number. "
            "It's a rough guide, not a rulebook, and it flexes easily around "
            "whatever you already like to eat."
        ),
        status=Post.Status.PUBLISHED,
        author="emma_hart",
        days_ago=1,
    ),
    dict(
        category="Healthy Eating",
        title="Simple Swaps to Cut Added Sugar",
        excerpt=(
            "Small, easy substitutions that quietly lower added sugar "
            "across a week of meals."
        ),
        content=(
            "Added sugar hides in places that don't taste especially sweet - "
            "sauces, dressings, bread. A few small swaps, like unsweetened "
            "yogurt "
            "or a squeeze of citrus instead of bottled dressing, add up "
            "over a week "
            "without feeling like a diet."
        ),
        status=Post.Status.PUBLISHED,
        author="daniel_cho",
        days_ago=14,
    ),
    dict(
        category="Healthy Eating",
        title="Meal Prep Basics for Busy Weeks",
        excerpt=(
            "A short draft outlining a starter meal-prep routine for hectic "
            "weeks."
        ),
        content=(
            "Draft notes: cover a base grain, a roasted vegetable, and a "
            "protein "
            "that reheats well, then mix and match across the week. Needs a "
            "shopping "
            "list section and photos before this goes live."
        ),
        status=Post.Status.DRAFT,
        author="emma_hart",
        days_ago=3,
    ),
    dict(
        category="Food News",
        title="Local Farmers Market Season Kicks Off Early This Year",
        excerpt=(
            "A mild spring has local growers bringing produce to market a few "
            "weeks ahead of schedule."
        ),
        content=(
            "Warmer-than-usual weather this spring pushed several regional "
            "farms to "
            "open their stalls earlier than planned. Early arrivals include "
            "leafy "
            "greens and the season's first strawberries, with vendors "
            "expecting a "
            "longer market season overall."
        ),
        status=Post.Status.PUBLISHED,
        author="daniel_cho",
        days_ago=7,
    ),
    dict(
        category="Food News",
        title="Study Links Fermented Foods to Better Gut Health",
        excerpt=(
            "New research points to regular fermented-food intake as a simple "
            "way to diversify gut bacteria."
        ),
        content=(
            "A recent nutrition study found that participants who added a "
            "daily "
            "serving of fermented food - things like yogurt, kimchi or "
            "sauerkraut - "
            "showed a more diverse gut microbiome after several weeks "
            "compared to a "
            "high-fiber-only group."
        ),
        status=Post.Status.PUBLISHED,
        author="emma_hart",
        days_ago=30,
    ),
    dict(
        category="Shopping Guides",
        title="How to Read Nutrition Labels Like a Pro",
        excerpt=(
            "What to actually look at on a nutrition label, and which numbers "
            "matter less than you think."
        ),
        content=(
            "Serving size is the number that changes everything else on the "
            "label, "
            "so it's worth checking first. From there, comparing labels side "
            "by "
            "side gets much easier once you know which lines to skim and "
            "which to "
            "read carefully."
        ),
        status=Post.Status.PUBLISHED,
        author="daniel_cho",
        days_ago=12,
    ),
    dict(
        category="Shopping Guides",
        title="Choosing the Best Olive Oil: A Buyer's Guide",
        excerpt=(
            "An older buyer's guide to olive oil grades, due for a refresh "
            "before republishing."
        ),
        content=(
            "Archived: this guide walks through extra-virgin versus refined "
            "olive "
            "oil, harvest dates, and storage tips. Pricing references are "
            "outdated "
            "and need updating before this is republished."
        ),
        status=Post.Status.ARCHIVED,
        author="emma_hart",
        days_ago=40,
    ),
]


class Command(BaseCommand):
    help = "Seed demo data for the blog app (categories and posts)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete previously-seeded blog data before reseeding.",
        )

    def handle(self, *args, **options):
        random.seed(42)

        if options["flush"]:
            self._flush()

        already_seeded = Category.objects.filter(
            name__in=CATEGORY_DATA
        ).exists()
        if not options["flush"] and already_seeded:
            self.stdout.write(
                self.style.WARNING(
                    "Seed data already present - skipping. "
                    "Re-run with --flush to reseed."
                )
            )
            return

        with transaction.atomic():
            authors = self._seed_authors()
            categories = self._seed_categories()
            self._seed_posts(authors, categories)

        self.stdout.write(
            self.style.SUCCESS("Blog data seeded successfully.")
        )

    # -- teardown -----------------------------------------------------
    def _flush(self):
        Post.objects.filter(
            title__in=[p["title"] for p in POST_DATA]
        ).delete()
        Category.objects.filter(name__in=CATEGORY_DATA).delete()
        User.objects.filter(username__in=AUTHOR_USERNAMES).delete()
        self.stdout.write(
            self.style.WARNING("Previously-seeded blog data removed.")
        )

    # -- seeders --------------------------------------------------------
    def _seed_authors(self):
        authors = {}
        for data in AUTHOR_DATA:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={
                    "email": data["email"],
                    "role": User.Role.ADMIN,
                    "is_staff": True,
                    "is_verified": True,
                },
            )
            if created:
                user.set_password(SEED_PASSWORD)
                user.save()
                profile = user.profile
                profile.first_name = data["first_name"]
                profile.last_name = data["last_name"]
                profile.display_name = (
                    f"{data['first_name']} {data['last_name']}"
                )
                profile.description = data["description"]
                profile.save()
            authors[data["username"]] = user
        return authors

    def _seed_categories(self):
        categories = {}
        for name in CATEGORY_DATA:
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category
        return categories

    def _seed_posts(self, authors, categories):
        now = timezone.now()
        for data in POST_DATA:
            post, created = Post.objects.get_or_create(
                title=data["title"],
                defaults={
                    "author": authors[data["author"]],
                    "category": categories[data["category"]],
                    "excerpt": data["excerpt"],
                    "content": data["content"],
                    "status": data["status"],
                },
            )
            if created:
                post.image.save(
                    f"{post.slug}.png",
                    placeholder_image(post.title),
                    save=True,
                )
                # auto_now_add prevents save() from setting created_date, so
                # back-date it directly for a realistic, varied ordering.
                created_dt = now - timedelta(days=data["days_ago"])
                Post.objects.filter(pk=post.pk).update(
                    created_date=created_dt
                )
