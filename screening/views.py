from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from resources.models import Resource

from .forms import GuidanceForm, ScreeningForm
from .models import Assessment, Guidance, ScoreBand, ScreeningTool
from .permissions import counsellor_required, has_consented
from .scoring import ScoringError, score_answers

SESSION_RESULT_KEY = "anon_result"      # anonymous result, kept in the session only
SESSION_CRISIS_KEY = "crisis_pending"   # result key waiting for the crisis screen
SESSION_CRISIS_SEEN = "crisis_seen"     # result keys whose crisis screen has been shown


# ---------------------------------------------------------------- public pages

def home(request):
    tools = ScreeningTool.objects.filter(is_active=True).annotate(item_count=Count("questions"))
    crisis_lines = Resource.objects.filter(is_crisis_line=True)[:2]
    return render(request, "screening/home.html", {"tools": tools, "crisis_lines": crisis_lines})


def about(request):
    tools = ScreeningTool.objects.filter(is_active=True).prefetch_related("bands__guidance")
    return render(request, "screening/about.html", {"tools": tools})


def tool_list(request):
    tools = ScreeningTool.objects.filter(is_active=True).annotate(item_count=Count("questions"))
    return render(request, "screening/tool_list.html", {"tools": tools})


@require_http_methods(["GET", "POST"])
def consent(request):
    """Consent notice shown before the first questionnaire."""
    next_url = request.GET.get("next") or request.POST.get("next") or reverse("screening:tools")
    if not next_url.startswith("/"):
        next_url = reverse("screening:tools")  # never redirect to another site

    if request.method == "POST":
        if request.POST.get("agree") != "yes":
            messages.error(request, "Please tick the box to agree before you continue.")
        else:
            if request.user.is_authenticated:
                profile = request.user.profile
                profile.consent_given_at = timezone.now()
                profile.save(update_fields=["consent_given_at"])
            else:
                request.session["consent_given"] = True
            messages.success(request, "Thank you. You can start a screening now.")
            return redirect(next_url)
    return render(request, "screening/consent.html", {"next": next_url})


# ---------------------------------------------------------------- taking a screening

@require_http_methods(["GET", "POST"])
def take_screening(request, slug):
    tool = get_object_or_404(
        ScreeningTool.objects.prefetch_related("questions", "choices"), slug=slug, is_active=True
    )
    if not has_consented(request):
        return redirect(f"{reverse('screening:consent')}?next={request.path}")

    signed_in = request.user.is_authenticated
    if request.method == "POST":
        form = ScreeningForm(tool, request.POST, allow_save=signed_in)
        if form.is_valid():
            try:
                result = score_answers(tool, form.answers())
            except ScoringError as exc:
                form.add_error(None, str(exc))
            else:
                save = signed_in and form.cleaned_data.get("save_result")
                if save:
                    assessment = Assessment.objects.create(
                        user=request.user, tool=tool, band=result.band,
                        raw_score=result.raw_score, final_score=result.final_score,
                        safety_flag=result.safety_flag,
                    )
                    key = f"a{assessment.pk}"
                    result_url = assessment.get_absolute_url()
                else:
                    # Anonymous mode: nothing is written to the database.
                    request.session[SESSION_RESULT_KEY] = result.as_session_dict()
                    key = "session"
                    result_url = reverse("screening:session_result")

                if result.safety_flag:
                    request.session[SESSION_CRISIS_KEY] = {"key": key, "next": result_url}
                    return redirect("screening:crisis")
                return redirect(result_url)
        messages.error(request, "Some answers are missing. Please check the highlighted questions.")
    else:
        form = ScreeningForm(tool, allow_save=signed_in)

    return render(request, "screening/take.html", {"tool": tool, "form": form})


def crisis(request):
    """Shown before the result whenever the safety item is answered above 0."""
    pending = request.session.get(SESSION_CRISIS_KEY)
    if not pending:
        return redirect("home")
    seen = set(request.session.get(SESSION_CRISIS_SEEN, []))
    seen.add(pending["key"])
    request.session[SESSION_CRISIS_SEEN] = list(seen)
    resources = Resource.objects.filter(
        Q(is_crisis_line=True) | Q(category__slug="campus-counselling")
    ).select_related("category")
    return render(request, "screening/crisis.html", {"resources": resources, "next_url": pending["next"]})


def _crisis_not_seen(request, key, safety_flag):
    return safety_flag and key not in request.session.get(SESSION_CRISIS_SEEN, [])


def _result_context(tool, band, raw_score, final_score, safety_flag):
    guidance = band.guidance
    resources = Resource.objects.select_related("category")
    if guidance.tier in ("moderate", "high"):
        resources = resources.filter(Q(is_crisis_line=True) | Q(category__slug__in=["campus-counselling", "hospital"]))
    else:
        resources = resources.filter(is_crisis_line=True)
    return {
        "tool": tool, "band": band, "guidance": guidance, "raw_score": raw_score,
        "final_score": final_score, "max_score": tool.max_final_score,
        "safety_flag": safety_flag, "resources": resources,
        "all_bands": tool.bands.select_related("guidance"),
    }


