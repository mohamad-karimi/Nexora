from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers.cart import CartItemSerializer, CartSerializer
from cart.models import Cart, CartItem


def get_or_create_cart(user):
    cart, _created = Cart.objects.get_or_create(user=user)
    return cart


class CartView(APIView):
    """Current user's cart: GET to view it, DELETE to empty it."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


class CartItemViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["cart"] = get_or_create_cart(self.request.user)
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)
