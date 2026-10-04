import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from studio.telegram import Telegram
from studio.integrations import IntegrationError

class Command(BaseCommand):
    help = 'Run one Telegram long-polling process. --check makes a read-only token check.'
    def add_arguments(self, parser):
        parser.add_argument('--check', action='store_true')
    def handle(self, **options):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_BOT_USERNAME:
            raise CommandError('Set TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME in .env.')
        bot = Telegram()
        try:
            identity = bot.request('getMe')
        except IntegrationError as exc:
            raise CommandError(str(exc))
        if identity.get('username', '').lower() != settings.TELEGRAM_BOT_USERNAME.lower():
            raise CommandError('TELEGRAM_BOT_USERNAME does not match the token.')
        if options['check']:
            self.stdout.write('Telegram token and username OK. No messages sent.')
            return
        self.stdout.write('Review bot started. DEMO_MODE=' + str(settings.DEMO_MODE))
        try:
            while True:
                try:
                    bot.poll()
                except IntegrationError as exc:
                    self.stderr.write(str(exc))
                    time.sleep(getattr(exc, 'retry_after', 5))
        except KeyboardInterrupt:
            self.stdout.write('Bot stopped.')
