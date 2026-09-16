from django.views.generic import TemplateView

from accounts.views import VendorRequiredMixin


# Create your views here.
class DashboardView(VendorRequiredMixin, TemplateView):
    """
    Vendor-only page. Was previously gated by VerifiedRequiredMixin only,
    which let any verified customer open it; VendorRequiredMixin adds the
    real role check (anonymous -> login, unverified -> verification page,
    verified non-vendor -> 403), same as vendors.views.GuideView.
    """

    template_name = "dashboard/vendor-dashboard.html"
    login_url = "accounts:login"
