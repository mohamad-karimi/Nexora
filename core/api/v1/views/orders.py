from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers.orders import (
    AddressSerializer,
    CouponSerializer,
    OrderCreateSerializer,
    OrderSerializer,
)
from orders.models import Address, Coupon, Order


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class CouponValidateView(APIView):
    """POST {"code": "..."} -> whether the coupon can currently be used."""

    permission_classes = [IsAuthenticated]

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


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "order_number"
    permission_classes = [IsAuthenticated]

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
