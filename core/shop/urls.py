from django.urls import path
from . import views

app_name = "shop"

urlpatterns = [
    path("compare/", views.CompareView.as_view(), name="compare"),
    path("filter/", views.FilterView.as_view(), name="filter"),
    path("grid-left/", views.GridLeftView.as_view(), name="grid_left"),
    path("product/", views.ProductFullView.as_view(), name="product_detail"),
    path("wishlist/", views.WishlistView.as_view(), name="wishlist"),
]
