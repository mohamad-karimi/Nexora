from django.db import models

__all__ = ["ProductSpecification"]


class ProductSpecification(models.Model):
    """
    A single free-form "name: value" spec row shown on the product's
    "Additional info" tab (e.g. "Color: Green, Pink", "Type Of Packing:
    Bottle").

    This replaces a fixed-column design (one field per possible spec)
    with a flexible key/value model, since different product
    categories need entirely different sets of specs and a rigid
    schema can't cover them all. See the project report for details.
    """

    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="specifications"
    )
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    ordering = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "id"]
        verbose_name = "Product specification"
        verbose_name_plural = "Product specifications"

    def __str__(self):
        return f"{self.name}: {self.value}"
