import xml.etree.ElementTree as ET

from django.test import TestCase
from django.urls import reverse

from blog.models import Category, Post


class BlogFeedTests(TestCase):
    def setUp(self):
        self.url = reverse("blog:feed")
        self.category = Category.objects.create(name="Feed Recipes")

    def test_feed_returns_200_and_valid_rss(self):
        Post.objects.create(
            category=self.category,
            title="Visible",
            slug="feed-post-visible",
            status=Post.Status.PUBLISHED,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("rss", response["Content-Type"])
        root = ET.fromstring(response.content)
        self.assertEqual(root.tag, "rss")

    def test_only_published_posts_are_in_feed(self):
        visible = Post.objects.create(
            category=self.category,
            title="Shown",
            slug="feed-post-shown",
            status=Post.Status.PUBLISHED,
        )
        hidden = Post.objects.create(
            category=self.category,
            title="Draft",
            slug="feed-post-hidden",
            status=Post.Status.DRAFT,
        )

        response = self.client.get(self.url)
        body = response.content.decode()

        self.assertIn(f"/blog/post/{visible.slug}/", body)
        self.assertNotIn(f"/blog/post/{hidden.slug}/", body)

    def test_links_are_absolute(self):
        Post.objects.create(
            category=self.category,
            title="Absolute Link",
            slug="feed-post-absolute",
            status=Post.Status.PUBLISHED,
        )

        response = self.client.get(self.url)
        root = ET.fromstring(response.content)
        channel = root.find("channel")
        link = channel.find("link").text
        item_link = channel.find("item/link").text

        self.assertTrue(
            link.startswith("http://") or link.startswith("https://")
        )
        self.assertTrue(
            item_link.startswith("http://")
            or item_link.startswith("https://")
        )
