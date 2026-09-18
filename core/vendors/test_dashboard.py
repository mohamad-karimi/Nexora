from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from orders.models import Address, Order, OrderItem
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


class PublicVendorVisibilityTests(APITestCase):
    def setUp(self):
        self.approved = make_user("approvedvendor", role=User.Role.VENDOR)
        self.approved.vendor_profile.store_name = "Approved Store"
        self.approved.vendor_profile.is_approved = True
        self.approved.vendor_profile.save()
        self.pending = make_user("pendingvendor", role=User.Role.VENDOR)
        self.pending.vendor_profile.store_name = "Pending Store"
        self.pending.vendor_profile.is_approved = False
        self.pending.vendor_profile.save()
        self.list_url = reverse("api:api_v1:vendor-list")

    def test_unapproved_vendor_is_hidden_from_public_list_and_detail(self):
        response = self.client.get(self.list_url)
        names = [item["store_name"] for item in response.data["results"]]
        self.assertIn("Approved Store", names)
        self.assertNotIn("Pending Store", names)

        detail = self.client.get(
            reverse(
                "api:api_v1:vendor-detail",
                kwargs={"slug": self.pending.vendor_profile.slug},
            )
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_product_count_only_includes_published_products(self):
        category = Category.objects.create(name="Groceries")
        Product.objects.create(
            vendor=self.approved.vendor_profile,
            category=category,
            name="Live",
            sku="VEN-LIVE",
            price="1.00",
            published=True,
        )
        Product.objects.create(
            vendor=self.approved.vendor_profile,
            category=category,
            name="Hidden",
            sku="VEN-HIDE",
            price="1.00",
            published=False,
        )

        response = self.client.get(
            reverse(
                "api:api_v1:vendor-detail",
                kwargs={"slug": self.approved.vendor_profile.slug},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["product_count"], 1)


class VendorDashboardOrdersAndBestSellersTests(APITestCase):
    def setUp(self):
        self.vendor_a = make_user("dashorda", role=User.Role.VENDOR)
        self.vendor_b = make_user("dashordb", role=User.Role.VENDOR)
        self.customer = make_user("dashordcust")
        self.category = Category.objects.create(name="Groceries")
        self.product_a = Product.objects.create(
            vendor=self.vendor_a.vendor_profile,
            category=self.category,
            name="A Milk",
            sku="DA-1",
            price="10.00",
            stock=20,
            published=True,
        )
        self.product_b = Product.objects.create(
            vendor=self.vendor_b.vendor_profile,
            category=self.category,
            name="B Bread",
            sku="DB-1",
            price="4.00",
            stock=20,
            published=True,
        )
        address = Address.objects.create(
            user=self.customer,
            full_name="Customer",
            phone="1",
            country="Iran",
            city="Tehran",
            postal_code="1",
            address_line1="St",
        )
        cart, _ = Cart.objects.get_or_create(user=self.customer)
        CartItem.objects.create(cart=cart, product=self.product_a, quantity=3)
        CartItem.objects.create(cart=cart, product=self.product_b, quantity=1)
        self.client.force_authenticate(user=self.customer)
        checkout = self.client.post(
            reverse("api:api_v1:order-list"),
            {"shipping_address_id": address.id},
        )
        self.assertEqual(checkout.status_code, status.HTTP_201_CREATED)
        self.order = Order.objects.get()

    def test_vendor_only_sees_own_order_line_items(self):
        self.client.force_authenticate(user=self.vendor_a)
        response = self.client.get(
            reverse("api:api_v1:vendor-dashboard-orders")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["product_name"] for item in response.data["results"]]
        self.assertEqual(names, ["A Milk"])
        self.assertEqual(response.data["results"][0]["quantity"], 3)

        self.client.force_authenticate(user=self.vendor_b)
        other = self.client.get(reverse("api:api_v1:vendor-dashboard-orders"))
        names = [item["product_name"] for item in other.data["results"]]
        self.assertEqual(names, ["B Bread"])

    def test_customer_cannot_access_vendor_orders_or_best_sellers(self):
        self.client.force_authenticate(user=self.customer)
        orders = self.client.get(
            reverse("api:api_v1:vendor-dashboard-orders")
        )
        best = self.client.get(
            reverse("api:api_v1:vendor-dashboard-best-sellers")
        )
        self.assertEqual(orders.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(best.status_code, status.HTTP_403_FORBIDDEN)

    def test_best_sellers_are_scoped_to_the_vendor_and_ignore_cancelled(self):
        cancelled = Order.objects.create(
            user=self.customer,
            shipping_address=self.order.shipping_address,
            billing_address=self.order.shipping_address,
            shipping_cost=0,
            discount_amount=0,
            total_amount=40,
            status=Order.Status.CANCELLED,
        )
        OrderItem.objects.create(
            order=cancelled,
            product=self.product_a,
            quantity=99,
            unit_price=self.product_a.price,
        )

        self.client.force_authenticate(user=self.vendor_a)
        response = self.client.get(
            reverse("api:api_v1:vendor-dashboard-best-sellers")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], self.product_a.slug)

    def test_unverified_vendor_is_blocked_from_dashboard_api(self):
        unverified = make_user(
            "unverifieddash", role=User.Role.VENDOR, is_verified=False
        )
        self.client.force_authenticate(user=unverified)
        response = self.client.get(
            reverse("api:api_v1:vendor-dashboard-products")
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
