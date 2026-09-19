from django.conf import settings
from django.db import models
from django.utils import timezone

__all__ = ["EmailVerificationCode"]


class EmailVerificationCode(models.Model):
    """
    The single outstanding 6-digit email-verification code for a user.

    One row per user (OneToOne): generating a new code -- via register or
    "Resend Code" -- replaces the previous row's hash/expiry/attempts in
    place, which is exactly "invalidate the old code" with no separate
    cleanup step. The raw code itself is never stored, only its hash
    (`code_hash`, written with Django's own password hasher), so reading
    the database never reveals a usable code.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_code",
    )
    code_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email verification code"
        verbose_name_plural = "Email verification codes"

    def __str__(self):
        return f"Verification code for user #{self.user_id}"

    def is_expired(self):
        return timezone.now() >= self.expires_at
