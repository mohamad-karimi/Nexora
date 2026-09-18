from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from orders.models import Address, Coupon, Order, OrderItem, Payment
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


def make_address(user, **kwargs):
    defaults = {
        "full_name": "Ada Lovelace",
        "phone": "09120000000",
        "country": "Iran",
        "city": "Tehran",
        "postal_code": "12345",
        "address_line1": "1 Example St",
    }
    defaults.update(kwargs)
    return Address.objects.create(user=user, **defaults)


class CheckoutAPITestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Groceries")
        self.user = make_user("buyer")
        self.other = make_user("otherbuyer")
        self.vendor_user = make_user("ordervendor", role=User.Role.VENDOR)
        self.vendor = self.vendor_user.vendor_profile
        self.product = Product.objects.create(
            vendor=self.vendor,
            category=self.category,
            name="Checkout Milk",
            sku="CHK-MILK",
            price="10.00",
            stock=20,
            published=True,
        )
        self.address = make_address(self.user)
        self.orders_url = reverse("api:api_v1:order-list")
        self.items_url = reverse("api:api_v1:cart-item-list")

    def _login(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def _add_to_cart(self, product=None, quantity=1, user=None):
        owner = user or self.user
        cart, _ = Cart.objects.get_or_create(user=owner)
        CartItem.objects.update_or_create(
            cart=cart,
            product=product or self.product,
            defaults={"quantity": quantity},
        )
        return cart


class CheckoutAuthAndValidationTests(CheckoutAPITestBase):
    def test_anonymous_cannot_checkout(self):
        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_unverified_user_cannot_checkout(self):
        unverified = make_user("unverifiedbuyer", is_verified=False)
        address = make_address(unverified)
        self._add_to_cart(user=unverified)
        self.client.force_authenticate(user=unverified)

        response = self.client.post(
            self.orders_url, {"shipping_address_id": address.id}
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_cart_checkout_is_rejected(self):
        self._login()
        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_missing_shipping_address_is_rejected(self):
        self._login()
        self._add_to_cart()
        response = self.client.post(self.orders_url, {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_users_address_cannot_be_used(self):
        self._login()
        self._add_to_cart()
        foreign = make_address(self.other, full_name="Not Mine")

        response = self.client.post(
            self.orders_url, {"shipping_address_id": foreign.id}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_stock_shortage_at_checkout_is_rejected(self):
        self._login()
        self._add_to_cart(quantity=5)
        self.product.stock = 1
        self.product.save(update_fields=["stock"])

        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)


class CheckoutCreateTests(CheckoutAPITestBase):
    def setUp(self):
        super().setUp()
        self._login()
        self._add_to_cart(quantity=2)

    def test_checkout_creates_order_items_payment_and_empties_cart(self):
        original_name = self.product.name
        original_price = Decimal(self.product.final_price)

        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "payment_method": Payment.Method.CARD,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.shipping_address_id, self.address.id)
        self.assertEqual(order.billing_address_id, self.address.id)
        self.assertEqual(order.items.count(), 1)

        item = order.items.get()
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.unit_price, original_price)
        self.assertEqual(item.product_name, original_name)
        self.assertEqual(item.vendor_id, self.vendor.id)
        self.assertEqual(item.total_price, original_price * 2)

        payment = order.payments.get()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.payment_method, Payment.Method.CARD)
        self.assertEqual(payment.amount, order.total_amount)

        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 18)

        self.assertEqual(response.data["order_number"], order.order_number)
        self.assertEqual(len(response.data["items"]), 1)

    def test_price_is_snapshotted_even_if_product_is_repriced_later(self):
        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        snapshotted = Decimal(response.data["items"][0]["unit_price"])

        self.product.price = Decimal("99.00")
        self.product.save(update_fields=["price"])
        item = OrderItem.objects.get(order__user=self.user)
        self.assertEqual(item.unit_price, snapshotted)
        self.assertEqual(item.unit_price, Decimal("10.00"))

    def test_billing_address_can_differ_from_shipping(self):
        billing = make_address(self.user, full_name="Billing Name", city="Isfahan")

        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "billing_address_id": billing.id,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        order = Order.objects.get()
        self.assertEqual(order.shipping_address_id, self.address.id)
        self.assertEqual(order.billing_address_id, billing.id)

    def test_flat_shipping_applies_below_free_threshold(self):
        # 2 * 10.00 = 20.00 < 50.00 → shipping 5.00
        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["shipping_cost"]), Decimal("5.00"))
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("20.00"))
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("25.00"))

    def test_free_shipping_applies_at_threshold(self):
        self.product.price = Decimal("25.00")
        self.product.save(update_fields=["price"])
        CartItem.objects.filter(cart__user=self.user).update(quantity=2)

        response = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Decimal(response.data["shipping_cost"]), Decimal("0.00"))
        self.assertEqual(Decimal(response.data["subtotal"]), Decimal("50.00"))
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("50.00"))


