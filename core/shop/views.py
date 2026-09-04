from django.views.generic import TemplateView


# Create your views here.
class CompareView(TemplateView):
    template_name = "shop/shop-compare.html"


class FilterView(TemplateView):
    template_name = "shop/shop-filter.html"


class GridLeftView(TemplateView):
    template_name = "shop/shop-grid-left.html"


class ProductFullView(TemplateView):
    template_name = "shop/shop-product-full.html"


class WishlistView(TemplateView):
    template_name = "shop/shop-wishlist.html"
