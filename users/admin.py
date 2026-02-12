from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FishermanProfile, CustomerProfile, PhoneVerificationTransaction


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'full_name', 'role', 'email_verified', 'phone_verified', 'is_active', 'created_at')
    list_filter = ('role', 'email_verified', 'phone_verified', 'is_active', 'created_at')
    search_fields = ('username', 'email', 'full_name', 'phone')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Authentication', {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'email_verified', 'phone', 'phone_verified', 'profile_picture')}),
        ('Role & Status', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Location', {'fields': ('location',)}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        ('Create Account', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(FishermanProfile)
class FishermanProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'phone', 'landing_site', 'location', 'mpesa_payment_type', 'mpesa_phone',
        'chairman_approved', 'chairman_name', 'is_verified', 'rating', 'total_sales'
    )
    list_filter = ('fulfillment_method', 'mpesa_payment_type', 'chairman_approved', 'is_verified', 'created_at')
    search_fields = (
        'user__username', 'user__email', 'location', 'landing_site', 'business_name',
        'mpesa_phone', 'mpesa_till_number', 'mpesa_paybill_number', 'chairman_name'
    )
    raw_id_fields = ('user',)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'delivery_location', 'preferred_fulfillment', 'created_at')
    list_filter = ('preferred_fulfillment', 'created_at')
    search_fields = ('user__username', 'user__email', 'delivery_location')
    raw_id_fields = ('user',)


@admin.register(PhoneVerificationTransaction)
class PhoneVerificationTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'amount', 'checkout_request_id', 'status', 'mpesa_receipt_number', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'phone_number', 'checkout_request_id', 'mpesa_receipt_number')
