import hashlib
import secrets
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Job, Review, Post
from .integrations import next_question

CONSENT_TEXT = ('Для сбора отзыва ответы будут обработаны AI (OpenAI в рабочем режиме). '
    'Не пишите адрес, телефон, имя и другие личные данные. Разрешаете такую обработку? '
    'Публикация в Instagram требует отдельного согласия. Остановить диалог: /stop.')

def issue_invitation(job):
    with transaction.atomic():
        job = Job.objects.select_for_update().get(pk=job.pk)
        review = Review.objects.filter(job=job).first()
        if review and review.stage != 'INVITED':
            raise ValidationError('Клиент уже начал диалог. Новое приглашение не требуется.')
        token = secrets.token_urlsafe(24)
        if review:
            review.token_hash = hashlib.sha256(token.encode()).hexdigest()
            review.expires_at = timezone.now() + timedelta(days=7)
            review.save()
        else:
            review = Review.objects.create(job=job, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=timezone.now() + timedelta(days=7))
        return review, token

def start_review(token, chat_id):
    try:
        review = Review.objects.get(token_hash=hashlib.sha256(token.encode()).hexdigest())
    except Review.DoesNotExist:
        raise ValidationError('Приглашение не найдено.')
    with transaction.atomic():
        Job.objects.select_for_update().get(pk=review.job_id)
        review = Review.objects.select_for_update().get(pk=review.pk)
        if review.expires_at <= timezone.now() or review.stage == Review.Stage.STOPPED:
            raise ValidationError('Приглашение истекло или отозвано.')
        if review.chat_id is not None and review.chat_id != chat_id:
            raise ValidationError('Приглашение уже использовано.')
        active = Review.objects.filter(chat_id=chat_id).exclude(pk=review.pk).exclude(stage__in=['DONE', 'STOPPED'])
        if active.exists():
            raise ValidationError('Сначала завершите текущий отзыв или отправьте /stop.')
        if review.stage == Review.Stage.INVITED:
            review.chat_id = chat_id
            review.stage = Review.Stage.CONSENT
            review.save()
        return response_for(review)

def response_for(review):
    text, choices = '', []
    if review.stage == 'CONSENT':
        text, choices = CONSENT_TEXT, [('ai_yes', 'Разрешаю'), ('stop', 'Отказаться')]
    elif review.stage == 'CHATTING':
        text = review.history[-1]['text'] if review.history else 'Как прошла работа? Расскажите о результате.'
    elif review.stage == 'APPROVAL':
        text = 'Проверьте точный текст отзыва:\n\n' + '\n'.join(review.answers)
        choices = [('approve', 'Подтверждаю отзыв'), ('edit', 'Написать заново'), ('stop', 'Отказаться')]
    elif review.stage == 'PUBLIC':
        text = 'Можно опубликовать этот отзыв в Instagram вместе с фотографией работы? Имя и контакты не добавляем.'
        choices = [('public_yes', 'Разрешаю публикацию'), ('public_no', 'Только для мастера')]
    elif review.stage == 'DONE':
        text = 'Спасибо! Отзыв сохранён.' + (' Разрешение на публикацию записано.' if review.public_consent else ' Публикация не разрешена.')
    else:
        text = 'Диалог остановлен. Новые публикации по этому отзыву запрещены. Уже опубликованный пост удаляется владельцем аккаунта вручную.'
    return {'text': text, 'choices': choices, 'stage': review.stage}

def interact(review_id, chat_id, *, text='', action=''):
    with transaction.atomic():
        initial = Review.objects.get(pk=review_id)
        job = Job.objects.select_for_update().get(pk=initial.job_id)
        review = Review.objects.select_for_update().get(pk=review_id)
        if review.chat_id != chat_id:
            raise ValidationError('Этот диалог принадлежит другому клиенту.')
        if action == 'stop' or text.strip() == '/stop':
            review.stage = Review.Stage.STOPPED
            review.public_consent = False
            review.ai_consent = False
            Post.objects.filter(job=job).exclude(status__in=['PUBLISHED', 'DEMO', 'UNCERTAIN']).update(status='CANCELLED')
        elif review.expires_at <= timezone.now():
            raise ValidationError('Срок приглашения истёк.')
        elif review.stage == 'CONSENT' and action == 'ai_yes':
            review.ai_consent = True
            review.stage = Review.Stage.CHATTING
            review.history = [{'role': 'assistant', 'text': 'Как прошла работа? Расскажите о результате.'}]
        elif review.stage == 'CHATTING' and text.strip() and not action:
            answer = text.strip()
            if len(answer) > 350:
                raise ValidationError('Напишите ответ до 350 символов.')
            answers = review.answers + [answer]
            result = next_question(answers)
            review.answers = answers
            review.history.append({'role': 'user', 'text': answer})
            if result.finish or len(answers) >= 4:
                review.stage = Review.Stage.APPROVAL
            else:
                review.history.append({'role': 'assistant', 'text': result.question})
        elif review.stage == 'APPROVAL' and action == 'edit':
            review.answers = []
            review.history = [{'role': 'assistant', 'text': 'Напишите отзыв заново. Как прошла работа?'}]
            review.stage = Review.Stage.CHATTING
        elif review.stage == 'APPROVAL' and action == 'approve':
            review.approved_text = '\n'.join(review.answers)
            review.stage = Review.Stage.PUBLIC
        elif review.stage == 'PUBLIC' and action in ('public_yes', 'public_no'):
            review.public_consent = action == 'public_yes'
            review.consent_at = timezone.now()
            review.stage = Review.Stage.DONE
            if review.public_consent and job.photo and job.photo_rights:
                Post.objects.get_or_create(job=job)
        else:
            # Duplicate/stale buttons never advance the conversation twice.
            return response_for(review)
        review.save()
        return response_for(review)