@login_required
def result(request, pk):
    # Filtering by user means nobody can open another person's result (they get 404).
    assessment = get_object_or_404(
        Assessment.objects.select_related("tool", "band__guidance"), pk=pk, user=request.user
    )
    if _crisis_not_seen(request, f"a{pk}", assessment.safety_flag):
        request.session[SESSION_CRISIS_KEY] = {"key": f"a{pk}", "next": assessment.get_absolute_url()}
        return redirect("screening:crisis")
    ctx = _result_context(assessment.tool, assessment.band, assessment.raw_score,
                          assessment.final_score, assessment.safety_flag)
    ctx.update({"assessment": assessment, "saved": True})
    return render(request, "screening/result.html", ctx)


def session_result(request):
    data = request.session.get(SESSION_RESULT_KEY)
    if not data:
        messages.info(request, "There is no private result in this session. Take a screening first.")
        return redirect("screening:tools")
    if _crisis_not_seen(request, "session", data["safety_flag"]):
        request.session[SESSION_CRISIS_KEY] = {"key": "session", "next": reverse("screening:session_result")}
        return redirect("screening:crisis")
    tool = get_object_or_404(ScreeningTool, pk=data["tool_id"])
    band = get_object_or_404(ScoreBand.objects.select_related("guidance"), pk=data["band_id"])
    ctx = _result_context(tool, band, data["raw_score"], data["final_score"], data["safety_flag"])
    ctx.update({"saved": False, "taken_at": timezone.now()})
    return render(request, "screening/result.html", ctx)


@require_POST
def clear_session_result(request):
    """Lets an anonymous user wipe their private result straight away."""
    for key in (SESSION_RESULT_KEY, SESSION_CRISIS_KEY, SESSION_CRISIS_SEEN):
        request.session.pop(key, None)
    messages.success(request, "Your private result has been cleared from this browser session.")
    return redirect("home")


# ---------------------------------------------------------------- history

@login_required
def history(request):
    assessments = request.user.assessments.select_related("tool", "band__guidance")
    tool_slug = request.GET.get("tool", "")
    tier = request.GET.get("tier", "")
    if tool_slug:
        assessments = assessments.filter(tool__slug=tool_slug)
    if tier:
        if tier not in Guidance.Tier.values:
            messages.error(request, "Unknown level filter - showing all results.")
            tier = ""
        else:
            assessments = assessments.filter(band__guidance__tier=tier)

    # One small chart per tool, oldest to newest.
    charts = []
    for tool in ScreeningTool.objects.filter(assessments__user=request.user).distinct():
        rows = request.user.assessments.filter(tool=tool).order_by("created_at")
        charts.append({
            "slug": tool.slug, "name": tool.short_name, "max": tool.max_final_score,
            "higher_is_better": tool.higher_is_better,
            "labels": [timezone.localtime(a.created_at).strftime("%d %b") for a in rows],
            "scores": [a.final_score for a in rows],
        })

    return render(request, "screening/history.html", {
        "assessments": assessments,
        "charts": charts,
        "tools": ScreeningTool.objects.filter(is_active=True),
        "tiers": Guidance.Tier.choices,
        "selected_tool": tool_slug,
        "selected_tier": tier,
    })


@login_required
@require_http_methods(["GET", "POST"])
def delete_assessment(request, pk):
    assessment = get_object_or_404(Assessment, pk=pk, user=request.user)
    if request.method == "POST":
        assessment.delete()
        messages.success(request, "That result has been permanently deleted.")
        return redirect("screening:history")
    return render(request, "screening/confirm_delete.html", {"assessment": assessment})


# ---------------------------------------------------------------- counsellor area

@counsellor_required
def counsellor_dashboard(request):
    """Aggregate numbers only - counsellors never see who took which screening."""
    tools = ScreeningTool.objects.annotate(
        total=Count("assessments"),
        low=Count("assessments", filter=Q(assessments__band__guidance__tier="low")),
        mild=Count("assessments", filter=Q(assessments__band__guidance__tier="mild")),
        moderate=Count("assessments", filter=Q(assessments__band__guidance__tier="moderate")),
        high=Count("assessments", filter=Q(assessments__band__guidance__tier="high")),
    )
    stats = {
        "members": User.objects.filter(profile__role="member").count(),
        "assessments": Assessment.objects.count(),
        "safety_flags": Assessment.objects.filter(safety_flag=True).count(),
        "resources": Resource.objects.count(),
        "stale_resources": Resource.objects.filter(
            last_verified__lt=timezone.localdate() - timedelta(days=90)).count(),
    }
    return render(request, "screening/counsellor_dashboard.html", {
        "tools": tools, "stats": stats, "guidance_list": Guidance.objects.all(),
    })


@counsellor_required
@require_http_methods(["GET", "POST"])
def edit_guidance(request, tier):
    guidance = get_object_or_404(Guidance, tier=tier)
    form = GuidanceForm(request.POST or None, instance=guidance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Guidance for the {guidance.get_tier_display()} level was updated.")
        return redirect("screening:counsellor")
    return render(request, "screening/guidance_form.html", {"form": form, "guidance": guidance})

