from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

__all__ = ["Coupon"]


class Coupon(models.Model):
    """A percentage-off discount code applied to an order at checkout."""

    code = models.CharField(max_length=50, unique=True)
    discount_percent = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_to = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum total number of times this coupon can be used. "
        "Leave empty for unlimited.",
    )
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return self.code

    @property
    def is_valid(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if not (self.valid_from <= now <= self.valid_to):
            return False
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return False
        return True
