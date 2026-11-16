from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse

phone_validator = RegexValidator(
    regex=r"^[0-9+\- ]{3,20}$",
    message="Use digits, spaces, '+' or '-' only (3 to 20 characters).",
)


class ResourceCategory(models.Model):
    """Type of support, e.g. National helpline, Campus counselling, Hospital."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "resource categories"

    def __str__(self):
        return self.name


class Resource(models.Model):
    """A verified place or helpline where a user can get support."""

    name = models.CharField(max_length=120)
    category = models.ForeignKey(ResourceCategory, on_delete=models.PROTECT, related_name="resources")
    description = models.TextField()
    phone = models.CharField(max_length=20, validators=[phone_validator])
    alt_phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    location = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=60, default="All India")
    hours = models.CharField(max_length=80, default="24/7")
    website = models.URLField(blank=True)
    is_free = models.BooleanField(default=True)
    is_crisis_line = models.BooleanField(
        default=False, help_text="Shown on the crisis support screen and high-band results."
    )
    last_verified = models.DateField(help_text="Date the phone number and details were last checked.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="resources_added",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_crisis_line", "name"]
        constraints = [
            models.UniqueConstraint(fields=["name", "city"], name="unique_resource_name_per_city"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("resources:detail", kwargs={"pk": self.pk})
