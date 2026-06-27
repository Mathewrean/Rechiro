from django.db import migrations
from django.conf import settings


def create_admin_user(apps, schema_editor):
    """Create admin superuser for production."""
    User = apps.get_model('users', 'User')
    
    admin_username = getattr(settings, 'ADMIN_USERNAME', 'admin')
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@rechiro.com')
    admin_password = getattr(settings, 'ADMIN_PASSWORD', 'changeme123')
    
    if not User.objects.filter(username=admin_username).exists():
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(create_admin_user, migrations.RunPython.noop),
    ]