from rest_framework import serializers

from orders.models import OrderItem
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


class VendorOrderItemSerializer(serializers.ModelSerializer):
    """
    A single order line item, as shown in the "Recent Orders" table of
    the Vendor Dashboard. Flattens the bits of the parent Order that
    the table needs (number/status/date) so the frontend doesn't have
    to fetch the order separately.
    """

    order_number = serializers.CharField(source="order.order_number", read_only=True)
    order_status = serializers.CharField(source="order.status", read_only=True)
    order_date = serializers.DateTimeField(source="order.created_date", read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order_number",
            "order_status",
            "order_date",
            "product_name",
            "quantity",
            "unit_price",
            "total_price",
        ]
