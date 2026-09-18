from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from api.v1.serializers.auth_jwt import VerifiedTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Obtain a JWT access/refresh token pair",
    description=(
        "Authenticates with username/password and returns a JWT "
        "`access`/`refresh` token pair -- for the API/other (non-browser) "
        "clients. Does **not** start a Django session; the existing "
        "session-based `POST /api/v1/auth/login/` is unaffected and "
        "still used by the site itself.\n\n"
        "Send the access token as `Authorization: Bearer <access>` on "
        "subsequent requests. Subject to the same login rules as session "
        "login: the account must be active and its email verified."
    ),
    responses={
        401: OpenApiResponse(
            description=(
                "Invalid credentials, inactive account, "
                "or unverified email."
            ),
            examples=[
                OpenApiExample(
                    "Invalid credentials",
                    value={
                        "detail": (
                            "No active account found with "
                            "the given credentials."
                        )
                    },
                ),
                OpenApiExample(
                    "Unverified email",
                    value={
                        "detail": (
                            "Please verify your email before " "logging in."
                        ),
                        "code": "unverified",
                    },
                ),
            ],
        ),
    },
)
class JWTTokenObtainPairView(TokenObtainPairView):
    """POST /api/v1/auth/token/ -- {"access": "...", "refresh": "..."}"""

    permission_classes = [AllowAny]
    serializer_class = VerifiedTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Refresh a JWT access token",
    description=(
        "Exchanges a valid, unexpired refresh token for a "
        "new access token."
    ),
)
class JWTTokenRefreshView(TokenRefreshView):
    """POST /api/v1/auth/token/refresh/ -- {"access": "..."}"""

    permission_classes = [AllowAny]


@extend_schema(
    tags=["Auth"],
    summary="Verify a JWT token",
    description=(
        "Checks whether a given token (access or refresh) is "
        "valid and not expired."
    ),
)
class JWTTokenVerifyView(TokenVerifyView):
    """POST /api/v1/auth/token/verify/ -- {} on success, 401
    if invalid/expired.
    """

    permission_classes = [AllowAny]
