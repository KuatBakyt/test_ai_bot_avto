import os
from datetime import timedelta
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)
def flag(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes')
DEBUG = flag('DJANGO_DEBUG', True)
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured('Set DJANGO_SECRET_KEY to at least 32 random characters.')
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,api,testserver').split(',')
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'rest_framework', 'rest_framework_simplejwt.token_blacklist', 'drf_spectacular',
    'corsheaders', 'studio']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
    'OPTIONS': {'context_processors': ['django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': dj_database_url.config(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}]
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Asia/Almaty'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:8081').split(',')
CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if os.getenv('CSRF_TRUSTED_ORIGINS') else []
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'EXCEPTION_HANDLER': 'studio.exceptions.handler',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '20/min', 'user': '120/min'}}
SIMPLE_JWT = {'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30), 'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True, 'BLACKLIST_AFTER_ROTATION': True}
SPECTACULAR_SETTINGS = {'TITLE': 'Review Studio API', 'VERSION': '1.0.0', 'COMPONENT_SPLIT_REQUEST': True}
DEMO_MODE = flag('DEMO_MODE', True)
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', '').lstrip('@')
INSTAGRAM_PUBLISH_ENABLED = flag('INSTAGRAM_PUBLISH_ENABLED')
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')
INSTAGRAM_USER_ID = os.getenv('INSTAGRAM_USER_ID', '')
INSTAGRAM_API_VERSION = os.getenv('INSTAGRAM_API_VERSION', 'v23.0')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = flag('TASKS_EAGER', False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {'dispatch-posts': {'task': 'studio.tasks.dispatch', 'schedule': 15.0}}
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = flag('SECURE_SSL_REDIRECT', True)
