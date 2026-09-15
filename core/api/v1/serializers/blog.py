from django.contrib.auth import get_user_model
from rest_framework import serializers

from blog.models import Category, Post, Tag


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
    """Same display-name fallback as shop's ReviewSerializer.get_user_display_name."""

    display_name = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "display_name"]

    def get_display_name(self, obj):
        display_name = getattr(obj, "profile", None) and obj.profile.display_name
        return display_name or obj.username


class PostListSerializer(serializers.ModelSerializer):
    """Lightweight representation used for listing/grid pages."""

    category = CategoryMinimalSerializer(read_only=True)
    author = AuthorMinimalSerializer(read_only=True)

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
        ]


class PostDetailSerializer(PostListSerializer):
    tags = TagSerializer(many=True, read_only=True)

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["content", "update_date", "tags"]
