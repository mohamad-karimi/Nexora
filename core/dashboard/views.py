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


class ProductEditView(VendorRequiredMixin, TemplateView):
    """
    Vendor-only "Edit Product" page. Same role gate as DashboardView --
    anonymous/unverified/non-vendor visitors never see this template.

    This page-level check only confirms the visitor *is* a vendor, not
    that they own the product named in the URL: the slug is just
    handed to the template/JS as-is, and the actual product data is
    loaded client-side from
    /api/v1/vendors/dashboard/products/<slug>/, which is the real
    ownership boundary (see api.v1.views.vendors.
    VendorDashboardProductDetailView) -- a vendor requesting another
    vendor's product slug gets an empty form and a "not found" message,
    never that product's data, exactly like ProductViewSet does for an
    unpublished product that isn't theirs.
    """

    template_name = "dashboard/vendor-product-edit.html"
    login_url = "accounts:login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product_slug"] = kwargs.get("slug", "")
        return context
