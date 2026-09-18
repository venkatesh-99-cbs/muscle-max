from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager


class User(AbstractUser):
    """
    Custom User model where email is the unique identifier for authentication.
    """

    ROLE_CUSTOMER = "customer"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = (
        (ROLE_CUSTOMER, "Customer"),
        (ROLE_ADMIN, "Admin"),
    )

    username = None
    email = models.EmailField(_("email address"), unique=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_CUSTOMER,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else self.email.split("@")[0]

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_staff or self.is_superuser
