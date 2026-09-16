from django.urls import include, path
from rest_framework.routers import DefaultRouter

from api.v1.views.accounts import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
    ResendVerificationEmailView,
    ResetPasswordView,
)
from api.v1.views.blog import CategoryViewSet as BlogCategoryViewSet
from api.v1.views.blog import PostViewSet as BlogPostViewSet
from api.v1.views.blog import TagViewSet as BlogTagViewSet
from api.v1.views.cart import CartItemViewSet, CartView
from api.v1.views.orders import AddressViewSet, CouponValidateView, OrderViewSet
from api.v1.views.shop import (
    CategoryViewSet,
    ProductViewSet,
    TagViewSet,
    WishlistViewSet,
)
from api.v1.views.vendors import (
    VendorDashboardBestSellersView,
    VendorDashboardOrderItemsView,
    VendorDashboardProductsView,
    VendorViewSet,
)
from api.v1.views.website import (
    ContactMessageView,
    VendorGuideContactMessageView,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("tags", TagViewSet, basename="tag")
router.register("products", ProductViewSet, basename="product")
router.register("vendors", VendorViewSet, basename="vendor")
router.register("wishlist", WishlistViewSet, basename="wishlist")
router.register("cart/items", CartItemViewSet, basename="cart-item")
router.register("addresses", AddressViewSet, basename="address")
router.register("orders", OrderViewSet, basename="order")
router.register("blog/categories", BlogCategoryViewSet, basename="blog-category")
router.register("blog/tags", BlogTagViewSet, basename="blog-tag")
router.register("blog/posts", BlogPostViewSet, basename="blog-post")

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
    path(
        "auth/forgot-password/",
        ForgotPasswordView.as_view(),
        name="auth-forgot-password",
    ),
    path(
        "auth/resend-verification/",
        ResendVerificationEmailView.as_view(),
        name="auth-resend-verification",
    ),
    path(
        "auth/reset-password/",
        ResetPasswordView.as_view(),
        name="auth-reset-password",
    ),
    path("cart/", CartView.as_view(), name="cart"),
    path(
        "vendors/dashboard/products/",
        VendorDashboardProductsView.as_view(),
        name="vendor-dashboard-products",
    ),
    path(
        "vendors/dashboard/best-sellers/",
        VendorDashboardBestSellersView.as_view(),
        name="vendor-dashboard-best-sellers",
    ),
    path(
        "vendors/dashboard/orders/",
        VendorDashboardOrderItemsView.as_view(),
        name="vendor-dashboard-orders",
    ),
    path(
        "coupons/validate/", CouponValidateView.as_view(), name="coupon-validate"
    ),
    path("contact/", ContactMessageView.as_view(), name="contact-message"),
    path(
        "contact/vendor-guide/",
        VendorGuideContactMessageView.as_view(),
        name="contact-message-vendor-guide",
    ),
    path("", include(router.urls)),
]
