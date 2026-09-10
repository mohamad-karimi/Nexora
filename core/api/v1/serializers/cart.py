from rest_framework import serializers

from cart.models import Cart, CartItem
from shop.models import Product

from .shop import ProductListSerializer


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source="product",
        write_only=True,
        help_text="ID of the product to add/reference.",
    )
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text="Snapshot of the product's price at the time it was added.",
    )
    subtotal = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True,
        help_text="unit_price * quantity.",
    )

    class Meta:
        model = CartItem
        fields = [
            "id",
            "product",
            "product_id",
            "quantity",
            "unit_price",
            "subtotal",
        ]

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        product = attrs.get("product")
        quantity = attrs.get("quantity", 1)
        if product and product.stock < quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {product.stock} item(s) left in stock."}
            )
        return attrs

    def create(self, validated_data):
        cart = self.context["cart"]
        product = validated_data["product"]
        quantity = validated_data.get("quantity", 1)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={"quantity": quantity}
        )
        if not created:
            item.quantity += quantity
            if item.quantity > product.stock:
                item.quantity = product.stock
            item.save(update_fields=["quantity"])
        return item


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "items", "total_items", "subtotal", "update_date"]
