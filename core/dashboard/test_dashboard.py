from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

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


class VendorDashboardPageAccessTests(TestCase):
    def setUp(self):
        self.url = reverse("dashboard:dashboard")
        self.vendor = make_user("dashvendor", role=User.Role.VENDOR)
        self.customer = make_user("dashcustomer")

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_verified_customer_gets_403(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_unverified_vendor_is_redirected_to_verification(self):
        unverified = make_user(
            "unverifiedvendor", role=User.Role.VENDOR, is_verified=False
        )
        self.client.force_login(unverified)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:email_verification_pending"),
            response["Location"],
        )

    def test_verified_vendor_can_open_dashboard(self):
        self.client.force_login(self.vendor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/vendor-dashboard.html")


class VendorProductEditPageAccessTests(TestCase):
    def setUp(self):
        self.vendor = make_user("editvendor", role=User.Role.VENDOR)
        self.customer = make_user("editcustomer")
        category = Category.objects.create(name="Groceries")
        self.product = Product.objects.create(
            vendor=self.vendor.vendor_profile,
            category=category,
            name="Edit Me",
            sku="EDIT-1",
            price="5.00",
            published=False,
        )
        self.url = reverse(
            "dashboard:product-edit", kwargs={"slug": self.product.slug}
        )

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_customer_gets_403(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_vendor_can_open_edit_page_shell(self):
        self.client.force_login(self.vendor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "dashboard/vendor-product-edit.html"
        )
        self.assertEqual(response.context["product_slug"], self.product.slug)


class CustomerAccountPageAccessTests(TestCase):
    """Customer 'dashboard' is /account/, gated by VerifiedRequiredMixin."""

    def setUp(self):
        self.url = reverse("accounts:account")

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_verified_customer_can_open_account_page(self):
        self.client.force_login(make_user("acctcustomer"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/page-account.html")
        self.assertFalse(response.context["is_vendor"])

    def test_verified_vendor_can_open_account_page_with_vendor_flag(self):
        self.client.force_login(
            make_user("acctvendor", role=User.Role.VENDOR)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_vendor"])

    def test_unverified_user_is_redirected_to_verification(self):
        self.client.force_login(
            make_user("acctunverified", is_verified=False)
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            reverse("accounts:email_verification_pending"),
            response["Location"],
        )


class VendorDashboardDataOwnershipAPITests(APITestCase):
    def setUp(self):
        self.vendor_a = make_user("ownera", role=User.Role.VENDOR)
        self.vendor_b = make_user("ownerb", role=User.Role.VENDOR)
        self.category = Category.objects.create(name="Groceries")
        self.product_a = Product.objects.create(
            vendor=self.vendor_a.vendor_profile,
            category=self.category,
            name="A Product",
            sku="OWN-A",
            price="9.00",
            published=False,
        )
        self.product_b = Product.objects.create(
            vendor=self.vendor_b.vendor_profile,
            category=self.category,
            name="B Product",
            sku="OWN-B",
            price="9.00",
            published=False,
        )
        self.detail_url = reverse(
            "api:api_v1:vendor-dashboard-product-detail",
            kwargs={"slug": self.product_a.slug},
        )

    def test_owner_can_retrieve_and_edit_unpublished_product(self):
        self.client.force_authenticate(user=self.vendor_a)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["sku"], "OWN-A")

        patched = self.client.patch(
            self.detail_url,
            {"name": "Renamed A", "price": "11.00"},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.name, "Renamed A")
        self.assertEqual(str(self.product_a.price), "11.00")

    def test_other_vendor_gets_404_for_product_detail_and_edit(self):
        self.client.force_authenticate(user=self.vendor_b)
        self.assertEqual(
            self.client.get(self.detail_url).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        patched = self.client.patch(
            self.detail_url, {"name": "Stolen"}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_404_NOT_FOUND)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.name, "A Product")

    def test_vendor_cannot_publish_or_reassign_product_via_edit(self):
        self.client.force_authenticate(user=self.vendor_a)
        response = self.client.patch(
            self.detail_url,
            {
                "published": True,
                "vendor": self.vendor_b.vendor_profile.id,
                "name": "Still Mine",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product_a.refresh_from_db()
        self.assertFalse(self.product_a.published)
        self.assertEqual(
            self.product_a.vendor_id, self.vendor_a.vendor_profile.id
        )
        self.assertEqual(self.product_a.name, "Still Mine")

    def test_customer_cannot_access_vendor_dashboard_product_detail(self):
        customer = make_user("dashapicustomer")
        self.client.force_authenticate(user=customer)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
