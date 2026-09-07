from django.db import models
from django.utils.text import slugify

__all__ = ["Tag"]


class Tag(models.Model):
    """
    A free-form label products can be grouped by (e.g. "Organic",
    "Snack"). A product can carry several tags and a tag can be
    shared by many products, hence the ManyToMany on Product.
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
