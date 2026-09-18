from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.constants import (
    EMAIL_OTP_LENGTH,
    LOGIN_SECURITY_CODE_SESSION_KEY,
    SECURITY_CODE_SESSION_KEY,
)
from accounts.models import Profile
from accounts.tokens import TokenError, get_user_for_password_reset_token

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
        help_text=(
            "Must satisfy Django's password validators (length, "
            "similarity, common-password checks, etc)."
        ),
    )
    first_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text=("Optional; used to seed the new user's profile " "display name."),
    )
    last_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text=("Optional; used to seed the new user's profile " "display name."),
    )
    security_code = serializers.CharField(
        write_only=True,
        help_text=(
            "Must match the code shown on the registration page "
            "for the current session."
        ),
    )
    agree_terms = serializers.BooleanField(
        write_only=True,
        help_text=(
            "Must be true; the user must accept the Terms & " "Policy to register."
        ),
    )
    account_type = serializers.ChoiceField(
        write_only=True,
        choices=[
            (User.Role.CUSTOMER, "Customer"),
            (User.Role.VENDOR, "Vendor"),
        ],
        default=User.Role.CUSTOMER,
        help_text="Which kind of account to create: customer or vendor.",
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "security_code",
            "agree_terms",
            "account_type",
        ]

    def validate_security_code(self, value):
        request = self.context.get("request")
        expected = request.session.get(SECURITY_CODE_SESSION_KEY) if request else None
        if not expected or value.strip() != expected:
            raise serializers.ValidationError("The security code is incorrect.")
        return value

    def validate_agree_terms(self, value):
        if not value:
            raise serializers.ValidationError(
                "You must agree to the Terms & Policy to register."
            )
        return value

    def create(self, validated_data):
        # These are only used for validation above / role assignment below --
        # they must never be written to the user's password, first_name, or
        # display_name.
        validated_data.pop("security_code", None)
        validated_data.pop("agree_terms", None)
        role = validated_data.pop("account_type", User.Role.CUSTOMER)
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            role=role,
        )

        profile = user.profile
        profile.first_name = first_name
        profile.last_name = last_name
        profile.display_name = f"{first_name} {last_name}".strip() or user.username
        profile.save()

        request = self.context.get("request")
        if request is not None:
            # One-time code: never reusable/brute-forceable after this point.
            request.session.pop(SECURITY_CODE_SESSION_KEY, None)

        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        trim_whitespace=False, style={"input_type": "password"}
    )
    security_code = serializers.CharField(
        write_only=True,
        help_text=(
            "Must match the code shown on the login page for " "the current session."
        ),
    )

    def validate_security_code(self, value):
        request = self.context.get("request")
        expected = (
            request.session.get(LOGIN_SECURITY_CODE_SESSION_KEY) if request else None
        )
        if not expected or value.strip() != expected:
            raise serializers.ValidationError("The security code is incorrect.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(style={"input_type": "password"})
    new_password = serializers.CharField(
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="Must satisfy Django's password validators.",
    )


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(
        help_text=(
            "If an account with this email exists, a reset " "link is sent to it."
        ),
    )


class VerifyEmailCodeSerializer(serializers.Serializer):
    code = serializers.RegexField(
        rf"^\d{{{EMAIL_OTP_LENGTH}}}$",
        write_only=True,
        help_text=(
            f"The {EMAIL_OTP_LENGTH}-digit code emailed to the account "
            "pending verification in this session."
        ),
    )


class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField(
        write_only=True,
        help_text="The JWT from the password-reset email link.",
    )
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
        help_text="Must satisfy Django's password validators.",
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )

        try:
            user = get_user_for_password_reset_token(attrs["token"])
        except TokenError as exc:
            raise serializers.ValidationError({"token": str(exc)})

        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        # The token's password stamp no longer matches, so it (and any
        # other outstanding reset token for this user) is now dead --
        # nothing further to revoke.
        return user
