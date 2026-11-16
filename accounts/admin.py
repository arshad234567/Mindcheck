from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ("role", "consent_given_at")


class UserAdmin(BaseUserAdmin):
    """Shows the role from the Profile directly on the user list."""

    inlines = [ProfileInline]
    list_display = ("username", "email", "get_role", "is_staff", "date_joined")
    list_filter = ("profile__role", "is_staff", "is_active")

    @admin.display(description="Role", ordering="profile__role")
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, "profile") else "-"


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "consent_given_at", "created_at")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")
    list_editable = ("role",)
