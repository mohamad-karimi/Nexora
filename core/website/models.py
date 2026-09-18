from django.conf import settings
from django.db import models


class HomeSlide(models.Model):
    """
    A single slide of the homepage hero slider (`home-slider` section
    of website/index.html). `title`/`description` mirror the
    slide's `<h1>`/`<p>` exactly; `title` may contain newlines, one
    per visual line (rendered as `<br />` the same way the original
    static markup broke "Don't miss amazing" / "grocery deals" onto
    two lines).
    """

    title = models.TextField(
        help_text="One line per <br /> break in the slide heading."
    )
    description = models.CharField(
        max_length=255, blank=True, help_text="Slide's supporting text line."
    )
    image = models.ImageField(upload_to="sliders/")
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return self.title.splitlines()[0] if self.title else f"Slide #{self.pk}"


class HomeBanner(models.Model):
    """
    A single tile of the homepage `banners mb-25` 3-up section.
    Only the first 3 active banners (by `ordering`) are ever shown,
    since the section's layout is a fixed 3-column row. `link_url`
    is optional -- when blank, the storefront falls back to the shop
    listing page, exactly like the original static "Shop Now" links.
    """

    title = models.TextField(
        help_text="One line per <br /> break in the banner heading."
    )
    image = models.ImageField(upload_to="banners/")
    link_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional. Defaults to the shop listing page when blank.",
    )
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordering", "id"]

    def __str__(self):
        return self.title.splitlines()[0] if self.title else f"Banner #{self.pk}"


class ContactMessage(models.Model):
    """
    A message submitted through one of the "Drop Us a Line" forms.

    The public Contact page (website:contact) is open to anonymous
    visitors; if the submitter is logged in, the message is linked to
    their account. The Vendor Guide page (vendors:guide) uses the same
    model but is vendor-only, so those rows also carry `source` and the
    submitting `vendor`.
    """

    class Source(models.TextChoices):
        CONTACT_PAGE = "contact", "Contact page"
        VENDOR_GUIDE = "vendor_guide", "Vendor guide"

    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.CONTACT_PAGE,
        help_text="Which form the message came from.",
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_messages",
        help_text=(
            "Set when the message was submitted by a vendor " "(vendors/guide)."
        ),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_messages",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_date"]

    def __str__(self):
        return f"{self.name} <{self.email}>"
