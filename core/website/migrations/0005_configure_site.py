from django.conf import settings
from django.db import migrations


def configure_site(apps, schema_editor):
    """
    Point the SITE_ID Site row at the project's real domain/display
    name, both of which come from settings (environment-configurable)
    -- never hardcoded here. This is what lets
    django.contrib.sitemaps / django.contrib.syndication build correct
    absolute URLs (see sitemap.xml, /blog/feed/, /shop/feed/) instead
    of falling back to the sites-framework default "example.com".
    """
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        id=settings.SITE_ID,
        defaults={
            "domain": settings.SITE_DOMAIN,
            "name": settings.SITE_DISPLAY_NAME,
        },
    )


def noop(apps, schema_editor):
    # Deliberately not reverting to "example.com": on rollback we'd
    # rather leave the previously-configured domain in place than
    # reintroduce the sites-framework placeholder.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sites", "0002_alter_domain_unique"),
        ("website", "0004_seed_home_slides_and_banners"),
    ]

    operations = [
        migrations.RunPython(configure_site, noop),
    ]
