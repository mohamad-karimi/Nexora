"""
Tests for the site Header (templates/base.html).

These cover the items from the Header fix request:
  1. Browse All Categories -> real category data, real route, no dead link
  2. Deals -> real route, no dead link; the widget itself asks the API
     to order by biggest discount first (?ordering=-discount_percent),
     never sorts client-side, and only ever sees published products
  3. Vendor Guide -> visible only to authenticated Vendor users
  4. Vendor menu -> a plain "Vendors" link for anonymous/Customer, a
     dropdown with exactly "Vendor List" + "Vendor Guide" for Vendor,
     decided from the authenticated user's real role
  5. Mega Menu -> no demo/dead links remain; both the desktop columns
     and the mobile accordion are populated client-side from real
     category (and, where they exist, subcategory) data
  6. Header Top Right (About Us / My Account / Wishlist / Order Tracking)
     -> real routes; Order Tracking hidden for Vendor users
  7/8. Category selector + Search -> the real /api/v1/categories/ and
     /api/v1/products/ endpoints the header's JS calls to load categories
     and to run/filter a search
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from shop.models import Category, Product

User = get_user_model()


def make_user(username, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=True,
    )


class HeaderDeadLinksTests(TestCase):
    """The header must no longer contain the template's old demo/dead
    links, and must use real Django routes instead."""

    def setUp(self):
        self.response = self.client.get(reverse("website:home"))

    def test_page_loads(self):
        self.assertEqual(self.response.status_code, 200)

    def test_no_leftover_demo_or_vercel_links_in_header(self):
        content = self.response.content.decode()
        self.assertNotIn("shop-grid-right.html", content)
        self.assertNotIn("nest-frontend-v6.vercel.app", content)
        # The Quick View modal is not part of the Header and is out of
        # scope for this fix, so it may still reference the demo page;
        # everything else on the page -- including the mobile header
        # menu, which sits after </header> but is still part of the
        # Header block -- must not.
        header_block, marker, _ = content.partition("<!--End header-->")
        self.assertIn(marker, content)  # sanity: marker actually exists
        self.assertNotIn("shop-product-right.html", header_block)

    def test_about_us_points_to_the_real_about_route(self):
        self.assertContains(self.response, reverse("website:about"))

    def test_deals_points_to_the_real_shop_filter_route(self):
        content = self.response.content.decode()
        deals_href = f'href="{reverse("shop:filter")}">Deals</a>'
        self.assertIn(deals_href, content)

    def test_my_account_and_wishlist_point_to_real_routes(self):
        self.assertContains(self.response, reverse("accounts:account"))
        self.assertContains(self.response, reverse("shop:wishlist"))

    def test_mega_menu_has_no_hardcoded_demo_categories(self):
        # The Mega Menu used to ship 3 hardcoded category columns and a
        # mobile fashion/tech accordion that didn't correspond to any
        # real Category in the database. It must now be populated
        # client-side from /api/v1/categories/ (see
        # HeaderMegaMenuTests below), so none of that old demo content
        # -- including its sub-item "search=" links -- may remain in
        # the rendered page.
        content = self.response.content.decode()
        for demo_text in (
            "fruit-vegetables",
            "breakfast-dairy",
            "meat-seafood",
            "Women's Fashion",
            "Men's Fashion",
            "Meat & Poultry",
            "Herbs & Seasonings",
            "Milk & Flavoured Milk",
            "Breakfast Sausage",
            "Gaming Laptops",
            "Casual Faux Leather",
        ):
            self.assertNotIn(demo_text, content)
        self.assertNotIn(f'{reverse("shop:filter")}?search=', content)


class HeaderMegaMenuTests(TestCase):
    """The Mega Menu (desktop columns + mobile accordion) is populated
    client-side from real category data. The template only needs to
    ship the empty slots the header JS fills in; the real-category
    contract those slots rely on is covered by
    HeaderCategoryDropdownAPITests below."""

    def setUp(self):
        self.response = self.client.get(reverse("website:home"))

    def test_desktop_mega_menu_ships_category_slots_for_js_to_fill(self):
        content = self.response.content.decode()
        self.assertEqual(content.count("js-mega-menu-slot"), 3)

    def test_mobile_mega_menu_ships_category_slots_for_js_to_fill(self):
        content = self.response.content.decode()
        self.assertEqual(content.count("js-mega-menu-mobile-slot"), 3)
        self.assertIn("js-mega-menu-mobile-link", content)
        self.assertIn("js-mega-menu-mobile-children", content)

    def test_mega_menu_slots_are_hidden_until_js_populates_them(self):
        # No flash of empty/fake content while /api/v1/categories/ is
        # still loading.
        content = self.response.content.decode()
        self.assertIn(
            'class="sub-mega-menu sub-mega-menu-width-22 js-mega-menu-slot" style="display:none"',
            content,
        )


class HeaderVendorMenuTests(TestCase):
    """The 'Vendors' header item has two mutually exclusive shapes:
    a plain link (anonymous/Customer) or a dropdown with exactly
    'Vendor List' + 'Vendor Guide' (authenticated Vendor). Role is
    read from the authenticated user, never from a frontend flag."""

    def setUp(self):
        self.home_url = reverse("website:home")
        self.vendors_list_url = reverse("vendors:list")
        self.vendor_guide_url = reverse("vendors:guide")
        self.plain_vendors_link = f'<a href="{self.vendors_list_url}">Vendors</a>'

    def test_anonymous_sees_a_plain_vendors_link_not_a_dropdown(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()
        self.assertIn(self.plain_vendors_link, content)
        self.assertNotIn(">Vendor List<", content)
        self.assertNotIn("Vendors List", content)
        self.assertNotIn(self.vendor_guide_url, content)

    def test_customer_sees_a_plain_vendors_link_not_a_dropdown(self):
        self.client.force_login(make_user("cara"))
        response = self.client.get(self.home_url)
        content = response.content.decode()
        self.assertIn(self.plain_vendors_link, content)
        self.assertNotIn(">Vendor List<", content)
        self.assertNotIn("Vendors List", content)
        self.assertNotIn(self.vendor_guide_url, content)

    def test_vendor_sees_a_dropdown_with_only_vendor_list_and_vendor_guide(self):
        self.client.force_login(make_user("vince", role=User.Role.VENDOR))
        response = self.client.get(self.home_url)
        content = response.content.decode()
        self.assertIn(">Vendor List<", content)
        self.assertIn(self.vendor_guide_url, content)
        # The dropdown-less "Vendors" link is the Customer/anonymous
        # shape and must not also appear for a Vendor.
        self.assertNotIn(self.plain_vendors_link, content)
        # Only the two required options -- no extra items snuck in.
        self.assertNotIn("Vendor Dashboard", content)


class HeaderVendorGuideVisibilityTests(TestCase):
    """'Vendor Guide' must only ever be shown to an authenticated user
    whose role is Vendor -- never anonymous, never a plain Customer."""

    def setUp(self):
        self.guide_url = reverse("vendors:guide")

    def test_anonymous_user_does_not_see_vendor_guide_link(self):
        response = self.client.get(reverse("website:home"))
        self.assertNotContains(response, self.guide_url)

    def test_customer_does_not_see_vendor_guide_link(self):
        self.client.force_login(make_user("carol"))
        response = self.client.get(reverse("website:home"))
        self.assertNotContains(response, self.guide_url)

    def test_vendor_sees_vendor_guide_link(self):
        self.client.force_login(make_user("vera", role=User.Role.VENDOR))
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, self.guide_url)

    def test_backend_permission_is_still_enforced_independently_of_the_link(self):
        # The link being hidden in the template must never be the only
        # thing standing between a customer and the page itself.
        self.client.force_login(make_user("carol"))
        response = self.client.get(self.guide_url)
        self.assertEqual(response.status_code, 403)


class HeaderOrderTrackingVisibilityTests(TestCase):
    """'Order Tracking' shows for Customers (and anonymous visitors, who
    are sent to log in), but never for an authenticated Vendor."""

    def setUp(self):
        self.tracking_href = f'{reverse("accounts:account")}#track-orders'

    def test_anonymous_visitor_sees_order_tracking_link(self):
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, self.tracking_href)

    def test_customer_sees_order_tracking_link(self):
        self.client.force_login(make_user("carol"))
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, self.tracking_href)

    def test_vendor_does_not_see_order_tracking_link(self):
        self.client.force_login(make_user("vera", role=User.Role.VENDOR))
        response = self.client.get(reverse("website:home"))
        self.assertNotContains(response, self.tracking_href)
        self.assertNotContains(response, "Order Tracking")


class HeaderCategoryDropdownAPITests(APITestCase):
    """The 'Browse All Categories' dropdown and the category selector next
    to Search are populated client-side from this endpoint."""

    def test_categories_list_exposes_real_slugs_for_linking(self):
        Category.objects.create(name="Milks and Dairies")
        Category.objects.create(name="Fresh Fruit")

        response = self.client.get(reverse("api:api_v1:category-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data["results"] if "results" in response.data else response.data
        slugs = {item["slug"] for item in results}
        self.assertIn("milks-and-dairies", slugs)
        self.assertIn("fresh-fruit", slugs)

    def test_categories_are_ordered_by_name(self):
        Category.objects.create(name="Zesty Snacks")
        Category.objects.create(name="Apples")

        response = self.client.get(reverse("api:api_v1:category-list"))

        results = response.data["results"] if "results" in response.data else response.data
        names = [item["name"] for item in results]
        self.assertEqual(names, sorted(names))


class HeaderSearchAndCategoryFilterAPITests(APITestCase):
    """The header Search box (with or without the category selector)
    drives /api/v1/products/?search=...&category=..., exactly like the
    full Shop filter page."""

    def setUp(self):
        self.url = reverse("api:api_v1:product-list")
        self.dairy = Category.objects.create(name="Dairy")
        self.produce = Category.objects.create(name="Produce")
        # role=Vendor auto-creates the Vendor row via vendors.signals --
        # use that row rather than creating a second one (the `user`
        # field is OneToOne, so a second create() would fail).
        self.vendor = make_user("vendorA", role=User.Role.VENDOR).vendor_profile
        self.cheese = Product.objects.create(
            vendor=self.vendor,
            category=self.dairy,
            name="Cheddar Cheese",
            sku="CHEESE-1",
            price="4.99",
            published=True,
        )
        self.apple = Product.objects.create(
            vendor=self.vendor,
            category=self.produce,
            name="Fresh Apple",
            sku="APPLE-1",
            price="1.99",
            published=True,
        )

    def test_search_query_returns_matching_products_only(self):
        response = self.client.get(self.url, {"search": "cheese"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Cheddar Cheese", names)
        self.assertNotIn("Fresh Apple", names)

    def test_category_filter_returns_only_that_category(self):
        response = self.client.get(self.url, {"category": self.produce.slug})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Fresh Apple", names)
        self.assertNotIn("Cheddar Cheese", names)

    def test_search_combined_with_category_applies_both_filters(self):
        # A product that matches the search term but is in the *other*
        # category must be excluded when a category is also selected.
        response = self.client.get(
            self.url, {"search": "cheese", "category": self.produce.slug}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertNotIn("Cheddar Cheese", names)
        self.assertNotIn("Fresh Apple", names)

    def test_unknown_category_slug_returns_no_results_not_an_error(self):
        response = self.client.get(self.url, {"category": "does-not-exist"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)


class HeaderDealsOrderingAPITests(APITestCase):
    """The 'Deals' widget (home page + Shop filter sidebar) asks the
    API for products ordered by biggest discount first
    (?ordering=-discount_percent); the frontend only displays what
    comes back, it doesn't sort or filter by discount itself."""

    def setUp(self):
        self.url = reverse("api:api_v1:product-list")
        self.category = Category.objects.create(name="Pantry")
        self.vendor = make_user("vendorB", role=User.Role.VENDOR).vendor_profile

    def make_product(self, name, sku, discount_percent, published=True, price="10.00"):
        return Product.objects.create(
            vendor=self.vendor,
            category=self.category,
            name=name,
            sku=sku,
            price=price,
            discount_percent=discount_percent,
            published=published,
        )

    def test_discount_percent_is_a_valid_ordering_field(self):
        self.make_product("Small Discount", "SKU-10", 10)
        self.make_product("Big Discount", "SKU-50", 50)
        self.make_product("Medium Discount", "SKU-30", 30)

        response = self.client.get(self.url, {"ordering": "-discount_percent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertEqual(names, ["Big Discount", "Medium Discount", "Small Discount"])

    def test_products_without_a_discount_are_excluded_by_is_on_sale(self):
        # discount_percent defaults to 0 -- is_on_sale (what the Deals
        # widget filters on client-side) must be false for these, even
        # though they're still returned by a plain listing request.
        no_discount = self.make_product("No Discount", "SKU-0", 0)

        response = self.client.get(
            reverse("api:api_v1:product-detail", kwargs={"slug": no_discount.slug})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_on_sale"])
        self.assertEqual(response.data["discount_percent"], 0)

    def test_unpublished_discounted_products_never_appear_in_listing(self):
        self.make_product("Hidden Deal", "SKU-99", 90, published=False)
        self.make_product("Visible Deal", "SKU-20", 20, published=True)

        response = self.client.get(self.url, {"ordering": "-discount_percent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item["name"] for item in response.data["results"]]
        self.assertIn("Visible Deal", names)
        self.assertNotIn("Hidden Deal", names)
