from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Product


class ProductSitemap(Sitemap):
    """Public storefront visibility mirrors Product.published exactly
    (same flag the Shop pages/API/related-products already gate on) --
    an unpublished product must never appear here."""

    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Product.objects.filter(published=True).order_by("-created_date")

    def lastmod(self, product):
        return product.update_date

    def location(self, product):
        # Product has no get_absolute_url() (deliberately not added --
        # see the report), so build the real /shop/product/<slug>/
        # route directly.
        return reverse("shop:product_detail", args=[product.slug])
