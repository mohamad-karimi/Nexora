from django.conf import settings
from django.db import models

__all__ = ["Wishlist"]


class Wishlist(models.Model):
    """A product a user has saved for later. One row per (user, product)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )
    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="wishlisted_by"
    )
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_wishlist_user_product"
            )
        ]

    def __str__(self):
        return f"{self.user} \u2192 {self.product}"
