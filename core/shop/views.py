from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class CompareView(TemplateView):
    template_name = "shop/shop-compare.html"


class FilterView(TemplateView):
    template_name = "shop/shop-filter.html"


class GridLeftView(TemplateView):
    template_name = "shop/shop-grid-left.html"


class ProductFullView(TemplateView):
    """
    Renders the page shell only. The product itself (and its images,
    specs, reviews) is fetched client-side from
    /api/v1/products/<slug>/ - only the slug from the URL is passed
    into the template context, never a queryset/model instance.
    """

    template_name = "shop/shop-product-full.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["product_slug"] = self.kwargs["slug"]
        return context


class WishlistView(LoginRequiredMixin, TemplateView):
    template_name = "shop/shop-wishlist.html"
    login_url = "accounts:login"
