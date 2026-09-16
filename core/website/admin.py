from django.contrib import admin

from website.models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "subject", "source", "user", "vendor", "created_date"]
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
