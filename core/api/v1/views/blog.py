from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from api.v1.filters import PostFilter
from api.v1.serializers.blog import (
    CategorySerializer,
    PostDetailSerializer,
    PostListSerializer,
    TagSerializer,
)
from blog.models import Category, Post, Tag


@extend_schema_view(
    list=extend_schema(summary="List blog categories"),
    retrieve=extend_schema(
        summary="Get a blog category",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Blog"])
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of blog categories, with a live post count."""

    serializer_class = CategorySerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Category.objects.annotate(
            post_count=Count("posts", filter=Q(posts__status=Post.Status.PUBLISHED))
        ).order_by("name")


@extend_schema_view(
    list=extend_schema(summary="List blog tags"),
    retrieve=extend_schema(
        summary="Get a blog tag",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Blog"])
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of blog tags (mirrors shop.Tag's API shape)."""

    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    lookup_field = "slug"


@extend_schema_view(
    list=extend_schema(
        summary="List published blog posts",
        description=(
            "Supports filtering by `category` slug; free-text search via "
            "`search`; and ordering via `ordering` (`created_date`, "
            "`title`, prefix with `-` to reverse)."
        ),
    ),
    retrieve=extend_schema(
        summary="Get a blog post",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Blog"])
class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only browsing of published blog posts."""

    lookup_field = "slug"
    filterset_class = PostFilter
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["created_date", "title"]
    ordering = ["-created_date"]

    def get_queryset(self):
        return (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .select_related("category", "author", "author__profile")
            .prefetch_related("tags")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer
