from django.views.generic import TemplateView

from accounts.views import VerifiedRequiredMixin


class CheckoutView(VerifiedRequiredMixin, TemplateView):
    template_name = "orders/shop-checkout.html"
    login_url = "accounts:login"


class InvoiceView(VerifiedRequiredMixin, TemplateView):
    """
    Renders the page shell only; the order itself is fetched
    client-side from /api/v1/orders/<order_number>/ using the
    order_number taken from the URL (passed through as plain context,
    never a queryset/model instance).
    """

    template_name = "orders/shop-invoice-1.html"
    login_url = "accounts:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order_number"] = self.kwargs["order_number"]
        return context
