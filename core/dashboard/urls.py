from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path(
        "product/<slug:slug>/edit/",
        views.ProductEditView.as_view(),
        name="product-edit",
    ),
]
