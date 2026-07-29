from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'full_name', 'role', 'phone', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('username', 'email', 'full_name', 'phone')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Authentication', {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'phone', 'profile_picture')}),
        ('Role & Status', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Location', {'fields': ('location',)}),
    )
    readonly_fields = ()
    
    add_fieldsets = (
        ('Create Account', {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


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


@admin.register(BeachChairmanProfile)
class BeachChairmanProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'beach_name', 'phone', 'created_at')
    search_fields = ('user__username', 'user__email', 'beach_name', 'phone')
    raw_id_fields = ('user',)
