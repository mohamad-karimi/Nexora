from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.permissions import IsVerified
from api.v1.serializers.cart import CartItemSerializer, CartSerializer
from cart.models import Cart, CartItem


def get_or_create_cart(user):
    cart, _created = Cart.objects.get_or_create(user=user)
    return cart


@extend_schema(tags=["Cart"])
class CartView(APIView):
    """Current user's cart: GET to view it, DELETE to empty it."""

    permission_classes = [IsVerified]

    @extend_schema(
        summary="Get the current user's cart",
        description=(
            "Returns the current user's cart, creating an "
            "empty one if none exists yet."
        ),
        responses={200: CartSerializer},
    )
    def get(self, request):
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    @extend_schema(
        summary="Empty the cart",
        description="Removes every item from the current user's cart.",
        request=None,
        responses={200: CartSerializer},
    )
    def delete(self, request):
        cart = get_or_create_cart(request.user)
        cart.items.all().delete()
        return Response(CartSerializer(cart).data)


@extend_schema_view(
    create=extend_schema(
        summary="Add an item to the cart",
        description=(
            "Adds `product_id` to the current user's cart. If the product "
            "is already in the cart, `quantity` is added to the existing "
            "line item instead of creating a duplicate one (capped at the "
            "available stock). Returns the whole updated cart."
        ),
        responses={201: CartSerializer},
    ),
    update=extend_schema(
        summary="Replace a cart item's quantity",
        responses={200: CartSerializer},
    ),
    partial_update=extend_schema(
        summary="Update a cart item's quantity",
        description=(
            "Partially updates a cart line item (typically " "just `quantity`)."
        ),
        responses={200: CartSerializer},
    ),
    destroy=extend_schema(
        summary="Remove an item from the cart",
        responses={200: CartSerializer},
    ),
)
@extend_schema(tags=["Cart"])
class CartItemViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Create/update/delete individual line items of the
    current user's cart.
    """

    serializer_class = CartItemSerializer
    permission_classes = [IsVerified]

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["cart"] = get_or_create_cart(self.request.user)
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        cart = get_or_create_cart(request.user)
        return Response(CartSerializer(cart).data)
