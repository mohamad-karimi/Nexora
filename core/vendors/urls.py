from django.urls import path
from . import views

app_name = "vendors"

urlpatterns = [
    path("", views.VendorsGridView.as_view(), name="list"),
    path("guide/", views.GuideView.as_view(), name="guide"),
]
