from django.db import migrations
from django.conf import settings
import os


def create_google_social_app_and_site(apps, schema_editor):
    """Create Google OAuth SocialApp and ensure site exists."""
    SocialApp = apps.get_model('socialaccount', 'SocialApp')
    Site = apps.get_model('sites', 'Site')
    
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    
    # Determine the site domain based on environment
    if os.environ.get('RAILWAY_STATIC_URL') or 'rechiro-production.up.railway.app' in str(getattr(settings, 'ALLOWED_HOSTS', [])):
        site_domain = 'rechiro-production.up.railway.app'
    else:
        site_domain = getattr(settings, 'ALLOWED_HOSTS', ['localhost:8000'])[0]
    
    # Create or update site
    site, _ = Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': site_domain,
            'name': 'Rechiro',
        }
    )
    
    # Create SocialApp if credentials are provided
    if client_id and client_secret:
        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
            }
        )
        
        # Update credentials if app exists
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
        
        # Add site to app if not already associated
        if site not in app.sites.all():
            app.sites.add(site)


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
        ('users', '0006_alter_user_role'),
    ]

    operations = [
        migrations.RunPython(create_google_social_app_and_site, migrations.RunPython.noop),
    ]