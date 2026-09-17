from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Registers the JWT Bearer security scheme with drf-spectacular
        # (Swagger's "Authorize" button) -- see the module docstring.
        from api.v1 import schema_extensions  # noqa: F401
