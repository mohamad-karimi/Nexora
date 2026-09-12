from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.serializers.website import ContactMessageSerializer


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
