from django.views.generic import TemplateView


# Create your views here.
class CheckoutView(TemplateView):
    template_name = "orders/shop-checkout.html"


class InvoiceView(TemplateView):
    template_name = "orders/shop-invoice-1.html"
