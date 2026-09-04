from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("invoice/", views.InvoiceView.as_view(), name="invoice"),
]
