from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # in cm
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True) # in kg
    skin_color = models.CharField(max_length=50, null=True, blank=True)
    profile_picture = models.ImageField(upload_to=r'profile_pics/', null=True, blank=True)


    def __str__(self):
        return self.username

