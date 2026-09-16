from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.permissions import IsVendor, IsVerified
from api.v1.serializers.website import ContactMessageSerializer
from website.models import ContactMessage


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
        serializer.save(
            user=request.user,
            vendor=getattr(request.user, "vendor_profile", None),
            source=ContactMessage.Source.VENDOR_GUIDE,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
