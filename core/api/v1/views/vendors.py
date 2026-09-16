from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, viewsets

from api.v1.pagination import StandardPagination
from api.v1.permissions import IsVendor, IsVerified
from api.v1.serializers.shop import ProductListSerializer
from api.v1.serializers.vendors import VendorOrderItemSerializer, VendorSerializer
from orders.models import Order, OrderItem
from shop.models import Product
from vendors.models import Vendor


@extend_schema_view(
    list=extend_schema(
        summary="List approved vendors",
        description=(
            "Supports free-text search via `search` (matches store name "
            "and description) and ordering via `ordering` "
            "(`store_name`, `created_date`, `product_count`, prefix with "
            "`-` to reverse)."
        ),
    ),
    retrieve=extend_schema(
        summary="Get a vendor",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Vendors"])
class VendorViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of approved marketplace vendors."""

    serializer_class = VendorSerializer
    lookup_field = "slug"
    search_fields = ["store_name", "description"]
    ordering_fields = ["store_name", "created_date", "product_count"]
    ordering = ["store_name"]

    def get_queryset(self):
        return Vendor.objects.filter(is_approved=True).annotate(
            product_count=Count(
                "products", filter=Q(products__status=Product.Status.PUBLISHED)
            )
        )


class VendorDashboardMixin:
    """
    Shared bits for the three Vendor Dashboard read endpoints below:
    restricted to verified vendor accounts, and resolved against the
    requester's own Vendor row (never a vendor slug from the URL, so
    a vendor can never end up looking at someone else's data).
    """

    permission_classes = [IsVerified, IsVendor]

    def get_vendor(self):
        return getattr(self.request.user, "vendor_profile", None)


@extend_schema(tags=["Vendors"])
class VendorDashboardProductsView(VendorDashboardMixin, generics.ListAPIView):
    """Paginated list of the current vendor's own products (any status), for the Vendor Dashboard's "Your Products" grid."""

    serializer_class = ProductListSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        vendor = self.get_vendor()
        if vendor is None:
            return Product.objects.none()
        return (
            Product.objects.filter(vendor=vendor)
            .select_related("category", "vendor")
            .prefetch_related("tags")
            .annotate(
                average_rating=Avg(
                    "reviews__score", filter=Q(reviews__is_approved=True)
                ),
                review_count=Count(
                    "reviews", filter=Q(reviews__is_approved=True), distinct=True
                ),
            )
            .order_by("-created_date")
        )


@extend_schema(tags=["Vendors"])
class VendorDashboardBestSellersView(VendorDashboardMixin, generics.ListAPIView):
    """The current vendor's top 3 products by units sold, for the Vendor Dashboard sidebar."""

    serializer_class = ProductListSerializer
    pagination_class = None

    def get_queryset(self):
        vendor = self.get_vendor()
        if vendor is None:
            return Product.objects.none()
        return (
            Product.objects.filter(vendor=vendor)
            .select_related("category", "vendor")
            .prefetch_related("tags")
            .annotate(
                average_rating=Avg(
                    "reviews__score", filter=Q(reviews__is_approved=True)
                ),
                review_count=Count(
                    "reviews", filter=Q(reviews__is_approved=True), distinct=True
                ),
                units_sold=Coalesce(
                    Sum(
                        "order_items__quantity",
                        filter=~Q(order_items__order__status=Order.Status.CANCELLED),
                    ),
                    0,
                ),
            )
            .order_by("-units_sold", "-created_date")[:3]
        )


@extend_schema(tags=["Vendors"])
class VendorDashboardOrderItemsView(VendorDashboardMixin, generics.ListAPIView):
    """Paginated order line items for the current vendor's own products, most recent first."""

    serializer_class = VendorOrderItemSerializer
    pagination_class = StandardPagination

    def get_queryset(self):
        vendor = self.get_vendor()
        if vendor is None:
            return OrderItem.objects.none()
        return (
            OrderItem.objects.filter(vendor=vendor)
            .select_related("order")
            .order_by("-order__created_date")
        )
