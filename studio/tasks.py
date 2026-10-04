from datetime import timedelta
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Job, Post
from .integrations import Instagram, IntegrationError, make_caption

ACTIVE = ['GENERATING', 'QUEUED', 'WAITING']

def permitted(job):
    return (job.photo and job.photo_rights and hasattr(job, 'review') and job.review.stage == 'DONE'
        and job.review.public_consent and job.review.ai_consent and bool(job.review.approved_text))

@shared_task
def advance(post_id):
    publish_now = False
    with transaction.atomic():
        initial = Post.objects.filter(pk=post_id).first()
        if not initial:
            return
        job = Job.objects.select_for_update().get(pk=initial.job_id)
        post = Post.objects.select_for_update().get(pk=post_id)
        now = timezone.now()
        if post.status not in ACTIVE or (post.due_at and post.due_at > now):
            return
        if not permitted(job):
            post.status, post.error = 'CANCELLED', 'Отсутствует разрешение клиента или право использовать фото.'
            post.save()
            return
        try:
            if post.status == 'GENERATING':
                post.caption = make_caption(job)
                if len(post.caption) > 2200:
                    raise IntegrationError('Текст поста слишком длинный.')
                post.status = 'QUEUED' if job.auto_publish and (settings.DEMO_MODE or job.is_demo or settings.INSTAGRAM_PUBLISH_ENABLED) else 'DRAFT'
                post.due_at = now
            elif settings.DEMO_MODE or job.is_demo:
                post.status, post.media_id = 'DEMO', 'demo-' + str(post.id)
                post.published_at = now
            elif post.status == 'QUEUED':
                adapter = Instagram()
                post.status = 'CREATING'
                # This transaction locks the job: edits/revocations cannot interleave with this step.
                post.container_id = adapter.create(post)
                post.status = 'WAITING'
                post.attempts = 0
                post.due_at = now + timedelta(seconds=15)
            elif post.status == 'WAITING':
                status = Instagram().status(post.container_id)
                post.attempts += 1
                if status == 'FINISHED':
                    post.status = 'PUBLISHING'
                    post.lease_until = now + timedelta(minutes=2)
                    publish_now = True
                elif status in ('ERROR', 'EXPIRED') or post.attempts >= 40:
                    raise IntegrationError('Instagram не обработал фотографию. Создайте новую попытку после проверки фото.')
                else:
                    post.due_at = now + timedelta(seconds=15)
        except IntegrationError as exc:
            post.status, post.error = 'FAILED', str(exc)
        post.save()
    # Persist PUBLISHING before sending the non-idempotent request. A crash is not retried blindly.
    if publish_now:
        publish(post_id)

def publish(post_id):
    with transaction.atomic():
        initial = Post.objects.get(pk=post_id)
        job = Job.objects.select_for_update().get(pk=initial.job_id)
        post = Post.objects.select_for_update().get(pk=post_id)
        if post.status != 'PUBLISHING':
            return
        if not permitted(job):
            post.status = 'CANCELLED'
            post.save()
            return
        try:
            adapter = Instagram()
            post.media_id = adapter.publish(post.container_id)
            post.status, post.published_at = 'PUBLISHED', timezone.now()
            post.error = ''
        except IntegrationError:
            post.status = 'UNCERTAIN'
            post.error = 'Исход публикации неизвестен. Проверьте Instagram; автоматический повтор запрещён.'
        post.save()
    # A failed permalink read must never turn a published post into a retryable failure.
    if post.status == 'PUBLISHED':
        try:
            Post.objects.filter(pk=post_id).update(permalink=Instagram().permalink(post.media_id))
        except IntegrationError:
            pass

@shared_task
def dispatch():
    now = timezone.now()
    Post.objects.filter(status='PUBLISHING', lease_until__lt=now).update(status='UNCERTAIN',
        error='Процесс публикации прерван. Проверьте Instagram перед дальнейшими действиями.')
    for pk in Post.objects.filter(status__in=ACTIVE).filter(due_at__isnull=True).values_list('pk', flat=True):
        advance.delay(str(pk))
    for pk in Post.objects.filter(status__in=ACTIVE, due_at__lte=now).values_list('pk', flat=True):
        advance.delay(str(pk))
