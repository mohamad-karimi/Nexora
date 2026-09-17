import random

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.generic import TemplateView

from accounts.constants import (
    EMAIL_VERIFICATION_SESSION_KEY,
    LOGIN_SECURITY_CODE_SESSION_KEY,
    SECURITY_CODE_SESSION_KEY,
)
from accounts.tokens import TokenError, get_user_for_password_reset_token

User = get_user_model()


class VerifiedRequiredMixin(LoginRequiredMixin):
    """
    Like LoginRequiredMixin, but also refuses an authenticated-yet-
    unverified visitor (e.g. a session that predates this check, or
    one created some other way). Login itself already won't start a
    session for an unverified account, so in the normal flow this is
    a defense-in-depth backstop rather than the primary gate -- but it
    keeps every "inside the account" page consistent with the API.
    """

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_verified:
            return redirect("accounts:email_verification_pending")
        return super().dispatch(request, *args, **kwargs)


class VendorRequiredMixin(VerifiedRequiredMixin):
    """
    Page-level counterpart of the API's IsVendor permission: the view is
    only rendered for an authenticated, verified account whose database
    role is Vendor.

    An anonymous visitor is sent to the login page by LoginRequiredMixin;
    a logged-in non-vendor gets a real 403 from the server, so the page is
    never delivered to the browser at all.
    """

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if (
            user.is_authenticated
            and user.is_verified
            and user.role != User.Role.VENDOR
        ):
            raise PermissionDenied("This page is only available to vendor accounts.")
        # Anonymous -> login redirect, unverified -> verification page,
        # both handled by the mixins above.
        return super().dispatch(request, *args, **kwargs)


class AccountView(VerifiedRequiredMixin, TemplateView):
    """
    Same template for every verified role; the template itself hides
    the customer-only tabs (Orders/Track/Address) and points
    "Dashboard" at the real Vendor Dashboard when `is_vendor` is set,
    so a vendor never has to pick a different page manually.
    """

    template_name = "accounts/page-account.html"
    login_url = "accounts:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["is_vendor"] = self.request.user.role == User.Role.VENDOR
        return context


class RedirectIfAuthenticatedMixin:
    """Sends already-logged-in visitors away from login/register pages."""

    authenticated_redirect_url = "accounts:account"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not request.user.is_verified:
                return redirect("accounts:email_verification_pending")
            return redirect(self.authenticated_redirect_url)
        return super().get(request, *args, **kwargs)


class LoginView(RedirectIfAuthenticatedMixin, TemplateView):
    template_name = "accounts/page-login.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Same pattern as RegisterView below: a fresh code is generated on
        # every page load and stored server-side (session) so it can be
        # validated for real -- not just cosmetically -- when the form is
        # submitted.
        code = f"{random.randint(0, 9999):04d}"
        self.request.session[LOGIN_SECURITY_CODE_SESSION_KEY] = code
        context["security_code"] = code
        return context


class RegisterView(RedirectIfAuthenticatedMixin, TemplateView):
    template_name = "accounts/page-register.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # A fresh code is generated on every page load and stored server-side
        # (session) so it can be validated for real when the form is submitted.
        code = f"{random.randint(0, 9999):04d}"
        self.request.session[SECURITY_CODE_SESSION_KEY] = code
        context["security_code"] = code
        return context


class ForgotPasswordView(TemplateView):
    template_name = "accounts/page-forgot-password.html"


class EmailVerificationPendingView(TemplateView):
    """
    "Verify Your Email" page for a just-registered (unverified,
    not-logged-in) user: enter the 6-digit code emailed to them.

    Only reachable while this browser session has a pending
    verification (set by POST /api/v1/auth/register/, see
    accounts.otp.start_email_verification) -- anyone else (direct visit,
    expired session, already verified) has nothing to submit against
    here and is redirected instead.
    """

    template_name = "accounts/page-email-verification-pending.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_verified:
            return redirect("accounts:account")
        if not request.session.get(EMAIL_VERIFICATION_SESSION_KEY):
            return redirect("accounts:register")
        return super().get(request, *args, **kwargs)


class ResetPasswordView(TemplateView):
    """
    /reset-password/ is not usable on its own: it only renders the actual
    "set new password" form when a valid, non-expired, not-yet-used JWT
    for a real user is supplied as ?token=... . Any other visit (no token,
    garbage token, expired token, tampered user id, already-used token)
    gets a "this link isn't valid" state instead of the form -- the token
    is re-validated independently by the API when the form is submitted,
    so this page-level check is a UX nicety, not the security boundary.
    """

    template_name = "accounts/page-reset-password.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        token = self.request.GET.get("token", "")
        try:
            get_user_for_password_reset_token(token)
        except TokenError as exc:
            context["token_valid"] = False
            context["token_error"] = str(exc)
        else:
            context["token_valid"] = True
            context["token"] = token
        return context
