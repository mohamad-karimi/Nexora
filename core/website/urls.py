from django.urls import path
from . import views

app_name = "website"

urlpatterns = [
    path('', views.IndexView.as_view(), name="home"),
    path('404/', views.Page404View.as_view(), name="404"),
    path('about/', views.AboutView.as_view(), name="about"),
    path('contact/', views.ContactView.as_view(), name="contact"),
    path('privacy-policy/', views.PrivacyPolicyView.as_view(), name="privacy_policy"),
    path('purchase-guide/', views.PurchaseGuideView.as_view(), name="purchase_guide"),
    path('terms/', views.TermsView.as_view(), name="terms"),
]