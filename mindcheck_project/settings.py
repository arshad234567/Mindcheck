"""
Django settings for the MindCheck project.

MindCheck is a private mental-health screening and signposting platform
built with Django 5.2 (LTS). It screens; it does not diagnose.
"""

import os
from pathlib import Path

# BASE_DIR is the folder that contains manage.py
BASE_DIR = Path(__file__).resolve().parent.parent

# The secret key can be overridden with an environment variable in a real deployment.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-mindcheck-dev-key-change-me-0b7c1f3e9a4d",
)

# True when the app runs on Vercel (Vercel sets the VERCEL environment variable).
ON_VERCEL = bool(os.environ.get("VERCEL"))

# DEBUG is on for local development and off on Vercel.
# Run locally with DJANGO_DEBUG=0 to see the custom 404/500 pages.
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if ON_VERCEL else "1") == "1"

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver", ".vercel.app"]
CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]


# Applications -----------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Project apps
    "accounts.apps.AccountsConfig",
    "screening.apps.ScreeningConfig",
    "resources.apps.ResourcesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves /static/ files, also on Vercel
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "mindcheck_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level templates folder (base.html, error pages, app templates)
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Adds the crisis helpline and the user's role to every page
                "screening.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "mindcheck_project.wsgi.application"


# Database ---------------------------------------------------------------
DB_FILE = BASE_DIR / "db.sqlite3"

if ON_VERCEL:
    # Vercel's project folder is read-only, so the filled database is copied to /tmp
    # (the only writable folder) when a server instance starts. Changes made on the
    # live site are temporary and reset when Vercel starts a fresh instance.
    import shutil

    TMP_DB = Path("/tmp/mindcheck.sqlite3")
    if not TMP_DB.exists():
        shutil.copyfile(DB_FILE, TMP_DB)
    DB_FILE = TMP_DB

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DB_FILE,
    }
}


# Password validation ----------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
LOGOUT_REDIRECT_URL = "home"


# Internationalisation ---------------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True


# Static files -----------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # used only by collectstatic
WHITENOISE_USE_FINDERS = True            # WhiteNoise serves straight from static/ (no collectstatic needed)


# Sessions and security --------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True   # anonymous results vanish when the browser closes
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
CSRF_FAILURE_VIEW = "mindcheck_project.error_views.csrf_failure"

if ON_VERCEL:
    # Vercel can run several short-lived instances, so sessions are kept in a signed
    # (tamper-proof) cookie instead of the database. HTTPS-only cookies on the live site.
    SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
