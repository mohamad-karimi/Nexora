from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product, Wishlist

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER, is_verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=is_verified,
    )


class WishlistAPITests(APITestCase):
    def setUp(self):
        self.user = make_user("wishuser")
        self.other = make_user("wishother")
        self.vendor = make_user("wishvendor", role=User.Role.VENDOR)
        self.category = Category.objects.create(name="Groceries")
        self.product = Product.objects.create(
            vendor=self.vendor.vendor_profile,
            category=self.category,
            name="Wishlist Apple",
            sku="WISH-1",
            price="2.00",
            published=True,
        )
        self.list_url = reverse("api:api_v1:wishlist-list")

    def test_anonymous_cannot_access_wishlist(self):
        response = self.client.get(self.list_url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unverified_user_cannot_access_wishlist(self):
        unverified = make_user("wishunverified", is_verified=False)
        self.client.force_authenticate(user=unverified)
        response = self.client.get(self.list_url)
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_add_list_and_remove_own_item(self):
        self.client.force_authenticate(user=self.user)
        created = self.client.post(self.list_url, {"product_id": self.product.id})
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data["product"]["slug"], self.product.slug)

        listed = self.client.get(self.list_url)
        self.assertEqual(len(listed.data["results"]), 1)

        deleted = self.client.delete(
            reverse(
                "api:api_v1:wishlist-detail",
                kwargs={"pk": created.data["id"]},
            )
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_adding_the_same_product_twice_is_idempotent(self):
        self.client.force_authenticate(user=self.user)
        first = self.client.post(self.list_url, {"product_id": self.product.id})
        second = self.client.post(self.list_url, {"product_id": self.product.id})
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Wishlist.objects.filter(user=self.user).count(), 1)

    def test_user_cannot_delete_another_users_wishlist_item(self):
        item = Wishlist.objects.create(user=self.other, product=self.product)
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(
            reverse("api:api_v1:wishlist-detail", kwargs={"pk": item.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Wishlist.objects.filter(pk=item.pk).exists())

    def test_list_is_isolated_per_user(self):
        Wishlist.objects.create(user=self.other, product=self.product)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.list_url)
        self.assertEqual(response.data["results"], [])

    def test_wishlist_page_requires_verified_user(self):
        page = reverse("shop:wishlist")
        anon = self.client.get(page)
        self.assertEqual(anon.status_code, 302)
        self.assertIn(reverse("accounts:login"), anon["Location"])

        self.client.force_login(self.user)
        authed = self.client.get(page)
        self.assertEqual(authed.status_code, 200)
