from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers.accounts import (
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)


@extend_schema(tags=["Auth"])
class RegisterView(APIView):
    """Create a new account and immediately sign the user in (session cookie)."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new account",
        description=(
            "Creates a new user account. On success the user is logged in "
            "immediately, so the response also sets the session cookie -- "
            "no separate login call is required afterwards."
        ),
        request=RegisterSerializer,
        responses={201: UserSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"])
class LoginView(APIView):
    """Session-based login."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Log in",
        description=(
            "Authenticates with username/password and starts a Django "
            "session. The `sessionid` cookie returned by this call must be "
            "sent with subsequent authenticated requests."
        ),
        request=LoginSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(
                description="Invalid credentials or inactive account.",
                examples=[
                    OpenApiExample(
                        "Invalid credentials",
                        value={"detail": "Invalid username or password."},
                    )
                ],
            ),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"detail": "This account is inactive."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


@extend_schema(tags=["Auth"])
class LogoutView(APIView):
    """Ends the current Django session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Log out",
        description="Ends the current user's session. Requires an active session.",
        request=None,
        responses={204: OpenApiResponse(description="Logged out successfully.")},
    )
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Auth"])
class MeView(APIView):
    """Read or update the profile of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get the current user",
        description="Returns the profile of the currently authenticated user.",
        responses={200: UserSerializer},
    )
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(
        summary="Update the current user's profile",
        description=(
            "Partially updates the current user's profile fields "
            "(first/last name, display name, avatar, phone, address, "
            "description). An `email` field may also be included in the "
            "body to update the account's email address; it is not part "
            "of the profile model but is applied to the user record."
        ),
        request=ProfileSerializer,
        responses={200: UserSerializer},
    )
    def patch(self, request):
        profile_serializer = ProfileSerializer(
            request.user.profile, data=request.data, partial=True
        )
        profile_serializer.is_valid(raise_exception=True)
        profile_serializer.save()

        email = request.data.get("email")
        if email:
            request.user.email = email
            request.user.save(update_fields=["email"])

        return Response(UserSerializer(request.user).data)


@extend_schema(tags=["Auth"])
class ChangePasswordView(APIView):
    """Change the current user's password."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change password",
        description=(
            "Changes the current user's password after verifying "
            "`old_password`. The session remains valid afterwards."
        ),
        request=ChangePasswordSerializer,
        responses={
            204: OpenApiResponse(description="Password changed successfully."),
            400: OpenApiResponse(
                description="Current password incorrect, or new password invalid.",
                examples=[
                    OpenApiExample(
                        "Wrong current password",
                        value={"old_password": "Current password is incorrect."},
                    )
                ],
            ),
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)
        return Response(status=status.HTTP_204_NO_CONTENT)
