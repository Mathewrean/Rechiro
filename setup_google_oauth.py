from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site
from django.conf import settings

client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')

if not client_id or not client_secret:
    print('ERROR: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set in .env')
else:
    app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': client_id,
            'secret': client_secret,
        }
    )
    try:
        site = Site.objects.get_current()
        if not app.sites.filter(id=site.id).exists():
            app.sites.add(site)
    except Site.DoesNotExist:
        pass
    print(f'Google SocialApp {"created" if created else "updated"}')
