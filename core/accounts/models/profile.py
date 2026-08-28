from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Profile(models.Model):
    """
    This is the profile of the user
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    display_name = models.CharField(max_length=50)
    avatar = models.ImageField(null=True, blank=True)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    description = models.TextField()
    create_date = models.DateTimeField(auto_now_add=True)
    update_date = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
