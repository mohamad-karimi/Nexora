from django.views.generic import TemplateView


# Create your views here.
class GuideView(TemplateView):
    template_name = "vendors/vendor-guide.html"


class VendorsGridView(TemplateView):
    template_name = "vendors/vendors-grid.html"
