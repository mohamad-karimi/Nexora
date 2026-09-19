from django.contrib import admin

from .models import Address, Coupon, Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product", "vendor")
    readonly_fields = ("product_name",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "user",
        "city",
        "country",
        "address_type",
        "is_default",
    )
    list_filter = ("address_type", "is_default", "country")
    search_fields = ("full_name", "city", "country", "user__username")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_percent",
        "valid_from",
        "valid_to",
        "is_active",
        "used_count",
        "usage_limit",
    )
    search_fields = ("code",)
    list_filter = ("is_active",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "user",
        "status",
        "total_amount",
        "created_date",
    )
    list_filter = ("status",)
    search_fields = ("order_number", "user__username", "tracking_code")
    readonly_fields = ("order_number", "created_date", "update_date")
    inlines = [OrderItemInline, PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "amount", "payment_method", "status", "paid_at")
    list_filter = ("status", "payment_method")
    search_fields = ("order__order_number", "transaction_id")
