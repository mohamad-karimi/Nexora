from django.conf import settings
from django.db import models


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
        help_text="Set when the message was submitted by a vendor (vendors/guide).",
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
