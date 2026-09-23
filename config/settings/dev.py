"""Development settings. Never used in production."""

from .base import *
from .base import env

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
CELERY_TASK_ALWAYS_EAGER = True

# Mail goes to the terminal by default, so that nobody's first local run sends
# a real message to a real student. Set EMAIL_BACKEND in .env to send for real
# -- which is what `manage.py check_email --to ...` needs.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
