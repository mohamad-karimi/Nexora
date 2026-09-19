"""Composes and sends the account emails.

These functions talk to SMTP synchronously, so they must only be called
from the Celery worker (see accounts.tasks) -- never from a request.
The wording of both emails is unchanged from before the move to Celery.
"""

from django.core.mail import send_mail
from django.urls import reverse

from accounts.constants import EMAIL_OTP_EXP_MINUTES
from accounts.tokens import make_password_reset_token


def send_verification_email(user, code):
    """Emails the 6-digit email-verification code. No link, no token --
    just the code the user types into the Verify Your Email page."""
    send_mail(
        subject="Verify your Nexora account",
        message=(
            f"Hi {user.username},\n\n"
            "Use the verification code below to confirm your email "
            f"address and activate your Nexora account. This code "
            f"expires in {EMAIL_OTP_EXP_MINUTES} minutes and can only be "
            "used once.\n\n"
            f"Your verification code: {code}\n\n"
            "If you didn't create a Nexora account, you can ignore this email."
        ),
        from_email=None,  # falls back to DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(user, origin):
    """Emails the password-reset link.

    `origin` is the scheme + host the user reached the site on (for
    example "https://shop.example.com", no trailing slash), captured from
    the request when the email was queued. The reset token is created here,
    at send time, so it never has to travel through the task queue.
    """
    token = make_password_reset_token(user)
    path = reverse("accounts:reset_password")
    reset_url = f"{origin}{path}?token={token}"

    send_mail(
        subject="Reset your Nexora password",
        message=(
            f"Hi {user.username},\n\n"
            "We received a request to reset your Nexora account password. "
            "Open the link below to choose a new password. This link is "
            "valid for a limited time and can only be used once.\n\n"
            f"{reset_url}\n\n"
            "If you didn't request this, you can safely ignore this email -- "
            "your password will not be changed."
        ),
        from_email=None,
        recipient_list=[user.email],
        fail_silently=False,
    )
