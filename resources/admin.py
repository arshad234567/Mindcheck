from django.contrib import admin

from .models import Resource, ResourceCategory


@admin.register(ResourceCategory)
class ResourceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "resource_count")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)

    @admin.display(description="Resources")
    def resource_count(self, obj):
        return obj.resources.count()


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "phone", "city", "hours", "is_crisis_line", "last_verified")
    list_filter = ("category", "is_crisis_line", "is_free", "city")
    search_fields = ("name", "description", "city", "phone")
    list_editable = ("is_crisis_line",)
    date_hierarchy = "last_verified"
    readonly_fields = ("created_by", "updated_at")
    fieldsets = (
        ("Basic details", {"fields": ("name", "category", "description")}),
        ("Contact", {"fields": ("phone", "alt_phone", "website", "location", "city", "hours")}),
        ("Flags", {"fields": ("is_free", "is_crisis_line", "last_verified")}),
        ("Audit", {"fields": ("created_by", "updated_at"), "classes": ("collapse",)}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
