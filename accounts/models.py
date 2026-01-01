from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model so we can attach a role (brand vs influencer vs admin)
    and later extend with more fields without fighting Django's default User.
    """

    class Roles(models.TextChoices):
        BRAND = "brand", "Brand"
        INFLUENCER = "influencer", "Influencer"
        ADMIN = "admin", "Admin"

    # Override email field to make it unique and required
    email = models.EmailField(
        unique=True,
        blank=False,
        null=False,
        help_text="Email address (must be unique across all accounts).",
    )

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.BRAND,
        help_text="What type of account this user has in Push-it.",
    )
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Set to true once the user has verified their email.",
    )

    def is_brand(self) -> bool:
        return self.role == self.Roles.BRAND

    def is_influencer(self) -> bool:
        return self.role == self.Roles.INFLUENCER

    def is_admin_user(self) -> bool:
        """
        Application-level admin (can manage dashboards etc).
        Django superuser/staff flags still work as usual.
        """
        return self.role == self.Roles.ADMIN

