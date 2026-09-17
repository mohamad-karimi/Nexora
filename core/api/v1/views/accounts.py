import logging

from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.constants import LOGIN_SECURITY_CODE_SESSION_KEY
from accounts.emails import send_password_reset_email
from accounts.otp import (
    OTPError,
    resend_email_verification,
    start_email_verification,
    verify_email_code,
)
from api.v1.permissions import IsVerified
from api.v1.serializers.accounts import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    ProfileSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    VerifyEmailCodeSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema(tags=["Auth"])
class RegisterView(APIView):
    """Create a new (unverified) account. Does NOT log the user in --
    they can't authenticate until they verify their email address."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new account",
        description=(
            "Creates a new user account and emails it a 6-digit "
            "verification code. The account is created with "
            "`is_verified=False` and the request is NOT logged in -- no "
            "authenticated session is started. This browser session is, "
            "however, tied server-side to the new account so the "
            "Verify Your Email page (and its Resend Code button) know "
            "which account to act on -- see `POST /auth/verify-email/`."
        ),
        request=RegisterSerializer,
        responses={201: UserSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        try:
            start_email_verification(request, user)
        except Exception:
            # Registration must still succeed even if the mail server is
            # unreachable/misconfigured -- the user can request the code
            # again later via Resend Code. (See accounts.otp.)
            logger.exception("Failed to send verification code to user %s", user.pk)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"])
class VerifyEmailCodeView(APIView):
    """Verifies the 6-digit code for the account pending verification in
    this session, then logs that account in."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Verify email with a 6-digit code",
        description=(
            "Verifies `code` against the account pending verification in "
            "this browser session (set by `POST /auth/register/` or "
            "`POST /auth/resend-verification/`). The target account is "
            "never taken from the request body -- only from this "
            "server-side session -- so this can't be used to verify a "
            "different account by changing an email or user id in the "
            "request. On success the account is marked verified, the "
            "code is invalidated, and the browser is logged in."
        ),
        request=VerifyEmailCodeSerializer,
        responses={
            200: UserSerializer,
            400: OpenApiResponse(
                description="No pending verification, or an incorrect/expired/exhausted code.",
                examples=[
                    OpenApiExample(
                        "Incorrect code",
                        value={"detail": "The code you entered is incorrect."},
                    ),
                ],
            ),
        },
    )
    def post(self, request):
        serializer = VerifyEmailCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = verify_email_code(request, serializer.validated_data["code"])
        except OTPError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        login(request, user)
        return Response(UserSerializer(user).data)


@extend_schema(tags=["Auth"])
class ResendVerificationEmailView(APIView):
    """Re-sends the email-verification code (e.g. after the first one expired)."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Resend the email verification code",
        description=(
            "Generates a new 6-digit code for the account pending "
            "verification in this browser session (set by "
            "`POST /auth/register/`), invalidating the previous code, "
            "and emails the new one. The account is taken only from this "
            "session, never from the request body. Subject to a short "
            "cooldown between requests."
        ),
        request=None,
        responses={
            200: OpenApiResponse(description="A new code has been sent."),
            400: OpenApiResponse(
                description="No pending verification for this session, or cooldown not elapsed."
            ),
        },
    )
    def post(self, request):
        try:
            resend_email_verification(request)
        except OTPError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Failed to resend verification code")
            return Response(
                {"detail": "Could not resend the verification code. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "A new verification code has been sent to your email."}
        )


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
                description="Invalid credentials, inactive account, or unverified email.",
                examples=[
                    OpenApiExample(
                        "Invalid credentials",
                        value={"detail": "Invalid username or password."},
                    ),
                    OpenApiExample(
                        "Unverified email",
                        value={"detail": "Please verify your email before logging in."},
                    ),
                ],
            ),
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
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
        if not user.is_verified:
            return Response(
                {"detail": "Please verify your email before logging in."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        # One-time code: never reusable/brute-forceable after this point.
        request.session.pop(LOGIN_SECURITY_CODE_SESSION_KEY, None)
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

    permission_classes = [IsVerified]

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

    permission_classes = [IsVerified]

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


@extend_schema(tags=["Auth"])
class ForgotPasswordView(APIView):
    """Requests a password-reset email."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Request a password reset email",
        description=(
            "If an account exists for the given email, sends it a "
            "one-time, time-limited JWT reset link. Always responds the "
            "same way whether or not the email is registered, so this "
            "endpoint can't be used to discover which emails have accounts."
        ),
        request=ForgotPasswordSerializer,
        responses={200: OpenApiResponse(description="Request accepted.")},
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        User = get_user_model()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            try:
                send_password_reset_email(request, user)
            except Exception:
                logger.exception("Failed to send password reset email to user %s", user.pk)

        return Response(
            {"detail": "If that email has an account, a reset link has been sent."}
        )


@extend_schema(tags=["Auth"])
class ResetPasswordView(APIView):
    """Sets a new password from a valid password-reset JWT."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Reset password with a token",
        description=(
            "Sets a new password for the user identified by `token` -- "
            "the JWT from the reset email. The user is identified only "
            "from the token, never from any other request field, so this "
            "can never be used to change another user's password. Expired, "
            "tampered, or already-used tokens are rejected."
        ),
        request=ResetPasswordSerializer,
        responses={
            204: OpenApiResponse(description="Password reset successfully."),
            400: OpenApiResponse(description="Invalid/expired token or invalid password."),
        },
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
