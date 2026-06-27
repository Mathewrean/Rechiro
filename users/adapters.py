from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.forms import SignupForm
from django import forms
from .models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile


def _ensure_role_profile(user):
    """Create appropriate profile based on user role."""
    if user.role == 'fisherman':
        FishermanProfile.objects.get_or_create(
            user=user,
            defaults={
                'phone': user.phone or '',
                'landing_site': user.location or '',
                'location': user.location or '',
                'contact_details': '',
            }
        )
    elif user.role == 'customer':
        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                'phone': user.phone or '',
                'delivery_location': user.location or '',
                'delivery_address': '',
                'preferred_fulfillment': 'delivery',
            }
        )
    elif user.role == 'chairman':
        BeachChairmanProfile.objects.get_or_create(
            user=user,
            defaults={
                'beach_name': user.location or '',
                'phone': user.phone or '',
                'notes': '',
            }
        )


class RechiroSocialSignupForm(SignupForm):
    """Custom signup form for Google OAuth with role and phone required."""
    ROLE_CHOICES_SOCIAL = [
        ('fisherman', 'Fisherman'),
        ('customer', 'Customer'),
        ('delivery', 'Delivery Agent'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES_SOCIAL, required=True)
    phone = forms.CharField(max_length=20, required=True, label="Phone Number")
    location = forms.CharField(max_length=100, required=False, label="Location")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    def save(self, request):
        user = super().save(request)
        user.role = self.cleaned_data.get('role', 'customer')
        user.phone = self.cleaned_data.get('phone', '')
        user.location = self.cleaned_data.get('location', '')
        user.save(update_fields=['role', 'phone', 'location'])
        _ensure_role_profile(user)
        return user


class RechiroSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Handle social account authentication with role selection.
    """

    def save_user(self, request, sociallogin, form=None):
        is_new_social_account = not sociallogin.is_existing
        user = super().save_user(request, sociallogin, form=form)
        if sociallogin.account.provider == "google" and is_new_social_account and form:
            user.role = form.cleaned_data.get('role', 'customer')
            user.phone = form.cleaned_data.get('phone', '')
            user.location = form.cleaned_data.get('location', '')
            user.save(update_fields=['role', 'phone', 'location'])
            _ensure_role_profile(user)
        return user
