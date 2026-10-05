"""
Development settings.
"""

from .base import *

DEBUG = True

# Allow all origins in development (override if needed)
CORS_ALLOW_ALL_ORIGINS = True

# More verbose logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django.db.backends": {
            "level": "DEBUG",  # show SQL queries
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

# Optional: use console email backend in pure local dev
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5173")