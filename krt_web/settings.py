"""
KRT Maker - Standalone Django Web Application

A beautiful web interface for generating Key Resources Tables (KRTs) from bioRxiv articles.
Supports both AI-powered (LLM) and pattern-based (regex) extraction methods.
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default="django-insecure-+_ds_u+nhnjy3gbu!t@98ddozkna6sj!!))7^!5)4e)p@@hml$")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,krt.xeradb.com', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
INSTALLED_APPS = [
    'web',  # Our KRT maker web app
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "krt_web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = "krt_web.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Add the static directory for browser extension
]

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50MB

# Production settings
if not DEBUG:
    # Security settings
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_HSTS_SECONDS = 31536000
    X_FRAME_OPTIONS = 'DENY'
    
    # Use WhiteNoise for static files in production
    MIDDLEWARE.insert(2, 'whitenoise.middleware.WhiteNoiseMiddleware')
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Database configuration
import dj_database_url
if config('DATABASE_URL', default=None):
    DATABASES['default'] = dj_database_url.parse(config('DATABASE_URL'))

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# XML File Storage Configuration
XML_STORAGE_DIR = os.path.join(BASE_DIR, 'xml_files')

# Create XML storage directory if it doesn't exist
os.makedirs(XML_STORAGE_DIR, exist_ok=True)
