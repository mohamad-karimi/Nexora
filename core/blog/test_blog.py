from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from blog.models import Category, Comment, Post, PostBookmark, PostLike, Tag

User = get_user_model()


def make_user(username, is_verified=True):
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="StrongPass123!",
        is_verified=is_verified,
    )


class BlogAPITestBase(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Recipes")
        self.other_category = Category.objects.create(name="News")
        self.tag = Tag.objects.create(name="Tips")
        self.author = make_user("blogauthor")
        self.reader = make_user("blogreader")
        self.published = Post.objects.create(
            author=self.author,
            category=self.category,
            title="Published Post",
            slug="published-post",
            excerpt="A tasty excerpt",
            content="Full published content about sourdough.",
            status=Post.Status.PUBLISHED,
        )
        self.published.tags.add(self.tag)
        self.draft = Post.objects.create(
            author=self.author,
            category=self.category,
            title="Draft Post",
            slug="draft-post",
            content="Secret draft",
            status=Post.Status.DRAFT,
        )
        self.archived = Post.objects.create(
            author=self.author,
            category=self.other_category,
            title="Archived Post",
            slug="archived-post",
            status=Post.Status.ARCHIVED,
        )
        self.list_url = reverse("api:api_v1:blog-post-list")


class BlogVisibilityTests(BlogAPITestBase):
    def test_list_returns_only_published_posts(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["published-post"])
        self.assertNotIn("content", response.data["results"][0])

    def test_published_detail_includes_content_and_tags(self):
        response = self.client.get(
            reverse(
                "api:api_v1:blog-post-detail",
                kwargs={"slug": self.published.slug},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], self.published.content)
        self.assertEqual(response.data["tags"][0]["slug"], self.tag.slug)

    def test_draft_and_archived_posts_are_not_retrievable(self):
        draft = self.client.get(
            reverse(
                "api:api_v1:blog-post-detail",
                kwargs={"slug": self.draft.slug},
            )
        )
        archived = self.client.get(
            reverse(
                "api:api_v1:blog-post-detail",
                kwargs={"slug": self.archived.slug},
            )
        )
        self.assertEqual(draft.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(archived.status_code, status.HTTP_404_NOT_FOUND)

    def test_author_cannot_open_own_draft_via_public_api(self):
        self.client.force_authenticate(user=self.author)
        response = self.client.get(
            reverse(
                "api:api_v1:blog-post-detail",
                kwargs={"slug": self.draft.slug},
            )
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_category_filter_and_post_count_ignore_drafts(self):
        listed = self.client.get(
            self.list_url, {"category": self.category.slug}
        )
        slugs = [item["slug"] for item in listed.data["results"]]
        self.assertEqual(slugs, ["published-post"])

        category = self.client.get(
            reverse(
                "api:api_v1:blog-category-detail",
                kwargs={"slug": self.category.slug},
            )
        )
        self.assertEqual(category.status_code, status.HTTP_200_OK)
        self.assertEqual(category.data["post_count"], 1)

    def test_tag_filter_and_search(self):
        tagged = self.client.get(self.list_url, {"tag": self.tag.slug})
        self.assertEqual(
            [item["slug"] for item in tagged.data["results"]],
            ["published-post"],
        )

        search = self.client.get(self.list_url, {"search": "sourdough"})
        self.assertEqual(
            [item["slug"] for item in search.data["results"]],
            ["published-post"],
        )

        miss = self.client.get(self.list_url, {"search": "unrelated-token"})
        self.assertEqual(miss.data["results"], [])


class BlogCommentTests(BlogAPITestBase):
    def setUp(self):
        super().setUp()
        self.comments_url = reverse(
            "api:api_v1:blog-post-comments",
            kwargs={"slug": self.published.slug},
        )

    def test_anonymous_can_list_published_comments_only(self):
        Comment.objects.create(
            post=self.published,
            user=self.reader,
            content="Visible",
            published=True,
        )
        Comment.objects.create(
            post=self.published,
            user=self.reader,
            content="Hidden by admin",
            published=False,
        )

        response = self.client.get(self.comments_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        bodies = [item["content"] for item in response.data["results"]]
        self.assertEqual(bodies, ["Visible"])

    def test_unpublished_comment_is_hidden_even_from_its_author(self):
        Comment.objects.create(
            post=self.published,
            user=self.reader,
            content="Please hide me",
            published=False,
        )
        self.client.force_authenticate(user=self.reader)

        response = self.client.get(self.comments_url)

        self.assertEqual(response.data["results"], [])

    def test_anonymous_cannot_create_a_comment(self):
        response = self.client.post(self.comments_url, {"content": "Hello"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(Comment.objects.count(), 0)

    def test_authenticated_user_can_create_a_published_comment(self):
        self.client.force_authenticate(user=self.reader)
        response = self.client.post(
            self.comments_url, {"content": "  Nice post  "}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        comment = Comment.objects.get()
        self.assertEqual(comment.user, self.reader)
        self.assertEqual(comment.content, "Nice post")
        self.assertTrue(comment.published)
        self.assertEqual(response.data["content"], "Nice post")

    def test_empty_comment_is_rejected(self):
        self.client.force_authenticate(user=self.reader)
        response = self.client.post(self.comments_url, {"content": "   "})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Comment.objects.count(), 0)

    def test_client_cannot_force_a_comment_unpublished(self):
        self.client.force_authenticate(user=self.reader)
        response = self.client.post(
            self.comments_url, {"content": "Live now", "published": False}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Comment.objects.get().published)

    def test_cannot_comment_on_a_draft_post(self):
        self.client.force_authenticate(user=self.reader)
        url = reverse(
            "api:api_v1:blog-post-comments", kwargs={"slug": self.draft.slug}
        )
        response = self.client.post(url, {"content": "Nope"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BlogLikeAndBookmarkTests(BlogAPITestBase):
    def setUp(self):
        super().setUp()
        self.like_url = reverse(
            "api:api_v1:blog-post-like", kwargs={"slug": self.published.slug}
        )
        self.bookmark_url = reverse(
            "api:api_v1:blog-post-bookmark",
            kwargs={"slug": self.published.slug},
        )
        self.detail_url = reverse(
            "api:api_v1:blog-post-detail",
            kwargs={"slug": self.published.slug},
        )

    def test_anonymous_cannot_like_or_bookmark(self):
        like = self.client.post(self.like_url)
        bookmark = self.client.post(self.bookmark_url)
        self.assertEqual(like.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(bookmark.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_like_toggles_on_and_off_and_updates_count(self):
        self.client.force_authenticate(user=self.reader)
        on = self.client.post(self.like_url)
        self.assertEqual(on.status_code, status.HTTP_200_OK)
        self.assertTrue(on.data["liked"])
        self.assertEqual(on.data["like_count"], 1)
        self.assertTrue(
            PostLike.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )

        off = self.client.post(self.like_url)
        self.assertFalse(off.data["liked"])
        self.assertEqual(off.data["like_count"], 0)
        self.assertFalse(
            PostLike.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )

    def test_bookmark_toggles_independently_of_like(self):
        self.client.force_authenticate(user=self.reader)
        self.client.post(self.like_url)
        bookmarked = self.client.post(self.bookmark_url)
        self.assertTrue(bookmarked.data["bookmarked"])
        self.assertTrue(
            PostLike.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )
        self.assertTrue(
            PostBookmark.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )

        unbookmarked = self.client.post(self.bookmark_url)
        self.assertFalse(unbookmarked.data["bookmarked"])
        self.assertTrue(
            PostLike.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )
        self.assertFalse(
            PostBookmark.objects.filter(
                user=self.reader, post=self.published
            ).exists()
        )

    def test_like_and_bookmark_flags_are_per_user(self):
        PostLike.objects.create(user=self.author, post=self.published)
        PostBookmark.objects.create(user=self.author, post=self.published)
        self.client.force_authenticate(user=self.reader)

        response = self.client.get(self.detail_url)

        self.assertFalse(response.data["is_liked"])
        self.assertFalse(response.data["is_bookmarked"])
        self.assertEqual(response.data["like_count"], 1)

        self.client.post(self.like_url)
        self.client.post(self.bookmark_url)
        mine = self.client.get(self.detail_url)
        self.assertTrue(mine.data["is_liked"])
        self.assertTrue(mine.data["is_bookmarked"])
        self.assertEqual(mine.data["like_count"], 2)

    def test_cannot_like_or_bookmark_a_draft(self):
        self.client.force_authenticate(user=self.reader)
        like = self.client.post(
            reverse(
                "api:api_v1:blog-post-like", kwargs={"slug": self.draft.slug}
            )
        )
        bookmark = self.client.post(
            reverse(
                "api:api_v1:blog-post-bookmark",
                kwargs={"slug": self.draft.slug},
            )
        )
        self.assertEqual(like.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(bookmark.status_code, status.HTTP_404_NOT_FOUND)
