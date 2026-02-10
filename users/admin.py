from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, FishermanProfile, CustomerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'full_name', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('username', 'email', 'full_name', 'phone')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Authentication', {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'phone', 'profile_picture')}),
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
    list_display = ('user', 'phone', 'location', 'fulfillment_method', 'is_verified', 'rating', 'total_sales')
    list_filter = ('fulfillment_method', 'is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'location', 'business_name')
    raw_id_fields = ('user',)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'delivery_location', 'preferred_fulfillment', 'created_at')
    list_filter = ('preferred_fulfillment', 'created_at')
    search_fields = ('user__username', 'user__email', 'delivery_location')
    raw_id_fields = ('user',)

