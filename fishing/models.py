from django.db import models
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


def generate_order_number():
    """Generate a unique order number"""
    return str(uuid.uuid4().hex[:8]).upper()


class Fish(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('unavailable', 'Unavailable'),
    ]
    
    FISH_TYPE_CHOICES = [
        ('tilapia', 'Tilapia'),
        ('catfish', 'Catfish'),
        ('sardine', 'Sardine'),
        ('tuna', 'Tuna'),
        ('salmon', 'Salmon'),
        ('mackerel', 'Mackerel'),
        ('cod', 'Cod'),
        ('snapper', 'Snapper'),
        ('prawns', 'Prawns'),
        ('crab', 'Crab'),
        ('lobster', 'Lobster'),
        ('octopus', 'Octopus'),
        ('squid', 'Squid'),
        ('other', 'Other'),
    ]
    
    fisherman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fish_listings')
    name = models.CharField(max_length=100)
    fish_type = models.CharField(max_length=50, choices=FISH_TYPE_CHOICES, default='other')
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='fish_images/', blank=True, null=True)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    available_weight = models.DecimalField(max_digits=8, decimal_places=2, help_text="Available weight in kg")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    catch_date = models.DateField()
    location = models.CharField(max_length=100, blank=True)
    is_organic = models.BooleanField(default=False, help_text="Wild-caught/organic fish")
    is_frozen = models.BooleanField(default=False, help_text="Fish is frozen")
    preparation_notes = models.TextField(blank=True, help_text="Cleaning, filleting instructions")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.fish_type} ({self.available_weight}kg @ KES {self.price_per_kg}/kg)"
    
    def get_absolute_url(self):
        return reverse('fishing:fish_detail', kwargs={'fish_id': self.pk})
    
    def get_total_value(self):
        """Calculate total value of available fish"""
        return self.available_weight * self.price_per_kg
    
    def reduce_stock(self, weight):
        """Reduce available weight after purchase"""
        normalized_weight = Decimal(str(weight))
        if normalized_weight <= self.available_weight:
            self.available_weight -= normalized_weight
            if self.available_weight <= 0:
                self.status = 'sold'
            self.save()
            return True
        return False
    
    def is_available(self):
        """Check if fish is available for purchase"""
        return self.status == 'available' and self.available_weight > 0
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fish Listing'
        verbose_name_plural = 'Fish Listings'


class Cart(models.Model):
    """Shopping cart for customers"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Cart for {self.user.username}"
    
    def get_total_items(self):
        """Get total number of items in cart"""
        return self.items.count()
    
    def get_total_weight(self):
        """Get total weight in cart"""
        return sum(item.get_total_weight() for item in self.items.all())
    
    def get_total_price(self):
        """Get total price of cart"""
        return sum(item.get_total_price() for item in self.items.all())
    
    def clear(self):
        """Clear all items from cart"""
        self.items.all().delete()
    
    def get_items(self):
        """Get all cart items"""
        return self.items.all()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    fish = models.ForeignKey(Fish, on_delete=models.CASCADE)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=1.00, help_text="Weight in kg")
    added_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.weight_kg}kg of {self.fish.name}"
    
    def get_total_weight(self):
        """Get total weight for this item"""
        return self.weight_kg
    
    def get_total_price(self):
        """Get total price for this item"""
        return self.weight_kg * self.fish.price_per_kg
    
    def save(self, *args, **kwargs):
        """Validate weight doesn't exceed available"""
        if self.weight_kg <= 0:
            raise ValidationError("Weight must be greater than 0kg.")
        if self.weight_kg > self.fish.available_weight:
            self.weight_kg = self.fish.available_weight
        super().save(*args, **kwargs)


