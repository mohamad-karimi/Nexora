import importlib

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER, **profile_fields):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=True,
    )
    if profile_fields:
        profile = user.profile
        for field, value in profile_fields.items():
            setattr(profile, field, value)
        profile.save()
    return user


def make_product(vendor, category, **kwargs):
    defaults = {
        "name": "Test Product",
        "sku": "SKU-0001",
        "price": "9.99",
    }
    defaults.update(kwargs)
    return Product.objects.create(vendor=vendor, category=category, **defaults)


class ProductPublishFlowAPITests(APITestCase):
    """
    End-to-end coverage of the vendor-create -> admin-publish flow:
    - a vendor-created product is saved immediately, with
      published=False, and is never publishable by the vendor
      themselves;
    - the owning vendor (and staff) can open its Product Detail
      before it's published, other vendors and the public cannot;
    - the public Shop/API only ever surfaces published=True products.
    """

    def setUp(self):
        self.category = Category.objects.create(name="Groceries")
        self.vendor_user = make_user("vera", role=User.Role.VENDOR)
        self.vendor = self.vendor_user.vendor_profile
        self.other_vendor_user = make_user("victor", role=User.Role.VENDOR)
        self.other_vendor = self.other_vendor_user.vendor_profile
        self.customer = make_user("carol")
        self.create_url = reverse("api:api_v1:vendor-dashboard-products")

    # 1 & 8 -- creation always lands as published=False, and a vendor
    # cannot force it to True from the request body.
    def test_created_product_is_unpublished_and_vendor_cannot_force_publish(self):
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.post(
            self.create_url,
            {
                "name": "Organic Honey",
                "category": self.category.id,
                "sku": "HONEY-001",
                "price": "9.99",
                "published": True,  # must be silently ignored
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        product = Product.objects.get(sku="HONEY-001")
        self.assertFalse(product.published)
        self.assertEqual(product.vendor, self.vendor)

    # 2 -- Vendor Dashboard listing shows the vendor's own products
    # regardless of publish state (must keep working exactly as
    # before -- this endpoint was never the bug).
    def test_vendor_dashboard_lists_own_unpublished_product(self):
        make_product(self.vendor, self.category, sku="DASH-1", published=False)
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    # 3 & 4 -- the actual bug report: the owning vendor must be able
    # to open Product Detail for their own unpublished product.
    def test_owner_vendor_can_open_unpublished_product_detail(self):
        product = make_product(
            self.vendor, self.category, sku="DETAIL-1", published=False
        )
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], product.slug)

    def test_staff_can_open_unpublished_product_detail(self):
        product = make_product(
            self.vendor, self.category, sku="DETAIL-2", published=False
        )
        staff = make_user("admin")
        staff.is_staff = True
        staff.save()
        self.client.force_authenticate(user=staff)

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # 9 -- another vendor must not be able to open it.
    def test_other_vendor_cannot_open_unpublished_product_detail(self):
        product = make_product(
            self.vendor, self.category, sku="DETAIL-3", published=False
        )
        self.client.force_authenticate(user=self.other_vendor_user)

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 4 -- and neither can an anonymous/customer visitor.
    def test_anonymous_cannot_open_unpublished_product_detail(self):
        product = make_product(
            self.vendor, self.category, sku="DETAIL-4", published=False
        )

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_open_unpublished_product_detail(self):
        product = make_product(
            self.vendor, self.category, sku="DETAIL-5", published=False
        )
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 6/7 -- once published (by admin -- there's no vendor-facing way
    # to do it), the product is visible everywhere public: list,
    # detail, category count.
    def test_published_product_is_visible_in_public_list_and_detail(self):
        product = make_product(
            self.vendor, self.category, sku="PUB-1", published=True
        )

        list_response = self.client.get(reverse("api:api_v1:product-list"))
        detail_response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": product.slug})
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        slugs = [p["slug"] for p in list_response.data["results"]]
        self.assertIn(product.slug, slugs)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

    # 4/8 -- unpublished products never leak into the public list, no
    # matter who's asking.
    def test_unpublished_product_never_appears_in_public_list(self):
        make_product(self.vendor, self.category, sku="HIDDEN-1", published=False)
        self.client.force_authenticate(user=self.vendor_user)

        response = self.client.get(reverse("api:api_v1:product-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_category_product_count_only_counts_published(self):
        make_product(self.vendor, self.category, sku="COUNT-1", published=True)
        make_product(self.vendor, self.category, sku="COUNT-2", published=False)

        response = self.client.get(
            reverse(
                "api:api_v1:category-detail", kwargs={"slug": self.category.slug}
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["product_count"], 1)


class _FakeAppsRegistry:
    """
    Minimal stand-in for the historical `apps` argument RunPython
    migrations receive, so the backfill function -- written against
    `apps.get_model(...)` -- can be called directly against the real
    (already-migrated) Product model from a normal test.
    """

    def get_model(self, app_label, model_name):
        from django.apps import apps as real_apps

        return real_apps.get_model(app_label, model_name)


class ProductPublishedBackfillMigrationTests(TestCase):
    """
    10 -- existing (pre-migration) products must keep working: a
    product that was already status=PUBLISHED has to end up
    published=True after the backfill migration runs, so it doesn't
    vanish from the Shop; anything else (draft/archived) stays
    published=False, matching the old status-based visibility exactly.
    """

    def test_backfill_publishes_only_previously_published_products(self):
        backfill_module = importlib.import_module(
            "shop.migrations.0004_backfill_product_published"
        )
        category = Category.objects.create(name="Groceries")
        vendor_user = make_user("vera", role=User.Role.VENDOR)
        vendor = vendor_user.vendor_profile

        published_before = make_product(
            vendor,
            category,
            sku="OLD-PUB",
            status=Product.Status.PUBLISHED,
            published=False,  # simulate pre-migration state
        )
        draft_before = make_product(
            vendor,
            category,
            sku="OLD-DRAFT",
            status=Product.Status.DRAFT,
            published=False,
        )

        backfill_module.backfill_published(
            apps=_FakeAppsRegistry(), schema_editor=None
        )

        published_before.refresh_from_db()
        draft_before.refresh_from_db()
        self.assertTrue(published_before.published)
        self.assertFalse(draft_before.published)
