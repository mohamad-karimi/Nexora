from django.db.models.signals import post_save
from django.conf import settings
from django.dispatch import receiver
from .models import Profile


# Signals
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_profile(sender, instance, created, **kwargs):
    """
    This signal function for make the same data in the profile
    dataset when a user add in the user data set and update them
    """
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()
