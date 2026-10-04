"""Isolated tests: never read the application's database or external credentials."""
import os
os.environ.setdefault('DJANGO_SECRET_KEY', 'test-only-secret-at-least-32-characters')
os.environ['DATABASE_URL'] = os.getenv('TEST_DATABASE_URL', 'sqlite:///:memory:')
from .settings import *  # noqa: F403
DEMO_MODE = True
OPENAI_API_KEY = ''
TELEGRAM_BOT_TOKEN = ''
TELEGRAM_BOT_USERNAME = ''
INSTAGRAM_PUBLISH_ENABLED = False
INSTAGRAM_ACCESS_TOKEN = ''
INSTAGRAM_USER_ID = ''
CELERY_TASK_ALWAYS_EAGER = False
