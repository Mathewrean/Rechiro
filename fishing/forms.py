from django import forms
from .models import Fish


class CatchForm(forms.ModelForm):
    class Meta:
        model = Fish
        fields = ['fish_type', 'available_weight', 'location', 'catch_date', 'status', 'price_per_kg', 'description']
        widgets = {
            'catch_date': forms.DateInput(attrs={'type': 'date'}),
            'available_weight': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'price_per_kg': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
        
        self.fields['price_per_kg'].required = False
        self.fields['description'].required = False


class CatchFilterForm(forms.Form):
    STATUS_CHOICES = [('', 'All Statuses')] + Fish.STATUS_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fish_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by fish type'
        })
    )
    
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by location'
        })
    )


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 XXX XXX XXX'}))
    role = forms.ChoiceField(choices=[('customer', 'Customer'), ('fisherman', 'Fisherman'), ('delivery_agent', 'Delivery Agent')], widget=forms.Select(attrs={'class': 'form-control'}))
    category = forms.ChoiceField(choices=[('billing', 'Billing Issue'), ('orders', 'Order Problem'), ('delivery', 'Delivery Issue'), ('account', 'Account Support'), ('other', 'Other')], widget=forms.Select(attrs={'class': 'form-control'}))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief subject'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'minlength': 20}))
    attachment = forms.FileField(required=False, widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.jpg,.jpeg,.png,.pdf'}))
    agreement = forms.BooleanField(required=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))
    
    def clean_message(self):
        message = self.cleaned_data.get('message')
        if message and len(message) < 20:
            raise forms.ValidationError('Message must be at least 20 characters.')
        return message
    
    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            ext = attachment.name.split('.')[-1].lower()
            if ext not in ['jpg', 'jpeg', 'png', 'pdf']:
                raise forms.ValidationError('Only JPG, PNG, and PDF files are allowed.')
            if attachment.size > 5 * 1024 * 1024:
                raise forms.ValidationError('File size must not exceed 5MB.')
        return attachment
