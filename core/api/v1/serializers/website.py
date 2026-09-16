from rest_framework import serializers

from website.models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "subject",
            "message",
            "source",
            "created_date",
        ]
        # `source`, `user` and `vendor` are never taken from the request
        # body - the view sets them from the authenticated session.
        read_only_fields = ["id", "source", "created_date"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value
