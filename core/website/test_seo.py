from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Category as BlogCategory, Post
from shop.models import Category as ShopCategory
from shop.tests import make_product, make_user

User = get_user_model()


class SitemapTests(TestCase):
    """/sitemap.xml aggregates the static pages, published products
    and published blog posts sitemaps registered in core/urls.py."""

    def setUp(self):
        self.url = reverse("sitemap")

    def test_sitemap_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_static_public_pages_are_listed(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        for name in (
            "website:home",
            "website:about",
            "website:contact",
            "website:privacy_policy",
            "website:terms",
        ):
            self.assertIn(f"{settings.SITE_DOMAIN}{reverse(name)}", body)

    def test_published_product_is_listed(self):
        category = ShopCategory.objects.create(name="Sitemap Groceries")
        vendor_user = make_user("sitemap-vendor", role=User.Role.VENDOR)
        vendor = vendor_user.vendor_profile
        product = make_product(
            vendor,
            category,
            sku="SKU-SM-1",
            slug="sitemap-visible",
            published=True,
        )

        response = self.client.get(self.url)

        self.assertContains(response, f"/shop/product/{product.slug}/")

    def test_unpublished_product_is_not_listed(self):
        category = ShopCategory.objects.create(
            name="Sitemap Hidden Groceries"
        )
        vendor_user = make_user("sitemap-vendor-2", role=User.Role.VENDOR)
        vendor = vendor_user.vendor_profile
        product = make_product(
            vendor,
            category,
            sku="SKU-SM-2",
            slug="sitemap-hidden",
            published=False,
        )

        response = self.client.get(self.url)

        self.assertNotContains(response, f"/shop/product/{product.slug}/")

    def test_published_blog_post_is_listed(self):
        category = BlogCategory.objects.create(name="Sitemap Recipes")
        post = Post.objects.create(
            category=category,
            title="Visible Post",
            slug="sitemap-post-visible",
            status=Post.Status.PUBLISHED,
        )

        response = self.client.get(self.url)

        self.assertContains(response, f"/blog/post/{post.slug}/")

    def test_unpublished_blog_post_is_not_listed(self):
        category = BlogCategory.objects.create(name="Sitemap Draft Recipes")
        post = Post.objects.create(
            category=category,
            title="Draft Post",
            slug="sitemap-post-hidden",
            status=Post.Status.DRAFT,
        )

        response = self.client.get(self.url)

        self.assertNotContains(response, f"/blog/post/{post.slug}/")

    def test_urls_are_absolute_and_use_configured_domain(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertIn(f"://{settings.SITE_DOMAIN}", body)
        self.assertNotIn("example.com", body)


class RobotsTxtTests(TestCase):
    def setUp(self):
        self.url = reverse("website:robots_txt")

    def test_robots_txt_returns_200(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_robots_txt_contains_correct_sitemap_url(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertIn("Sitemap: ", body)
        self.assertIn(reverse("sitemap"), body)
        self.assertRegex(body, r"Sitemap: https?://")

    def test_private_paths_are_disallowed(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        for path in (
            "/admin/",
            "/api/",
            "/cart/",
            "/orders/",
            "/dashboard/",
            "/account/",
        ):
            self.assertIn(f"Disallow: {path}", body)

    def test_sitemap_url_uses_configured_domain_not_hardcoded(self):
        response = self.client.get(self.url)
        body = response.content.decode()
        self.assertIn(settings.SITE_DOMAIN, body)
