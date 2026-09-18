from django.contrib import admin

from website.models import ContactMessage, HomeBanner, HomeSlide


@admin.register(HomeSlide)
class HomeSlideAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "description",
        "ordering",
        "is_active",
        "update_date",
    ]
    list_filter = ["is_active"]
    list_editable = ["ordering", "is_active"]
    search_fields = ["title", "description"]


@admin.register(HomeBanner)
class HomeBannerAdmin(admin.ModelAdmin):
    list_display = [
        "__str__",
        "link_url",
        "ordering",
        "is_active",
        "update_date",
    ]
    list_filter = ["is_active"]
    list_editable = ["ordering", "is_active"]
    search_fields = ["title", "link_url"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "email",
        "phone",
        "subject",
        "source",
        "user",
        "vendor",
        "created_date",
    ]
    list_filter = ["source", "created_date"]
    search_fields = ["name", "email", "phone", "subject", "message"]
    readonly_fields = [
        "source",
        "vendor",
        "user",
        "name",
        "email",
        "phone",
        "subject",
        "message",
        "created_date",
    ]
