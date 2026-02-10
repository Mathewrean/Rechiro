from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings

from .models import Fish, Cart, CartItem, Order, OrderItem, PaymentTransaction, Delivery, FishTransactionLog
from .mpesa_service import initiate_stk_push, process_payment_callback
from users.models import FishermanProfile, CustomerProfile


def fish_marketplace(request):
    """Display all available fish in Amazon-style grid layout"""
    fish_list = Fish.objects.filter(
        status='available',
        available_weight__gt=0
    ).select_related('fisherman').order_by('-created_at')
    
    # Filters
    fish_type_filter = request.GET.get('fish_type')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort_by = request.GET.get('sort', '-created_at')
    
    if fish_type_filter:
        fish_list = fish_list.filter(fish_type__icontains=fish_type_filter)
    
    if min_price:
        fish_list = fish_list.filter(price_per_kg__gte=min_price)
    
    if max_price:
        fish_list = fish_list.filter(price_per_kg__lte=max_price)
    
    # Sort
    if sort_by == 'price_low':
        fish_list = fish_list.order_by('price_per_kg')
    elif sort_by == 'price_high':
        fish_list = fish_list.order_by('-price_per_kg')
    elif sort_by == 'weight':
        fish_list = fish_list.order_by('-available_weight')
    else:
        fish_list = fish_list.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(fish_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get cart count for navbar
    cart_count = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.get_total_items()
        except Cart.DoesNotExist:
            pass
    
    context = {
        'page_obj': page_obj,
        'cart_count': cart_count,
        'fish_type_filter': fish_type_filter,
        'min_price': min_price,
        'max_price': max_price,
        'sort_by': sort_by,
        'fish_types': Fish.FISH_TYPE_CHOICES,
    }
    return render(request, 'fishing/marketplace.html', context)


def fish_detail(request, fish_id):
    """Display detailed fish information with weight selection"""
    fish = get_object_or_404(Fish, id=fish_id)
    
    # Get related fish from same fisherman
    related_fish = Fish.objects.filter(
        fisherman=fish.fisherman,
        status='available',
        available_weight__gt=0
    ).exclude(id=fish.id)[:4]
    
    # Get fisherman profile
    fisherman_profile = None
    try:
        fisherman_profile = fish.fisherman.fisherman_profile
    except FishermanProfile.DoesNotExist:
        pass
    
    # Cart item in current cart
    in_cart = False
    cart_weight = 0
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_item = CartItem.objects.filter(cart=cart, fish=fish).first()
            if cart_item:
                in_cart = True
                cart_weight = cart_item.weight_kg
        except Cart.DoesNotExist:
            pass
    
    context = {
        'fish': fish,
        'related_fish': related_fish,
        'fisherman_profile': fisherman_profile,
        'in_cart': in_cart,
        'cart_weight': cart_weight,
    }
    return render(request, 'fishing/fish_detail.html', context)


@login_required
def add_to_cart(request, fish_id):
    """Add fish to shopping cart"""
    fish = get_object_or_404(Fish, id=fish_id)
    
    if fish.status != 'available':
        messages.error(request, 'This fish is not available for purchase.')
        return redirect('fishing:fish_detail', fish_id=fish.id)
    
    if request.method == 'POST':
        try:
            weight = float(request.POST.get('weight', 1))
        except (ValueError, TypeError):
            weight = 1
        
        # Validate weight
        if weight <= 0:
            weight = 1
        if weight > float(fish.available_weight):
            weight = float(fish.available_weight)
            messages.warning(request, f'Maximum available weight is {fish.available_weight}kg')
        
        # Get or create cart
        cart, created = Cart.objects.get_or_create(user=request.user)
        
        # Check if item already in cart
        cart_item, item_created = CartItem.objects.get_or_create(
            cart=cart,
            fish=fish,
            defaults={'weight_kg': weight}
        )
        
        if not item_created:
            # Update existing item weight
            cart_item.weight_kg = weight
            cart_item.save()
            messages.success(request, f'Updated {fish.name} to {weight}kg in cart.')
        else:
            messages.success(request, f'Added {fish.name} ({weight}kg) to cart.')
        
        return redirect('fishing:cart')
    
    return redirect('fishing:fish_detail', fish_id=fish.id)


@login_required
def cart_view(request):
    """Display shopping cart"""
    try:
        cart = Cart.objects.get(user=request.user)
        items = cart.items.select_related('fish', 'fish__fisherman').all()
    except Cart.DoesNotExist:
        cart = None
        items = []
    
    # Calculate totals
    total_weight = sum(item.get_total_weight() for item in items)
    total_price = sum(item.get_total_price() for item in items)
    
    # Check availability before checkout
    unavailable_items = []
    for item in items:
        if not item.fish.is_available() or item.weight_kg > item.fish.available_weight:
            unavailable_items.append(item)
    
    context = {
        'cart': cart,
        'items': items,
        'total_weight': total_weight,
        'total_price': total_price,
        'unavailable_items': unavailable_items,
    }
    return render(request, 'fishing/cart.html', context)


@login_required
def update_cart_item(request, item_id):
    """Update cart item weight"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    
    if request.method == 'POST':
        try:
            weight = float(request.POST.get('weight', 1))
        except (ValueError, TypeError):
            weight = 1
        
        # Validate weight
        if weight <= 0:
            messages.error(request, 'Weight must be greater than 0.')
            return redirect('fishing:cart')
        
        if weight > float(cart_item.fish.available_weight):
            weight = float(cart_item.fish.available_weight)
            messages.warning(request, f'Maximum available is {cart_item.fish.available_weight}kg')
        
        cart_item.weight_kg = weight
        cart_item.save()
        messages.success(request, f'Updated {cart_item.fish.name} to {weight}kg.')
    
    return redirect('fishing:cart')


@login_required
def remove_from_cart(request, item_id):
    """Remove item from cart"""
    cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    fish_name = cart_item.fish.name
    cart_item.delete()
    messages.success(request, f'Removed {fish_name} from cart.')
    return redirect('fishing:cart')


@login_required
def checkout_initiate(request):
    """Initiate checkout process"""
    try:
        cart = Cart.objects.get(user=request.user)
        items = cart.items.select_related('fish', 'fish__fisherman').all()
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('fishing:marketplace')
    
    if not items:
        messages.error(request, 'Your cart is empty.')
        return redirect('fishing:marketplace')
    
    # Validate all items are still available
    for item in items:
        if not item.fish.is_available():
            messages.error(request, f'{item.fish.name} is no longer available.')
            return redirect('fishing:cart')
        if item.weight_kg > item.fish.available_weight:
            messages.error(request, f'Not enough {item.fish.name} in stock.')
            return redirect('fishing:cart')
    
    # Calculate totals
    total_weight = sum(item.get_total_weight() for item in items)
    total_price = sum(item.get_total_price() for item in items)
    
    # Get customer profile for delivery info
    customer_profile = None
    if request.user.role == 'customer':
        try:
            customer_profile = request.user.customer_profile
        except CustomerProfile.DoesNotExist:
            messages.warning(request, 'Please complete your profile before checkout.')
            return redirect('users:edit_profile')
    
    context = {
        'cart': cart,
        'items': items,
        'total_weight': total_weight,
        'total_price': total_price,
        'customer_profile': customer_profile,
    }
    return render(request, 'fishing/checkout.html', context)


@login_required
def checkout_process(request):
    """Process checkout and initiate M-Pesa payment"""
    if request.method != 'POST':
        return redirect('fishing:cart')
    
    try:
        cart = Cart.objects.get(user=request.user)
        items = cart.items.select_related('fish').all()
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('fishing:marketplace')
    
    # Get form data
    fulfillment_method = request.POST.get('fulfillment_method', 'delivery')
    delivery_location = request.POST.get('delivery_location', '')
    delivery_address = request.POST.get('delivery_address', '')
    delivery_notes = request.POST.get('delivery_notes', '')
    
    # Validate customer profile for delivery
    if fulfillment_method == 'delivery':
        if not delivery_location:
            messages.error(request, 'Please provide a delivery location.')
            return redirect('fishing:checkout_initiate')
    
    # Calculate totals
    total_price = sum(item.get_total_price() for item in items)
    
    # Create order
    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            total_amount=total_price,
            fulfillment_method=fulfillment_method,
            delivery_location=delivery_location,
            delivery_address=delivery_address,
            delivery_notes=delivery_notes,
            customer_phone=request.user.phone,
            customer_email=request.user.email,
            status='PENDING'
        )
        
        # Create order items
        for item in items:
            OrderItem.objects.create(
                order=order,
                fish=item.fish,
                fisherman=item.fish.fisherman,
                fish_name=item.fish.name,
                fish_type=item.fish.fish_type,
                weight_kg=item.weight_kg,
                price_per_kg=item.fish.price_per_kg,
                total_price=item.get_total_price()
            )
            
            # Log transaction
            FishTransactionLog.objects.create(
                fish=item.fish,
                action='RESERVED',
                user=request.user,
                weight_change=item.weight_kg,
                notes=f'Reserved for Order #{order.order_number}'
            )
        
        # Clear cart
        cart.delete()
    
    # Initiate M-Pesa payment
    phone_number = request.user.phone
    if not phone_number:
        messages.error(request, 'Please add a phone number to your profile.')
        return redirect('users:edit_profile')
    
    payment_result = initiate_stk_push(
        phone_number=phone_number,
        amount=float(total_price),
        order_number=order.order_number
    )
    
    if payment_result.get('success'):
        # Create payment transaction record
        PaymentTransaction.objects.create(
            order=order,
            transaction_id=payment_result.get('merchant_request_id'),
            checkout_request_id=payment_result.get('checkout_request_id'),
            amount=total_price,
            phone_number=phone_number,
            status='PENDING'
        )
        
        messages.success(request, 'Payment request sent to your phone. Please enter your PIN to complete payment.')
        return redirect('fishing:order_detail', order_number=order.order_number)
    else:
        messages.error(request, f'Payment initiation failed: {payment_result.get("error")}')
        # Keep order in PENDING state for retry
        return redirect('fishing:order_detail', order_number=order.order_number)


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa payment callback"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=400)
    
    print(f"M-Pesa Callback Received - Body: {request.body}")
    
    try:
        raw_data = request.body.decode('utf-8')
        result = process_payment_callback(raw_data)
        
        if result.get('success'):
            # Find the transaction
            checkout_request_id = result.get('checkout_request_id')
            try:
                transaction = PaymentTransaction.objects.get(checkout_request_id=checkout_request_id)
                order = transaction.order
                
                # Update transaction
                transaction.mpesa_receipt_number = result.get('transaction_id')
                transaction.result_code = result.get('result_code')
                transaction.result_desc = result.get('result_desc')
                transaction.status = 'COMPLETED'
                transaction.save()
                
                # Update order status
                order.mark_as_paid(transaction_id=transaction.transaction_id)
                
                # Log successful payment
                FishTransactionLog.objects.create(
                    fish=None,
                    action='PAYMENT_RECEIVED',
                    user=order.customer,
                    notes=f'Payment received: {transaction.mpesa_receipt_number} for Order #{order.order_number}'
                )
                
                return JsonResponse({'status': 'success', 'message': 'Payment processed'})
            except PaymentTransaction.DoesNotExist:
                logger.error(f'Transaction not found for checkout_request_id: {checkout_request_id}')
                return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
        else:
            # Payment failed
            checkout_request_id = result.get('checkout_request_id')
            try:
                transaction = PaymentTransaction.objects.get(checkout_request_id=checkout_request_id)
                order = transaction.order
                
                transaction.status = 'FAILED'
                transaction.result_code = result.get('result_code')
                transaction.result_desc = result.get('result_desc')
                transaction.save()
                
                order.status = 'FAILED'
                order.save()
                
                # Release reserved stock
                for item in order.items.all():
                    FishTransactionLog.objects.create(
                        fish=item.fish,
                        action='STOCK_RELEASED',
                        user=order.customer,
                        weight_change=item.weight_kg,
                        notes=f'Stock released due to payment failure for Order #{order.order_number}'
                    )
                
                return JsonResponse({'status': 'failed', 'message': result.get('result_desc')})
            except PaymentTransaction.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)
    
    except Exception as e:
        logger.error(f'Error processing M-Pesa callback: {str(e)}')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def order_detail(request, order_number):
    """Display order details"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    items = order.items.select_related('fish').all()
    
    # Get delivery info if exists
    delivery = None
    if order.status in ['READY', 'OUT_FOR_DELIVERY', 'DELIVERED']:
        try:
            delivery = order.delivery
        except Delivery.DoesNotExist:
            pass
    
    # Get payment transactions
    transactions = order.transactions.all()
    
    context = {
        'order': order,
        'items': items,
        'delivery': delivery,
        'transactions': transactions,
    }
    return render(request, 'fishing/order_detail.html', context)


@login_required
def order_list(request):
    """Display user's orders"""
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
    }
    return render(request, 'fishing/order_list.html', context)


