from django.conf import settings
from django.db import models

__all__ = ["Address"]


class Address(models.Model):
    """
    A postal address belonging to a user, usable as an order's
    shipping and/or billing address.

    This merges what the original schema modeled as two separate,
    overlapping tables ("Adress" and "Billing") into one - see the
    project report for why.
    """

    class AddressType(models.TextChoices):
        SHIPPING = "shipping", "Shipping"
        BILLING = "billing", "Billing"
        BOTH = "both", "Shipping & Billing"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    address_type = models.CharField(
        max_length=10, choices=AddressType.choices, default=AddressType.BOTH
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=150, blank=True)
    additional_information = models.TextField(blank=True)
    is_default = models.BooleanField(default=False)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_date"]

    def __str__(self):
        return f"{self.full_name} - {self.city}, {self.country}"
