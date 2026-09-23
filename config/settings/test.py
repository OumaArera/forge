"""Test settings: fast, isolated, no external services."""

from .base import *

DEBUG = False
SECRET_KEY = "test-key-not-secret"
CELERY_TASK_ALWAYS_EAGER = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# A fixed key so that signature tests are deterministic.
PORTFOLIO_SIGNING_KEY = (
    "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
)
PORTFOLIO_SIGNING_KEY_ID = "forge-test-key"

# WhiteNoise complains about a missing staticfiles directory during tests and
# nothing under test serves static files anyway.
STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}
WHITENOISE_AUTOREFRESH = True
WHITENOISE_USE_FINDERS = True
