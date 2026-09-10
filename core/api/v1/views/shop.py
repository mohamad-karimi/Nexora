from django.db.models import Avg, Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.v1.filters import ProductFilter
from api.v1.serializers.shop import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewSerializer,
    TagSerializer,
    WishlistSerializer,
)
from shop.models import Category, Product, Review, Tag, Wishlist


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count(
                "products", filter=Q(products__status=Product.Status.PUBLISHED)
            )
        ).order_by("name")


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    lookup_field = "slug"


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "short_description", "description", "sku"]
    ordering_fields = ["price", "created_date", "name", "average_rating"]
    ordering = ["-created_date"]

    def get_queryset(self):
        return (
            Product.objects.filter(status=Product.Status.PUBLISHED)
            .select_related("category", "vendor")
            .prefetch_related("tags", "images", "specifications")
            .annotate(
                average_rating=Avg(
                    "reviews__score", filter=Q(reviews__is_approved=True)
                ),
                review_count=Count(
                    "reviews", filter=Q(reviews__is_approved=True), distinct=True
                ),
            )
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

    @action(detail=True, methods=["get", "post"], url_path="reviews")
    def reviews(self, request, slug=None):
        product = self.get_object()

        if request.method == "GET":
            queryset = product.reviews.select_related("user__profile")
            if not (request.user.is_authenticated):
                queryset = queryset.filter(is_approved=True)
            else:
                queryset = queryset.filter(
                    Q(is_approved=True) | Q(user=request.user)
                )
            page = self.paginate_queryset(queryset.order_by("-created_date"))
            serializer = ReviewSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to leave a review."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review, _created = Review.objects.update_or_create(
            user=request.user,
            product=product,
            defaults={
                "score": serializer.validated_data["score"],
                "comment": serializer.validated_data.get("comment", ""),
                "is_approved": False,
            },
        )
        return Response(
            ReviewSerializer(review).data, status=status.HTTP_201_CREATED
        )


class WishlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related("product", "product__category", "product__vendor")
            .prefetch_related("product__tags")
            .order_by("-created_date")
        )
