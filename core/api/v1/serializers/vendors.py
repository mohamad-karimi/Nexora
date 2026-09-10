from rest_framework import serializers

from vendors.models import Vendor


class VendorSerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "store_name",
            "slug",
            "logo",
            "description",
            "phone",
            "email",
            "address",
            "product_count",
            "created_date",
        ]
