from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        # One place lists which model changes empty the public cache
        # (for shop, vendors, home and blog data alike).
        from core import cache_invalidation

        cache_invalidation.connect()
