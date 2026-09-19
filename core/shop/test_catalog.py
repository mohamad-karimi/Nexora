from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import (
    Category,
    Product,
    ProductImage,
    ProductSpecification,
    Tag,
)

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=True,
    )


class ProductCatalogAPITests(APITestCase):
    def setUp(self):
        self.list_url = reverse("api:api_v1:product-list")
        self.vendor_a = make_user("cata", role=User.Role.VENDOR)
        self.vendor_b = make_user("catb", role=User.Role.VENDOR)
        self.vendor_a.vendor_profile.is_approved = True
        self.vendor_a.vendor_profile.store_name = "Store A"
        self.vendor_a.vendor_profile.save()
        self.vendor_b.vendor_profile.is_approved = True
        self.vendor_b.vendor_profile.store_name = "Store B"
        self.vendor_b.vendor_profile.save()
        self.category = Category.objects.create(name="Snacks")
        self.organic = Tag.objects.create(name="Organic")
        self.in_stock = Product.objects.create(
            vendor=self.vendor_a.vendor_profile,
            category=self.category,
            name="Granola",
            sku="CAT-1",
            price="12.00",
            stock=5,
            published=True,
        )
        self.in_stock.tags.add(self.organic)
        self.out_of_stock = Product.objects.create(
            vendor=self.vendor_b.vendor_profile,
            category=self.category,
            name="Chips",
            sku="CAT-2",
            price="3.00",
            stock=0,
            published=True,
        )

    def test_tag_filter_returns_only_tagged_products(self):
        response = self.client.get(self.list_url, {"tag": self.organic.slug})
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Granola"])

    def test_vendor_filter_returns_only_that_vendor(self):
        response = self.client.get(
            self.list_url, {"vendor": self.vendor_b.vendor_profile.slug}
        )
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Chips"])

    def test_in_stock_filter(self):
        available = self.client.get(self.list_url, {"in_stock": "true"})
        unavailable = self.client.get(self.list_url, {"in_stock": "false"})
        self.assertEqual(
            [item["name"] for item in available.data["results"]], ["Granola"]
        )
        self.assertEqual(
            [item["name"] for item in unavailable.data["results"]], ["Chips"]
        )

    def test_ordering_by_price_and_pagination(self):
        response = self.client.get(
            self.list_url, {"ordering": "price", "page_size": 1}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["name"], "Chips")
        self.assertIsNotNone(response.data["next"])

        page2 = self.client.get(
            self.list_url, {"ordering": "price", "page_size": 1, "page": 2}
        )
        self.assertEqual(page2.data["results"][0]["name"], "Granola")

    def test_detail_includes_images_and_specifications(self):
        ProductImage.objects.create(
            product=self.in_stock,
            image="products/gallery/granola.png",
            alt_text="side",
        )
        ProductSpecification.objects.create(
            product=self.in_stock, name="Weight", value="500g"
        )

        response = self.client.get(
            reverse(
                "api:api_v1:product-detail",
                kwargs={"slug": self.in_stock.slug},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], "CAT-1")
        self.assertEqual(len(response.data["images"]), 1)
        self.assertEqual(response.data["specifications"][0]["value"], "500g")
        self.assertTrue(response.data["in_stock"])

    def test_unapproved_vendor_products_still_follow_published_flag(self):
        """Public listing is gated on Product.published, not
        Vendor.is_approved.
        """
        self.vendor_a.vendor_profile.is_approved = False
        self.vendor_a.vendor_profile.save()

        response = self.client.get(self.list_url)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Granola", names)
