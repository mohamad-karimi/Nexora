import random

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView

from accounts.constants import SECURITY_CODE_SESSION_KEY


class AccountView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/page-account.html"
    login_url = "accounts:login"


class RedirectIfAuthenticatedMixin:
    """Sends already-logged-in visitors away from login/register pages."""

    authenticated_redirect_url = "accounts:account"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.authenticated_redirect_url)
        return super().get(request, *args, **kwargs)


class LoginView(RedirectIfAuthenticatedMixin, TemplateView):
    template_name = "accounts/page-login.html"


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


class ResetPasswordView(TemplateView):
    template_name = "accounts/page-reset-password.html"
