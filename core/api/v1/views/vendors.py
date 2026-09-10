from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from api.v1.serializers.vendors import VendorSerializer
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
