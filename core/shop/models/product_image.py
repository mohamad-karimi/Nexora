from django.db import models

__all__ = ["ProductImage"]


class ProductImage(models.Model):
    """
    Extra gallery images for a product (the product detail page shows
    a multi-image slider + thumbnails, so a single `Product.image`
    field is not enough).
    """

    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="products/gallery/")
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"
