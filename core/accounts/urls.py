from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("account/", views.AccountView.as_view(), name="account"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("forgot-password/", views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
    path("verify-email/<str:token>/", views.VerifyEmailView.as_view(), name="verify_email"),
]
