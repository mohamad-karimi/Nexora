from django.db import IntegrityError
from rest_framework import serializers

from shop.models import (
    Category,
    Product,
    ProductImage,
    ProductSpecification,
    Review,
    Tag,
    Wishlist,
)
from vendors.models import Vendor


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "description",
            "parent",
            "product_count",
        ]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class VendorMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "store_name", "slug", "logo"]


class CategoryMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ["id", "image", "alt_text", "is_primary", "ordering"]


class ProductSpecificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpecification
        fields = ["id", "name", "value", "ordering"]


class ReviewSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "user_display_name",
            "score",
            "comment",
            "is_approved",
            "created_date",
        ]
        read_only_fields = ["id", "product", "is_approved", "created_date"]

    def get_user_display_name(self, obj):
        display_name = (
            getattr(obj.user, "profile", None) and obj.user.profile.display_name
        )
        return display_name or obj.user.username


class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight representation used for listing/grid pages."""

    category = CategoryMinimalSerializer(read_only=True)
    vendor = VendorMinimalSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    final_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    is_on_sale = serializers.BooleanField(read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    average_rating = serializers.FloatField(read_only=True, default=None)
    review_count = serializers.IntegerField(read_only=True, default=0)
    is_wishlisted = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "name",
            "short_description",
            "category",
            "vendor",
            "tags",
            "price",
            "final_price",
            "discount_percent",
            "is_on_sale",
            "stock",
            "in_stock",
            "image",
            "average_rating",
            "review_count",
            "is_wishlisted",
        ]

    def get_is_wishlisted(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        wishlisted_ids = self.context.get("wishlisted_ids")
        if wishlisted_ids is None:
            wishlisted_ids = set(
                Wishlist.objects.filter(user=request.user).values_list(
                    "product_id", flat=True
                )
            )
            self.context["wishlisted_ids"] = wishlisted_ids
        return obj.id in wishlisted_ids


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description",
            "sku",
            "product_type",
            "manufacture_date",
            "shelf_life_days",
            "images",
            "specifications",
            "created_date",
        ]


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Used by vendors to create their own product from the Vendor
    Dashboard's "Your Products" panel (see
    api.v1.views.vendors.VendorDashboardProductsView).

    `vendor` is intentionally *not* one of the fields below: the view
    sets it from the authenticated user's own `vendor_profile`, so
    nothing in the request body can ever assign the product to a
    different vendor. `slug` is left to `Product.save()`, which fills
    it in from `name` when blank.
    """

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "short_description",
            "description",
            "sku",
            "price",
            "discount_percent",
            "discount_end",
            "stock",
            "image",
            "product_type",
            "manufacture_date",
            "shelf_life_days",
            "status",
            "color",
            "condition",
        ]
        read_only_fields = ["id", "slug"]


class WishlistSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source="product", write_only=True
    )

    class Meta:
        model = Wishlist
        fields = ["id", "product", "product_id", "created_date"]
        read_only_fields = ["id", "created_date"]

    def create(self, validated_data):
        user = self.context["request"].user
        try:
            instance, _created = Wishlist.objects.get_or_create(
                user=user, product=validated_data["product"]
            )
        except IntegrityError:
            instance = Wishlist.objects.get(
                user=user, product=validated_data["product"]
            )
        return instance
