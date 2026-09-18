from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from orders.models import Address, Coupon, Order, OrderItem, Payment
from vendors.models import Vendor

FLAT_SHIPPING_COST = Decimal("5.00")
FREE_SHIPPING_THRESHOLD = Decimal("50.00")


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            "id",
            "address_type",
            "full_name",
            "phone",
            "country",
            "city",
            "postal_code",
            "address_line1",
            "address_line2",
            "company",
            "additional_information",
            "is_default",
            "created_date",
            "update_date",
        ]
        read_only_fields = ["id", "created_date", "update_date"]

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class CouponSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Coupon
        fields = ["code", "discount_percent", "valid_to", "is_valid"]


class CouponValidateSerializer(serializers.Serializer):
    """Request body for `POST /api/v1/coupons/validate/` (schema/docs only)."""

    code = serializers.CharField(
        help_text="The coupon code to look up (case-insensitive)."
    )


class OrderItemVendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "store_name", "slug"]


class OrderItemSerializer(serializers.ModelSerializer):
    vendor = OrderItemVendorSerializer(read_only=True)
    product_slug = serializers.SlugField(
        source="product.slug", read_only=True
    )
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product",
            "product_slug",
            "product_name",
            "vendor",
            "quantity",
            "unit_price",
            "total_price",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "payment_method",
            "status",
            "paid_at",
            "created_date",
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    billing_address = AddressSerializer(read_only=True)
    coupon = CouponSerializer(read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "shipping_address",
            "billing_address",
            "coupon",
            "subtotal",
            "shipping_cost",
            "discount_amount",
            "total_amount",
            "tracking_code",
            "items",
            "payments",
            "created_date",
            "update_date",
        ]


class OrderCreateSerializer(serializers.Serializer):
    """
    Checkout: turns the current user's cart into an Order. Read the
    result back through OrderSerializer.
    """

    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all(),
        help_text="ID of one of the current user's addresses to ship to.",
    )
    billing_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.all(),
        required=False,
        allow_null=True,
        help_text=(
            "ID of the billing address. Defaults to the "
            "shipping address when omitted."
        ),
    )
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=(
            "Optional discount coupon code, validated and "
            "applied at checkout."
        ),
    )
    payment_method = serializers.ChoiceField(
        choices=Payment.Method.choices,
        default=Payment.Method.CARD,
        help_text="How the order will be paid for.",
    )

    def validate_shipping_address_id(self, address):
        self._check_owner(address)
        return address

    def validate_billing_address_id(self, address):
        if address is not None:
            self._check_owner(address)
        return address

    def _check_owner(self, address):
        request = self.context["request"]
        if address.user_id != request.user.id:
            raise serializers.ValidationError(
                "That address does not belong to you."
            )

    def validate(self, attrs):
        request = self.context["request"]
        cart = getattr(request.user, "cart", None)
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Your cart is empty.")

        for item in cart.items.select_related("product"):
            if item.quantity > item.product.stock:
                raise serializers.ValidationError(
                    f"Only {item.product.stock} of "
                    f'"{item.product.name}" left in stock.'
                )

        coupon = None
        code = attrs.get("coupon_code")
        if code:
            try:
                coupon = Coupon.objects.get(code__iexact=code)
            except Coupon.DoesNotExist:
                raise serializers.ValidationError(
                    {"coupon_code": "Invalid coupon code."}
                )
            if not coupon.is_valid:
                raise serializers.ValidationError(
                    {"coupon_code": "This coupon is not valid right now."}
                )

        attrs["cart"] = cart
        attrs["coupon"] = coupon
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        cart = validated_data["cart"]
        coupon = validated_data["coupon"]
        shipping_address = validated_data["shipping_address_id"]
        billing_address = (
            validated_data.get("billing_address_id") or shipping_address
        )
        payment_method = validated_data["payment_method"]
        user = self.context["request"].user

        cart_items = list(cart.items.select_related("product"))
        subtotal = sum((item.subtotal for item in cart_items), Decimal("0"))
        shipping_cost = (
            Decimal("0")
            if subtotal >= FREE_SHIPPING_THRESHOLD
            else FLAT_SHIPPING_COST
        )
        discount_amount = Decimal("0")
        if coupon:
            discount_amount = (
                subtotal * coupon.discount_percent / 100
            ).quantize(Decimal("0.01"))
        total_amount = subtotal + shipping_cost - discount_amount

        order = Order.objects.create(
            user=user,
            shipping_address=shipping_address,
            billing_address=billing_address,
            coupon=coupon,
            shipping_cost=shipping_cost,
            discount_amount=discount_amount,
            total_amount=total_amount,
            status=Order.Status.PENDING,
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            item.product.stock = max(item.product.stock - item.quantity, 0)
            item.product.save(update_fields=["stock"])

        if coupon:
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

        Payment.objects.create(
            order=order,
            amount=total_amount,
            payment_method=payment_method,
            status=Payment.Status.PENDING,
        )

        cart.items.all().delete()

        return order
