from django.db.models import Avg, Count, Q
from django.http import Http404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
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
                "products", filter=Q(products__published=True)
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
            "(`price`, `created_date`, `name`, `average_rating`, "
            "`discount_percent`, prefix with `-` to reverse)."
        ),
    ),
    retrieve=extend_schema(
        summary="Get a product",
        description="Looked up by `slug`, not the numeric id. Returns the extended detail representation.",
    ),
)
@extend_schema(tags=["Catalog"])
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only browsing of products, plus a nested `reviews` action.

    Listing (and every other list-style access -- category/tag/vendor
    filtering, search, ordering) only ever returns `published=True`
    products, so an unapproved product never shows up in the Shop,
    category/list pages, search, or related-products.

    Looking up a single product by slug (`retrieve`, and the nested
    `reviews` action) is a little more permissive: the product's own
    vendor and staff/admin can open it even while it's unpublished --
    e.g. right after creating it from the Vendor Dashboard, before an
    admin has approved it -- via get_object() below. Everyone else
    gets the same 404 a nonexistent slug would, so an unpublished
    product's existence is never revealed to the public or to a
    vendor who doesn't own it.
    """

    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ["name", "short_description", "description", "sku"]
    ordering_fields = [
        "price",
        "created_date",
        "name",
        "average_rating",
        "discount_percent",
    ]
    ordering = ["-created_date"]

    def get_queryset(self):
        queryset = (
            Product.objects.select_related("category", "vendor")
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
        if self.action == "list":
            queryset = queryset.filter(published=True)
        return queryset

    def get_object(self):
        queryset = self.filter_queryset(self.get_queryset())
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        obj = get_object_or_404(queryset, slug=self.kwargs[lookup_url_kwarg])

        if not obj.published and not self._can_view_unpublished(obj):
            # Same 404 an unknown slug would give -- an unpublished
            # product's existence isn't revealed to anyone but its
            # owner/staff.
            raise Http404(
                f"No {queryset.model._meta.object_name} matches the given query."
            )

        self.check_object_permissions(self.request, obj)
        return obj

    def _can_view_unpublished(self, product):
        user = self.request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_staff or user.is_superuser:
            return True
        vendor = getattr(user, "vendor_profile", None)
        return vendor is not None and product.vendor_id == vendor.id

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
