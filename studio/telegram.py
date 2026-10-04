import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Review, BotState, TelegramOutbox
from .reviews import start_review, interact
from .integrations import IntegrationError

class TelegramError(IntegrationError):
    def __init__(self, code, retry_after=5):
        self.code = code
        self.retry_after = min(max(int(retry_after), 5), 60)
        super().__init__('Telegram отклонил запрос. Проверьте токен и доступ к боту.')

class Telegram:
    def request(self, method, **payload):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise IntegrationError('Не настроен TELEGRAM_BOT_TOKEN.')
        try:
            response = httpx.post(f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}',
                json=payload, timeout=35)
            result = response.json()
            if not result.get('ok'):
                raise TelegramError(result.get('error_code', 0), result.get('parameters', {}).get('retry_after', 5))
            return result['result']
        except IntegrationError:
            raise
        except Exception:
            raise IntegrationError('Telegram недоступен. Токен не выводится в журнал.') from None

    def flush(self):
        for item in TelegramOutbox.objects.order_by('created_at')[:50]:
            try:
                self.request('sendMessage', chat_id=item.chat_id, **item.payload)
            except TelegramError as exc:
                if exc.code not in (400, 403):
                    raise
                # A blocked/deleted chat must not stop replies to other clients.
            item.delete()

    def poll(self):
        state, _ = BotState.objects.get_or_create(name='telegram')
        updates = self.request('getUpdates', offset=state.offset, timeout=20,
            allowed_updates=['message', 'callback_query'], limit=30)
        for update in updates:
            self.process(update)
        self.flush()

    def process(self, update):
        update_id = update['update_id']
        callback = update.get('callback_query')
        message = update.get('message') or (callback or {}).get('message') or {}
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        with transaction.atomic():
            state = BotState.objects.select_for_update().get(name='telegram')
            if update_id < state.offset:
                return
            result = None
            if chat.get('type') == 'private' and chat_id and chat_id > 0:
                text = message.get('text', '') if not callback else ''
                try:
                    if text.startswith('/start '):
                        result = start_review(text.split(maxsplit=1)[1], chat_id)
                    else:
                        review = Review.objects.filter(chat_id=chat_id).exclude(stage='STOPPED').order_by('-created_at').first()
                        if callback:
                            data = callback.get('data', '').split(':', 1)
                            if len(data) != 2 or not review or data[0] != str(review.id):
                                result = {'text': 'Эта кнопка больше не действует.', 'choices': []}
                            else:
                                result = interact(review.pk, chat_id, action=data[1])
                        elif review and text:
                            result = interact(review.pk, chat_id, text=text)
                        else:
                            result = {'text': 'Откройте ссылку-приглашение от мастера. Для отзыва нужны данные о выполненной работе.', 'choices': []}
                except (ValidationError, IntegrationError) as exc:
                    detail = getattr(exc, 'detail', str(exc))
                    result = {'text': str(detail)[:800], 'choices': []}
                if result:
                    payload = {'text': result['text'], 'disable_web_page_preview': True}
                    if result.get('choices'):
                        active = Review.objects.filter(chat_id=chat_id).order_by('-created_at').first()
                        payload['reply_markup'] = {'inline_keyboard': [[{'text': label,
                            'callback_data': f'{active.id}:{key}'}] for key, label in result['choices']]}
                    TelegramOutbox.objects.get_or_create(update_id=update_id,
                        defaults={'chat_id': chat_id, 'payload': payload})
            state.offset = update_id + 1
            state.save()
        if callback:
            try:
                self.request('answerCallbackQuery', callback_query_id=callback['id'])
            except IntegrationError:
                pass
