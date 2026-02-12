from django.contrib import admin
from .models import (
    Fish, Cart, CartItem, Order, OrderItem, PaymentTransaction, Delivery,
    FishTransactionLog, PickupPoint, DeliveryAuditLog, SellerNotification, PlatformFeeLog, ChairmanApprovalRequest,
    UserNotification
)


@admin.register(Fish)
class FishAdmin(admin.ModelAdmin):
    list_display = ('name', 'fish_type', 'fisherman', 'price_per_kg', 'available_weight', 'status', 'catch_date', 'created_at')
    list_filter = ('fish_type', 'status', 'is_organic', 'is_frozen', 'catch_date', 'created_at')
    search_fields = ('name', 'fisherman__username', 'fisherman__email', 'location')
    raw_id_fields = ('fisherman',)
    date_hierarchy = 'catch_date'
    ordering = ('-created_at',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'fish', 'weight_kg', 'added_at')
    list_filter = ('added_at',)
    raw_id_fields = ('cart', 'fish')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('fish_name', 'fish_type', 'weight_kg', 'price_per_kg', 'total_price')
    raw_id_fields = ('fish', 'fisherman')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'status', 'total_amount', 'platform_fee', 'fishermen_net_amount', 'fulfillment_method', 'created_at')
    list_filter = ('status', 'fulfillment_method', 'created_at')
    search_fields = ('order_number', 'customer__username', 'customer__email', 'customer_phone')
    raw_id_fields = ('customer',)
    inlines = (OrderItemInline,)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'fish_name', 'fisherman', 'weight_kg', 'price_per_kg', 'total_price', 'platform_fee', 'fisherman_net_payout', 'fulfillment_status')
    list_filter = ('fulfillment_status', 'fish_type')
    search_fields = ('order__order_number', 'fish_name', 'fisherman__username')
    raw_id_fields = ('order', 'fish', 'fisherman')


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'order', 'order_item', 'buyer', 'fisherman', 'amount', 'platform_fee', 'net_payout', 'phone_number', 'status', 'mpesa_receipt_number', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('transaction_id', 'order__order_number', 'mpesa_receipt_number', 'phone_number')
    raw_id_fields = ('order',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'fisherman', 'assigned_agent', 'updated_by', 'estimated_delivery', 'actual_delivery', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__order_number', 'fisherman__username')
    raw_id_fields = ('order', 'fisherman')


@admin.register(FishTransactionLog)
class FishTransactionLogAdmin(admin.ModelAdmin):
    list_display = ('fish', 'action', 'user', 'weight_change', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('fish__name', 'user__username', 'notes')
    raw_id_fields = ('fish', 'user')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


@admin.register(PickupPoint)
class PickupPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'general_location', 'contact_person', 'phone_number')
    search_fields = ('name', 'general_location', 'contact_person', 'phone_number')


@admin.register(DeliveryAuditLog)
class DeliveryAuditLogAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery', 'updated_by', 'previous_status', 'new_status', 'created_at')
    list_filter = ('previous_status', 'new_status', 'created_at')
    search_fields = ('order__order_number', 'updated_by__username', 'notes')


@admin.register(SellerNotification)
class SellerNotificationAdmin(admin.ModelAdmin):
    list_display = ('fisherman', 'order', 'fish_item', 'total_amount', 'net_earnings', 'receipt_number', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('fisherman__username', 'order__order_number', 'fish_item', 'receipt_number')


@admin.register(UserNotification)
class UserNotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'order', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'order__order_number', 'message')


@admin.register(PlatformFeeLog)
class PlatformFeeLogAdmin(admin.ModelAdmin):
    list_display = ('order', 'payment_transaction', 'fisherman', 'gross_amount', 'fee_amount', 'net_amount', 'logged_at')
    list_filter = ('logged_at',)
    search_fields = ('order__order_number', 'payment_transaction__checkout_request_id', 'fisherman__username')


@admin.register(ChairmanApprovalRequest)
class ChairmanApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('fisherman', 'status', 'reviewed_by', 'requested_at', 'reviewed_at')
    list_filter = ('status', 'requested_at', 'reviewed_at')
    search_fields = ('fisherman__username', 'reviewed_by__username', 'notes')
