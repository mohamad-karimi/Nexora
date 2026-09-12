from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.v1.views.accounts import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)
from api.v1.views.cart import CartItemViewSet, CartView
from api.v1.views.orders import AddressViewSet, CouponValidateView, OrderViewSet
from api.v1.views.shop import (
    CategoryViewSet,
    ProductViewSet,
    TagViewSet,
    WishlistViewSet,
)
from api.v1.views.vendors import VendorViewSet
from api.v1.views.website import ContactMessageView

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("products", ProductViewSet, basename="product")
router.register("vendors", VendorViewSet, basename="vendor")
router.register("wishlist", WishlistViewSet, basename="wishlist")
router.register("cart/items", CartItemViewSet, basename="cart-item")
router.register("addresses", AddressViewSet, basename="address")
router.register("orders", OrderViewSet, basename="order")

app_name = "api_v1"

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path(
        "auth/change-password/",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    path("cart/", CartView.as_view(), name="cart"),
    path(
        "coupons/validate/", CouponValidateView.as_view(), name="coupon-validate"
    ),
    path("contact/", ContactMessageView.as_view(), name="contact-message"),
    path("", include(router.urls)),
]