class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PAID', 'Paid'),
        ('FULLY_PAID', 'Fully Paid'),
        ('DELIVERY_IN_PROGRESS', 'Delivery In Progress'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready for Fulfillment'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('PICKED_UP', 'Picked Up'),
        ('FAILED', 'Payment Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order_number = models.CharField(max_length=20, unique=True, default=generate_order_number)
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    fishermen_net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    fulfillment_method = models.CharField(max_length=20, default='delivery')
    pickup_point = models.ForeignKey('PickupPoint', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    delivery_location = models.CharField(max_length=200, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_notes = models.TextField(blank=True)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Order #{self.order_number}"
    
    def get_absolute_url(self):
        return reverse('fishing:order_detail', kwargs={'order_number': self.order_number})
    
    def get_status_display_name(self):
        """Get human-readable status"""
        status_names = {
            'PENDING': 'Pending Payment',
            'PAID': 'Paid',
            'FULLY_PAID': 'Fully Paid',
            'DELIVERY_IN_PROGRESS': 'Delivery In Progress',
            'PROCESSING': 'Being Prepared',
            'READY': 'Ready for Pickup/Delivery',
            'READY_FOR_PICKUP': 'Ready for Pickup',
            'OUT_FOR_DELIVERY': 'Out for Delivery',
            'DELIVERED': 'Delivered',
            'PICKED_UP': 'Picked Up',
            'FAILED': 'Payment Failed',
            'CANCELLED': 'Cancelled',
        }
        return status_names.get(self.status, self.status)
    
    def get_items_by_fisherman(self):
        """Group order items by fisherman"""
        items_by_fisherman = {}
        for item in self.items.all():
            fisherman_id = item.fisherman_id
            if fisherman_id not in items_by_fisherman:
                items_by_fisherman[fisherman_id] = []
            items_by_fisherman[fisherman_id].append(item)
        return items_by_fisherman
    
    def mark_as_paid(self, transaction_id=None):
        """Mark order as paid and ready for delivery flow"""
        self.status = 'FULLY_PAID'
        self.save()
        
        # Deduct stock for each item
        for item in self.items.all():
            item.fish.reduce_stock(item.weight_kg)

    def calculate_financials(self):
        gross = sum((item.total_price for item in self.items.all()), Decimal('0.00'))
        fee = (gross * Decimal('0.02')).quantize(Decimal('0.01'))
        net = (gross - fee).quantize(Decimal('0.01'))
        self.total_amount = gross
        self.platform_fee = fee
        self.fishermen_net_amount = net

    def cancel(self):
        """Cancel the order"""
        if self.status in ['PENDING', 'PAID', 'FULLY_PAID']:
            self.status = 'CANCELLED'
            self.save()
            return True
        return False
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    fish = models.ForeignKey(Fish, on_delete=models.SET_NULL, null=True, related_name='order_items')
    fisherman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sold_items')
    fish_name = models.CharField(max_length=100)
    fish_type = models.CharField(max_length=50)
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    price_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    fisherman_net_payout = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    fulfillment_status = models.CharField(max_length=20, default='PENDING')
    
    def __str__(self):
        return f"{self.weight_kg}kg of {self.fish_name} for Order #{self.order.order_number}"
    
    def save(self, *args, **kwargs):
        """Calculate total price before saving"""
        if self.weight_kg <= 0:
            raise ValidationError("Weight must be greater than 0kg.")
        if self.price_per_kg <= 0:
            raise ValidationError("Price per kg must be greater than 0.")
        self.total_price = (self.weight_kg * self.price_per_kg).quantize(Decimal('0.01'))
        self.platform_fee = (self.total_price * Decimal('0.02')).quantize(Decimal('0.01'))
        self.fisherman_net_payout = (self.total_price - self.platform_fee).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='transactions')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='buyer_transactions')
    fisherman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fisherman_transactions')
    transaction_id = models.CharField(max_length=100, unique=True)
    mpesa_receipt_number = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_payout = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.TextField(blank=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    checkout_request_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Transaction {self.transaction_id} for Order #{self.order.order_number}"
    
    class Meta:
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'


class Delivery(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('READY_FOR_PICKUP', 'Ready for Pickup'),
        ('DELIVERY_IN_PROGRESS', 'Delivery In Progress'),
        ('DELIVERED', 'Delivered'),
        ('FAILED', 'Delivery Failed'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    fisherman = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='deliveries')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_updates')
    estimated_delivery = models.DateTimeField(null=True, blank=True)
    actual_delivery = models.DateTimeField(null=True, blank=True)
    delivery_person_name = models.CharField(max_length=100, blank=True)
    delivery_person_phone = models.CharField(max_length=20, blank=True)
    delivery_notes = models.TextField(blank=True)
    signature_image = models.ImageField(upload_to='delivery_signatures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Delivery for Order #{self.order.order_number} - {self.status}"
    
    class Meta:
        verbose_name = 'Delivery'
        verbose_name_plural = 'Deliveries'


class FishTransactionLog(models.Model):
    """Audit log for all fish transactions"""
    ACTION_CHOICES = [
        ('LISTED', 'Fish Listed'),
        ('PURCHASED', 'Fish Purchased'),
        ('RESERVED', 'Fish Reserved'),
        ('STOCK_RELEASED', 'Stock Released'),
        ('PAYMENT_RECEIVED', 'Payment Received'),
        ('STOCK_ADJUSTED', 'Stock Adjusted'),
        ('STATUS_CHANGED', 'Status Changed'),
        ('DELETED', 'Fish Deleted'),
    ]
    
    fish = models.ForeignKey(Fish, on_delete=models.SET_NULL, related_name='transaction_logs', null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    weight_change = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} - {self.fish.name} at {self.created_at}"
    
    class Meta:
        verbose_name = 'Transaction Log'
        verbose_name_plural = 'Transaction Logs'
        ordering = ['-created_at']


class PickupPoint(models.Model):
    name = models.CharField(max_length=120)
    general_location = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.general_location})"


class DeliveryAuditLog(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='audit_logs')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='delivery_audit_logs')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    previous_status = models.CharField(max_length=30)
    new_status = models.CharField(max_length=30)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
