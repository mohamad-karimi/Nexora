from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """
    The project's real public, non-model pages. Deliberately excludes
    website:404 (not a page anyone should land on/index) and every
    account/cart/checkout/dashboard route (private, never public).
    """

    changefreq = "monthly"

    def items(self):
        return [
            "website:home",
            "website:about",
            "website:contact",
            "website:privacy_policy",
            "website:purchase_guide",
            "website:terms",
        ]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        # Slightly favour the homepage over the informational pages.
        return 1.0 if item == "website:home" else 0.5
