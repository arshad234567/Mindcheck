from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def counsellor_required(view_func):
    """Allow only signed-in users whose profile role is Counsellor (others get the 403 page)."""

    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if not (profile and profile.is_counsellor):
            raise PermissionDenied("Only counsellors can open this page.")
        return view_func(request, *args, **kwargs)

    return wrapper


def has_consented(request):
    """Signed-in users consent once (stored on Profile); visitors consent per session."""
    if request.user.is_authenticated:
        return request.user.profile.has_consented
    return bool(request.session.get("consent_given"))
