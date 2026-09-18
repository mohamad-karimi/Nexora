"""
Site-wide template context processors.
"""

from django.conf import settings
from django.utils.translation import get_language_info


def site_locale(request):
    """
    Exposes the project's single supported display language and
    currency to every template (see templates/base.html's header
    Language/Currency indicators).

    The storefront does not implement multi-language content or
    multi-currency pricing (there are no translation catalogs, no
    LocaleMiddleware, and every price in the shop/cart/checkout
    flow is a plain DecimalField with no currency field). Rather
    than fake a switcher for options that don't exist, these are
    derived from the real settings that already govern the rest of
    the project -- LANGUAGE_CODE (also used by Django's own i18n
    machinery) and DEFAULT_CURRENCY (the currency every price in
    the database is denominated in). If real multi-language or
    multi-currency support is added later, this is the single place
    that would grow to reflect it.
    """
    language_name = get_language_info(settings.LANGUAGE_CODE)["name"]
    return {
        "SITE_LANGUAGE_NAME": language_name,
        "SITE_CURRENCY_CODE": settings.DEFAULT_CURRENCY,
    }
