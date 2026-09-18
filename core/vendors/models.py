from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Vendor(models.Model):
    """
    A seller / storefront on the marketplace. Every vendor is backed by
    exactly one CustomUser account (role=Role.VENDOR) so that the vendor
    can log in and manage their own store, products and orders.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vendor_profile",
        help_text="The account that owns and manages this store.",
    )
    store_name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    logo = models.ImageField(
        upload_to="vendors/logos/", blank=True, null=True
    )
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_approved = models.BooleanField(
        default=False,
        help_text=(
            "Vendors must be approved by an admin before their "
            "products go live."
        ),
    )
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["store_name"]

    def __str__(self):
        return self.store_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.store_name)
        super().save(*args, **kwargs)
