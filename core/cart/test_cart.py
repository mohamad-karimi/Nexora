from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from shop.models import Category, Product

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER, is_verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=is_verified,
    )


def make_product(vendor, category, **kwargs):
    defaults = {
        "name": "Cart Product",
        "sku": "CART-0001",
        "price": "10.00",
        "stock": 10,
        "published": True,
    }
    defaults.update(kwargs)
    return Product.objects.create(vendor=vendor, category=category, **defaults)


class CartAPITestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Groceries")
        self.user = make_user("cartuser")
        self.other = make_user("othercart")
        self.vendor_user = make_user("cartvendor", role=User.Role.VENDOR)
        self.vendor = self.vendor_user.vendor_profile
        self.product = make_product(self.vendor, self.category)
        self.cart_url = reverse("api:api_v1:cart")
        self.items_url = reverse("api:api_v1:cart-item-list")


class CartAuthTests(CartAPITestBase):
    def test_anonymous_cannot_view_or_mutate_cart(self):
        get_response = self.client.get(self.cart_url)
        post_response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 1}
        )
        self.assertIn(
            get_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertIn(
            post_response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(Cart.objects.count(), 0)

    def test_unverified_user_cannot_access_cart(self):
        unverified = make_user("unverifiedcart", is_verified=False)
        self.client.force_authenticate(user=unverified)

        response = self.client.get(self.cart_url)

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class CartCRUDTests(CartAPITestBase):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.user)

    def test_get_creates_empty_cart_with_zero_totals(self):
        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["total_items"], 0)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("0"))
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_add_item_returns_updated_cart(self):
        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 2}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["items"]), 1)
        item = response.data["items"][0]
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(Decimal(item["unit_price"]), Decimal("10.00"))
        self.assertEqual(Decimal(item["subtotal"]), Decimal("20.00"))
        self.assertEqual(response.data["total_items"], 2)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("20.00"))

    def test_adding_the_same_product_increments_quantity_instead_of_duplicating(self):
        self.client.post(self.items_url, {"product_id": self.product.id, "quantity": 2})
        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 3}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["quantity"], 5)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)

    def test_duplicate_add_is_capped_at_available_stock(self):
        self.product.stock = 4
        self.product.save(update_fields=["stock"])
        self.client.post(self.items_url, {"product_id": self.product.id, "quantity": 3})

        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 3}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["items"][0]["quantity"], 4)

    def test_quantity_above_stock_on_create_is_rejected(self):
        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 99}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_quantity_below_one_is_rejected(self):
        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 0}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_quantity(self):
        add = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 1}
        )
        item_id = add.data["items"][0]["id"]

        response = self.client.patch(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": item_id}),
            {"quantity": 4},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"][0]["quantity"], 4)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("40.00"))

    def test_update_quantity_above_stock_is_rejected(self):
        add = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 1}
        )
        item_id = add.data["items"][0]["id"]

        response = self.client.patch(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": item_id}),
            {"quantity": 99},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        item = CartItem.objects.get(pk=item_id)
        self.assertEqual(item.quantity, 1)

    def test_remove_item(self):
        add = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 2}
        )
        item_id = add.data["items"][0]["id"]

        response = self.client.delete(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": item_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(response.data["total_items"], 0)
        self.assertFalse(CartItem.objects.filter(pk=item_id).exists())

    def test_clear_cart_removes_every_item(self):
        extra = make_product(self.vendor, self.category, sku="CART-0002", name="Extra")
        self.client.post(self.items_url, {"product_id": self.product.id, "quantity": 1})
        self.client.post(self.items_url, {"product_id": extra.id, "quantity": 2})

        response = self.client.delete(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_subtotal_uses_sale_price(self):
        self.product.discount_percent = 50
        self.product.save(update_fields=["discount_percent"])

        response = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 2}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["items"][0]["unit_price"]), Decimal("5.00"))
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("10.00"))

    def test_combined_operations_keep_totals_consistent(self):
        extra = make_product(
            self.vendor, self.category, sku="CART-0003", name="Milk", price="4.00"
        )
        self.client.post(self.items_url, {"product_id": self.product.id, "quantity": 2})
        add_extra = self.client.post(
            self.items_url, {"product_id": extra.id, "quantity": 3}
        )
        extra_id = [
            item["id"]
            for item in add_extra.data["items"]
            if item["product"]["slug"] == extra.slug
        ][0]
        self.client.delete(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": extra_id})
        )

        response = self.client.get(self.cart_url)

        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["total_items"], 2)
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("20.00"))


class CartIsolationTests(CartAPITestBase):
    def test_user_cannot_update_or_delete_another_users_cart_item(self):
        self.client.force_authenticate(user=self.other)
        other_add = self.client.post(
            self.items_url, {"product_id": self.product.id, "quantity": 1}
        )
        other_item_id = other_add.data["items"][0]["id"]

        self.client.force_authenticate(user=self.user)
        patch_response = self.client.patch(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": other_item_id}),
            {"quantity": 9},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("api:api_v1:cart-item-detail", kwargs={"pk": other_item_id})
        )

        self.assertEqual(patch_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(delete_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(CartItem.objects.get(pk=other_item_id).quantity, 1)

    def test_get_cart_never_includes_another_users_items(self):
        self.client.force_authenticate(user=self.other)
        self.client.post(self.items_url, {"product_id": self.product.id, "quantity": 3})

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.cart_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["items"], [])


class CartPageAccessTests(CartAPITestBase):
    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(reverse("cart:cart"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_verified_user_can_open_cart_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("cart:cart"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "cart/shop-cart.html")

    def test_unverified_user_is_redirected_away_from_cart_page(self):
        unverified = make_user("pageunverified", is_verified=False)
        self.client.force_login(unverified)
        response = self.client.get(reverse("cart:cart"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:email_verification_pending"), response["Location"]
        )
