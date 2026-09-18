from django.contrib.auth import get_user_model
from rest_framework import serializers

from blog.models import Category, Comment, Post, PostBookmark, PostLike, Tag


class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "post_count"]


class CategoryMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class AuthorMinimalSerializer(serializers.ModelSerializer):
    """Same display-name fallback as shop's
    ReviewSerializer.get_user_display_name.
    """

    display_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    bio = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "display_name", "avatar", "bio"]

    def get_display_name(self, obj):
        display_name = getattr(obj, "profile", None) and obj.profile.display_name
        return display_name or obj.username

    def get_avatar(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile or not profile.avatar:
            return None
        request = self.context.get("request")
        url = profile.avatar.url
        return request.build_absolute_uri(url) if request else url

    def get_bio(self, obj):
        profile = getattr(obj, "profile", None)
        return (profile and profile.description) or ""


class PostListSerializer(serializers.ModelSerializer):
    """Lightweight representation used for listing/grid pages."""

    category = CategoryMinimalSerializer(read_only=True)
    author = AuthorMinimalSerializer(read_only=True)
    is_bookmarked = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Post
        fields = [
            "id",
            "slug",
            "title",
            "excerpt",
            "image",
            "category",
            "author",
            "created_date",
            "is_bookmarked",
            "is_liked",
            "like_count",
        ]

    def get_is_bookmarked(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        bookmarked_ids = self.context.get("bookmarked_ids")
        if bookmarked_ids is None:
            bookmarked_ids = set(
                PostBookmark.objects.filter(user=request.user).values_list(
                    "post_id", flat=True
                )
            )
            self.context["bookmarked_ids"] = bookmarked_ids
        return obj.id in bookmarked_ids

    def get_is_liked(self, obj):
        # Deliberately separate cache key/query from is_bookmarked -
        # liking and bookmarking a post are independent actions with
        # independent state, not two views of the same toggle.
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        liked_ids = self.context.get("liked_ids")
        if liked_ids is None:
            liked_ids = set(
                PostLike.objects.filter(user=request.user).values_list(
                    "post_id", flat=True
                )
            )
            self.context["liked_ids"] = liked_ids
        return obj.id in liked_ids


class PostDetailSerializer(PostListSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            "content",
            "update_date",
            "tags",
        ]


class CommentSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    user_avatar = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "user_display_name",
            "user_avatar",
            "content",
            "is_approved",
            "published",
            "created_date",
        ]
        read_only_fields = [
            "id",
            "post",
            "is_approved",
            "published",
            "created_date",
        ]

    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment can't be empty.")
        return value.strip()

    def get_user_display_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        display_name = profile and profile.display_name
        return display_name or obj.user.username

    def get_user_avatar(self, obj):
        profile = getattr(obj.user, "profile", None)
        if not profile or not profile.avatar:
            return None
        request = self.context.get("request")
        url = profile.avatar.url
        return request.build_absolute_uri(url) if request else url
