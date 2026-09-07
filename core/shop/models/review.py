from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

__all__ = ["Review"]


class Review(models.Model):
    """
    A customer's rating/comment on a product. One review per
    (user, product) pair - a customer edits their existing review
    instead of piling up duplicates.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    product = models.ForeignKey(
        "shop.Product", on_delete=models.CASCADE, related_name="reviews"
    )
    score = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    is_approved = models.BooleanField(
        default=False, help_text="Reviews are moderated before they go public."
    )
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_review_per_user_product"
            )
        ]

    def __str__(self):
        return f"{self.score}\u2605 by {self.user} on {self.product}"
