from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("invoice/<str:order_number>/", views.InvoiceView.as_view(), name="invoice"),
]
