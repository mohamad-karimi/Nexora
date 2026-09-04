from django.views.generic import TemplateView


# Create your views here.
class CategoryListView(TemplateView):
    template_name = "blog/blog-category-list.html"


class PostFullwidthView(TemplateView):
    template_name = "blog/blog-post-fullwidth.html"
