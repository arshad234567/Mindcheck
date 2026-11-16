from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Extra information for each user: their role and whether they gave consent."""

    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        COUNSELLOR = "counsellor", "Counsellor"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    consent_given_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the user accepted the privacy and consent notice.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_counsellor(self):
        return self.role == self.Role.COUNSELLOR

    @property
    def has_consented(self):
        return self.consent_given_at is not None


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Every new user automatically gets a Profile with the default Member role."""
    if created:
        Profile.objects.get_or_create(user=instance)
