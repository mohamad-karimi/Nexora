from django.conf import settings
from django.db import models
from django.utils.text import slugify

__all__ = ["Category", "Post", "Tag", "Comment", "PostBookmark", "PostLike"]


class Category(models.Model):
    """
    A blog category (e.g. "Recipes", "Kitchen"). Mirrors shop.Category:
    a flat, reusable label that posts are grouped under.
    """

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=170, unique=True, blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """
    A free-form label posts can be grouped by (e.g. "Recipe", "Tips").
    Mirrors shop.Tag: a post can carry several tags and a tag can be
    shared by many posts, hence the ManyToMany on Post. Backs the
    blog sidebar's "Popular Tags" widget.
    """

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Post(models.Model):
    """
    A blog article. Mirrors shop.Product's shape (status-gated
    visibility, slug, category FK, image, created/update timestamps)
    so the blog listing can reuse the exact same DRF/list-page pattern
    already built for the shop.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blog_posts",
    )
    category = models.ForeignKey(
        "blog.Category",
        on_delete=models.PROTECT,
        related_name="posts",
    )
    tags = models.ManyToManyField("blog.Tag", related_name="posts", blank=True)

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    excerpt = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to="blog/", blank=True, null=True)

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )

    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class Comment(models.Model):
    """
    A logged-in user's comment on a post. Published by default -
    `published` gates public visibility (an admin can uncheck it to
    hide a comment from every visitor without deleting it). Mirrors
    shop.Review's shape minus the score field and the one-per-user
    uniqueness constraint, since a reader may leave more than one
    comment on a post.
    """

    post = models.ForeignKey(
        "blog.Post", on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_comments",
    )
    content = models.TextField()
    is_approved = models.BooleanField(
        default=False, help_text="Comments are moderated before they go public."
    )
    published = models.BooleanField(
        default=True,
        help_text="Visible on the site when checked. Uncheck to hide this "
        "comment from every visitor without deleting it.",
    )
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return f"Comment by {self.user} on {self.post}"


class PostBookmark(models.Model):
    """
    A post a user has saved/bookmarked. Mirrors shop.Wishlist exactly
    (one row per user+post, same cascade behaviour) so the blog's
    save/like buttons reuse the project's one existing "save this for
    later" pattern instead of a second bespoke one.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_bookmarks",
    )
    post = models.ForeignKey(
        "blog.Post", on_delete=models.CASCADE, related_name="bookmarked_by"
    )
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"], name="unique_bookmark_per_user_post"
            )
        ]

    def __str__(self):
        return f"{self.user} \u2192 {self.post}"


class PostLike(models.Model):
    """
    A user liking a post. Deliberately separate from PostBookmark -
    same shape, same one-row-per-user-per-post pattern, but a
    distinct table/endpoint so liking and bookmarking a post are two
    completely independent actions (one doesn't affect the other).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="post_likes",
    )
    post = models.ForeignKey("blog.Post", on_delete=models.CASCADE, related_name="likes")
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"], name="unique_like_per_user_post"
            )
        ]

    def __str__(self):
        return f"{self.user} \u2665 {self.post}"
