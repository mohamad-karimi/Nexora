from django.views.generic import TemplateView


# Create your views here.
class AccountView(TemplateView):
    template_name = "accounts/page-account.html"


class LoginView(TemplateView):
    template_name = "accounts/page-login.html"


class RegisterView(TemplateView):
    template_name = "accounts/page-register.html"


class ForgotPasswordView(TemplateView):
    template_name = "accounts/page-forgot-password.html"


class ResetPasswordView(TemplateView):
    template_name = "accounts/page-reset-password.html"
