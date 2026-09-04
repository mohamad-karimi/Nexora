from django.views.generic import TemplateView

# Create your views here.
class IndexView(TemplateView):
    template_name = 'website/index.html'

class Page404View(TemplateView):
    template_name = 'website/page-404.html'

class AboutView(TemplateView):
    template_name = 'website/page-about.html'

class ContactView(TemplateView):
    template_name = 'website/page-contact.html'

class PrivacyPolicyView(TemplateView):
    template_name = 'website/page-privacy-policy.html'

class PurchaseGuideView(TemplateView):
    template_name = 'website/page-purchase-guide.html'

class TermsView(TemplateView):
    template_name = 'website/page-terms.html'