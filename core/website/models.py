from django.conf import settings
from django.db import models


class ContactMessage(models.Model):
    """
    A message submitted through the "Drop Us a Line" form on the
    Contact page (website:contact). Open to anonymous visitors; if the
    submitter is logged in, the message is linked to their account.
    """

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
