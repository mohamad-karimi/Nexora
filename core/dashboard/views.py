from django.views.generic import TemplateView

from accounts.views import VerifiedRequiredMixin


# Create your views here.
class DashboardView(VerifiedRequiredMixin, TemplateView):
    template_name = "dashboard/vendor-dashboard.html"
    login_url = "accounts:login"
