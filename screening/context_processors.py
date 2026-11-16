def site_context(request):
    """Values available in every template."""
    user = request.user
    is_counsellor = bool(
        user.is_authenticated and hasattr(user, "profile") and user.profile.is_counsellor
    )
    return {
        "SITE_NAME": "MindCheck",
        "HELPLINE_NAME": "Tele-MANAS",
        "HELPLINE_NUMBER": "14416",
        "HELPLINE_ALT": "1-800-891-4416",
        "is_counsellor": is_counsellor,
    }
