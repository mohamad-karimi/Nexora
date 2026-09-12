from django.contrib import admin

from website.models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "phone", "subject", "created_date", "user"]
    list_filter = ["created_date"]
    search_fields = ["name", "email", "phone", "subject", "message"]
    readonly_fields = [
        "user",
        "name",
        "email",
        "phone",
        "subject",
        "message",
        "created_date",
    ]