# Fisherman Views
@login_required
def fisherman_dashboard(request):
    """Fisherman dashboard with sales overview"""
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied. Fisherman account required.')
        return redirect('users:profile')
    
    # Get fisherman profile
    try:
        profile = request.user.fisherman_profile
    except FishermanProfile.DoesNotExist:
        messages.warning(request, 'Please complete your fisherman profile.')
        return redirect('users:edit_profile')
    
    # Get fish listings
    fish_listings = Fish.objects.filter(fisherman=request.user).order_by('-created_at')
    available_fish = fish_listings.filter(status='available')
    sold_fish = fish_listings.filter(status='sold')
    
    # Get orders containing this fisherman's fish
    from fishing.models import OrderItem
    my_order_items = OrderItem.objects.filter(fisherman=request.user).select_related('order')
    
    # Calculate stats
    total_sales_amount = sum(item.total_price for item in my_order_items if item.order.status in ['PAID', 'DELIVERED'])
    total_items_sold = sum(item.weight_kg for item in my_order_items if item.order.status in ['PAID', 'DELIVERED'])
    pending_orders = my_order_items.filter(order__status='PAID', fulfillment_status='PENDING').count()
    
    # Recent orders
    recent_orders = my_order_items.order_by('-order__created_at')[:10]
    
    context = {
        'profile': profile,
        'fish_listings': fish_listings,
        'available_fish': available_fish,
        'sold_fish': sold_fish,
        'my_order_items': my_order_items,
        'recent_orders': recent_orders,
        'total_sales_amount': total_sales_amount,
        'total_items_sold': total_items_sold,
        'pending_orders': pending_orders,
    }
    return render(request, 'fishing/fisherman_dashboard.html', context)


