from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product

User = get_user_model()


def make_vendor(username, store_name, **vendor_fields):
    """A verified, approved vendor with a real Vendor row -- created the
    same way the app itself creates one (vendors.signals), then updated
    with the specific fields each test needs."""
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=User.Role.VENDOR,
        is_verified=True,
    )
    vendor = user.vendor_profile
    vendor.store_name = store_name
    vendor.is_approved = True
    for field, value in vendor_fields.items():
        setattr(vendor, field, value)
    vendor.save()
    return vendor


class VendorListShowAPITests(APITestCase):
    """
    GET /api/v1/vendors/ -- the "Show: 50/100/150/200/All" dropdown maps
    directly onto page_size (see StandardPagination), so these exercise
    the real API + database, not a frontend-only count.
    """

    def setUp(self):
        self.url = reverse("api:api_v1:vendor-list")
        for i in range(60):
            make_vendor(f"vendor{i}", f"Store {i:02d}")

    def test_default_show_uses_the_50_page_size_used_by_the_ui_default(self):
        response = self.client.get(self.url, {"page_size": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 60)
        self.assertEqual(len(response.data["results"]), 50)

    def test_show_100_returns_up_to_100_real_vendors(self):
        response = self.client.get(self.url, {"page_size": 100})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 60)
        # Only 60 exist -- page_size is a ceiling, not a fabricated count.
        self.assertEqual(len(response.data["results"]), 60)

    def test_show_all_maps_to_the_backend_max_page_size(self):
        # "All" -> page_size=200, the API's own configured max (see
        # StandardPagination.max_page_size), so it isn't an unbounded
        # or fake request.
        response = self.client.get(self.url, {"page_size": 200})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 60)

    def test_page_size_is_capped_at_the_configured_maximum(self):
        response = self.client.get(self.url, {"page_size": 10000})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data["results"]), 200)

    def test_changing_show_changes_pagination(self):
        small = self.client.get(self.url, {"page_size": 50})
        large = self.client.get(self.url, {"page_size": 100})
        self.assertIsNotNone(small.data["next"])
        self.assertIsNone(large.data["next"])

    def test_vendor_count_reflects_real_database_state_not_a_hardcoded_number(
        self,
    ):
        response = self.client.get(self.url, {"page_size": 200})
        self.assertEqual(response.data["count"], 60)

        make_vendor("vendor60", "Store 60")
        response = self.client.get(self.url, {"page_size": 200})
        self.assertEqual(response.data["count"], 61)


class VendorListSortAPITests(APITestCase):
    """
    GET /api/v1/vendors/?ordering=... -- only fields VendorViewSet
    actually declares in ordering_fields (store_name, created_date,
    product_count) are exercised; there is no "featured" field on the
    Vendor model, so it must not appear here.
    """

    def setUp(self):
        self.url = reverse("api:api_v1:vendor-list")
        self.category = Category.objects.create(name="Groceries")
        self.zeta = make_vendor("zeta", "Zeta Market")
        self.alpha = make_vendor("alpha", "Alpha Grocery")
        self.mid = make_vendor("mid", "Mid Foods")
        # Give them differing, real, checkable product counts.
        for i in range(3):
            Product.objects.create(
                vendor=self.zeta,
                category=self.category,
                name=f"Zeta product {i}",
                sku=f"ZETA-{i}",
                price="1.00",
                published=True,
            )
        Product.objects.create(
            vendor=self.mid,
            category=self.category,
            name="Mid product",
            sku="MID-0",
            price="1.00",
            published=True,
        )

    def test_default_ordering_is_by_store_name_ascending(self):
        response = self.client.get(self.url, {"page_size": 200})
        names = [v["store_name"] for v in response.data["results"]]
        self.assertEqual(names, sorted(names))
        self.assertEqual(names[0], "Alpha Grocery")

    def test_sort_by_name_descending(self):
        response = self.client.get(
            self.url, {"page_size": 200, "ordering": "-store_name"}
        )
        names = [v["store_name"] for v in response.data["results"]]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_sort_by_newest_uses_real_created_date(self):
        response = self.client.get(
            self.url, {"page_size": 200, "ordering": "-created_date"}
        )
        slugs = [v["slug"] for v in response.data["results"]]
        # mid was created last in setUp, zeta first.
        self.assertEqual(slugs[0], self.mid.slug)
        self.assertEqual(slugs[-1], self.zeta.slug)

    def test_sort_by_total_items_uses_real_published_product_count(self):
        response = self.client.get(
            self.url, {"page_size": 200, "ordering": "-product_count"}
        )
        results = response.data["results"]
        self.assertEqual(results[0]["slug"], self.zeta.slug)
        self.assertEqual(results[0]["product_count"], 3)
        # alpha has zero products -- must sort last on -product_count.
        self.assertEqual(results[-1]["slug"], self.alpha.slug)
        self.assertEqual(results[-1]["product_count"], 0)

    def test_unsupported_ordering_field_is_rejected_not_silently_faked(self):
        # DRF's OrderingFilter ignores fields not in ordering_fields and
        # falls back to the declared default (store_name) -- it must
        # NOT silently pretend to sort by something like "featured" that
        # has no backing field.
        response = self.client.get(
            self.url, {"page_size": 200, "ordering": "featured"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [v["store_name"] for v in response.data["results"]]
        self.assertEqual(names, sorted(names))

    def test_show_and_sort_work_together(self):
        response = self.client.get(
            self.url, {"page_size": 2, "ordering": "-product_count"}
        )
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(response.data["results"][0]["slug"], self.zeta.slug)
        self.assertIsNotNone(response.data["next"])


class VendorListPageRenderTests(TestCase):
    """The Vendor List page itself must not ship a hardcoded vendor
    count or dead '#' sort links -- those are populated/wired by JS
    against the real API."""

    def test_page_has_no_hardcoded_vendor_count(self):
        response = self.client.get(reverse("vendors:list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("780", content)

    def test_show_and_sort_options_carry_real_data_attributes(self):
        response = self.client.get(reverse("vendors:list"))
        content = response.content.decode()
        for page_size in ("50", "100", "150", "200"):
            self.assertIn(f'data-page-size="{page_size}"', content)
        for ordering in ("store_name", "-created_date", "-product_count"):
            self.assertIn(f'data-ordering="{ordering}"', content)
        # No fake sort criteria the backend can't act on.
        self.assertNotIn(">Featured<", content)
        self.assertNotIn(">Mall<", content)
        self.assertNotIn(">Preferred<", content)
        self.assertNotIn(">Avg. Rating<", content)
