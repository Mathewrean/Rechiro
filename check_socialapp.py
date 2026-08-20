from allauth.socialaccount.models import SocialApp
print(SocialApp.objects.filter(provider='google').exists())
