import uuid
from django.conf import settings
from django.db import models

def demo_default():
    return settings.DEMO_MODE

class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=2000)
    city = models.CharField(max_length=80, default='Алматы')
    photo = models.FileField(upload_to='jobs/', blank=True)
    photo_rights = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=demo_default, editable=False)
    auto_publish = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Review(models.Model):
    class Stage(models.TextChoices):
        INVITED = 'INVITED', 'Приглашён'
        CONSENT = 'CONSENT', 'Согласие на AI'
        CHATTING = 'CHATTING', 'Диалог'
        APPROVAL = 'APPROVAL', 'Подтверждение отзыва'
        PUBLIC = 'PUBLIC', 'Разрешение публикации'
        DONE = 'DONE', 'Готово'
        STOPPED = 'STOPPED', 'Остановлен'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='review')
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    chat_id = models.BigIntegerField(null=True, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.INVITED)
    ai_consent = models.BooleanField(default=False)
    public_consent = models.BooleanField(default=False)
    history = models.JSONField(default=list)
    answers = models.JSONField(default=list)
    approved_text = models.TextField(blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Post(models.Model):
    class Status(models.TextChoices):
        GENERATING = 'GENERATING', 'Подготовка'
        DRAFT = 'DRAFT', 'Черновик'
        QUEUED = 'QUEUED', 'В очереди'
        CREATING = 'CREATING', 'Создание контейнера'
        WAITING = 'WAITING', 'Обработка фотографии'
        PUBLISHING = 'PUBLISHING', 'Публикация'
        PUBLISHED = 'PUBLISHED', 'Опубликован'
        DEMO = 'DEMO', 'Тест завершён'
        FAILED = 'FAILED', 'Ошибка'
        UNCERTAIN = 'UNCERTAIN', 'Нужна сверка с Instagram'
        CANCELLED = 'CANCELLED', 'Отменён'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='post')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.GENERATING)
    caption = models.TextField(blank=True)
    container_id = models.CharField(max_length=100, blank=True)
    media_id = models.CharField(max_length=100, blank=True)
    permalink = models.URLField(blank=True)
    media_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    error = models.CharField(max_length=300, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class BotState(models.Model):
    name = models.CharField(primary_key=True, max_length=40)
    offset = models.BigIntegerField(default=0)

class TelegramOutbox(models.Model):
    update_id = models.BigIntegerField(unique=True)
    chat_id = models.BigIntegerField()
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
