from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class VerifiedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Same as SimpleJWT's TokenObtainPairSerializer (username/password ->
    access + refresh token pair), plus the project's existing login rule
    that an unverified account (`is_verified=False`) cannot log in --
    mirrors the check in api.v1.views.accounts.LoginView so JWT login
    and session login enforce exactly the same policy.

    Inactive accounts and wrong credentials are already rejected by the
    parent class (via Django's `authenticate()` / ModelBackend, which
    Django's own PermissionsMixin runs `is_active` through), so nothing
    extra is needed for those.

    The resulting token carries only SimpleJWT's default claims
    (`user_id`, `token_type`, `exp`, `iat`, `jti`) -- never the password
    or any other sensitive user data.
    """

    def validate(self, attrs):
        data = super().validate(attrs)
        # super().validate() has already set self.user on success.
        if not self.user.is_verified:
            raise AuthenticationFailed(
                "Please verify your email before logging in.",
                "unverified",
            )
        return data
