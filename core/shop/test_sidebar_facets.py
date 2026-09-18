from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product

User = get_user_model()


def make_vendor(username, store_name):
    """A verified, approved vendor with a real Vendor row -- created the
    same way the app itself creates one (vendors.signals)."""
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
    vendor.save()
    return vendor


def make_product(vendor, category, **kwargs):
    sku = kwargs.get("sku", "SKU-0001")
    defaults = {
        "name": f"Test Product {sku}",
        "sku": sku,
        "price": "9.99",
        "published": True,
    }
    defaults.update(kwargs)
    return Product.objects.create(
        vendor=vendor, category=category, **defaults
    )


class ProductFacetsAPITests(APITestCase):
    """
    GET /api/v1/products/facets/ -- backs the Shop sidebar's "Fill by
    price", "Color" and "Item Condition" widgets. Every number here
    must come from real published Product rows, never a hardcoded
    demo value (see templates/shop/sidebar.html /
    static/js/pages/sidebar-price-filter.js).
    """

    def setUp(self):
        self.url = reverse("api:api_v1:product-facets")
        self.vendor = make_vendor("vera", "Vera's Store")
        self.category = Category.objects.create(name="Groceries")

    def test_price_bounds_come_from_real_published_products(self):
        make_product(self.vendor, self.category, sku="P-1", price="15.00")
        make_product(self.vendor, self.category, sku="P-2", price="120.50")
        make_product(self.vendor, self.category, sku="P-3", price="42.00")
        # Unpublished -- must not widen the range.
        make_product(
            self.vendor,
            self.category,
            sku="P-4",
            price="999.00",
            published=False,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"]["min"], 15.00)
        self.assertEqual(response.data["price"]["max"], 120.50)

    def test_price_bounds_are_none_when_no_published_products_exist(self):
        make_product(self.vendor, self.category, sku="P-1", published=False)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["price"]["min"])
        self.assertIsNone(response.data["price"]["max"])

    def test_color_counts_are_real_and_only_actually_occurring_colors_appear(
        self,
    ):
        for i in range(7):
            make_product(
                self.vendor,
                self.category,
                sku=f"RED-{i}",
                color=Product.Color.RED,
            )
        for i in range(3):
            make_product(
                self.vendor,
                self.category,
                sku=f"GREEN-{i}",
                color=Product.Color.GREEN,
            )
        # No blue products at all, and one with color left blank.
        make_product(self.vendor, self.category, sku="NO-COLOR", color="")

        response = self.client.get(self.url)

        colors = {c["value"]: c["count"] for c in response.data["colors"]}
        self.assertEqual(colors, {"red": 7, "green": 3})
        self.assertNotIn("blue", colors)

    def test_unpublished_products_are_excluded_from_color_counts(self):
        make_product(
            self.vendor,
            self.category,
            sku="RED-PUB",
            color=Product.Color.RED,
            published=True,
        )
        make_product(
            self.vendor,
            self.category,
            sku="RED-UNPUB",
            color=Product.Color.RED,
            published=False,
        )

        response = self.client.get(self.url)

        colors = {c["value"]: c["count"] for c in response.data["colors"]}
        self.assertEqual(colors["red"], 1)

    def test_condition_counts_only_include_occurring_conditions(
        self,
    ):
        for i in range(5):
            make_product(
                self.vendor,
                self.category,
                sku=f"NEW-{i}",
                condition=Product.Condition.NEW,
            )
        make_product(
            self.vendor,
            self.category,
            sku="USED-1",
            condition=Product.Condition.USED,
        )
        # No refurbished products at all.

        response = self.client.get(self.url)

        conditions = {
            c["value"]: c["count"] for c in response.data["conditions"]
        }
        self.assertEqual(conditions, {"new": 5, "used": 1})
        self.assertNotIn("refurbished", conditions)

    def test_color_and_condition_filters_apply_on_the_product_list(self):
        red_new = make_product(
            self.vendor,
            self.category,
            sku="RED-NEW",
            color=Product.Color.RED,
            condition=Product.Condition.NEW,
        )
        make_product(
            self.vendor,
            self.category,
            sku="GREEN-NEW",
            color=Product.Color.GREEN,
            condition=Product.Condition.NEW,
        )
        make_product(
            self.vendor,
            self.category,
            sku="RED-USED",
            color=Product.Color.RED,
            condition=Product.Condition.USED,
        )

        list_url = reverse("api:api_v1:product-list")
        response = self.client.get(
            list_url, {"color": "red", "condition": "new"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], red_new.slug)

    def test_price_range_combines_with_color_filter(self):
        make_product(
            self.vendor,
            self.category,
            sku="RED-CHEAP",
            price="10.00",
            color=Product.Color.RED,
        )
        expensive_red = make_product(
            self.vendor,
            self.category,
            sku="RED-PRICEY",
            price="80.00",
            color=Product.Color.RED,
        )

        list_url = reverse("api:api_v1:product-list")
        response = self.client.get(
            list_url, {"color": "red", "min_price": "50", "max_price": "100"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["slug"], expensive_red.slug
        )

    def test_price_bounds_when_every_published_product_shares_one_price(self):
        # min == max is a real value, not a bug -- the "Fill by price"
        # widget must still show it (see sidebar-price-filter.js's
        # handling of this exact case for the noUiSlider range).
        make_product(self.vendor, self.category, sku="P-1", price="20.00")
        make_product(self.vendor, self.category, sku="P-2", price="20.00")

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"]["min"], 20.00)
        self.assertEqual(response.data["price"]["max"], 20.00)


class ShopPriceFilterAPITests(APITestCase):
    """
    GET /api/v1/products/ -- exercises the "Fill by price" widget's
    From/To behaviour end-to-end against the real product list
    endpoint (api/v1/filters.py::ProductFilter), the same endpoint
    static/js/pages/shop-list.js calls.
    """

    def setUp(self):
        self.vendor = make_vendor("priya", "Priya's Store")
        self.category = Category.objects.create(name="Groceries")
        self.list_url = reverse("api:api_v1:product-list")
        self.cheap = make_product(
            self.vendor, self.category, sku="CHEAP", price="10.00"
        )
        self.mid = make_product(
            self.vendor, self.category, sku="MID", price="50.00"
        )
        self.pricey = make_product(
            self.vendor, self.category, sku="PRICEY", price="90.00"
        )

    def test_changing_from_only_filters_by_min_price(self):
        response = self.client.get(self.list_url, {"min_price": "40"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {p["slug"] for p in response.data["results"]}
        self.assertEqual(slugs, {self.mid.slug, self.pricey.slug})

    def test_changing_to_only_filters_by_max_price(self):
        response = self.client.get(self.list_url, {"max_price": "60"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {p["slug"] for p in response.data["results"]}
        self.assertEqual(slugs, {self.cheap.slug, self.mid.slug})

    def test_from_and_to_together_filter_the_correct_range(self):
        response = self.client.get(
            self.list_url, {"min_price": "20", "max_price": "60"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], self.mid.slug)

    def test_unpublished_products_never_appear_regardless_of_price_range(
        self,
    ):
        hidden = make_product(
            self.vendor,
            self.category,
            sku="HIDDEN",
            price="50.00",
            published=False,
        )

        response = self.client.get(
            self.list_url, {"min_price": "0", "max_price": "1000"}
        )

        slugs = {p["slug"] for p in response.data["results"]}
        self.assertNotIn(hidden.slug, slugs)
        self.assertEqual(response.data["count"], 3)

    def test_price_range_persists_alongside_sort_and_show(self):
        # Show=2 (page_size), Sort=price ascending, plus the active
        # price range -- all three must combine correctly, exactly
        # like shop-list.js sends them as one request.
        response = self.client.get(
            self.list_url,
            {
                "min_price": "20",
                "max_price": "100",
                "ordering": "price",
                "page_size": 2,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(
            [p["slug"] for p in response.data["results"]],
            [self.mid.slug, self.pricey.slug],
        )

    def test_price_range_combines_with_pagination(self):
        response = self.client.get(
            self.list_url,
            {
                "min_price": "0",
                "max_price": "1000",
                "page_size": 1,
                "page": 2,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)
        self.assertEqual(len(response.data["results"]), 1)
