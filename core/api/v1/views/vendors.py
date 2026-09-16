from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from api.v1.pagination import StandardPagination
from api.v1.permissions import IsVendor, IsVerified
from api.v1.serializers.shop import (
    ProductCreateSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
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
                "products", filter=Q(products__published=True)
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


@extend_schema_view(
    get=extend_schema(
        summary="List your products",
        description="Paginated list of the current vendor's own products (any status), for the Vendor Dashboard's \"Your Products\" grid.",
    ),
    post=extend_schema(
        summary="Create a product",
        description=(
            "Creates a new product owned by the current vendor. The "
            "`vendor` is always taken from the authenticated user's own "
            "vendor profile -- it is not a field on this endpoint, so a "
            "vendor can never create a product for someone else's store."
        ),
        request=ProductCreateSerializer,
        responses={201: ProductDetailSerializer},
    ),
)
@extend_schema(tags=["Vendors"])
class VendorDashboardProductsView(VendorDashboardMixin, generics.ListCreateAPIView):
    """
    GET: paginated list of the current vendor's own products (any
    status), for the Vendor Dashboard's "Your Products" grid.

    POST: lets a vendor create a new product for their own store from
    the Vendor Account's "Add Product" panel.
    """

    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProductCreateSerializer
        return ProductListSerializer

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

    def perform_create(self, serializer):
        # The vendor is resolved from the authenticated user's own
        # Vendor row -- never from request data -- so this is the one
        # and only place `vendor` gets set on a vendor-created product.
        vendor = self.get_vendor()
        if vendor is None:
            raise PermissionDenied(
                "Your account does not have a vendor profile yet."
            )
        serializer.save(vendor=vendor)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output_serializer = ProductDetailSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(output_serializer.data)
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )


@extend_schema_view(
    get=extend_schema(
        summary="Get one of your products",
        description=(
            "Looked up by `slug`, scoped to the current vendor's own "
            "products only (same resolution as the list above) -- a "
            "slug belonging to another vendor's product 404s exactly "
            "like an unknown slug would, for the Vendor Dashboard's "
            "Edit Product page."
        ),
        responses={200: ProductCreateSerializer},
    ),
    put=extend_schema(
        summary="Update one of your products",
        description=(
            "Full update of a product owned by the current vendor. "
            "`vendor` and `published` are not fields on this endpoint "
            "-- the product stays owned by the same vendor, and its "
            "`published` status is left untouched, no matter what the "
            "request body contains. Only staff/admin can change "
            "`published`, from Django Admin."
        ),
        request=ProductCreateSerializer,
        responses={200: ProductDetailSerializer},
    ),
    patch=extend_schema(
        summary="Partially update one of your products",
        request=ProductCreateSerializer,
        responses={200: ProductDetailSerializer},
    ),
)
@extend_schema(tags=["Vendors"])
class VendorDashboardProductDetailView(
    VendorDashboardMixin, generics.RetrieveUpdateAPIView
):
    """
    GET/PUT/PATCH a single product owned by the current vendor, for
    the Vendor Dashboard's Edit Product page.

    Reuses ProductCreateSerializer -- the same fields the Create
    Product form uses, minus `vendor` and `published` -- so a vendor
    can never reassign a product to another store or publish it from
    this endpoint, exactly like VendorDashboardProductsView.create()
    above. Ownership is enforced by scoping get_queryset() to the
    requester's own vendor: a slug that exists but belongs to a
    different vendor's product simply isn't in that queryset, so it
    404s the same way a nonexistent slug would, instead of leaking a
    403 that would confirm the slug is real.
    """

    serializer_class = ProductCreateSerializer
    lookup_field = "slug"

    def get_queryset(self):
        vendor = self.get_vendor()
        if vendor is None:
            return Product.objects.none()
        return (
            Product.objects.filter(vendor=vendor)
            .select_related("category", "vendor")
            .prefetch_related("tags")
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        # ModelSerializer.update() only ever touches the fields declared
        # on ProductCreateSerializer, so `vendor` and `published` are
        # never among validated_data -- this can't move the product to
        # another vendor or change its approval state, whatever the
        # request body contains.
        self.perform_update(serializer)
        output_serializer = ProductDetailSerializer(
            serializer.instance, context=self.get_serializer_context()
        )
        return Response(output_serializer.data)


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
