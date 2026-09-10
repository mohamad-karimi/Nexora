from django.db.models import Count, Q
from rest_framework import viewsets

from api.v1.serializers.vendors import VendorSerializer
from shop.models import Product
from vendors.models import Vendor


class VendorViewSet(viewsets.ReadOnlyModelViewSet):
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
