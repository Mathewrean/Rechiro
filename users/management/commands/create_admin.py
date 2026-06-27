from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings

class Command(BaseCommand):
    help = 'Create admin superuser if not exists'

    def handle(self, *args, **options):
        User = get_user_model()
        admin_username = getattr(settings, 'ADMIN_USERNAME', 'admin')
        admin_password = getattr(settings, 'ADMIN_PASSWORD', 'changeme')
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@rechiro.com')
        
        if User.objects.filter(username=admin_username).exists():
            self.stdout.write(self.style.WARNING(f'Admin user "{admin_username}" already exists'))
            return
        
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
        self.stdout.write(self.style.SUCCESS(f'Created admin user: {admin_username}'))
