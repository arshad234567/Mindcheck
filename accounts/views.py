from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from screening.models import ScreeningTool

from .forms import LoginForm, RegisterForm


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)  # Django also rotates the session key here
        messages.success(request, f"Welcome, {user.username}! Your account has been created.")
        return redirect("screening:consent")
    return render(request, "accounts/register.html", {"form": form})


class MindCheckLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("home")


@login_required
def dashboard(request):
    if request.user.profile.is_counsellor:
        return redirect("screening:counsellor")
    recent = request.user.assessments.select_related("tool", "band__guidance")[:5]
    latest_by_tool = []
    for tool in ScreeningTool.objects.filter(is_active=True):
        latest = request.user.assessments.filter(tool=tool).select_related("band__guidance").first()
        latest_by_tool.append({"tool": tool, "latest": latest})
    return render(request, "accounts/dashboard.html", {
        "recent": recent,
        "latest_by_tool": latest_by_tool,
        "total": request.user.assessments.count(),
    })


@login_required
@require_http_methods(["GET", "POST"])
def delete_my_data(request):
    """Lets a user erase all saved results, or their whole account (DPDP Act: right to erasure)."""
    count = request.user.assessments.count()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "results":
            request.user.assessments.all().delete()
            messages.success(request, f"All {count} saved results were permanently deleted.")
            return redirect("accounts:dashboard")
        if action == "account":
            user = request.user
            logout(request)
            user.delete()  # cascades to Profile and every Assessment
            messages.success(request, "Your account and all of its data have been permanently deleted.")
            return redirect("home")
        messages.error(request, "Please choose what you want to delete.")
    return render(request, "accounts/delete_my_data.html", {"count": count})
