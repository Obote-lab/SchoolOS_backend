"""
Base settings shared by all environments.
"""

import os
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from decouple import config, Csv

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # schoolOS/

# Security
SECRET_KEY = config("SECRET_KEY")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost", cast=Csv())

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="http://localhost:5173", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="http://localhost:5173", cast=Csv())

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5173")

# Application definition
DJANGO_APPS = [
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "rest_framework_gis",
    "corsheaders",
    "django_filters",
    "django_redis",
    "whitenoise.runserver_nostatic",
]

DOMAIN_APPS = [
    "core",
    "accounts",
    "schools",
    "students",
    "staff",
    "academics",
    "attendance",
    "finance",
    "welfare",
    "activities",
    "communications",
    "compliance",
    "dormitory",
    "branding",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + DOMAIN_APPS

# Middleware
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
    "schools.middleware.SchoolContextMiddleware",

    # Add Rollbar as the LAST middleware
    'rollbar.contrib.django.middleware.RollbarNotifierMiddleware',
]

ROOT_URLCONF = "schoolOS.urls"
WSGI_APPLICATION = "schoolOS.wsgi.application"

# Templates
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

EMAIL_TEMPLATE_DIR = BASE_DIR / "templates" / "accounts" / "emails"

# Database (PostGIS)
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": config("POSTGRES_DB"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "ATOMIC_REQUESTS": True,
        "CONN_HEALTH_CHECKS":True
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Nairobi"
USE_I18N = True
USE_TZ = True

# Static & Media
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Auth
AUTH_USER_MODEL = "accounts.CustomUser"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "2000/hour",
    },

    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler'
}

# Simple JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
}

# DRF Spectacular (OpenAPI)
SPECTACULAR_SETTINGS = {
    "TITLE": "School Operating System API",
    "DESCRIPTION": "Comprehensive Education Operating System for Kenyan Schools",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "SECURITY": [{"Bearer": []}],
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "filter": True,
    },
    "TAGS": [
        {"name": "Authentication", "description": "Authentication endpoints"},
        {"name": "Users", "description": "User management"},
        {"name": "Roles", "description": "Role management"},
        {"name": "Permissions", "description": "Permission management"},
    ],
    "ENUM_NAME_OVERRIDES": {
    "GenderEnum": "core.choices.common.GenderChoices",
    "NutritionQualityEnum": "core.choices.welfare.NutritionQualityChoices",
    "StreamEnum": "core.choices.academic.SubjectSpecializationChoices",
    "AttendanceSessionTypeEnum": "core.choices.attendance.SessionTypeChoices",
    "CounselingSessionTypeEnum": "core.choices.welfare.CounselingSessionTypeChoices",
    "BannerLevelChoices": "branding.models.BannerLevelChoices",
    "LevelE02Enum": "branding.models.BannerLevelChoices",
},
}


# Cache (Redis)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "eduos",
    }
}

CACHE_TTL = 60 * 15  # 15 minutes

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@schoolos.com")

# GIS libraries (optional – only set if provided)
# GDAL_LIBRARY_PATH = config("GDAL_LIBRARY_PATH", default=None)
# GEOS_LIBRARY_PATH = config("GEOS_LIBRARY_PATH", default=None)
GDAL_LIBRARY_PATH=None
GEOS_LIBRARY_PATH=None
if GDAL_LIBRARY_PATH:
    os.environ["GDAL_LIBRARY_PATH"] = GDAL_LIBRARY_PATH
if GEOS_LIBRARY_PATH:
    os.environ["GEOS_LIBRARY_PATH"] = GEOS_LIBRARY_PATH

# Defaults
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Phone numbers (Kenya)
# PHONENUMBER_DEFAULT_REGION = "KE"
DEFAULT_COUNTRY = config(
    "DEFAULT_COUNTRY",
    default="KE"
)
PHONENUMBER_DB_FORMAT = "E164"


# the Rollba Settings# settings.py
ROLLBAR_ACCESS_TOKEN = config('ROLLBAR_ACCESS_TOKEN')
ROLLBAR_ENVIRONMENT = config('ROLLBAR_ENVIRONMENT', 'development')



ROLLBAR = {
    'access_token': config('ROLLBAR_ACCESS_TOKEN'),
    'environment': 'development',
    'code_version': config('GIT_SHA', '1.0.0'),
    'root': BASE_DIR,
}

print("DEBUG =", settings.DEBUG)
print("MEDIA_ROOT =", settings.MEDIA_ROOT)
print("MEDIA_URL =", settings.MEDIA_URL)