from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        CITIZEN = "CITIZEN", "Citizen"
        WORKER = "WORKER", "Worker"
        AUTHORITY = "AUTHORITY", "Authority"

    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    profile_picture = models.ImageField(upload_to="profiles/%Y/%m/", blank=True, null=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CITIZEN, db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
