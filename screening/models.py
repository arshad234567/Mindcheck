from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Guidance(models.Model):
    """
    One of the four action tiers (Low, Mild, Moderate, High).
    Every score band of every tool points to one of these, so the same
    plain-language guidance is shown whichever questionnaire was taken.
    """

    class Tier(models.TextChoices):
        LOW = "low", "Low"
        MILD = "mild", "Mild"
        MODERATE = "moderate", "Moderate"
        HIGH = "high", "High"

    tier = models.CharField(max_length=10, choices=Tier.choices, unique=True)
    severity_rank = models.PositiveSmallIntegerField(
        unique=True, help_text="1 = lowest, 4 = highest. Used for ordering and colour."
    )
    headline = models.CharField(max_length=120)
    advice = models.TextField(help_text="One self-help step per line.")
    follow_up = models.CharField(max_length=200)
    retake_after_days = models.PositiveSmallIntegerField(default=30)
    show_professional_banner = models.BooleanField(
        default=False, help_text="Show 'please speak to a professional soon' at the top."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["severity_rank"]
        verbose_name_plural = "guidance"

    def __str__(self):
        return self.get_tier_display()

    def advice_lines(self):
        return [line.strip() for line in self.advice.splitlines() if line.strip()]


class ScreeningTool(models.Model):
    """A validated questionnaire such as PHQ-9, GAD-7 or WHO-5."""

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=20, unique=True)
    slug = models.SlugField(max_length=30, unique=True)
    domain = models.CharField(max_length=100, help_text="What it screens, e.g. 'Depression symptoms'.")
    description = models.TextField()
    instructions = models.CharField(max_length=255, help_text="The question stem shown above the items.")
    score_multiplier = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)],
        help_text="WHO-5 raw total is multiplied by 4 to give a 0-100 score.",
    )
    higher_is_better = models.BooleanField(
        default=False, help_text="True for WHO-5, where a higher score means better wellbeing."
    )
    citation = models.CharField(max_length=255)
    minutes_to_complete = models.PositiveSmallIntegerField(default=2)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.short_name

    def get_absolute_url(self):
        return reverse("screening:take", kwargs={"slug": self.slug})

    @property
    def max_final_score(self):
        top = self.choices.aggregate(models.Max("value"))["value__max"] or 0
        return top * self.questions.count() * self.score_multiplier


class Question(models.Model):
    """One item of a questionnaire."""

    tool = models.ForeignKey(ScreeningTool, on_delete=models.CASCADE, related_name="questions")
    number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    text = models.CharField(max_length=255)
    is_safety_item = models.BooleanField(
        default=False,
        help_text="If any answer above 0 is given, the crisis support screen is shown first (PHQ-9 item 9).",
    )

    class Meta:
        ordering = ["tool", "number"]
        constraints = [
            models.UniqueConstraint(fields=["tool", "number"], name="unique_question_number_per_tool"),
        ]

    def __str__(self):
        return f"{self.tool.short_name} Q{self.number}"


class AnswerChoice(models.Model):
    """A response option for a tool, e.g. 'Several days' = 1."""

    tool = models.ForeignKey(ScreeningTool, on_delete=models.CASCADE, related_name="choices")
    value = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=60)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["tool", "display_order", "value"]
        constraints = [
            models.UniqueConstraint(fields=["tool", "value"], name="unique_choice_value_per_tool"),
        ]

    def __str__(self):
        return f"{self.label} ({self.value})"


class ScoreBand(models.Model):
    """A score range of a tool on its final scale, linked to one guidance tier."""

    tool = models.ForeignKey(ScreeningTool, on_delete=models.CASCADE, related_name="bands")
    label = models.CharField(max_length=60, help_text="e.g. 'Moderately severe'")
    min_score = models.PositiveSmallIntegerField()
    max_score = models.PositiveSmallIntegerField()
    interpretation = models.CharField(
        max_length=255, help_text="Plain-language, non-diagnostic: starts with 'Your answers suggest'."
    )
    guidance = models.ForeignKey(Guidance, on_delete=models.PROTECT, related_name="bands")

    class Meta:
        ordering = ["tool", "min_score"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_score__lte=models.F("max_score")),
                name="band_min_not_above_max",
            ),
            models.UniqueConstraint(fields=["tool", "min_score"], name="unique_band_start_per_tool"),
        ]

    def __str__(self):
        return f"{self.tool.short_name}: {self.label} ({self.min_score}-{self.max_score})"


class Assessment(models.Model):
    """
    A completed screening saved for a signed-in user.
    Only the scores, band and date are stored - never the individual answers
    and never any free text (data minimisation). Anonymous results are never saved.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessments"
    )
    tool = models.ForeignKey(ScreeningTool, on_delete=models.PROTECT, related_name="assessments")
    band = models.ForeignKey(ScoreBand, on_delete=models.PROTECT, related_name="assessments")
    raw_score = models.PositiveSmallIntegerField()
    final_score = models.PositiveSmallIntegerField()
    safety_flag = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "tool", "created_at"])]

    def __str__(self):
        return f"{self.user.username} - {self.tool.short_name} - {self.final_score}"

    def get_absolute_url(self):
        return reverse("screening:result", kwargs={"pk": self.pk})
