from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    """
    This function for add the profile signal
    """

    def ready(self):
        import accounts.signals