@login_required
def my_fish_listing(request):
    """List all fish listings by fisherman"""
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied. Fisherman account required.')
        return redirect('users:profile')
    
    fish_listings = Fish.objects.filter(fisherman=request.user).order_by('-created_at')
    
    # Pagination
    paginator = Paginator(fish_listings, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'fishing/my_fish_listing.html', context)


@login_required
def add_fish(request):
    """Add new fish listing"""
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied. Fisherman account required.')
        return redirect('users:profile')
    
    if request.method == 'POST':
        try:
            fish = Fish.objects.create(
                fisherman=request.user,
                name=request.POST.get('name'),
                fish_type=request.POST.get('fish_type'),
                description=request.POST.get('description', ''),
                price_per_kg=request.POST.get('price_per_kg'),
                available_weight=request.POST.get('available_weight'),
                catch_date=request.POST.get('catch_date'),
                location=request.POST.get('location', ''),
                is_organic='is_organic' in request.POST,
                is_frozen='is_frozen' in request.POST,
                preparation_notes=request.POST.get('preparation_notes', ''),
            )
            
            # Log transaction
            FishTransactionLog.objects.create(
                fish=fish,
                action='LISTED',
                user=request.user,
                notes=f'Listed {fish.available_weight}kg of {fish.name}'
            )
            
            messages.success(request, f'Listed {fish.name} for sale!')
            return redirect('fishing:my_fish_listing')
        except Exception as e:
            messages.error(request, f'Error listing fish: {str(e)}')
    
    context = {
        'fish_types': Fish.FISH_TYPE_CHOICES,
    }
    return render(request, 'fishing/add_fish.html', context)


