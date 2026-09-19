from django.db.models import Count, Q
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.v1.filters import PostFilter
from api.v1.public_cache import PublicDetailCacheMixin, PublicListCacheMixin
from api.v1.serializers.blog import (
    CategorySerializer,
    CommentSerializer,
    PostDetailSerializer,
    PostListSerializer,
    TagSerializer,
)
from blog.models import Category, Post, PostBookmark, PostLike, Tag


@extend_schema_view(
    list=extend_schema(summary="List blog categories"),
    retrieve=extend_schema(
        summary="Get a blog category",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Blog"])
class CategoryViewSet(PublicListCacheMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of blog categories, with a live post count."""

    serializer_class = CategorySerializer
    lookup_field = "slug"

    public_cache_domain = "blog"
    public_cache_ttl = "taxonomy"
    public_cache_name = "blog-categories"
    public_cache_params = frozenset({"page", "page_size", "ordering"})
    public_cache_orderings = frozenset({"name", "-name"})

    def get_queryset(self):
        return Category.objects.annotate(
            post_count=Count(
                "posts", filter=Q(posts__status=Post.Status.PUBLISHED)
            )
        ).order_by("name")


@extend_schema_view(
    list=extend_schema(summary="List blog tags"),
    retrieve=extend_schema(
        summary="Get a blog tag",
        description="Looked up by `slug`, not the numeric id.",
    ),
)
@extend_schema(tags=["Blog"])
class TagViewSet(PublicListCacheMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only listing/detail of blog tags (mirrors shop.Tag's API shape)."""

    queryset = Tag.objects.all().order_by("name")
    serializer_class = TagSerializer
    lookup_field = "slug"

    public_cache_domain = "blog"
    public_cache_ttl = "taxonomy"
    public_cache_name = "blog-tags"
    public_cache_params = frozenset({"page", "page_size", "ordering"})
    public_cache_orderings = frozenset({"name", "-name"})


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
class PostViewSet(
    PublicListCacheMixin, PublicDetailCacheMixin, viewsets.ReadOnlyModelViewSet
):
    """Read-only browsing of published blog posts."""

    lookup_field = "slug"
    filterset_class = PostFilter
    search_fields = ["title", "excerpt", "content"]
    ordering_fields = ["created_date", "title"]
    ordering = ["-created_date"]

    # Only published posts ever reach the queryset, and only those are
    # cached. The per-user `is_liked` / `is_bookmarked` are added by the
    # serializer on every request; the like_count follows PostLike changes
    # (core/cache_invalidation.py). Searches are not cached. The comments /
    # bookmark / like actions call get_object() too but always hit the
    # database (the detail cache only serves `retrieve`).
    public_cache_domain = "blog"
    public_cache_ttl = "blog"
    public_cache_name = "blog-posts"
    public_cache_params = frozenset(
        {"category", "tag", "ordering", "page", "page_size"}
    )
    public_cache_slug_params = frozenset({"category", "tag"})
    public_cache_orderings = frozenset(
        ordering_fields + [f"-{field}" for field in ordering_fields]
    )

    def public_cache_is_public(self, post):
        return post.status == Post.Status.PUBLISHED

    def get_queryset(self):
        return (
            Post.objects.filter(status=Post.Status.PUBLISHED)
            .select_related("category", "author", "author__profile")
            .prefetch_related("tags")
            .annotate(like_count=Count("likes", distinct=True))
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PostDetailSerializer
        return PostListSerializer

    @extend_schema(
        tags=["Blog"],
        summary="List or submit comments for a post",
        description=(
            "**GET**: paginated list of published comments on the "
            "post. A comment an admin has unpublished "
            "(`published=false`) is never returned, even to its own "
            "author.\n\n"
            "**POST**: requires authentication. Adds a new comment "
            "from the current user, published immediately "
            "(`published=true`) unless an admin later hides it."
        ),
        request=CommentSerializer,
        responses={
            200: CommentSerializer(many=True),
            201: CommentSerializer,
            401: OpenApiResponse(
                description="Authentication required to leave a comment.",
                examples=[
                    OpenApiExample(
                        "Anonymous POST",
                        value={
                            "detail": (
                                "Authentication required to "
                                "leave a comment."
                            )
                        },
                    )
                ],
            ),
        },
    )
    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, slug=None):
        post = self.get_object()

        if request.method == "GET":
            # published=True is the only visibility gate: unpublished
            # comments never appear in this list, not even for their
            # own author, so the filtering can't be bypassed client-side.
            queryset = post.comments.select_related("user__profile").filter(
                published=True
            )
            page = self.paginate_queryset(queryset.order_by("-created_date"))
            serializer = CommentSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to leave a comment."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = CommentSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        # published defaults to True on the model, so the comment is
        # live immediately unless an admin unpublishes it later.
        comment = post.comments.create(
            user=request.user,
            content=serializer.validated_data["content"],
        )
        return Response(
            CommentSerializer(comment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        tags=["Blog"],
        summary="Toggle bookmarking the post",
        description=(
            "Requires authentication. Saves the post for the current "
            "user if it wasn't bookmarked yet, or removes it if it "
            "was. Returns the resulting state."
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                description="Resulting bookmark state.",
                examples=[
                    OpenApiExample("Toggled on", value={"bookmarked": True})
                ],
            ),
            401: OpenApiResponse(
                description="Authentication required to bookmark a post.",
                examples=[
                    OpenApiExample(
                        "Anonymous POST",
                        value={
                            "detail": (
                                "Authentication required to "
                                "bookmark a post."
                            )
                        },
                    )
                ],
            ),
        },
    )
    @action(detail=True, methods=["post"], url_path="bookmark")
    def bookmark(self, request, slug=None):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to bookmark a post."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        post = self.get_object()
        existing = PostBookmark.objects.filter(
            user=request.user, post=post
        ).first()
        if existing:
            existing.delete()
            return Response({"bookmarked": False})
        PostBookmark.objects.create(user=request.user, post=post)
        return Response({"bookmarked": True})

    @extend_schema(
        tags=["Blog"],
        summary="Toggle liking the post",
        description=(
            "Requires authentication. Likes the post for the current "
            "user if they hadn't liked it yet, or removes the like if "
            "they had. Completely independent from bookmarking - "
            "liking/unliking a post never changes its bookmark state "
            "and vice versa. Returns the resulting state and the "
            "post's total like count."
        ),
        request=None,
        responses={
            200: OpenApiResponse(
                description="Resulting like state and total count.",
                examples=[
                    OpenApiExample(
                        "Toggled on", value={"liked": True, "like_count": 4}
                    )
                ],
            ),
            401: OpenApiResponse(
                description="Authentication required to like a post.",
                examples=[
                    OpenApiExample(
                        "Anonymous POST",
                        value={
                            "detail": "Authentication required to like a post."
                        },
                    )
                ],
            ),
        },
    )
    @action(detail=True, methods=["post"], url_path="like")
    def like(self, request, slug=None):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required to like a post."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        post = self.get_object()
        existing = PostLike.objects.filter(
            user=request.user, post=post
        ).first()
        if existing:
            existing.delete()
            liked = False
        else:
            PostLike.objects.create(user=request.user, post=post)
            liked = True
        like_count = PostLike.objects.filter(post=post).count()
        return Response({"liked": liked, "like_count": like_count})
