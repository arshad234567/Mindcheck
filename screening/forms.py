from django import forms

from .models import Guidance


class ScreeningForm(forms.Form):
    """
    Built at run time from the questions stored in the database,
    so a new tool can be added in the admin without changing code.
    """

    def __init__(self, tool, *args, allow_save=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool = tool
        choices = [(str(c.value), c.label) for c in tool.choices.all()]
        for q in tool.questions.all():
            self.fields[f"q{q.number}"] = forms.ChoiceField(
                label=q.text,
                choices=choices,
                widget=forms.RadioSelect,
                error_messages={"required": f"Please answer question {q.number}."},
            )
            self.fields[f"q{q.number}"].number = q.number
        if allow_save:
            self.fields["save_result"] = forms.BooleanField(
                required=False, initial=True,
                label="Save this result to my history (untick for a private, unsaved result)",
            )

    def question_fields(self):
        return [self[name] for name in self.fields if name.startswith("q")]

    def answers(self):
        """Returns {question_number: value} from cleaned data."""
        return {
            int(name[1:]): int(value)
            for name, value in self.cleaned_data.items()
            if name.startswith("q")
        }


class GuidanceForm(forms.ModelForm):
    class Meta:
        model = Guidance
        fields = ["headline", "advice", "follow_up", "retake_after_days", "show_professional_banner"]
        widgets = {
            "headline": forms.TextInput(attrs={"class": "form-control"}),
            "advice": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "follow_up": forms.TextInput(attrs={"class": "form-control"}),
            "retake_after_days": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 90}),
            "show_professional_banner": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    # Phrases that would make guidance diagnostic or give medication advice.
    BANNED_PHRASES = ("you have ", "you are depressed", "you are anxious", "diagnos", "medication", "dosage")

    def clean_retake_after_days(self):
        days = self.cleaned_data["retake_after_days"]
        if not 1 <= days <= 90:
            raise forms.ValidationError("Choose between 1 and 90 days.")
        return days

    def clean(self):
        """Guidance must stay non-diagnostic and must not give medication advice."""
        cleaned = super().clean()
        text = " ".join(str(cleaned.get(f, "")) for f in ("headline", "advice", "follow_up")).lower()
        for phrase in self.BANNED_PHRASES:
            if phrase in text:
                raise forms.ValidationError(
                    "Guidance must be non-diagnostic (use 'your answers suggest') and must not "
                    "include diagnosis, medication or dosage advice."
                )
        return cleaned
