"""Tests for the Redis public cache (core.public_cache + the API mixins).

The suite normally runs with the cache OFF and no Redis (see conftest.py);
these tests switch it on against a local-memory backend to check the logic
-- keys, hits and misses, invalidation, per-user isolation, publish rules
-- and against a real RedisCache pointed at a closed port to check the
Redis-is-down fallback. `assertNumQueries(0)` on a repeated request is the
proof that a hit is served from the cache and not from the database.
"""

from datetime import timedelta
from unittest import mock

import redis
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from blog.models import Category as BlogCategory
from blog.models import Post, PostLike
from blog.models import Tag as BlogTag
from core import public_cache
from shop.models import (
    Category,
    Product,
    ProductImage,
    ProductSpecification,
    Review,
    Tag,
    Wishlist,
)
from website.models import HomeBanner, HomeSlide

User = get_user_model()

LOCMEM = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nexora-public-cache-tests",
    }
}
DEAD_REDIS = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        # Nothing listens on port 1: a real connection failure.
        "LOCATION": "redis://127.0.0.1:1/0",
        "OPTIONS": {"socket_connect_timeout": 0.2, "socket_timeout": 0.2},
    }
}


def make_user(username, role=User.Role.CUSTOMER):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        role=role,
        is_verified=True,
    )


class CacheTestCase(APITestCase):
    def setUp(self):
        # Enabled here rather than with a class decorator: conftest's
        # autouse fixture switches the cache off before every test and would
        # undo a class-level override.
        enabled = override_settings(PUBLIC_CACHE_ENABLED=True, CACHES=LOCMEM)
        enabled.enable()
        self.addCleanup(enabled.disable)
        cache.clear()
        public_cache.reset_state()

    def assertServedFromCache(self, url, params=None, **extra):
        """Second identical request: 0 queries, same body as the first."""
        first = self.client.get(url, params, **extra)
        with self.assertNumQueries(0):
            second = self.client.get(url, params, **extra)
        self.assertEqual(second.status_code, first.status_code)
        self.assertEqual(second.json(), first.json())
        return second

    def queries_for(self, url, params=None):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url, params)
        return response, len(ctx)


class CatalogFixtureMixin:
    def make_catalog(self):
        self.vendor_user = make_user("vend", role=User.Role.VENDOR)
        self.vendor = self.vendor_user.vendor_profile
        self.vendor.is_approved = True
        self.vendor.store_name = "Green Store"
        self.vendor.save()
        self.category = Category.objects.create(name="Snacks")
        self.tag = Tag.objects.create(name="Organic")
        self.product = self.make_product("Granola", "SKU-1", published=True)
        self.product.tags.add(self.tag)
        self.draft = self.make_product("Secret Draft", "SKU-2")

    def make_product(self, name, sku, **kwargs):
        defaults = dict(
            vendor=self.vendor,
            category=self.category,
            name=name,
            sku=sku,
            price="10.00",
            stock=5,
        )
        defaults.update(kwargs)
        return Product.objects.create(**defaults)

    def names(self, response):
        return [item["name"] for item in response.json()["results"]]


