import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


SECRET_KEY = env("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "common",
    "organisations",
    "authentication",
    "users",
    "workorders",
    "scheduling",
    "progress_events",
    "attachments",
    "audit",
    "notifications",
    "realtime",
    "reporting",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "common.middleware.CorrelationIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.middleware.RequestLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "fielddesk"),
        "USER": env("POSTGRES_USER", "fielddesk"),
        "PASSWORD": env("POSTGRES_PASSWORD", "fielddesk-development-only"),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PAGINATION_CLASS": "common.pagination.FieldDeskPageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "common.exception_handler.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

JWT_REFRESH_COOKIE_NAME = "fielddesk_refresh"
JWT_REFRESH_COOKIE_SECURE = env_bool("JWT_REFRESH_COOKIE_SECURE", True)

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "auth_login_ip": env("AUTH_LOGIN_IP_RATE", "20/hour"),
    "auth_login_identity": env("AUTH_LOGIN_IDENTITY_RATE", "10/hour"),
    "progress_event": env("PROGRESS_EVENT_RATE", "120/minute"),
}

PROGRESS_EVENT_MAX_FUTURE_SECONDS = int(env("PROGRESS_EVENT_MAX_FUTURE_SECONDS", "300"))
PROGRESS_EVENT_MAX_AGE_DAYS = int(env("PROGRESS_EVENT_MAX_AGE_DAYS", "30"))
ATTACHMENT_MAX_BYTES = int(env("ATTACHMENT_MAX_BYTES", "10485760"))
ORGANISATION_STORAGE_LIMIT_BYTES = int(
    env("ORGANISATION_STORAGE_LIMIT_BYTES", "104857600")
)

CORS_ALLOWED_ORIGINS = env_list("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "staticfiles"
MEDIA_URL = "/protected-media/"
MEDIA_ROOT = BASE_DIR.parent / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.User"

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
NOTIFICATION_PROVIDER_MODE = env("NOTIFICATION_PROVIDER_MODE", "success")
NOTIFICATION_PROVIDER_TEMPORARY_FAILURES = int(
    env("NOTIFICATION_PROVIDER_TEMPORARY_FAILURES", "1")
)
NOTIFICATION_MAX_RETRIES = int(env("NOTIFICATION_MAX_RETRIES", "3"))
NOTIFICATION_RETRY_BASE_SECONDS = int(env("NOTIFICATION_RETRY_BASE_SECONDS", "2"))
REALTIME_HEARTBEAT_SECONDS = int(env("REALTIME_HEARTBEAT_SECONDS", "15"))
REALTIME_MAX_CONNECTION_SECONDS = int(env("REALTIME_MAX_CONNECTION_SECONDS", "600"))
REPORT_EXPORT_MAX_ROWS = int(env("REPORT_EXPORT_MAX_ROWS", "100000"))
REPORT_EXPORT_CHUNK_SIZE = int(env("REPORT_EXPORT_CHUNK_SIZE", "1000"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "common.logging.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.server": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "fielddesk": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
