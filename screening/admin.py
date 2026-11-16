from django.contrib import admin

from .models import AnswerChoice, Assessment, Guidance, Question, ScoreBand, ScreeningTool

admin.site.site_header = "MindCheck administration"
admin.site.site_title = "MindCheck admin"
admin.site.index_title = "Manage tools, guidance, resources and users"


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


class AnswerChoiceInline(admin.TabularInline):
    model = AnswerChoice
    extra = 0


class ScoreBandInline(admin.TabularInline):
    model = ScoreBand
    extra = 0


@admin.register(ScreeningTool)
class ScreeningToolAdmin(admin.ModelAdmin):
    list_display = ("short_name", "name", "domain", "question_count", "score_multiplier", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    list_filter = ("is_active", "higher_is_better")
    search_fields = ("name", "short_name", "domain")
    prepopulated_fields = {"slug": ("short_name",)}
    inlines = [QuestionInline, AnswerChoiceInline, ScoreBandInline]

    @admin.display(description="Items")
    def question_count(self, obj):
        return obj.questions.count()


@admin.register(Guidance)
class GuidanceAdmin(admin.ModelAdmin):
    list_display = ("tier", "severity_rank", "headline", "retake_after_days", "show_professional_banner", "updated_at")
    list_editable = ("retake_after_days", "show_professional_banner")


@admin.register(ScoreBand)
class ScoreBandAdmin(admin.ModelAdmin):
    list_display = ("tool", "label", "min_score", "max_score", "guidance")
    list_filter = ("tool", "guidance")


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("user", "tool", "final_score", "band", "safety_flag", "created_at")
    list_filter = ("tool", "band__guidance", "safety_flag", "created_at")
    search_fields = ("user__username",)
    date_hierarchy = "created_at"
    list_select_related = ("user", "tool", "band")
    # Scores are calculated by the server, so they cannot be edited by hand.
    readonly_fields = ("user", "tool", "band", "raw_score", "final_score", "safety_flag", "created_at")

    def has_add_permission(self, request):
        return False
