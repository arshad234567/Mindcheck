from django import forms
from django.utils import timezone

from .models import Resource, ResourceCategory


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            "name", "category", "description", "phone", "alt_phone", "location",
            "city", "hours", "website", "is_free", "is_crisis_line", "last_verified",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "last_verified": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            else:
                field.widget.attrs["class"] = "form-control"

    def clean_last_verified(self):
        value = self.cleaned_data["last_verified"]
        if value > timezone.localdate():
            raise forms.ValidationError("The verification date cannot be in the future.")
        return value

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("phone") and cleaned.get("phone") == cleaned.get("alt_phone"):
            self.add_error("alt_phone", "The alternative number must be different from the main number.")
        return cleaned


class ResourceSearchForm(forms.Form):
    """GET form used on the directory page."""

    q = forms.CharField(required=False, max_length=80, label="Search",
                        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Name, city or service"}))
    category = forms.ModelChoiceField(
        queryset=ResourceCategory.objects.all(), required=False, empty_label="All categories",
        to_field_name="slug", widget=forms.Select(attrs={"class": "form-select"}),
    )
    crisis_only = forms.BooleanField(required=False, label="24/7 crisis lines only",
                                     widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
