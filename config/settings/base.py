"""
Base settings for the FORGE backend.

FORGE is a voluntary, student-led project and collaboration ecosystem for
the Open University of Kenya. The settings here are deliberately boring:
successive generations of student maintainers have to be able to read them.

Environment variables are documented in .env.example. Nothing secret is ever
committed to the repository -- the platform is developed in the open.
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-development-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "django_celery_beat",
]

LOCAL_APPS = [
    "forge.common",
    "forge.accounts",
    "forge.audit",
    "forge.projects",
    "forge.workspace",
    "forge.contributions",
    "forge.recognition",
    "forge.community",
    "forge.showcase",
    "forge.mentorship",
    "forge.moderation",
    "forge.notifications",
    "forge.portfolio",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "forge.audit.middleware.AuditContextMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default="postgres://postgres:postgres@localhost:5432/forge",
    )
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Passwords and authentication
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static and media
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Screenshots are small; demonstration VIDEO IS NEVER HOSTED HERE. Teams link
# to an unlisted video on an external platform. See forge/showcase/validators.py
# for the rationale -- video is the single largest bandwidth and storage cost
# on a platform of this kind and carries moderation risk we will not take on.
MAX_UPLOAD_BYTES = env.int("MAX_UPLOAD_BYTES", default=5 * 1024 * 1024)

# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "forge.common.pagination.ForgePagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Two layers: a global burst-and-sustained pair that every request passes
    # through, plus ScopedRateThrottle for the endpoints that need a tighter
    # limit of their own. See forge/common/throttling.py for why both exist.
    "DEFAULT_THROTTLE_CLASSES": (
        "forge.common.throttling.BurstAnonThrottle",
        "forge.common.throttling.SustainedAnonThrottle",
        "forge.common.throttling.BurstUserThrottle",
        "forge.common.throttling.SustainedUserThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        # Global ceilings. Generous, because they apply to everything --
        # a dashboard legitimately fires a dozen requests on mount.
        "anon-burst": env("THROTTLE_ANON_BURST", default="60/min"),
        "anon-sustained": env("THROTTLE_ANON_SUSTAINED", default="600/hour"),
        "user-burst": env("THROTTLE_USER_BURST", default="180/min"),
        "user-sustained": env("THROTTLE_USER_SUSTAINED", default="3000/hour"),

        # Credential endpoints. Tight, and backed by a lockout with a backoff
        # -- a rate limit alone still permits thousands of guesses a day.
        "login": env("THROTTLE_LOGIN", default="10/min"),
        "login-email": env("THROTTLE_LOGIN_EMAIL", default="8/hour"),
        "auth": "10/min",
        "registration": env("THROTTLE_REGISTRATION", default="5/hour"),
        "email-verification": env("THROTTLE_EMAIL_VERIFICATION", default="6/hour"),

        # Anything that costs the platform real work.
        "expensive": env("THROTTLE_EXPENSIVE", default="30/hour"),
        "export": "10/day",
        "pdf": env("THROTTLE_PDF", default="40/hour"),
        "write": "120/hour",
        "report": "20/day",
        "invite": env("THROTTLE_INVITE", default="60/day"),
    },
    "EXCEPTION_HANDLER": "forge.common.exceptions.forge_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FORGE API",
    "DESCRIPTION": (
        "FORGE -- a student project, collaboration and practical experience "
        "ecosystem, powered by the Open University of Kenya.\n\n"
        "FORGE awards no academic credit and issues nothing that could be "
        "mistaken for a University qualification. It complements the Learning "
        "Management System; it does not duplicate it."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    # Several models legitimately have a field called "status" or "kind" with
    # different choices. Naming them explicitly keeps the generated client
    # readable instead of producing Status859Enum and friends.
    "ENUM_NAME_OVERRIDES": {
        "ProjectStatusEnum": "forge.projects.models.Project.Status",
        "ApplicationStatusEnum": "forge.projects.models.Application.Status",
        "ContributionStatusEnum": "forge.contributions.models.Contribution.Status",
        "TaskStatusEnum": "forge.workspace.models.Task.Status",
        "MilestoneStatusEnum": "forge.workspace.models.Milestone.Status",
        "ReportStatusEnum": "forge.moderation.models.Report.Status",
        "MentorshipRequestStatusEnum": "forge.mentorship.models.MentorshipRequest.Status",
        "DimensionEnum": "forge.contributions.models.Dimension",
        "ThreadKindEnum": "forge.community.models.Thread.Kind",
        "BadgeKindEnum": "forge.recognition.models.Badge.Kind",
        "CertificateKindEnum": "forge.recognition.models.Certificate.Kind",
        "UserKindEnum": "forge.accounts.models.User.Kind",
        "MemberStatusEnum": "forge.accounts.models.User.Status",
        "NotificationCategoryEnum": "forge.notifications.models.Category",
    },
}

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------
# The pilot authenticates against a verified University email address. The
# settings below allow the Directorate of ICT to switch the platform onto
# University single sign-on without a code change. Until OIDC_ENABLED is true,
# UNIVERSITY_EMAIL_DOMAINS is the gate that keeps non-students out.

UNIVERSITY_EMAIL_DOMAINS = env.list(
    "UNIVERSITY_EMAIL_DOMAINS", default=["ouk.ac.ke", "students.ouk.ac.ke"]
)
OIDC_ENABLED = env.bool("OIDC_ENABLED", default=False)
OIDC_ISSUER = env("OIDC_ISSUER", default="")
OIDC_CLIENT_ID = env("OIDC_CLIENT_ID", default="")
OIDC_CLIENT_SECRET = env("OIDC_CLIENT_SECRET", default="")

EMAIL_VERIFICATION_TTL_HOURS = env.int("EMAIL_VERIFICATION_TTL_HOURS", default=24)

# ---------------------------------------------------------------------------
# Portfolio export signing
# ---------------------------------------------------------------------------
# A portfolio export is signed with an Ed25519 key so that an employer can
# verify it without trusting whoever handed them the file. The public key is
# served at /api/v1/portfolio/verification-key/ and the private key never
# leaves the server. Generate a pair with: python manage.py generate_signing_key

PORTFOLIO_SIGNING_KEY = env("PORTFOLIO_SIGNING_KEY", default="")
PORTFOLIO_SIGNING_KEY_ID = env("PORTFOLIO_SIGNING_KEY_ID", default="forge-dev-key-1")
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", default="http://localhost:8000")

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
#
# Port 26, not 25/465/587.
#
# Most cloud providers filter outbound 25, 465 and 587. Sends to a filtered
# port do not fail cleanly -- they hang until EMAIL_TIMEOUT and nothing in the
# logs says why, which is the worst failure mode available. cPanel-style hosts
# (zafrika.com is on HostPinnacle) also listen on 26, which is rarely filtered,
# and 26 speaks plaintext SMTP with STARTTLS rather than the implicit TLS that
# 465 expects.
#
# `python manage.py check_email` reports which ports are actually reachable
# from wherever you are running, and can send a real test message.

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=26)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")

# Never leave this unset. smtplib waits forever by default, and because
# ATOMIC_REQUESTS is on, a stalled send holds a database transaction open while
# it waits. Mail is not worth the database.
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="FORGE <forge@zafrika.com>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default="forge@zafrika.com")

# Two combinations silently deliver no mail at all. Refuse them at boot rather
# than let somebody diagnose it from a verification link that never arrives.
if EMAIL_BACKEND.endswith("smtp.EmailBackend") and EMAIL_HOST:
    from django.core.exceptions import ImproperlyConfigured

    if EMAIL_PORT == 465 and not EMAIL_USE_SSL:
        raise ImproperlyConfigured(
            "EMAIL_PORT=465 is implicit TLS and requires EMAIL_USE_SSL=True. "
            "For STARTTLS use port 26 or 587 with EMAIL_USE_TLS=True."
        )
    if EMAIL_USE_SSL and EMAIL_USE_TLS:
        raise ImproperlyConfigured(
            "EMAIL_USE_SSL and EMAIL_USE_TLS are mutually exclusive; Django refuses both."
        )

# Where the web client lives. Verification links are built against this, so it
# has to be the site a member actually opens -- not the API.
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:5173").rstrip("/")

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
#
# This is not an optional optimisation: throttle counters and sign-in lockouts
# live here. With the default local-memory backend each worker process keeps
# its own counters, so a limit of "10 a minute" silently becomes "10 a minute
# per worker". Development is fine on locmem; anything with more than one
# process needs the shared backend.

REDIS_URL = env("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "forge",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "forge-local",
        }
    }

# ---------------------------------------------------------------------------
# Background work
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TIMEZONE = TIME_ZONE

# The scheduled work, stated here so that a maintainer can see the whole of it
# in one place. django-celery-beat keeps the live schedule in the database and
# the Advisory Committee can adjust it through the admin without a deployment.
CELERY_BEAT_SCHEDULE = {
    "daily-digests": {
        "task": "forge.notifications.tasks.send_daily_digests",
        "schedule": crontab(hour=18, minute=0),      # early evening, Nairobi
    },
    "weekly-digests": {
        "task": "forge.notifications.tasks.send_weekly_digests",
        "schedule": crontab(hour=18, minute=30, day_of_week="sun"),
    },
    "flag-stale-projects": {
        "task": "forge.projects.tasks.flag_stale_projects",
        "schedule": crontab(hour=3, minute=0, day_of_week="mon"),
    },
    "expire-stale-applications": {
        "task": "forge.projects.tasks.expire_stale_applications",
        "schedule": crontab(hour=3, minute=30),
    },
    "nudge-quiet-members": {
        "task": "forge.projects.tasks.nudge_quiet_members",
        # Fortnightly, not weekly. A voluntary platform that nags gets muted.
        "schedule": crontab(hour=9, minute=0, day_of_week="wed"),
    },
    "rebuild-leaderboards": {
        "task": "forge.recognition.tasks.rebuild_leaderboards",
        "schedule": crontab(hour=2, minute=0),
    },
    "verify-ledger": {
        "task": "forge.recognition.tasks.verify_ledger_integrity",
        # A tamper-evident record nobody checks is just a record.
        "schedule": crontab(hour=4, minute=0),
    },
    "prune-old-notifications": {
        "task": "forge.notifications.tasks.prune_old_notifications",
        "schedule": crontab(hour=5, minute=0, day_of_week="sun"),
    },
}

# ---------------------------------------------------------------------------
# Platform policy knobs
# ---------------------------------------------------------------------------
# These encode commitments made in the concept proposal. They are settings
# rather than constants so that the Advisory Committee can tune them during
# the pilot without a code change.

FORGE_POLICY = {
    # Section 9, stage 2: a proposal that no mentor considers feasible must
    # not consume the time of five students before that becomes apparent.
    "PROPOSAL_REVIEW_TARGET_DAYS": env.int("PROPOSAL_REVIEW_TARGET_DAYS", default=7),
    # Section 9, stage 7: recognition is confirmed by two independent parties.
    "REQUIRED_ATTESTATIONS": env.int("REQUIRED_ATTESTATIONS", default=2),
    # A project with no activity for this long is flagged to its lead and
    # mentor, then archived. Abandoned work should not sit in the showcase.
    "PROJECT_STALE_AFTER_DAYS": env.int("PROJECT_STALE_AFTER_DAYS", default=30),
    "PROJECT_ABANDON_AFTER_DAYS": env.int("PROJECT_ABANDON_AFTER_DAYS", default=60),
    # Section 3.2: isolation is a retention risk. A student who has joined
    # nothing and posted nothing for this long gets a nudge, not a penalty.
    "LEARNER_QUIET_AFTER_DAYS": env.int("LEARNER_QUIET_AFTER_DAYS", default=21),
    # Section 10.4: separate leaderboards per discipline, so that the platform
    # does not collapse into a single programming contest.
    "LEADERBOARD_SIZE": env.int("LEADERBOARD_SIZE", default=25),
    # A lead may not attest to their own contribution. Enforced in code; the
    # setting exists only so the test suite can prove it is on.
    "FORBID_SELF_ATTESTATION": True,
    # How many concurrent active projects one student may lead. Prevents the
    # enthusiastic-founder failure mode where one person opens nine projects.
    "MAX_LED_PROJECTS": env.int("MAX_LED_PROJECTS", default=2),
    # Students do not choose their own password at sign-up. They give a
    # University address and the credentials are emailed to it, so an account
    # can only be opened by somebody who can read that mailbox.
    "CREDENTIALS_BY_EMAIL": env.bool("CREDENTIALS_BY_EMAIL", default=True),
    # How long an invitation stays usable.
    "INVITATION_TTL_DAYS": env.int("INVITATION_TTL_DAYS", default=14),
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# Django rejects a cross-origin POST that carries a session cookie unless the
# origin is listed here. The SPA authenticates with a bearer token and so does
# not strictly need it, but DRF's SessionAuthentication is also enabled -- for
# the browsable API and anything driven from a signed-in admin session -- and
# that path does enforce CSRF. Defaults to the CORS list, which is the same
# set of hosts in every deployment so far.
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=CORS_ALLOWED_ORIGINS)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "forge": {"handlers": ["console"], "level": "DEBUG" if DEBUG else "INFO",
                  "propagate": False},
    },
}