@login_required
def edit_fish(request, fish_id):
    """Edit fish listing"""
    fish = get_object_or_404(Fish, id=fish_id, fisherman=request.user)
    
    if request.method == 'POST':
        old_weight = fish.available_weight
        
        fish.name = request.POST.get('name')
        fish.fish_type = request.POST.get('fish_type')
        fish.description = request.POST.get('description', '')
        fish.price_per_kg = request.POST.get('price_per_kg')
        fish.available_weight = request.POST.get('available_weight')
        fish.catch_date = request.POST.get('catch_date')
        fish.location = request.POST.get('location', '')
        fish.is_organic = 'is_organic' in request.POST
        fish.is_frozen = 'is_frozen' in request.POST
        fish.preparation_notes = request.POST.get('preparation_notes', '')
        fish.save()
        
        # Log changes
        weight_change = float(fish.available_weight) - float(old_weight)
        FishTransactionLog.objects.create(
            fish=fish,
            action='STOCK_ADJUSTED',
            user=request.user,
            weight_change=weight_change,
            notes=f'Updated listing for {fish.name}'
        )
        
        messages.success(request, f'Updated {fish.name}!')
        return redirect('fishing:my_fish_listing')
    
    context = {
        'fish': fish,
        'fish_types': Fish.FISH_TYPE_CHOICES,
    }
    return render(request, 'fishing/edit_fish.html', context)


