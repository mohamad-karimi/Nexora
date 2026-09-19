from django.views.generic import TemplateView

from accounts.views import VerifiedRequiredMixin


class CartView(VerifiedRequiredMixin, TemplateView):
    template_name = "cart/shop-cart.html"
    login_url = "accounts:login"
