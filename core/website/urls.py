from django.urls import path
from . import views

urlpatterns = [
    path('', views.IndexView.as_view(), name="home"),
    path('404/', views.Page404View.as_view(), name="404"),
    path('about/', views.AboutView.as_view(), name="about"),
    path('contact/', views.ContactView.as_view(), name="contact"),
]