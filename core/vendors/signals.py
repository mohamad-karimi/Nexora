from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Vendor


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_vendor_profile_for_vendor_role(sender, instance, **kwargs):
    """
    Keeps the User <-> Vendor relationship consistent with the
    project's business rule that every account with role=Vendor owns
    exactly one Vendor row (`Vendor.user` is a required OneToOneField,
    reachable from the user as `user.vendor_profile`).

    Mirrors the existing accounts.signals.create_or_update_profile
    pattern (a post_save receiver on the user model), so it fires
    for every path that can put a user into the Vendor role: normal
    self-registration as a vendor (RegisterSerializer.create()) and
    an admin flipping `role` to Vendor by hand in Django Admin.

    Only *creates* a Vendor row when one doesn't already exist -- it
    never touches an existing vendor's store data, and the `getattr`
    check (same pattern used elsewhere for this reverse relation, e.g.
    VendorDashboardMixin.get_vendor()) keeps this from ever attempting
    a second Vendor.objects.create() for the same user, which `user`
    being OneToOne would turn into an IntegrityError.
    """
    if instance.role != instance.Role.VENDOR:
        return
    if getattr(instance, "vendor_profile", None) is not None:
        return
    Vendor.objects.create(
        user=instance,
        store_name=f"{instance.username}'s Store",
    )
