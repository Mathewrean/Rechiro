from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate
from .models import User, FishermanProfile, CustomerProfile


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=100, required=True)
    phone = forms.CharField(max_length=20, required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES, required=True)
    location = forms.CharField(max_length=100, required=False)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'full_name', 'phone', 'role', 'location', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data['full_name']
        user.phone = self.cleaned_data['phone']
        user.role = self.cleaned_data['role']
        user.location = self.cleaned_data.get('location', '')
        
        if commit:
            user.save()
            # Create appropriate profile based on role
            if user.role == 'fisherman':
                FishermanProfile.objects.create(
                    user=user,
                    phone=user.phone,
                    location=user.location,
                    contact_details=''
                )
            elif user.role == 'customer':
                CustomerProfile.objects.create(
                    user=user,
                    phone=user.phone,
                    delivery_location=user.location,
                    delivery_address='',
                    preferred_fulfillment='delivery'
                )
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Username'
        self.fields['password'].label = 'Password'


class FishermanProfileForm(forms.ModelForm):
    class Meta:
        model = FishermanProfile
        fields = ('phone', 'business_name', 'location', 'address', 'contact_details', 'fulfillment_method')
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'contact_details': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ('phone', 'delivery_location', 'delivery_address', 'preferred_fulfillment', 'alternative_phone', 'delivery_notes')
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3}),
            'delivery_notes': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('full_name', 'email', 'phone', 'location', 'profile_picture')
        widgets = {
            'profile_picture': forms.FileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name == 'profile_picture':
                field.widget.attrs['class'] = 'form-control-file'
            else:
                field.widget.attrs['class'] = 'form-control'
    
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Update associated profile
            if user.role == 'fisherman':
                try:
                    profile = user.fisherman_profile
                    profile.phone = user.phone
                    profile.location = user.location
                    profile.save()
                except FishermanProfile.DoesNotExist:
                    FishermanProfile.objects.create(
                        user=user,
                        phone=user.phone,
                        location=user.location,
                        contact_details=''
                    )
            elif user.role == 'customer':
                try:
                    profile = user.customer_profile
                    profile.phone = user.phone
                    profile.save()
                except CustomerProfile.DoesNotExist:
                    CustomerProfile.objects.create(
                        user=user,
                        phone=user.phone,
                        delivery_location=user.location,
                        delivery_address='',
                        preferred_fulfillment='delivery'
                    )
        return user


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Current Password'
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='New Password'
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Confirm New Password'
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if not self.user.check_password(current_password):
            raise forms.ValidationError('Current password is incorrect.')
        return current_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password1 = cleaned_data.get('new_password1')
        new_password2 = cleaned_data.get('new_password2')
        
        if new_password1 and new_password2 and new_password1 != new_password2:
            raise forms.ValidationError('New passwords do not match.')
        
        return cleaned_data
    
    def save(self):
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save()
        return self.user

