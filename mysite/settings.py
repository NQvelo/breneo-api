from pathlib import Path
import os
from dotenv import load_dotenv
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent
# Load .env from project root so env vars are found regardless of CWD
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key")
# Set DEBUG=1 or DJANGO_DEBUG=1 in env to see full error pages and tracebacks
DEBUG = os.getenv("DEBUG", os.getenv("DJANGO_DEBUG", "0")) in ("1", "true", "True")

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "breneo.onrender.com",
    "www.breneo.onrender.com",
    "web-production-80ed8.up.railway.app",  # your Railway deployment
]
# Railway: add host from env if set (for other Railway services)
_railway_host = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if _railway_host and _railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_host)
# Optional: add more hosts via comma-separated env var
_extra_hosts = os.getenv("ALLOWED_HOSTS", "")
if _extra_hosts:
    ALLOWED_HOSTS.extend(h.strip() for h in _extra_hosts.split(",") if h.strip())




INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    'rest_framework_simplejwt',
    "corsheaders",
    "app",
    'cloudinary',
    'cloudinary_storage',
]


# ----------------- MEDIA & CLOUDINARY CONFIG -----------------

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Cloudinary keys: set in .env (project root), e.g. CLOUDINARY_CLOUD_NAME=xxx
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'



STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'






MIDDLEWARE = [
    "mysite.debug_middleware.LogExceptionMiddleware",  # log full traceback to console on 500
    "corsheaders.middleware.CorsMiddleware", 
    "django.middleware.security.SecurityMiddleware",
    'whitenoise.middleware.WhiteNoiseMiddleware',
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

WHITENOISE_USE_FINDERS = True

CORS_ALLOW_ALL_ORIGINS = True






ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

WSGI_APPLICATION = "mysite.wsgi.application"


# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }


import os
import dj_database_url


# Use SQLite for local dev when DATABASE_URL is not set
if os.environ.get("DATABASE_URL"):
    _db = dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        ssl_require=True,
    )
    # Ensure PostgreSQL uses SSL on Railway/cloud
    if _db.get("ENGINE") == "django.db.backends.postgresql":
        _opts = _db.setdefault("OPTIONS", {})
        _opts.setdefault("sslmode", "require")
    DATABASES = {"default": _db}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": os.getenv("DB_NAME"),
#         "USER": os.getenv("DB_USER"),
#         "PASSWORD": os.getenv("DB_PASSWORD"),
#         "HOST": os.getenv("DB_HOST"),
#         "PORT": os.getenv("DB_PORT"),
#     }
# }



# Project static (e.g. admin JS overrides) — always include so collectstatic picks it up
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


GSK_API_KEY = os.getenv("GSK_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        
    ),
}


CSRF_TRUSTED_ORIGINS = [
    "https://breneo.onrender.com",
    "https://www.breneo.onrender.com",
    "https://web-production-80ed8.up.railway.app",
]
# Add Railway origin from env if set
_r = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if _r:
    _railway_origin = f"https://{_r}"
    if _railway_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(_railway_origin)
# Optional: comma-separated list of origins, e.g. https://app.example.com
_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
if _origins:
    CSRF_TRUSTED_ORIGINS.extend(o.strip() for o in _origins.split(",") if o.strip())




# Email: Resend SMTP (set RESEND_API_KEY in .env to enable) or console for local dev
# Use os.getenv so we read the same .env that load_dotenv() loaded
RESEND_API_KEY = (os.getenv("RESEND_API_KEY") or "").strip()
if RESEND_API_KEY:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "resend"
    EMAIL_HOST_PASSWORD = RESEND_API_KEY
    DEFAULT_FROM_EMAIL = (os.getenv("DEFAULT_FROM_EMAIL") or "onboarding@resend.dev").strip()
else:
    EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
    EMAIL_HOST = config("EMAIL_HOST", default="localhost")
    EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
    EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
    EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
    DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@localhost")

# Show which email backend is active when settings load (restart server to see this)
if RESEND_API_KEY:
    print("[Email] Using Resend SMTP – emails will appear in resend.com → Logs")
else:
    print("[Email] RESEND_API_KEY not set – emails only in terminal, not in Resend")


# ----------- BOG Payment Integration Settings -----------

BOG_CLIENT_ID = os.getenv("BOG_CLIENT_ID")
BOG_CLIENT_SECRET = os.getenv("BOG_CLIENT_SECRET")
BOG_TOKEN_URL = os.getenv("BOG_TOKEN_URL")
BOG_ORDER_URL = os.getenv("BOG_ORDER_URL")
BOG_SUBSCRIBE_URL = os.getenv("BOG_SUBSCRIBE_URL")
BOG_CALLBACK_SECRET_PUBLIC_KEY = os.getenv("BOG_CALLBACK_SECRET_PUBLIC_KEY")

# ----------- Debug: log all errors with traceback to console -----------
import sys
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "app": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "mysite.debug_middleware": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}