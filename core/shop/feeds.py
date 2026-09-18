from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Product


class ProductFeed(Feed):
    """
    /shop/feed/ -- published products only (mirrors the same
    Product.published gate the Shop pages/API already use). No vendor
    or other private data is exposed; item_description only surfaces
    what's already public on the product page.
    """

    title = "Nexora Products"
    description = "Latest published products from the Nexora marketplace."

    def link(self):
        return reverse("shop:grid_left")

    def items(self):
        return Product.objects.filter(published=True).order_by(
            "-created_date"
        )[:50]

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        parts = []
        if item.short_description:
            parts.append(item.short_description)
        parts.append(f"Price: {item.final_price}")
        return " | ".join(parts)

    def item_link(self, item):
        return reverse("shop:product_detail", args=[item.slug])

    def item_pubdate(self, item):
        return item.created_date

    def item_updateddate(self, item):
        return item.update_date

    def __call__(self, request, *args, **kwargs):
        # Stashed so item_enclosure_url() below can build an absolute
        # image URL -- Django's syndication framework absolutizes
        # item_link/the feed's own link via the current Site automatically,
        # but it does NOT do the same for enclosure URLs.
        self.request = request
        return super().__call__(request, *args, **kwargs)

    def item_enclosure_url(self, item):
        if item.image:
            return self.request.build_absolute_uri(item.image.url)
        return None

    def item_enclosure_length(self, item):
        return "0"

    def item_enclosure_mime_type(self, item):
        return "image/jpeg" if item.image else None
