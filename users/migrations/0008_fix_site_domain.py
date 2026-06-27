from django.db import migrations
from django.conf import settings


def fix_site_domain(apps, schema_editor):
    """Ensure site domain matches the deployment domain."""
    Site = apps.get_model('sites', 'Site')
    
    # Check if we're on Railway (from environment)
    import os
    if 'RAILWAY_ENVIRONMENT' in os.environ or 'rechiro-production.up.railway.app' in settings.ALLOWED_HOSTS:
        site_domain = 'rechiro-production.up.railway.app'
    else:
        site_domain = 'localhost:8000'
    
    # Update or create site with correct domain
    Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': site_domain,
            'name': 'Rechiro'
        }
    )


class Migration(migrations.Migration):

    dependencies = [
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(fix_site_domain, migrations.RunPython.noop),
    ]