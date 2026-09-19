from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.permissions import IsVerified
from api.v1.serializers.orders import (
    AddressSerializer,
    CouponSerializer,
    CouponValidateSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from orders.models import Address, Coupon, Order


@extend_schema_view(
    list=extend_schema(summary="List the current user's addresses"),
    retrieve=extend_schema(summary="Get an address"),
    create=extend_schema(summary="Add a new address"),
    update=extend_schema(summary="Replace an address"),
    partial_update=extend_schema(summary="Update an address"),
    destroy=extend_schema(
        summary="Delete an address",
        description=(
            "Rejects the request with 400 if this is the user's only "
            "remaining address - every user must keep at least one."
        ),
    ),
)
@extend_schema(tags=["Addresses"])
class AddressViewSet(viewsets.ModelViewSet):
    """Full CRUD over the current user's shipping/billing addresses."""

    serializer_class = AddressSerializer
    permission_classes = [IsVerified]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        self.get_object()  # 404s if this address isn't the current user's
        if Address.objects.filter(user=request.user).count() <= 1:
            return Response(
                {
                    "detail": (
                        "Please add another address before "
                        "deleting your current address."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(tags=["Coupons"])
class CouponValidateView(APIView):
    """POST {"code": "..."} -> whether the coupon can currently be used."""

    permission_classes = [IsVerified]

    @extend_schema(
        summary="Validate a coupon code",
        description=(
            "Looks up a coupon by its code (case-insensitive) and returns "
            "its details, including whether it is currently usable "
            "(`is_valid`). Does not apply the coupon; that happens at "
            "checkout via `POST /api/v1/orders/` with `coupon_code`."
        ),
        request=CouponValidateSerializer,
        responses={
            200: CouponSerializer,
            404: OpenApiResponse(
                description="No coupon exists with that code.",
                examples=[
                    OpenApiExample(
                        "Not found",
                        value={
                            "detail": "Invalid coupon code.",
                            "is_valid": False,
                        },
                    )
                ],
            ),
        },
    )
    def post(self, request):
        code = request.data.get("code", "")
        try:
            coupon = Coupon.objects.get(code__iexact=code)
        except Coupon.DoesNotExist:
            return Response(
                {"detail": "Invalid coupon code.", "is_valid": False},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CouponSerializer(coupon).data)


@extend_schema_view(
    list=extend_schema(
        summary="List the current user's orders",
        description=(
            "Returns the current user's order history, most " "recent first."
        ),
    ),
    retrieve=extend_schema(
        summary="Get an order",
        description="Looked up by `order_number`, not the numeric id.",
    ),
    create=extend_schema(
        summary="Checkout: create an order from the current cart",
        description=(
            "Converts the current user's cart into an order. The cart "
            "must not be empty and every line item must still be within "
            "available stock. On success the cart is emptied, stock is "
            "decremented, and a pending `Payment` record is created."
        ),
        request=OrderCreateSerializer,
        responses={201: OrderSerializer},
    ),
)
@extend_schema(tags=["Orders"])
class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only access to the current user's orders, plus
    checkout via `create`.
    """

    lookup_field = "order_number"
    permission_classes = [IsVerified]

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .select_related("shipping_address", "billing_address", "coupon")
            .prefetch_related("items__product", "items__vendor", "payments")
        )

    def get_serializer_class(self):
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderSerializer(order).data, status=status.HTTP_201_CREATED
        )
