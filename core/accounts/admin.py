from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Profile


# Register your models here.
class CustomUserAdmin(UserAdmin):
    """
    This class for making custom admin panel for the user
    """

    model = CustomUser
    list_display = (
        "username",
        "role",
        "email",
        "is_staff",
        "is_active",
        "is_superuser",
        "is_verified",
    )
    list_filter = (
        "is_staff",
        "is_active",
        "is_superuser",
        "is_verified",
        "role",
    )
    readonly_fields = ("create_date", "update_date")
    fieldsets = (
        ("Authentication", {"fields": ("username", "email", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "is_verified",
                    "role",
                )
            },
        ),
        (
            "Groups and Permissions",
            {"fields": ("groups", "user_permissions")},
        ),
        ("Important Dates", {"fields": ("last_login",)}),
    )

    add_fieldsets = (
        (
            "Authentication",
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
        (
            "Permissions",
            {
                "classes": ("wide",),
                "fields": (
                    "is_staff",
                    "is_active",
                    "is_superuser",
                    "is_verified",
                    "role",
                ),
            },
        ),
        (
            "Groups and Permissions",
            {
                "classes": ("wide",),
                "fields": ("groups", "user_permissions"),
            },
        ),
    )

    search_fields = ("email", "username")
    ordering = ("email", "username")


admin.site.register(Profile)
admin.site.register(CustomUser, CustomUserAdmin)
