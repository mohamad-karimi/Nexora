"""Idempotently sync the django.contrib.sites Site row from settings.

`website/migrations/0005_configure_site.py` only ever runs ONCE (the first
time it is applied) -- a later change to SITE_DOMAIN / SITE_DISPLAY_NAME in
`.env` does NOT get picked up by re-running `migrate`, since Django never
re-runs an already-applied migration. That matters here because
sitemap.xml / the blog and shop RSS feeds build their absolute URLs from
this Site row (see core/website/migrations/0005_configure_site.py).

Run this command on every deploy (see docs/production-deployment.md) so a
domain change always takes effect, without hardcoding the domain anywhere
or requiring a new migration each time it changes.
"""

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Create/update the django.contrib.sites Site row (id=SITE_ID) from "
        "SITE_DOMAIN / SITE_DISPLAY_NAME. Safe to run on every deploy."
    )

    def handle(self, *args, **options):
        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={
                "domain": settings.SITE_DOMAIN,
                "name": settings.SITE_DISPLAY_NAME,
            },
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} Site(id={site.id}): domain={site.domain!r} "
                f"name={site.name!r}"
            )
        )