class ProductListCacheTests(CatalogFixtureMixin, CacheTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.url = reverse("api:api_v1:product-list")

    def test_miss_hits_the_database_then_hit_is_served_from_redis(self):
        _, queries = self.queries_for(self.url)
        self.assertGreater(queries, 0)  # miss
        self.assertServedFromCache(self.url)  # hit: 0 queries

    def test_cached_result_equals_the_uncached_result(self):
        self.client.get(self.url)  # populate
        cached = self.client.get(self.url).json()
        with override_settings(PUBLIC_CACHE_ENABLED=False):
            fresh = self.client.get(self.url).json()
        self.assertEqual(cached, fresh)

    def test_only_published_products_are_ever_listed(self):
        self.assertEqual(self.names(self.client.get(self.url)), ["Granola"])
        self.assertEqual(self.names(self.client.get(self.url)), ["Granola"])

    def test_publishing_and_unpublishing_show_up_immediately(self):
        self.client.get(self.url)
        self.draft.published = True
        self.draft.save()
        self.assertEqual(
            sorted(self.names(self.client.get(self.url))),
            ["Granola", "Secret Draft"],
        )
        self.draft.published = False
        self.draft.save()
        self.assertEqual(self.names(self.client.get(self.url)), ["Granola"])

    def test_new_products_and_deletions_show_up_immediately(self):
        self.client.get(self.url)
        extra = self.make_product("Pretzels", "SKU-3", published=True)
        self.assertIn("Pretzels", self.names(self.client.get(self.url)))
        extra.delete()
        self.assertNotIn("Pretzels", self.names(self.client.get(self.url)))

    def test_price_stock_and_discount_updates_show_up_immediately(self):
        self.client.get(self.url)
        self.product.price = "20.00"
        self.product.discount_percent = 50
        self.product.stock = 0
        self.product.save()
        item = self.client.get(self.url).json()["results"][0]
        self.assertEqual(item["price"], "20.00")
        self.assertEqual(item["final_price"], "10.00")
        self.assertFalse(item["in_stock"])

    def test_a_purchase_style_stock_save_invalidates(self):
        self.client.get(self.url)
        self.product.stock = 3
        self.product.save(update_fields=["stock"])  # what checkout does
        item = self.client.get(self.url).json()["results"][0]
        self.assertEqual(item["stock"], 3)

    def test_an_expired_discount_stops_counting_even_from_the_cache(self):
        # is_on_sale is computed per request from the cached discount_end.
        self.product.discount_percent = 30
        self.product.discount_end = timezone.now() + timedelta(seconds=30)
        self.product.save()
        self.assertTrue(
            self.client.get(self.url).json()["results"][0]["is_on_sale"]
        )
        later = timezone.now() + timedelta(minutes=5)
        with mock.patch(
            "shop.models.product.timezone.now", return_value=later
        ):
            item = self.client.get(self.url).json()["results"][0]
        self.assertFalse(item["is_on_sale"])
        self.assertEqual(item["final_price"], "10.00")

    def test_category_tag_and_vendor_edits_show_up_on_product_cards(self):
        self.client.get(self.url)
        self.category.name = "Treats"
        self.category.save()
        self.tag.name = "Bio"
        self.tag.save()
        self.vendor.store_name = "Blue Store"
        self.vendor.save()
        item = self.client.get(self.url).json()["results"][0]
        self.assertEqual(item["category"]["name"], "Treats")
        self.assertEqual(item["tags"][0]["name"], "Bio")
        self.assertEqual(item["vendor"]["store_name"], "Blue Store")

    def test_tag_assignment_and_reviews_show_up_immediately(self):
        self.client.get(self.url)
        other = Tag.objects.create(name="Vegan")
        self.product.tags.add(other)
        tags = self.client.get(self.url).json()["results"][0]["tags"]
        self.assertEqual({t["name"] for t in tags}, {"Organic", "Vegan"})

        reviewer = make_user("reviewer")
        Review.objects.create(
            user=reviewer, product=self.product, score=4, is_approved=True
        )
        item = self.client.get(self.url).json()["results"][0]
        self.assertEqual(item["review_count"], 1)
        self.assertEqual(item["average_rating"], 4.0)

    def test_filters_and_ordering_are_cached_per_combination(self):
        second = self.make_product(
            "Almonds", "SKU-4", published=True, price="3.00"
        )
        cheap_first = {"ordering": "price"}
        expensive_first = {"ordering": "-price"}
        self.assertEqual(
            self.names(self.assertServedFromCache(self.url, cheap_first)),
            ["Almonds", "Granola"],
        )
        self.assertEqual(
            self.names(self.assertServedFromCache(self.url, expensive_first)),
            ["Granola", "Almonds"],
        )
        by_tag = {"tag": self.tag.slug}
        self.assertEqual(
            self.names(self.assertServedFromCache(self.url, by_tag)),
            ["Granola"],
        )
        self.assertEqual(second.name, "Almonds")

    def test_parameter_order_does_not_create_separate_entries(self):
        self.client.get(
            self.url + f"?ordering=price&category={self.category.slug}"
        )
        with self.assertNumQueries(0):
            self.client.get(
                self.url + f"?category={self.category.slug}&ordering=price"
            )

    def test_pagination_links_follow_each_requests_own_host(self):
        self.make_product("Almonds", "SKU-4", published=True)
        with override_settings(ALLOWED_HOSTS=["*"]):
            first = self.client.get(
                self.url, {"page_size": 1}, HTTP_HOST="a.example"
            )
            second = self.client.get(
                self.url, {"page_size": 1}, HTTP_HOST="b.example"
            )
        self.assertEqual(first.json()["count"], 2)
        self.assertIn("a.example", first.json()["next"])
        self.assertIn("b.example", second.json()["next"])  # not a.example
        self.assertNotIn("a.example", second.json()["next"])

    def test_invalid_page_still_404s_from_the_cache_path(self):
        self.client.get(self.url)
        self.assertEqual(
            self.client.get(self.url, {"page": 9}).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_search_price_range_and_unknown_parameters_are_not_cached(self):
        for params in (
            {"search": "gran"},
            {"min_price": "1"},
            {"cache_buster": "123"},
            {"ordering": "not-a-field"},
            {"page_size": "9999"},
        ):
            with self.subTest(params=params):
                self.client.get(self.url, params)
                _, queries = self.queries_for(self.url, params)
                self.assertGreater(queries, 0)

    def test_empty_results_are_not_cached(self):
        params = {"category": "no-such-category"}
        self.client.get(self.url, params)
        _, queries = self.queries_for(self.url, params)
        self.assertGreater(queries, 0)

    def test_invalid_filter_values_still_return_400(self):
        response = self.client.get(self.url, {"color": "purple"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProductListUserIsolationTests(CatalogFixtureMixin, CacheTestCase):
    """The cache is shared, so nothing per-user may live in it."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.url = reverse("api:api_v1:product-list")
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        Wishlist.objects.create(user=self.alice, product=self.product)

    def wishlisted(self, user=None):
        self.client.force_authenticate(user=user)
        return self.client.get(self.url).json()["results"][0]["is_wishlisted"]

    def test_wishlist_state_is_never_shared_between_users(self):
        self.assertTrue(self.wishlisted(self.alice))  # populates the cache
        self.assertFalse(self.wishlisted(self.bob))  # served from it
        self.assertTrue(self.wishlisted(self.alice))
        self.assertFalse(self.wishlisted(None))  # anonymous
        Wishlist.objects.create(user=self.bob, product=self.product)
        self.assertTrue(self.wishlisted(self.bob))

    def test_wishlist_endpoint_is_never_cached(self):
        self.client.force_authenticate(user=self.alice)
        wishlist_url = reverse("api:api_v1:wishlist-list")
        self.assertEqual(self.client.get(wishlist_url).json()["count"], 1)
        self.client.force_authenticate(user=self.bob)
        self.assertEqual(self.client.get(wishlist_url).json()["count"], 0)


class ProductDetailCacheTests(CatalogFixtureMixin, CacheTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()
        ProductImage.objects.create(product=self.product, image="p/x.jpg")
        ProductSpecification.objects.create(
            product=self.product, name="Weight", value="1kg"
        )

    def url(self, product):
        return reverse("api:api_v1:product-detail", args=[product.slug])

    def test_published_detail_is_served_from_redis_on_the_second_request(self):
        response = self.assertServedFromCache(self.url(self.product))
        body = response.json()
        self.assertEqual(body["name"], "Granola")
        self.assertEqual(len(body["images"]), 1)
        self.assertEqual(body["specifications"][0]["name"], "Weight")

    def test_updates_show_up_immediately(self):
        self.client.get(self.url(self.product))
        self.product.description = "Now crunchier"
        self.product.save()
        self.assertEqual(
            self.client.get(self.url(self.product)).json()["description"],
            "Now crunchier",
        )
        # images / specifications of a published product invalidate too
        ProductSpecification.objects.create(
            product=self.product, name="Origin", value="Iran"
        )
        ProductImage.objects.create(product=self.product, image="p/y.jpg")
        body = self.client.get(self.url(self.product)).json()
        self.assertEqual(len(body["specifications"]), 2)
        self.assertEqual(len(body["images"]), 2)

    def test_unpublishing_hides_the_product_from_the_public_at_once(self):
        self.assertEqual(
            self.client.get(self.url(self.product)).status_code, 200
        )
        self.product.published = False
        self.product.save()
        self.assertEqual(
            self.client.get(self.url(self.product)).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unpublished_product_is_never_served_from_the_cache(self):
        owner = self.vendor_user
        url = self.url(self.draft)
        self.client.force_authenticate(user=owner)
        self.assertEqual(
            self.client.get(url).status_code, 200
        )  # owner sees it
        self.assertEqual(self.client.get(url).status_code, 200)
        # Everyone else still gets the plain 404, however often the owner
        # asked.
        for user in (None, make_user("stranger"), self.vendor_user_other()):
            self.client.force_authenticate(user=user)
            self.assertEqual(
                self.client.get(url).status_code,
                status.HTTP_404_NOT_FOUND,
                msg=f"leaked to {user}",
            )

    def vendor_user_other(self):
        other = make_user("othervendor", role=User.Role.VENDOR)
        return other

    def test_publishing_makes_it_visible_to_everyone_at_once(self):
        url = self.url(self.draft)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.draft.published = True
        self.draft.save()
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_staff_can_still_see_unpublished_products(self):
        staff = make_user("staffer")
        staff.is_staff = True
        staff.save()
        self.client.force_authenticate(user=staff)
        self.assertEqual(
            self.client.get(self.url(self.draft)).status_code, 200
        )

    def test_per_user_field_is_not_shared_through_the_detail_cache(self):
        alice, bob = make_user("alice"), make_user("bob")
        Wishlist.objects.create(user=alice, product=self.product)
        url = self.url(self.product)
        self.client.force_authenticate(user=alice)
        self.assertTrue(self.client.get(url).json()["is_wishlisted"])
        self.client.force_authenticate(user=bob)
        self.assertFalse(self.client.get(url).json()["is_wishlisted"])

    def test_requests_with_query_parameters_bypass_the_detail_cache(self):
        url = self.url(self.product)
        self.client.get(url)
        # A filter that excludes the product must still 404, as before.
        response = self.client.get(url, {"category": "some-other-category"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reviews_action_is_not_served_from_the_cache(self):
        url = reverse("api:api_v1:product-reviews", args=[self.product.slug])
        reviewer = make_user("rev")
        Review.objects.create(user=reviewer, product=self.product, score=5)
        self.client.force_authenticate(user=reviewer)
        self.assertEqual(
            self.client.get(url).json()["count"], 1
        )  # own pending
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(url).json()["count"], 0)


class FacetsCategoriesTagsVendorsCacheTests(
    CatalogFixtureMixin, CacheTestCase
):
    def setUp(self):
        super().setUp()
        self.make_catalog()

    def test_facets_are_cached_and_follow_price_and_publish_changes(self):
        url = reverse("api:api_v1:product-facets")
        first = self.assertServedFromCache(url).json()
        self.assertEqual(first["price"], {"min": 10.0, "max": 10.0})
        self.product.price = "25.00"
        self.product.save()
        self.assertEqual(self.client.get(url).json()["price"]["max"], 25.0)
        self.product.published = False
        self.product.save()
        self.assertIsNone(self.client.get(url).json()["price"]["max"])

    def test_category_list_is_cached_and_counts_follow_publishing(self):
        url = reverse("api:api_v1:category-list")
        body = self.assertServedFromCache(url, {"page_size": 5}).json()
        self.assertEqual(body["results"][0]["product_count"], 1)
        self.draft.published = True
        self.draft.save()
        body = self.client.get(url, {"page_size": 5}).json()
        self.assertEqual(body["results"][0]["product_count"], 2)
        self.category.name = "Sweets"
        self.category.save()
        self.assertEqual(
            self.client.get(url, {"page_size": 5}).json()["results"][0][
                "name"
            ],
            "Sweets",
        )

    def test_new_category_shows_up_immediately(self):
        url = reverse("api:api_v1:category-list")
        self.client.get(url)
        Category.objects.create(name="Drinks")
        names = [c["name"] for c in self.client.get(url).json()["results"]]
        self.assertIn("Drinks", names)

    def test_tag_list_is_cached_and_follows_edits(self):
        url = reverse("api:api_v1:tag-list")
        self.assertServedFromCache(url)
        Tag.objects.create(name="Vegan")
        names = [t["name"] for t in self.client.get(url).json()["results"]]
        self.assertEqual(names, ["Organic", "Vegan"])
        Tag.objects.filter(name="Vegan").first().delete()
        names = [t["name"] for t in self.client.get(url).json()["results"]]
        self.assertEqual(names, ["Organic"])

    def test_vendor_list_shows_only_approved_vendors_and_follows_changes(self):
        pending_user = make_user("pendingvendor", role=User.Role.VENDOR)
        url = reverse("api:api_v1:vendor-list")
        body = self.assertServedFromCache(url).json()
        self.assertEqual(
            [v["store_name"] for v in body["results"]], ["Green Store"]
        )
        self.assertEqual(body["results"][0]["product_count"], 1)

        pending = pending_user.vendor_profile
        pending.is_approved = True
        pending.save()
        stores = [
            v["store_name"] for v in self.client.get(url).json()["results"]
        ]
        self.assertEqual(len(stores), 2)
        pending.is_approved = False
        pending.save()
        stores = [
            v["store_name"] for v in self.client.get(url).json()["results"]
        ]
        self.assertEqual(stores, ["Green Store"])

        self.draft.published = True
        self.draft.save()
        results = self.client.get(url).json()["results"]
        self.assertEqual(results[0]["product_count"], 2)

    def test_vendor_search_is_not_cached(self):
        url = reverse("api:api_v1:vendor-list")
        self.client.get(url, {"search": "green"})
        _, queries = self.queries_for(url, {"search": "green"})
        self.assertGreater(queries, 0)


class HomeCacheTests(CacheTestCase):
    def setUp(self):
        super().setUp()
        self.slide_url = reverse("api:api_v1:home-slide-list")
        self.banner_url = reverse("api:api_v1:home-banner-list")
        # The migrations seed default slides/banners; start from a clean slate.
        HomeSlide.objects.all().delete()
        HomeBanner.objects.all().delete()
        self.slide = HomeSlide.objects.create(title="Deals", image="s/a.jpg")
        self.banner = HomeBanner.objects.create(title="Fruit", image="b/a.jpg")

    def test_slides_and_banners_are_served_from_redis(self):
        self.assertEqual(
            len(self.assertServedFromCache(self.slide_url).json()), 1
        )
        self.assertEqual(
            len(self.assertServedFromCache(self.banner_url).json()), 1
        )

    def test_slider_edits_show_up_immediately(self):
        self.client.get(self.slide_url)
        self.slide.title = "New deals"
        self.slide.save()
        self.assertEqual(
            self.client.get(self.slide_url).json()[0]["title"], "New deals"
        )
        HomeSlide.objects.create(title="Second", image="s/b.jpg", ordering=5)
        self.assertEqual(len(self.client.get(self.slide_url).json()), 2)
        self.slide.is_active = False
        self.slide.save()
        titles = [s["title"] for s in self.client.get(self.slide_url).json()]
        self.assertEqual(titles, ["Second"])
        HomeSlide.objects.all().delete()
        self.assertEqual(self.client.get(self.slide_url).json(), [])

    def test_banner_edits_show_up_immediately(self):
        self.client.get(self.banner_url)
        self.banner.link_url = "/shop/filter/?category=fruit"
        self.banner.save()
        self.assertEqual(
            self.client.get(self.banner_url).json()[0]["link_url"],
            "/shop/filter/?category=fruit",
        )
        self.banner.delete()
        self.assertEqual(self.client.get(self.banner_url).json(), [])

    def test_home_and_catalog_caches_are_independent(self):
        version = public_cache.get_version("home")
        Category.objects.create(name="Unrelated")
        self.assertEqual(public_cache.get_version("home"), version)


class BlogCacheTests(CacheTestCase):
    def setUp(self):
        super().setUp()
        self.category = BlogCategory.objects.create(name="Recipes")
        self.tag = BlogTag.objects.create(name="Tips")
        self.author = make_user("author")
        self.post = Post.objects.create(
            author=self.author,
            category=self.category,
            title="Published Post",
            slug="published-post",
            content="Body",
            status=Post.Status.PUBLISHED,
        )
        self.draft = Post.objects.create(
            author=self.author,
            category=self.category,
            title="Draft Post",
            slug="draft-post",
            content="Secret",
            status=Post.Status.DRAFT,
        )
        self.list_url = reverse("api:api_v1:blog-post-list")

    def slugs(self, response):
        return [p["slug"] for p in response.json()["results"]]

    def test_only_published_posts_are_cached_and_listed(self):
        self.assertEqual(
            self.slugs(self.assertServedFromCache(self.list_url)),
            ["published-post"],
        )
        detail = reverse(
            "api:api_v1:blog-post-detail", args=["published-post"]
        )
        self.assertServedFromCache(detail)
        draft_detail = reverse(
            "api:api_v1:blog-post-detail", args=["draft-post"]
        )
        self.assertEqual(self.client.get(draft_detail).status_code, 404)
        self.assertEqual(self.client.get(draft_detail).status_code, 404)

    def test_publishing_and_unpublishing_show_up_immediately(self):
        self.client.get(self.list_url)
        draft_detail = reverse(
            "api:api_v1:blog-post-detail", args=["draft-post"]
        )
        self.assertEqual(self.client.get(draft_detail).status_code, 404)
        self.draft.status = Post.Status.PUBLISHED
        self.draft.save()
        self.assertEqual(len(self.slugs(self.client.get(self.list_url))), 2)
        self.assertEqual(self.client.get(draft_detail).status_code, 200)
        self.draft.status = Post.Status.ARCHIVED
        self.draft.save()
        self.assertEqual(
            self.slugs(self.client.get(self.list_url)), ["published-post"]
        )
        self.assertEqual(self.client.get(draft_detail).status_code, 404)

    def test_post_edits_tags_and_likes_show_up_immediately(self):
        detail = reverse(
            "api:api_v1:blog-post-detail", args=["published-post"]
        )
        self.client.get(detail)
        self.post.title = "Renamed"
        self.post.save()
        self.assertEqual(self.client.get(detail).json()["title"], "Renamed")
        self.post.tags.add(self.tag)
        self.assertEqual(len(self.client.get(detail).json()["tags"]), 1)
        PostLike.objects.create(user=make_user("fan"), post=self.post)
        self.assertEqual(self.client.get(detail).json()["like_count"], 1)

    def test_liked_state_is_never_shared_between_users(self):
        alice, bob = make_user("alice"), make_user("bob")
        PostLike.objects.create(user=alice, post=self.post)
        self.client.force_authenticate(user=alice)
        self.assertTrue(
            self.client.get(self.list_url).json()["results"][0]["is_liked"]
        )
        self.client.force_authenticate(user=bob)
        self.assertFalse(
            self.client.get(self.list_url).json()["results"][0]["is_liked"]
        )
        self.client.force_authenticate(user=None)
        self.assertFalse(
            self.client.get(self.list_url).json()["results"][0]["is_liked"]
        )

    def test_like_toggle_endpoint_still_writes_through(self):
        like_url = reverse(
            "api:api_v1:blog-post-like", args=["published-post"]
        )
        self.client.force_authenticate(user=make_user("fan"))
        self.assertTrue(self.client.post(like_url).json()["liked"])
        self.assertEqual(
            self.client.get(self.list_url).json()["results"][0]["like_count"],
            1,
        )
        self.assertFalse(self.client.post(like_url).json()["liked"])
        self.assertEqual(
            self.client.get(self.list_url).json()["results"][0]["like_count"],
            0,
        )

    def test_blog_categories_and_tags_are_cached_and_follow_changes(self):
        cat_url = reverse("api:api_v1:blog-category-list")
        tag_url = reverse("api:api_v1:blog-tag-list")
        body = self.assertServedFromCache(cat_url).json()
        self.assertEqual(body["results"][0]["post_count"], 1)
        self.assertServedFromCache(tag_url)
        self.draft.status = Post.Status.PUBLISHED
        self.draft.save()
        self.assertEqual(
            self.client.get(cat_url).json()["results"][0]["post_count"], 2
        )
        BlogTag.objects.create(name="Quick")
        self.assertEqual(len(self.client.get(tag_url).json()["results"]), 2)


class InvalidationMechanicsTests(CatalogFixtureMixin, CacheTestCase):
    def setUp(self):
        super().setUp()
        self.make_catalog()

    def test_editing_a_draft_does_not_empty_the_cache(self):
        version = public_cache.get_version("catalog")
        self.draft.description = "still a draft"
        self.draft.price = "99.00"
        self.draft.save()
        ProductSpecification.objects.create(
            product=self.draft, name="Draft spec", value="x"
        )
        self.assertEqual(public_cache.get_version("catalog"), version)

    def test_a_published_products_edit_does_change_the_version(self):
        version = public_cache.get_version("catalog")
        self.product.description = "edited"
        self.product.save()
        self.assertNotEqual(public_cache.get_version("catalog"), version)

    def test_a_result_computed_during_a_change_is_never_served(self):
        slot = public_cache.lookup("catalog", "probe")
        # ... a change lands while the caller is still computing ...
        public_cache.bump("catalog")
        public_cache.store(slot, "stale", "catalog")
        self.assertFalse(public_cache.lookup("catalog", "probe").hit)

    def test_a_lost_version_never_resurrects_old_entries(self):
        slot = public_cache.lookup("catalog", "probe")
        public_cache.store(slot, "old", "catalog")
        self.assertTrue(public_cache.lookup("catalog", "probe").hit)
        cache.delete("pubcache:version:catalog")  # e.g. evicted by Redis
        self.assertFalse(public_cache.lookup("catalog", "probe").hit)

    def test_invalidation_also_runs_after_the_surrounding_commit(self):
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            with transaction.atomic():
                public_cache.bump("catalog")
        self.assertEqual(len(callbacks), 1)
        version = public_cache.get_version("catalog")
        callbacks[0]()
        self.assertNotEqual(public_cache.get_version("catalog"), version)

    def test_entries_use_the_configured_ttl(self):
        with mock.patch("core.public_cache.cache") as fake:
            fake.get.side_effect = [7, None]  # version, then a miss
            slot = public_cache.lookup("home", "x")
            public_cache.store(slot, "v", "home")
        args = fake.set.call_args.args
        self.assertEqual(args[2], 300)
        self.assertEqual(args[1], ("v",))

    def test_kill_switch_serves_from_the_database_but_still_invalidates(self):
        url = reverse("api:api_v1:product-list")
        self.client.get(url)
        version = public_cache.get_version("catalog")
        with override_settings(PUBLIC_CACHE_ENABLED=False):
            _, queries = self.queries_for(url)
            self.assertGreater(queries, 0)
            _, queries = self.queries_for(url)
            self.assertGreater(queries, 0)  # never served from cache
            self.product.description = "edited while switched off"
            self.product.save()
        # Switched back on: nothing written meanwhile can resurface.
        self.assertNotEqual(public_cache.get_version("catalog"), version)


def _failing_cache():
    fake = mock.MagicMock()
    error = redis.exceptions.ConnectionError("Redis is down")
    for method in ("get", "set", "add", "incr"):
        getattr(fake, method).side_effect = error
    return fake


class RedisFailureTests(CatalogFixtureMixin, CacheTestCase):
    """If Redis is down the site keeps working, straight from the DB."""

    def setUp(self):
        super().setUp()
        self.make_catalog()
        self.url = reverse("api:api_v1:product-list")

    def test_reads_fall_back_to_the_database_with_correct_data(self):
        with mock.patch("core.public_cache.cache", _failing_cache()):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names(response), ["Granola"])

    def test_a_dead_redis_is_tried_once_then_skipped_for_the_cooldown(self):
        failing = _failing_cache()
        with mock.patch("core.public_cache.cache", failing):
            for _ in range(5):
                self.assertEqual(self.client.get(self.url).status_code, 200)
        # Only the first request touched Redis; the rest skipped it.
        self.assertEqual(failing.get.call_count, 1)
        self.assertFalse(public_cache.available())
        # After the cooldown it is tried again.
        public_cache._state["down_until"] = 0.0
        self.assertTrue(public_cache.available())

    def test_writes_do_not_fail_when_invalidation_cannot_reach_redis(self):
        with mock.patch("core.public_cache.cache", _failing_cache()):
            self.product.description = "edited during the outage"
            self.product.save()  # must not raise
            Category.objects.create(name="Made during outage")
        self.assertEqual(
            Product.objects.get(pk=self.product.pk).description,
            "edited during the outage",
        )

    def test_an_invalidation_missed_during_an_outage_is_applied_afterwards(
        self,
    ):
        self.client.get(self.url)  # cached with the old data
        with mock.patch("core.public_cache.cache", _failing_cache()):
            self.product.name = "Granola v2"
            self.product.save()  # bump cannot be delivered
        # Redis is back (breaker window over): the missed bump is replayed
        # before anything is read, so the old page cannot be served.
        public_cache._state["down_until"] = 0.0
        self.assertEqual(self.names(self.client.get(self.url)), ["Granola v2"])

    @override_settings(CACHES=DEAD_REDIS, PUBLIC_CACHE_FAILURE_COOLDOWN=30)
    def test_against_a_real_unreachable_redis_everything_still_works(self):
        public_cache.reset_state()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.names(response), ["Granola"])
        self.product.save()  # signal -> invalidation -> no crash
        detail = reverse("api:api_v1:product-detail", args=[self.product.slug])
        self.assertEqual(self.client.get(detail).status_code, 200)
        facets = reverse("api:api_v1:product-facets")
        self.assertEqual(self.client.get(facets).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("api:api_v1:home-slide-list")).status_code,
            200,
        )

    def test_an_unreadable_cache_entry_is_just_a_miss(self):
        self.client.get(self.url)
        real_get = cache.get

        def flaky_get(key, *args, **kwargs):
            if "version" in key:
                return real_get(key, *args, **kwargs)
            raise ValueError("cannot unpickle entry from an older release")

        with mock.patch.object(cache, "get", side_effect=flaky_get):
            response = self.client.get(self.url)
        self.assertEqual(self.names(response), ["Granola"])
        self.assertTrue(public_cache.available())  # not treated as an outage
