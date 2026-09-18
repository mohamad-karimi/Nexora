from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

__all__ = ["Product"]


class Product(models.Model):
    """
    A sellable item in the marketplace.

    Notes on a few deliberate design choices (see project report for
    the full list):
    - price/stock live on the product itself (no separate SKU-level
      variants are modeled yet; see report for why).
    - vendor is required: every product is sold by exactly one vendor.
    - `final_price` / `is_on_sale` are computed, not stored, so a
      change to price or discount is reflected everywhere instantly.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    class Color(models.TextChoices):
        RED = "red", "Red"
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        REFURBISHED = "refurbished", "Refurbished"
        USED = "used", "Used"

    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.PROTECT,
        related_name="products",
    )
    category = models.ForeignKey(
        "shop.Category",
        on_delete=models.PROTECT,
        related_name="products",
    )
    tags = models.ManyToManyField(
        "shop.Tag", blank=True, related_name="products"
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    short_description = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    sku = models.CharField(max_length=64, unique=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percent = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    discount_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the current discount stops applying.",
    )
    stock = models.PositiveIntegerField(default=0)

    image = models.ImageField(upload_to="products/", blank=True, null=True)
    product_type = models.CharField(
        max_length=100,
        blank=True,
        help_text='Free-form label, e.g. "Organic".',
    )
    manufacture_date = models.DateField(
        null=True,
        blank=True,
        help_text="Manufacturing date, for perishable goods.",
    )
    shelf_life_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Shelf life in days from the manufacture date.",
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    published = models.BooleanField(
        default=False,
        help_text=(
            "Controls public storefront visibility (Shop, category/list "
            "pages, search, related products, and the public Product "
            "API). Only staff/admin can set this to True, from Django "
            "Admin -- vendors cannot publish their own products. The "
            "owning vendor and staff can still view/manage the product "
            "before it's published; everyone else cannot."
        ),
    )
    color = models.CharField(
        max_length=10,
        choices=Color.choices,
        blank=True,
        help_text="Optional; powers the storefront's color filter.",
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.NEW,
        help_text="Powers the storefront's item-condition filter.",
    )

    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_date"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
            models.Index(
                fields=["published"], name="shop_product_published_idx"
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            # Same dedup approach used elsewhere in the project (see
            # vendors/migrations/0002_backfill_vendor_profiles.py):
            # append a numeric suffix on collision, since slug is
            # unique=True and two products can easily share a name.
            base_slug = slugify(self.name) or "product"
            slug = base_slug
            suffix = 2
            qs = Product.objects.filter(slug=slug)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.exists():
                slug = f"{base_slug}-{suffix}"
                suffix += 1
                qs = Product.objects.filter(slug=slug)
                if self.pk:
                    qs = qs.exclude(pk=self.pk)
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def is_on_sale(self):
        if self.discount_percent <= 0:
            return False
        if self.discount_end and self.discount_end < timezone.now():
            return False
        return True

    @property
    def final_price(self):
        if self.is_on_sale:
            discount = (self.price * self.discount_percent) / 100
            return round(self.price - discount, 2)
        return self.price

    @property
    def in_stock(self):
        return self.stock > 0
