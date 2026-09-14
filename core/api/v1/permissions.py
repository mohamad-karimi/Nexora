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


class IsVerified(BasePermission):
    """
    Like IsAuthenticated, but also requires the account's email to be
    verified. Used on every authenticated endpoint that represents an
    "inside the account" feature (profile, cart, wishlist, addresses,
    orders...), so a session that somehow exists for an unverified
    user -- e.g. one created before this check existed -- still can't
    reach them. Login itself already refuses to start a session for
    an unverified user (see LoginView), so this is a defense-in-depth
    backstop rather than the primary gate.
    """

    message = "Please verify your email before accessing your account."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_verified)