@login_required
def delete_fish(request, fish_id):
    """Delete fish listing"""
    fish = get_object_or_404(Fish, id=fish_id, fisherman=request.user)
    
    if request.method == 'POST':
        fish_name = fish.name
        weight = fish.available_weight
        fish.delete()
        
        FishTransactionLog.objects.create(
            fish=None,
            action='DELETED',
            user=request.user,
            weight_change=weight,
            notes=f'Deleted listing for {fish_name}'
        )
        
        messages.success(request, f'Deleted {fish_name}.')
        return redirect('fishing:my_fish_listing')
    
    context = {'fish': fish}
    return render(request, 'fishing/delete_fish.html', context)


@login_required
def order_fulfillment(request):
    """View and fulfill orders containing fisherman's fish"""
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied. Fisherman account required.')
        return redirect('users:profile')
    
    from fishing.models import OrderItem
    order_items = OrderItem.objects.filter(
        fisherman=request.user,
        order__status__in=['PAID', 'PROCESSING', 'READY']
    ).select_related('order', 'fish').order_by('-order__created_at')
    
    # Group by order
    orders_by_number = {}
    for item in order_items:
        if item.order.order_number not in orders_by_number:
            orders_by_number[item.order.order_number] = {
                'order': item.order,
                'items': [],
                'items_count': 0,
                'total_weight': 0,
            }
        orders_by_number[item.order.order_number]['items'].append(item)
        orders_by_number[item.order.order_number]['items_count'] += 1
        orders_by_number[item.order.order_number]['total_weight'] += float(item.weight_kg)
    
    context = {
        'orders_by_number': orders_by_number,
    }
    return render(request, 'fishing/order_fulfillment.html', context)


