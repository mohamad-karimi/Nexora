from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = [
            "first_name",
            "last_name",
            "display_name",
            "avatar",
            "phone",
            "address",
            "description",
        ]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "profile"]
        read_only_fields = ["id", "username", "role"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        help_text="Must satisfy Django's password validators (length, similarity, common-password checks, etc).",
    )
    first_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        help_text="Optional; used to seed the new user's profile display name.",
    )
    last_name = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        help_text="Optional; used to seed the new user's profile display name.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "first_name", "last_name"]

    def create(self, validated_data):
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )
        if first_name or last_name:
            profile = user.profile
            profile.first_name = first_name
            profile.last_name = last_name
            profile.display_name = f"{first_name} {last_name}".strip() or user.username
            profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={"input_type": "password"})
    new_password = serializers.CharField(
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="Must satisfy Django's password validators.",
    )
