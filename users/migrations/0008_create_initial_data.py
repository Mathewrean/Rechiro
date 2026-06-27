from django.db import migrations
from django.conf import settings
import os


def create_initial_data(apps, schema_editor):
    """Create admin superuser and Google OAuth SocialApp if credentials exist."""
    User = apps.get_model('users', 'User')
    
    # Create admin superuser
    admin_username = getattr(settings, 'ADMIN_USERNAME', '')
    admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@rechiro.com')
    admin_password = getattr(settings, 'ADMIN_PASSWORD', '')
    
    if admin_username and admin_password and not User.objects.filter(username=admin_username).exists():
        User.objects.create_superuser(
            username=admin_username,
            email=admin_email,
            password=admin_password
        )
    
    # Create Google SocialApp if allauth is installed and credentials exist
    try:
        SocialApp = apps.get_model('socialaccount', 'SocialApp')
        Site = apps.get_model('sites', 'Site')
        
        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
        
        if client_id and client_secret:
            # Determine site domain
            if os.environ.get('RAILWAY_STATIC_URL') or 'rechiro-production.up.railway.app' in str(getattr(settings, 'ALLOWED_HOSTS', [])):
                site_domain = 'rechiro-production.up.railway.app'
            else:
                site_domain = getattr(settings, 'ALLOWED_HOSTS', ['localhost:8000'])[0] if getattr(settings, 'ALLOWED_HOSTS', []) else 'localhost:8000'
            
            # Create or update site
            site, _ = Site.objects.update_or_create(
                id=1,
                defaults={'domain': site_domain, 'name': 'Rechiro'}
            )
            
            # Create SocialApp
            app, created = SocialApp.objects.get_or_create(
                provider='google',
                defaults={
                    'name': 'Google',
                    'client_id': client_id,
                    'secret': client_secret,
                }
            )
            
            if not created:
                updated = False
                if app.client_id != client_id:
                    app.client_id = client_id
                    updated = True
                if app.secret != client_secret:
                    app.secret = client_secret
                    updated = True
                if updated:
                    app.save()
            
            if site not in app.sites.all():
                app.sites.add(site)
    except Exception:
        pass  # allauth not installed or other error - skip


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('users', '0006_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(create_initial_data, migrations.RunPython.noop),
    ]