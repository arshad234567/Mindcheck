"""Custom error handlers that render friendly pages using the site layout."""

from django.shortcuts import render


def bad_request(request, exception=None):
    return render(request, "errors/400.html", status=400)


def permission_denied(request, exception=None):
    return render(request, "errors/403.html", {"reason": str(exception or "")}, status=403)


def page_not_found(request, exception=None):
    return render(request, "errors/404.html", {"path": request.path}, status=404)


def server_error(request):
    # Uses a stand-alone template that does not depend on the database.
    return render(request, "errors/500.html", status=500)


def csrf_failure(request, reason=""):
    return render(request, "errors/403.html", {
        "reason": "The form expired or was sent without its security token. Please go back, refresh and try again."
    }, status=403)
