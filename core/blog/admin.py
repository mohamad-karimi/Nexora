from django.contrib import admin

from blog.models import Category, Post


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "author", "status", "created_date")
    list_filter = ("status", "category")
    search_fields = ("title", "excerpt", "content")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category",)
