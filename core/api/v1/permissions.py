from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Object-level permission restricting access to the object's `user`
    (or `order.user`, for nested objects) matching the requester.
    """

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "order"):
            owner = obj.order.user
        return owner == request.user
