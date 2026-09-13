from django.core.mail import send_mail
from django.urls import reverse

from accounts.tokens import make_email_verification_token, make_password_reset_token


def send_verification_email(request, user):
    token = make_email_verification_token(user)
    path = reverse("accounts:verify_email", kwargs={"token": token})
    verify_url = request.build_absolute_uri(path)

    send_mail(
        subject="Verify your Nexora account",
        message=(
            f"Hi {user.username},\n\n"
            "Please confirm your email address by opening the link below. "
            "This link is valid for a limited time.\n\n"
            f"{verify_url}\n\n"
            "If you didn't create a Nexora account, you can ignore this email."
        ),
        from_email=None,  # falls back to DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        fail_silently=False,
    )


def send_password_reset_email(request, user):
    token = make_password_reset_token(user)
    path = reverse("accounts:reset_password")
    reset_url = request.build_absolute_uri(f"{path}?token={token}")

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
