import xml.etree.ElementTree as ET

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from shop.models import Category
from shop.tests import make_product, make_user

User = get_user_model()


class ProductFeedTests(TestCase):
    def setUp(self):
        self.url = reverse("shop:feed")
        self.category = Category.objects.create(name="Feed Groceries")
        self.vendor = make_user("feed-vendor", role=User.Role.VENDOR).vendor_profile

    def test_feed_returns_200_and_valid_rss(self):
        make_product(
            self.vendor, self.category, sku="SKU-FEED-1", slug="feed-visible",
            published=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("rss", response["Content-Type"])
        # Must parse as well-formed XML.
        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, "rss")

    def test_only_published_products_are_in_feed(self):
        visible = make_product(
            self.vendor, self.category, sku="SKU-FEED-2", slug="feed-shown",
            published=True,
        )
        hidden = make_product(
            self.vendor, self.category, sku="SKU-FEED-3", slug="feed-hidden",
            published=False,
        )

        response = self.client.get(self.url)
        body = response.content.decode()

        self.assertIn(f"/shop/product/{visible.slug}/", body)
        self.assertNotIn(f"/shop/product/{hidden.slug}/", body)

    def test_links_are_absolute(self):
        make_product(
            self.vendor, self.category, sku="SKU-FEED-4", slug="feed-absolute",
            published=True,
        )

        response = self.client.get(self.url)
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        link = channel.find("link").text
        item_link = channel.find("item/link").text

        self.assertTrue(link.startswith("http://") or link.startswith("https://"))
        self.assertTrue(item_link.startswith("http://") or item_link.startswith("https://"))
