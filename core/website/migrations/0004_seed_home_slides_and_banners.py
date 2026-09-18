import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations

# Content mirrors the static markup that templates/website/index.html
# previously hard-coded for the `home-slider` and `banners mb-25`
# sections, so switching them to be DB-driven does not change what's
# shown on a fresh deploy. Source images are copied from `static/` (a
# read-only theme asset dir) into `media/` (the ImageField-backed
# upload dir) under the same relative path.

SLIDES = [
    {
        "title": "Don\u2019t miss amazing\ngrocery deals",
        "description": "Sign up for the daily newsletter",
        "source": "imgs/slider/slider-1.png",
        "filename": "slider-1.png",
        "ordering": 0,
    },
    {
        "title": "Fresh Vegetables\nBig discount",
        "description": "Save up to 50% off on your first order",
        "source": "imgs/slider/slider-2.png",
        "filename": "slider-2.png",
        "ordering": 1,
    },
]

BANNERS = [
    {
        "title": "Everyday Fresh & \nClean with Our\nProducts",
        "source": "imgs/banner/banner-1.png",
        "filename": "banner-1.png",
        "ordering": 0,
    },
    {
        "title": "Make your Breakfast\nHealthy and Easy",
        "source": "imgs/banner/banner-2.png",
        "filename": "banner-2.png",
        "ordering": 1,
    },
    {
        "title": "The best Organic \nProducts Online",
        "source": "imgs/banner/banner-3.png",
        "filename": "banner-3.png",
        "ordering": 2,
    },
]


def _copy_static_to_media(source_rel_path, media_subdir, filename):
    src = Path(settings.BASE_DIR) / "static" / source_rel_path
    dest_dir = Path(settings.MEDIA_ROOT) / media_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if src.exists() and not dest.exists():
        shutil.copyfile(src, dest)
    return f"{media_subdir}/{filename}"


def seed_home_content(apps, schema_editor):
    HomeSlide = apps.get_model("website", "HomeSlide")
    HomeBanner = apps.get_model("website", "HomeBanner")

    if not HomeSlide.objects.exists():
        for slide in SLIDES:
            image_path = _copy_static_to_media(
                slide["source"], "sliders", slide["filename"]
            )
            HomeSlide.objects.create(
                title=slide["title"],
                description=slide["description"],
                image=image_path,
                ordering=slide["ordering"],
                is_active=True,
            )

    if not HomeBanner.objects.exists():
        for banner in BANNERS:
            image_path = _copy_static_to_media(
                banner["source"], "banners", banner["filename"]
            )
            HomeBanner.objects.create(
                title=banner["title"],
                image=image_path,
                link_url="",
                ordering=banner["ordering"],
                is_active=True,
            )


def unseed_home_content(apps, schema_editor):
    HomeSlide = apps.get_model("website", "HomeSlide")
    HomeBanner = apps.get_model("website", "HomeBanner")
    HomeSlide.objects.filter(title__in=[s["title"] for s in SLIDES]).delete()
    HomeBanner.objects.filter(title__in=[b["title"] for b in BANNERS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0003_homebanner_homeslide"),
    ]

    operations = [
        migrations.RunPython(seed_home_content, unseed_home_content),
    ]