class CheckoutCouponTests(CheckoutAPITestBase):
    def setUp(self):
        super().setUp()
        self._login()
        self._add_to_cart(quantity=2)
        now = timezone.now()
        self.coupon = Coupon.objects.create(
            code="SAVE10",
            discount_percent=10,
            valid_from=now - timedelta(days=1),
            valid_to=now + timedelta(days=7),
            is_active=True,
        )
        self.validate_url = reverse("api:api_v1:coupon-validate")

    def test_valid_coupon_is_applied_and_usage_incremented(self):
        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "coupon_code": "save10",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # subtotal 20, shipping 5, 10% of 20 = 2 → total 23
        self.assertEqual(Decimal(response.data["discount_amount"]), Decimal("2.00"))
        self.assertEqual(Decimal(response.data["total_amount"]), Decimal("23.00"))
        self.assertEqual(response.data["coupon"]["code"], "SAVE10")
        self.coupon.refresh_from_db()
        self.assertEqual(self.coupon.used_count, 1)

    def test_invalid_coupon_code_is_rejected(self):
        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "coupon_code": "NOPE",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_inactive_coupon_is_rejected(self):
        self.coupon.is_active = False
        self.coupon.save(update_fields=["is_active"])

        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "coupon_code": "SAVE10",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_coupon_is_rejected(self):
        self.coupon.valid_to = timezone.now() - timedelta(days=1)
        self.coupon.save(update_fields=["valid_to"])

        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "coupon_code": "SAVE10",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_usage_limit_exhausted_coupon_is_rejected(self):
        self.coupon.usage_limit = 1
        self.coupon.used_count = 1
        self.coupon.save(update_fields=["usage_limit", "used_count"])

        response = self.client.post(
            self.orders_url,
            {
                "shipping_address_id": self.address.id,
                "coupon_code": "SAVE10",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_endpoint_returns_valid_coupon(self):
        response = self.client.post(self.validate_url, {"code": "save10"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_valid"])
        self.assertEqual(response.data["code"], "SAVE10")

    def test_validate_endpoint_unknown_code_is_not_found(self):
        response = self.client.post(self.validate_url, {"code": "MISSING"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data["is_valid"])

    def test_anonymous_cannot_validate_coupon(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.validate_url, {"code": "SAVE10"})
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class OrderOwnershipTests(CheckoutAPITestBase):
    def setUp(self):
        super().setUp()
        self._login()
        self._add_to_cart(quantity=1)
        created = self.client.post(
            self.orders_url, {"shipping_address_id": self.address.id}
        )
        self.order_number = created.data["order_number"]

    def test_user_can_list_and_retrieve_own_order(self):
        listed = self.client.get(self.orders_url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        numbers = [item["order_number"] for item in listed.data["results"]]
        self.assertEqual(numbers, [self.order_number])

        detail = self.client.get(
            reverse(
                "api:api_v1:order-detail",
                kwargs={"order_number": self.order_number},
            )
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data["status"], Order.Status.PENDING)

    def test_user_cannot_retrieve_another_users_order(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.get(
            reverse(
                "api:api_v1:order-detail",
                kwargs={"order_number": self.order_number},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_see_another_users_order_in_list(self):
        self.client.force_authenticate(user=self.other)
        response = self.client.get(self.orders_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])

    def test_orders_are_read_only_after_create(self):
        url = reverse(
            "api:api_v1:order-detail", kwargs={"order_number": self.order_number}
        )
        patch_response = self.client.patch(
            url, {"status": Order.Status.DELIVERED}, format="json"
        )
        delete_response = self.client.delete(url)
        self.assertEqual(patch_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(delete_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(Order.objects.get().status, Order.Status.PENDING)

    def test_numeric_id_is_not_a_valid_lookup(self):
        order = Order.objects.get(order_number=self.order_number)
        response = self.client.get(f"/api/v1/orders/{order.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CheckoutPageAccessTests(CheckoutAPITestBase):
    def test_anonymous_visitor_is_redirected_from_checkout(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_verified_user_can_open_checkout_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/shop-checkout.html")

    def test_invoice_page_requires_verified_user(self):
        response = self.client.get(
            reverse("orders:invoice", kwargs={"order_number": "ABC123"})
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
