from django.views.generic import TemplateView


# Create your views here.
class CategoryListView(TemplateView):
    template_name = "blog/blog-category-list.html"


class PostFullwidthView(TemplateView):
    """
    Renders the page shell only. The post itself (title, image,
    content, author, tags) is fetched client-side from
    /api/v1/blog/posts/<slug>/ - only the slug from the URL is passed
    into the template context, mirroring shop.ProductFullView.
    """

    template_name = "blog/blog-post-fullwidth.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["post_slug"] = self.kwargs.get("slug", "")
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
        return context
