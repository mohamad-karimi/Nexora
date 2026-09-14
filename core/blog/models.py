from django.conf import settings
from django.db import models
from django.utils.text import slugify

__all__ = ["Category", "Post"]


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
