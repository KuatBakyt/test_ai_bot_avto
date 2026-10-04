import os
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

class Command(BaseCommand):
    help = 'Create the first owner using OWNER_USERNAME and OWNER_PASSWORD; never overwrite an existing password.'
    def handle(self, **options):
        username = os.getenv('OWNER_USERNAME', 'owner')
        password = os.getenv('OWNER_PASSWORD', '')
        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages))
        if get_user_model().objects.filter(username=username).exists():
            self.stdout.write('Owner exists; password unchanged.')
            return
        get_user_model().objects.create_superuser(username=username, password=password)
        self.stdout.write('Owner created.')
