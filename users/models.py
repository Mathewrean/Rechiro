from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [
        ('fisherman', 'Fisherman'),
        ('customer', 'Customer'),
        ('delivery', 'Delivery / Pickup'),
        ('admin', 'Admin'),
    ]
    
    full_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.full_name or self.username} ({self.get_role_display()})"
    
    def get_fisherman_profile(self):
        """Get fisherman profile if user is a fisherman"""
        if self.role == 'fisherman':
            try:
                return self.fisherman_profile
            except FishermanProfile.DoesNotExist:
                return None
        return None
    
    def get_customer_profile(self):
        """Get customer profile if user is a customer"""
        if self.role == 'customer':
            try:
                return self.customer_profile
            except CustomerProfile.DoesNotExist:
                return None
        return None


class FishermanProfile(models.Model):
    FULFILLMENT_CHOICES = [
        ('pickup', 'Pickup Only'),
        ('delivery', 'Delivery Only'),
        ('both', 'Pickup and Delivery'),
    ]

    MPESA_PAYMENT_TYPE_CHOICES = [
        ('STK_PUSH', 'STK Push'),
        ('TILL', 'Till'),
        ('PAYBILL', 'Paybill'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fisherman_profile')
    phone = models.CharField(max_length=20)
    business_name = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    contact_details = models.TextField(help_text="Additional contact information")
    fulfillment_method = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='both')
    is_verified = models.BooleanField(default=False, help_text="Whether the fisherman is verified")
    mpesa_phone = models.CharField(max_length=20, blank=True, help_text="M-Pesa phone in local or 254 format")
    mpesa_payment_type = models.CharField(max_length=20, choices=MPESA_PAYMENT_TYPE_CHOICES, default='STK_PUSH')
    mpesa_till_number = models.CharField(max_length=20, blank=True)
    mpesa_paybill_number = models.CharField(max_length=20, blank=True)
    mpesa_account_reference = models.CharField(max_length=50, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_sales = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Fisherman Profile: {self.user.username}"
    
    class Meta:
        verbose_name = 'Fisherman Profile'
        verbose_name_plural = 'Fisherman Profiles'


class CustomerProfile(models.Model):
    FULFILLMENT_CHOICES = [
        ('pickup', 'Pickup'),
        ('delivery', 'Delivery'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=20)
    delivery_location = models.CharField(max_length=200)
    delivery_address = models.TextField(blank=True)
    preferred_fulfillment = models.CharField(max_length=20, choices=FULFILLMENT_CHOICES, default='delivery')
    alternative_phone = models.CharField(max_length=20, blank=True)
    delivery_notes = models.TextField(blank=True, help_text="Special delivery instructions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Customer Profile: {self.user.username}"
    
    class Meta:
        verbose_name = 'Customer Profile'
        verbose_name_plural = 'Customer Profiles'
