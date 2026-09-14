from django.urls import path
from . import views

app_name = "blog"

urlpatterns = [
    path("", views.CategoryListView.as_view(), name="category_list"),
    path("post/", views.PostFullwidthView.as_view(), name="post_detail"),
    path("post/<slug:slug>/", views.PostFullwidthView.as_view(), name="post_detail"),
]