@login_required
def update_order_status(request, order_number, item_id):
    """Update fulfillment status of an order item"""
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied. Fisherman account required.')
        return redirect('users:profile')
    
    from fishing.models import OrderItem
    item = get_object_or_404(
        OrderItem, 
        id=item_id, 
        order__order_number=order_number,
        fisherman=request.user
    )
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        item.fulfillment_status = new_status
        item.save()
        
        # Update main order status if all items are ready
        order = item.order
        all_items = order.items.all()
        if all(item.fulfillment_status in ['READY', 'DELIVERED'] for item in all_items):
            order.status = 'READY'
            order.save()
            
            # Create delivery record
            if order.fulfillment_method == 'delivery':
                Delivery.objects.create(
                    order=order,
                    fisherman=request.user,
                    status='READY'
                )
        
        messages.success(request, f'Updated status for order item.')
        return redirect('fishing:order_fulfillment')
    
    context = {'item': item}
    return render(request, 'fishing/update_order_status.html', context)


# Customer Dashboard
@login_required
def customer_dashboard(request):
    """Customer dashboard with order history"""
    if request.user.role != 'customer':
        messages.error(request, 'Access denied. Customer account required.')
        return redirect('users:profile')
    
    # Get customer profile
    try:
        profile = request.user.customer_profile
    except CustomerProfile.DoesNotExist:
        messages.warning(request, 'Please complete your customer profile.')
        return redirect('users:edit_profile')
    
    # Get orders
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    
    # Recent orders
    recent_orders = orders[:5]
    
    # Stats
    total_orders = orders.count()
    pending_orders = orders.filter(status__in=['PENDING', 'PAID', 'PROCESSING']).count()
    completed_orders = orders.filter(status='DELIVERED').count()
    
    context = {
        'profile': profile,
        'recent_orders': recent_orders,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
    }
    return render(request, 'fishing/customer_dashboard.html', context)


@login_required
def delivery_tracking(request, order_number):
    """Track delivery status"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if order.fulfillment_method != 'delivery':
        messages.error(request, 'This order is not for delivery.')
        return redirect('fishing:order_detail', order_number=order_number)
    
    try:
        delivery = order.delivery
    except Delivery.DoesNotExist:
        delivery = None
    
    context = {
        'order': order,
        'delivery': delivery,
    }
    return render(request, 'fishing/delivery_tracking.html', context)


@login_required
def confirm_delivery(request, order_number):
    """Customer confirms delivery received"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if request.method == 'POST':
        order.status = 'DELIVERED'
        order.save()
        
        try:
            delivery = order.delivery
            delivery.status = 'DELIVERED'
            delivery.actual_delivery = timezone.now()
            delivery.save()
        except Delivery.DoesNotExist:
            pass
        
        messages.success(request, 'Thank you! Delivery confirmed.')
        return redirect('fishing:order_detail', order_number=order_number)
    
    context = {'order': order}
    return render(request, 'fishing/confirm_delivery.html', context)


# API Views
@login_required
@require_http_methods(['POST'])
def api_add_to_cart(request, fish_id):
    """API endpoint to add fish to cart"""
    fish = get_object_or_404(Fish, id=fish_id)
    
    try:
        weight = float(request.POST.get('weight', 1))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid weight'})
    
    if weight <= 0 or weight > float(fish.available_weight):
        return JsonResponse({'success': False, 'error': 'Invalid weight'})
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        fish=fish,
        defaults={'weight_kg': weight}
    )
    
    if not item_created:
        cart_item.weight_kg = weight
        cart_item.save()
    
    return JsonResponse({
        'success': True,
        'cart_count': cart.get_total_items(),
        'message': f'Added {weight}kg of {fish.name} to cart'
    })


@login_required
def api_cart_count(request):
    """API endpoint to get cart count"""
    try:
        cart = Cart.objects.get(user=request.user)
        return JsonResponse({'count': cart.get_total_items()})
    except Cart.DoesNotExist:
        return JsonResponse({'count': 0})


# Landing Page
def marketplace_home(request):
    """Marketplace home page with featured fish"""
    featured_fish = Fish.objects.filter(
        status='available',
        available_weight__gt=0
    ).select_related('fisherman').order_by('-created_at')[:8]
    
    context = {
        'featured_fish': featured_fish,
    }
    return render(request, 'fishing/marketplace_home.html', context)

