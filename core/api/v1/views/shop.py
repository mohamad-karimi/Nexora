from django.db.models import Avg, Count, Q
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.v1.filters import ProductFilter
from api.v1.permissions import IsVerified
from api.v1.serializers.shop import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    ReviewSerializer,
    TagSerializer,
    WishlistSerializer,
)
from shop.models import Category, Product, Review, Tag, Wishlist


@extend_schema_view(
    list=extend_schema(summary="List categories"),
    retrieve=extend_schema(
        summary="Get a category",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Catalog"])
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of product categories, with a live product count."""

    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count(
                "products", filter=Q(products__status=Product.Status.PUBLISHED)
            )
        ).order_by("name")


@extend_schema_view(
    list=extend_schema(summary="List tags"),
    retrieve=extend_schema(
        summary="Get a tag",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Catalog"])
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of product tags."""

    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    lookup_field = "slug"


@extend_schema_view(
    list=extend_schema(
        summary="List published products",
        description=(
            "Supports filtering by `category`/`vendor`/`tag` slug, a "
            "`min_price`/`max_price` range and `in_stock`; free-text "
            "search via `search`; and ordering via `ordering` "
            "(`price`, `created_date`, `name`, `average_rating`, prefix "
            "with `-` to reverse)."
        ),
    ),
    retrieve=extend_schema(
        summary="Get a product",
        description="Looked up by `slug`, not the numeric id. Returns the extended detail representation.",
    ),
)
@extend_schema(tags=["Catalog"])
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only browsing of published products, plus a nested `reviews` action."""

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

    @extend_schema(
        tags=["Reviews"],
        summary="List or submit reviews for a product",
        description=(
            "**GET**: paginated list of approved reviews for the product "
            "(an authenticated user also sees their own pending review, "
            "if any). Anonymous requests only see approved reviews.\n\n"
            "**POST**: requires authentication. Creates the current "
            "user's review for this product, or updates it if one "
            "already exists. New/updated reviews are unapproved "
            "(`is_approved=false`) until moderated."
        ),
        request=ReviewSerializer,
        responses={
            200: ReviewSerializer(many=True),
            201: ReviewSerializer,
            401: OpenApiResponse(
                description="Authentication required to leave a review.",
                examples=[
                    OpenApiExample(
                        "Anonymous POST",
                        value={"detail": "Authentication required to leave a review."},
                    )
                ],
            ),
        },
    )
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


@extend_schema_view(
    list=extend_schema(summary="List the current user's wishlist"),
    create=extend_schema(
        summary="Add a product to the wishlist",
        description="Idempotent: adding a product already on the wishlist just returns the existing entry.",
    ),
    destroy=extend_schema(summary="Remove a product from the wishlist"),
)
@extend_schema(tags=["Wishlist"])
class WishlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """List, add to, and remove products from the current user's wishlist."""

    serializer_class = WishlistSerializer
    permission_classes = [IsVerified]

    def get_queryset(self):
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related("product", "product__category", "product__vendor")
            .prefetch_related("product__tags")
            .order_by("-created_date")
        )
