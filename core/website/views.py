from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.views.generic import TemplateView


# Create your views here.
class IndexView(TemplateView):
    template_name = "website/index.html"


class Page404View(TemplateView):
    template_name = "website/page-404.html"


class AboutView(TemplateView):
    template_name = "website/page-about.html"


class ContactView(TemplateView):
    template_name = "website/page-contact.html"

    def get_context_data(self, **kwargs):
        # Passed to the template so the Leaflet map script can read the
        # Mapbox token from a server-rendered JS variable instead of a
        # hardcoded value in static/js/plugins/leaflet.js -- the token
        # itself lives only in the environment (settings.MAPBOX_ACCESS_TOKEN).
        context = super().get_context_data(**kwargs)
        context["mapbox_access_token"] = settings.MAPBOX_ACCESS_TOKEN
        return context


class PrivacyPolicyView(TemplateView):
    template_name = "website/page-privacy-policy.html"


class PurchaseGuideView(TemplateView):
    template_name = "website/page-purchase-guide.html"


class TermsView(TemplateView):
    template_name = "website/page-terms.html"


class RobotsTxtView(TemplateView):
    """
    /robots.txt -- always the same Disallow rules regardless of
    DEBUG (so "logical, testable" behaviour is identical in dev and
    prod, per the task), pointing crawlers at the real /sitemap.xml.
    The Sitemap URL is built from the current Site's domain (same
    source django.contrib.sitemaps/syndication use), never hardcoded.
    """

    template_name = "website/robots.txt"
    content_type = "text/plain"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site = get_current_site(self.request)
        scheme = "https" if self.request.is_secure() else "http"
        context["sitemap_url"] = f"{scheme}://{site.domain}{reverse('sitemap')}"
        return context
