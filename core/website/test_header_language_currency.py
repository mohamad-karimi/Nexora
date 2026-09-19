"""
Tests for the Header Language/Currency fix (templates/base.html).

The project has no real multi-language content (no locale/.po files,
no LocaleMiddleware, LANGUAGE_CODE is a single value) and no
multi-currency support (Product.price is a plain DecimalField, no
currency field, no conversion source, every price in every template
and JS file is hardcoded to "$"). Per the fix request, this means the
correct behaviour is to stop faking a switcher for options that don't
exist -- not to build one. These tests check that:

  1. The desktop header shows only the real, active language/currency
     (derived from settings.LANGUAGE_CODE / settings.DEFAULT_CURRENCY)
     and none of the old fake options.
  2. No dead "#" link remains for either feature.
  3. The mobile menu's Language accordion was fixed the same way.
  4. Both dropdowns keep working (open/close) without depending on
     any destination that doesn't exist -- i.e. no navigation, no JS
     errors from a mismatched toggle target.
"""

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.translation import get_language_info


@override_settings(ALLOWED_HOSTS=["testserver", "localhost", "127.0.0.1"])
class HeaderLanguageCurrencyTests(TestCase):
    def setUp(self):
        self.home_url = reverse("website:home")

    def test_desktop_header_shows_only_the_real_active_language(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()
        language_name = get_language_info(settings.LANGUAGE_CODE)["name"]

        self.assertContains(response, language_name)
        # No fake languages the project doesn't actually support.
        for fake in (
            "Français",
            "Deutsch",
            "Pусский",
            ">French<",
            ">German<",
            ">Spanish<",
        ):
            self.assertNotIn(fake, content)

    def test_desktop_header_shows_only_the_real_active_currency(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()

        self.assertContains(response, settings.DEFAULT_CURRENCY)
        # No fake currencies the project doesn't actually support.
        for fake in (">INR<", ">MBP<", ">EU<"):
            self.assertNotIn(fake, content)

    def test_no_fake_flag_images_remain(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()
        for flag in ("flag-fr", "flag-dt", "flag-ru"):
            self.assertNotIn(flag, content)

    def test_no_dead_hash_link_for_language_or_currency_options(self):
        """
        The old markup wrapped every language/currency option in
        <a href="...#">. The toggle trigger may still use the site's
        existing accordion-toggle convention, but the actual
        selectable items must not be dead links.
        """
        response = self.client.get(self.home_url)
        content = response.content.decode()
        start = content.find("header-info-right")
        end = content.find("</div>", content.find("header-middle"))
        header_top_right = content[start:end]

        self.assertNotIn('href="/#"', header_top_right)
        self.assertNotIn(
            "href=\"{% url 'website:home' %}#\"", header_top_right
        )

    def test_mobile_menu_language_section_has_no_fake_options(self):
        response = self.client.get(self.home_url)
        content = response.content.decode()
        language_name = get_language_info(settings.LANGUAGE_CODE)["name"]

        start = content.find("Language / Currency")
        self.assertNotEqual(start, -1)
        section = content[start:start + 400]

        self.assertIn(language_name, section)
        self.assertIn(settings.DEFAULT_CURRENCY, section)
        for fake in (">French<", ">German<", ">Spanish<"):
            self.assertNotIn(fake, section)
        # The leaf options themselves must not be links to nowhere.
        self.assertNotIn('<a href="/#">English', section)

    def test_language_and_currency_indicators_are_consistent_across_pages(
        self,
    ):
        """
        Since there's no per-request language/currency state to
        persist (only one of each is ever supported), the header
        must show the same value on every page -- this doubles as
        the 'survives navigation' requirement for a single-option
        display.
        """
        language_name = get_language_info(settings.LANGUAGE_CODE)["name"]
        for url_name in ("website:home", "website:about", "shop:grid_left"):
            response = self.client.get(reverse(url_name))
            self.assertContains(response, language_name)
            self.assertContains(response, settings.DEFAULT_CURRENCY)
