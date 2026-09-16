from django.views.generic import TemplateView

from accounts.views import VendorRequiredMixin


# Create your views here.
class GuideView(VendorRequiredMixin, TemplateView):
    """Vendor-only guide page. Access is decided by the server, not the template."""

    template_name = "vendors/vendor-guide.html"
    login_url = "accounts:login"


class VendorsGridView(TemplateView):
    template_name = "vendors/vendors-grid.html"
