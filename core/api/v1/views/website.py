from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.permissions import IsVendor, IsVerified
from api.v1.serializers.website import (
    ContactMessageSerializer,
    HomeBannerSerializer,
    HomeSlideSerializer,
)
from vendors.models import Vendor
from website.models import ContactMessage, HomeBanner, HomeSlide


@extend_schema_view(
    list=extend_schema(summary="List active homepage slider slides"),
    retrieve=extend_schema(summary="Get a homepage slider slide"),
)
@extend_schema(tags=["Website"])
class HomeSlideViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing of the homepage hero slider's active slides, in display order."""

    serializer_class = HomeSlideSerializer
    pagination_class = None

    def get_queryset(self):
        return HomeSlide.objects.filter(is_active=True).order_by("ordering", "id")


@extend_schema_view(
    list=extend_schema(summary="List active homepage banners"),
    retrieve=extend_schema(summary="Get a homepage banner"),
)
@extend_schema(tags=["Website"])
class HomeBannerViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only listing of the homepage 3-up banners section's active tiles, in display order."""

    serializer_class = HomeBannerSerializer
    pagination_class = None

    def get_queryset(self):
        return HomeBanner.objects.filter(is_active=True).order_by("ordering", "id")


@extend_schema(tags=["Website"])
class ContactMessageView(APIView):
    """Accepts submissions from the public "Drop Us a Line" contact form."""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Submit a contact message",
        description=(
            "Stores a message sent through the Contact page form. Open to "
            "anonymous visitors; if the request is made by an authenticated "
            "user the message is linked to their account."
        ),
        request=ContactMessageSerializer,
        responses={201: ContactMessageSerializer},
    )
    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user if request.user.is_authenticated else None)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Website"])
class VendorGuideContactMessageView(APIView):
    """Accepts submissions from the vendor-only Vendor Guide contact form."""

    # Same session auth as the rest of the site. The vendor role is
    # re-checked here on every submit, independently of the page-level
    # check that guards vendors/guide itself.
    permission_classes = [IsVerified, IsVendor]

    @extend_schema(
        summary="Submit a Vendor Guide contact message",
        description=(
            "Stores a message sent through the contact form on the Vendor "
            "Guide page (vendors/guide). Vendor accounts only. The message "
            "is linked to the authenticated user, tagged with "
            "source=vendor_guide, and linked to the submitter's vendor "
            "store when one exists."
        ),
        request=ContactMessageSerializer,
        responses={201: ContactMessageSerializer},
    )
    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Looked up fresh from the DB rather than via
        # `request.user.vendor_profile` -- the reverse-O2O accessor
        # caches on the user instance, so if that profile row was
        # deleted after the cache was already populated (e.g. earlier
        # in the same request/test), the cached-but-stale object would
        # be an unsaved instance rather than None.
        vendor = Vendor.objects.filter(user=request.user).first()
        serializer.save(
            user=request.user,
            vendor=vendor,
            source=ContactMessage.Source.VENDOR_GUIDE,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
