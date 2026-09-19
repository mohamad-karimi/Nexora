from django.contrib import admin

from .models import (
    Category,
    Product,
    ProductImage,
    ProductSpecification,
    Review,
    Tag,
    Wishlist,
)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "created_date")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "vendor",
        "category",
        "price",
        "stock",
        "status",
        "published",
        "created_date",
    )
    list_editable = ("published",)
    list_filter = ("published", "status", "category", "vendor")
    search_fields = ("name", "sku")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("vendor", "category", "tags")
    inlines = [ProductImageInline, ProductSpecificationInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "score", "is_approved", "created_date")
    list_filter = ("is_approved", "score")
    search_fields = ("product__name", "user__username")


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_date")
    search_fields = ("user__username", "product__name")
