from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.views.generic import TemplateView


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


class ForgotPasswordView(TemplateView):
    template_name = "accounts/page-forgot-password.html"


class ResetPasswordView(TemplateView):
    template_name = "accounts/page-reset-password.html"
