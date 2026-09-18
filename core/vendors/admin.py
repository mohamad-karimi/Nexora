from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "store_name",
        "user",
        "phone",
        "is_approved",
        "created_date",
    )
    list_filter = ("is_approved",)
    search_fields = ("store_name", "user__username", "phone", "email")
    prepopulated_fields = {"slug": ("store_name",)}
    readonly_fields = ("created_date", "update_date")
