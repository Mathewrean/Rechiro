from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Sum
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
import logging
from urllib.parse import urlparse

from .models import (
    Fish, Cart, CartItem, Order, OrderItem, PaymentTransaction, Delivery, FishTransactionLog,
    PickupPoint, DeliveryAuditLog, SellerNotification, PlatformFeeLog, ChairmanApprovalRequest
)
from .mpesa_service import initiate_stk_push, process_payment_callback
from users.models import FishermanProfile, CustomerProfile
from users.models import PhoneVerificationTransaction

logger = logging.getLogger(__name__)


def _fisherman_payment_ready(profile, fisherman_user):
    """
    Determine if fisherman can receive checkout-triggered STK requests.
    Uses fallback phone from profile/user when mpesa_phone is not explicitly set.
    """
    payment_phone = profile.mpesa_phone or profile.phone or fisherman_user.phone
    if not payment_phone:
        return False, "missing M-Pesa phone number"

    payment_type = profile.mpesa_payment_type or 'STK_PUSH'
    if payment_type == 'PAYBILL' and not profile.mpesa_paybill_number:
        return False, "missing Paybill number"
    if payment_type == 'TILL' and not profile.mpesa_till_number:
        return False, "missing Till number"
    return True, ""


def _is_public_callback_url(url_value):
    if not url_value:
        return False
    parsed = urlparse(url_value)
    if parsed.scheme not in ['http', 'https'] or not parsed.netloc:
        return False
    host = parsed.hostname or ''
    if host in ['localhost', '127.0.0.1', '0.0.0.0']:
        return False
    return True

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
            weight = Decimal(str(request.POST.get('weight', '1')))
        except (ValueError, TypeError):
            weight = Decimal('1')
        
        # Validate weight
        if weight <= Decimal('0'):
            weight = Decimal('1')
        if weight > fish.available_weight:
            weight = fish.available_weight
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
            weight = Decimal(str(request.POST.get('weight', '1')))
        except (ValueError, TypeError):
            weight = Decimal('1')
        
        # Validate weight
        if weight <= Decimal('0'):
            messages.error(request, 'Weight must be greater than 0.')
            return redirect('fishing:cart')
        
        if weight > cart_item.fish.available_weight:
            weight = cart_item.fish.available_weight
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
    if request.user.role == 'customer' and not request.user.email_verified:
        messages.error(request, 'Please verify your email before checkout.')
        return redirect('users:email_verification')
    if not request.user.phone:
        messages.error(request, 'Please add a phone number to your profile.')
        return redirect('users:edit_profile')
    
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
        'pickup_points': PickupPoint.objects.all().order_by('name'),
    }
    return render(request, 'fishing/checkout.html', context)


@login_required
def checkout_process(request):
    """Process checkout and initiate M-Pesa STK push per fisherman-linked fish item."""
    if request.method != 'POST':
        return redirect('fishing:cart')
    
    try:
        cart = Cart.objects.get(user=request.user)
        items = cart.items.select_related('fish', 'fish__fisherman').all()
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('fishing:marketplace')
    if not items:
        messages.error(request, 'Your cart is empty.')
        return redirect('fishing:marketplace')
    if request.user.role == 'customer' and not request.user.email_verified:
        messages.error(request, 'Please verify your email before checkout.')
        return redirect('users:email_verification')
    if not _is_public_callback_url(getattr(settings, 'MPESA_CALLBACK_URL', '')):
        messages.error(
            request,
            'Payment callback URL is not publicly accessible. Set MPESA_CALLBACK_URL to your live ngrok/public URL.'
        )
        return redirect('fishing:checkout_initiate')
    
    # Get form data
    fulfillment_method = request.POST.get('fulfillment_method', 'delivery')
    delivery_location = request.POST.get('delivery_location', '')
    delivery_address = request.POST.get('delivery_address', '')
    delivery_notes = request.POST.get('delivery_notes', '')
    pickup_point_id = request.POST.get('pickup_point')
    
    # Validate customer profile for delivery
    if fulfillment_method == 'delivery':
        if not delivery_location:
            messages.error(request, 'Please provide a delivery location.')
            return redirect('fishing:checkout_initiate')
    if fulfillment_method == 'pickup' and not pickup_point_id:
        messages.error(request, 'Please select a pickup point.')
        return redirect('fishing:checkout_initiate')
    
    # Validate items and settlement destination.
    fishermen_profiles = {}
    for item in items:
        if item.weight_kg <= Decimal('0'):
            messages.error(request, f'Invalid weight for {item.fish.name}.')
            return redirect('fishing:cart')
        if item.fish.price_per_kg <= Decimal('0'):
            messages.error(request, f'Invalid price-per-kg for {item.fish.name}.')
            return redirect('fishing:cart')
        if item.weight_kg > item.fish.available_weight or not item.fish.is_available():
            messages.error(request, f'{item.fish.name} is no longer available in requested weight.')
            return redirect('fishing:cart')
        try:
            profile = item.fish.fisherman.fisherman_profile
        except FishermanProfile.DoesNotExist:
            messages.error(request, f'Fisherman profile missing for {item.fish.name}.')
            return redirect('fishing:cart')
        is_ready, reason = _fisherman_payment_ready(profile, item.fish.fisherman)
        if not is_ready:
            messages.error(
                request,
                f'Fisherman for {item.fish.name} is not payment-ready ({reason}).'
            )
            return redirect('fishing:cart')
        if not profile.is_verified:
            # Auto-verify when complete M-Pesa config is present.
            profile.is_verified = True
            profile.save(update_fields=['is_verified', 'updated_at'])
        if not profile.mpesa_phone:
            profile.mpesa_phone = profile.phone or item.fish.fisherman.phone
            profile.save(update_fields=['mpesa_phone', 'updated_at'])
        fishermen_profiles[item.fish.fisherman_id] = profile

    pickup_point = None
    if pickup_point_id:
        pickup_point = get_object_or_404(PickupPoint, id=pickup_point_id)
    
    # Create order
    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            total_amount=Decimal('0.00'),
            fulfillment_method=fulfillment_method,
            pickup_point=pickup_point,
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

        order.calculate_financials()
        order.save(update_fields=['total_amount', 'platform_fee', 'fishermen_net_amount'])

        # Create payment requests item-by-item to settle directly to each fisherman.
        payment_errors = []
        for order_item in order.items.select_related('fisherman', 'fish'):
            fisher_profile = fishermen_profiles.get(order_item.fisherman_id)
            payment_type = fisher_profile.mpesa_payment_type or 'STK_PUSH'
            if payment_type in ['STK_PUSH', 'PAYBILL']:
                transaction_type = 'CustomerPayBillOnline'
            else:
                transaction_type = 'CustomerBuyGoodsOnline'
            payment_result = initiate_stk_push(
                phone_number=request.user.phone,
                amount=float(order_item.total_price),
                order_number=order.order_number,
                business_shortcode=(fisher_profile.mpesa_paybill_number or fisher_profile.mpesa_till_number or None),
                account_reference=(fisher_profile.mpesa_account_reference or f"{order.order_number}-{order_item.id}"),
                transaction_type=transaction_type,
            )
            if payment_result.get('success'):
                PaymentTransaction.objects.create(
                    order=order,
                    order_item=order_item,
                    buyer=request.user,
                    fisherman=order_item.fisherman,
                    transaction_id=payment_result.get('merchant_request_id') or f"{order.order_number}-{order_item.id}",
                    merchant_request_id=payment_result.get('merchant_request_id', ''),
                    checkout_request_id=payment_result.get('checkout_request_id', ''),
                    amount=order_item.total_price,
                    unit_price_per_kg=order_item.price_per_kg,
                    weight_kg=order_item.weight_kg,
                    platform_fee=order_item.platform_fee,
                    net_payout=order_item.fisherman_net_payout,
                    phone_number=request.user.phone,
                    status='PENDING',
                )
            else:
                payment_errors.append(f"{order_item.fish_name}: {payment_result.get('error', 'Unknown error')}")
                PaymentTransaction.objects.create(
                    order=order,
                    order_item=order_item,
                    buyer=request.user,
                    fisherman=order_item.fisherman,
                    transaction_id=f"FAILED-{order.order_number}-{order_item.id}",
                    amount=order_item.total_price,
                    unit_price_per_kg=order_item.price_per_kg,
                    weight_kg=order_item.weight_kg,
                    platform_fee=order_item.platform_fee,
                    net_payout=order_item.fisherman_net_payout,
                    phone_number=request.user.phone,
                    status='FAILED',
                    result_desc=payment_result.get('error', 'STK push failed'),
                )

        # Clear cart after creating order + transactions.
        cart.clear()

        if payment_errors:
            order.status = 'FAILED'
            order.save(update_fields=['status', 'updated_at'])
            messages.error(request, f'One or more STK requests failed: {"; ".join(payment_errors)}')
        else:
            messages.success(request, 'STK push sent for each listing. Complete payment prompts on your phone.')
        return redirect('fishing:order_detail', order_number=order.order_number)


@csrf_exempt
def mpesa_callback(request):
    """Handle M-Pesa payment callback"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=400)
    
    try:
        raw_data = request.body.decode('utf-8')
        logger.info('M-Pesa callback payload: %s', raw_data)
        result = process_payment_callback(raw_data)
        checkout_request_id = result.get('checkout_request_id')
        if not checkout_request_id:
            logger.error('M-Pesa callback missing checkout_request_id. Parsed result=%s', result)
            return JsonResponse({'status': 'error', 'message': 'Missing checkout request id'}, status=400)

        with transaction.atomic():
            try:
                payment_txn = PaymentTransaction.objects.select_for_update().select_related('order', 'order_item').get(
                    checkout_request_id=checkout_request_id
                )
            except PaymentTransaction.DoesNotExist:
                # Fallback: phone ownership verification callbacks.
                try:
                    verification_txn = PhoneVerificationTransaction.objects.select_for_update().select_related('user').get(
                        checkout_request_id=checkout_request_id
                    )
                except PhoneVerificationTransaction.DoesNotExist:
                    logger.error('Transaction not found for checkout_request_id=%s', checkout_request_id)
                    return JsonResponse({'status': 'error', 'message': 'Transaction not found'}, status=404)

                if verification_txn.status == 'COMPLETED':
                    return JsonResponse({'status': 'success', 'message': 'Phone verification already processed'})

                result_code = result.get('result_code')
                try:
                    normalized_result_code = int(result_code)
                except (TypeError, ValueError):
                    normalized_result_code = -1

                verification_txn.result_code = normalized_result_code
                verification_txn.result_desc = result.get('result_desc', '')
                if normalized_result_code == 0 and result.get('success'):
                    verification_txn.status = 'COMPLETED'
                    verification_txn.mpesa_receipt_number = result.get('transaction_id', '') or ''
                    verification_txn.save(update_fields=[
                        'status', 'mpesa_receipt_number', 'result_code', 'result_desc', 'updated_at'
                    ])
                    verification_txn.user.phone_verified = True
                    verification_txn.user.save(update_fields=['phone_verified'])
                    logger.info('Seller phone verified for user_id=%s via checkout_request_id=%s', verification_txn.user_id, checkout_request_id)
                    return JsonResponse({'status': 'success', 'message': 'Phone verification completed'})

                verification_txn.status = 'FAILED'
                verification_txn.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])
                return JsonResponse({'status': 'failed', 'message': 'Phone verification failed'})

            order = payment_txn.order

            # Idempotency: callback already handled.
            if payment_txn.status == 'COMPLETED':
                logger.info('Duplicate callback ignored for checkout_request_id=%s', checkout_request_id)
                return JsonResponse({'status': 'success', 'message': 'Already processed'})

            result_code = result.get('result_code')
            try:
                normalized_result_code = int(result_code)
            except (TypeError, ValueError):
                normalized_result_code = -1

            if normalized_result_code == 0 and result.get('success'):
                callback_amount = result.get('amount')
                if callback_amount is not None:
                    try:
                        callback_amount_dec = Decimal(str(callback_amount)).quantize(Decimal('0.01'))
                    except Exception:
                        logger.error('Invalid callback amount for checkout_request_id=%s amount=%s', checkout_request_id, callback_amount)
                        return JsonResponse({'status': 'error', 'message': 'Invalid callback amount'}, status=400)
                    if callback_amount_dec != payment_txn.amount:
                        payment_txn.status = 'FAILED'
                        payment_txn.result_desc = 'Amount mismatch in callback validation'
                        payment_txn.result_code = normalized_result_code
                        payment_txn.save(update_fields=['status', 'result_desc', 'result_code', 'updated_at'])
                        logger.error(
                            'Amount mismatch for checkout_request_id=%s expected=%s got=%s',
                            checkout_request_id, payment_txn.amount, callback_amount_dec
                        )
                        return JsonResponse({'status': 'error', 'message': 'Callback amount validation failed'}, status=400)

                receipt_number = result.get('transaction_id', '') or ''
                payment_txn.mpesa_receipt_number = receipt_number
                payment_txn.result_code = normalized_result_code
                payment_txn.result_desc = result.get('result_desc', '')
                payment_txn.status = 'COMPLETED'
                payment_txn.save(update_fields=[
                    'mpesa_receipt_number', 'result_code', 'result_desc', 'status', 'updated_at'
                ])

                if payment_txn.order_item and payment_txn.order_item.fulfillment_status != 'PAID':
                    payment_txn.order_item.fulfillment_status = 'PAID'
                    payment_txn.order_item.save(update_fields=['fulfillment_status'])
                    FishTransactionLog.objects.create(
                        fish=payment_txn.order_item.fish,
                        action='PAYMENT_RECEIVED',
                        user=order.customer,
                        weight_change=payment_txn.order_item.weight_kg,
                        notes=(
                            f'Buyer={order.customer_id}, Fisherman={payment_txn.fisherman_id}, '
                            f'Fish={payment_txn.order_item.fish_name}, WeightKg={payment_txn.weight_kg}, '
                            f'UnitPrice={payment_txn.unit_price_per_kg}, Total={payment_txn.amount}, '
                            f'PlatformFee={payment_txn.platform_fee}, NetPayout={payment_txn.net_payout}, '
                            f'MpesaID={payment_txn.mpesa_receipt_number}, Status={payment_txn.status}'
                        )
                    )

                    SellerNotification.objects.get_or_create(
                        fisherman=payment_txn.fisherman,
                        buyer=order.customer,
                        order=order,
                        payment_transaction=payment_txn,
                        defaults={
                            'fish_item': payment_txn.order_item.fish_name,
                            'weight_kg': payment_txn.weight_kg,
                            'total_amount': payment_txn.amount,
                            'net_earnings': payment_txn.net_payout,
                            'receipt_number': payment_txn.mpesa_receipt_number,
                            'message': (
                                f'Payment received from {order.customer.username} for {payment_txn.order_item.fish_name}. '
                                f'{payment_txn.weight_kg}kg, KES {payment_txn.amount}, '
                                f'net KES {payment_txn.net_payout}, receipt {payment_txn.mpesa_receipt_number}.'
                            ),
                        }
                    )
                    PlatformFeeLog.objects.get_or_create(
                        order=order,
                        payment_transaction=payment_txn,
                        defaults={
                            'fisherman': payment_txn.fisherman,
                            'fee_amount': payment_txn.platform_fee,
                            'gross_amount': payment_txn.amount,
                            'net_amount': payment_txn.net_payout,
                        }
                    )

                pending_count = order.transactions.filter(status='PENDING').count()
                failed_count = order.transactions.filter(status='FAILED').count()
                if pending_count == 0 and failed_count == 0:
                    if order.status not in ['FULLY_PAID', 'DELIVERY_IN_PROGRESS', 'DELIVERED']:
                        order.mark_as_paid(transaction_id=payment_txn.transaction_id)
                        order.status = 'DELIVERY_IN_PROGRESS'
                        order.save(update_fields=['status', 'updated_at'])
                    if order.fulfillment_method == 'pickup':
                        Delivery.objects.update_or_create(
                            order=order,
                            defaults={
                                'fisherman': payment_txn.fisherman,
                                'status': 'READY_FOR_PICKUP',
                                'updated_by': payment_txn.fisherman,
                            }
                        )
                    else:
                        Delivery.objects.update_or_create(
                            order=order,
                            defaults={
                                'fisherman': payment_txn.fisherman,
                                'status': 'DELIVERY_IN_PROGRESS',
                                'updated_by': payment_txn.fisherman,
                            }
                        )
                    return JsonResponse({'status': 'success', 'message': 'Payment confirmed. Order is paid.'})

                if order.status == 'PENDING':
                    order.status = 'PAID'
                    order.save(update_fields=['status', 'updated_at'])
                return JsonResponse({'status': 'success', 'message': 'Payment entry confirmed.'})

            # Failed / cancelled callback
            payment_txn.status = 'FAILED'
            payment_txn.result_code = normalized_result_code
            payment_txn.result_desc = result.get('result_desc', '')
            payment_txn.save(update_fields=['status', 'result_code', 'result_desc', 'updated_at'])

            if order.transactions.filter(status='FAILED').exists():
                order.status = 'FAILED'
                order.save(update_fields=['status', 'updated_at'])

            if payment_txn.order_item:
                FishTransactionLog.objects.create(
                    fish=payment_txn.order_item.fish,
                    action='STOCK_RELEASED',
                    user=order.customer,
                    weight_change=payment_txn.order_item.weight_kg,
                    notes=f'Stock released due to payment failure for Order #{order.order_number}'
                )
            return JsonResponse({'status': 'failed', 'message': result.get('result_desc')})
    
    except Exception as e:
        logger.exception('Error processing M-Pesa callback')
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def order_detail(request, order_number):
    """Display order details"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    items = order.items.select_related('fish').all()
    
    # Get delivery info if exists
    delivery = None
    if order.status in ['READY', 'READY_FOR_PICKUP', 'DELIVERY_IN_PROGRESS', 'OUT_FOR_DELIVERY', 'DELIVERED']:
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
    
    # Calculate stats from confirmed payment transactions
    confirmed_sales = PaymentTransaction.objects.filter(
        fisherman=request.user,
        status='COMPLETED'
    )
    gross_revenue = confirmed_sales.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    platform_fee_total = confirmed_sales.aggregate(total=Sum('platform_fee'))['total'] or Decimal('0.00')
    net_earnings = confirmed_sales.aggregate(total=Sum('net_payout'))['total'] or Decimal('0.00')
    total_sales_amount = gross_revenue
    total_items_sold = sum(item.weight_kg for item in my_order_items if item.order.status in ['PAID', 'FULLY_PAID', 'DELIVERY_IN_PROGRESS', 'DELIVERED'])
    pending_orders = my_order_items.filter(order__status__in=['PAID', 'FULLY_PAID', 'DELIVERY_IN_PROGRESS'], fulfillment_status='PENDING').count()
    
    # Recent orders
    recent_orders = my_order_items.order_by('-order__created_at')[:10]
    notifications = SellerNotification.objects.filter(fisherman=request.user).order_by('-created_at')[:10]
    unread_notifications_count = SellerNotification.objects.filter(fisherman=request.user, is_read=False).count()
    approval_request = ChairmanApprovalRequest.objects.filter(fisherman=request.user).first()
    
    context = {
        'profile': profile,
        'fish_listings': fish_listings,
        'available_fish': available_fish,
        'sold_fish': sold_fish,
        'my_order_items': my_order_items,
        'recent_orders': recent_orders,
        'total_sales_amount': total_sales_amount,
        'gross_revenue': gross_revenue,
        'platform_fee_total': platform_fee_total,
        'net_earnings': net_earnings,
        'total_items_sold': total_items_sold,
        'pending_orders': pending_orders,
        'notifications': notifications,
        'unread_notifications_count': unread_notifications_count,
        'approval_request': approval_request,
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
    try:
        fisher_profile = request.user.fisherman_profile
    except FishermanProfile.DoesNotExist:
        messages.error(request, 'Complete fisherman profile first.')
        return redirect('users:edit_profile')
    if not request.user.phone_verified:
        messages.error(request, 'Complete KES 1 phone ownership verification before listing fish.')
        return redirect('users:phone_verification')
    if not fisher_profile.chairman_approved:
        messages.error(request, 'Your listing access is pending Lake Chairman approval.')
        return redirect('users:profile')
    
    if request.method == 'POST':
        try:
            uploaded_image = request.FILES.get('image')
            if uploaded_image and not str(uploaded_image.content_type).startswith('image/'):
                messages.error(request, 'Please upload a valid image file.')
                return redirect('fishing:add_fish')

            fish = Fish.objects.create(
                fisherman=request.user,
                name=request.POST.get('name'),
                fish_type=request.POST.get('fish_type'),
                description=request.POST.get('description', ''),
                image=uploaded_image,
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
        uploaded_image = request.FILES.get('image')
        remove_image = request.POST.get('remove_image') == 'on'
        if uploaded_image and not str(uploaded_image.content_type).startswith('image/'):
            messages.error(request, 'Please upload a valid image file.')
            return redirect('fishing:edit_fish', fish_id=fish.id)
        
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
        if remove_image and fish.image:
            fish.image.delete(save=False)
            fish.image = None
        if uploaded_image:
            fish.image = uploaded_image
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
        order__status__in=['PAID', 'FULLY_PAID', 'DELIVERY_IN_PROGRESS', 'PROCESSING', 'READY', 'READY_FOR_PICKUP']
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
        if new_status not in ['PENDING', 'READY', 'DELIVERED']:
            messages.error(request, 'Invalid status update.')
            return redirect('fishing:order_fulfillment')
        item.fulfillment_status = new_status
        item.save()
        
        # Update main order status if all items are ready
        order = item.order
        all_items = order.items.all()
        if all(item.fulfillment_status in ['READY', 'DELIVERED'] for item in all_items):
            order.status = 'READY_FOR_PICKUP' if order.fulfillment_method == 'pickup' else 'DELIVERY_IN_PROGRESS'
            order.save(update_fields=['status', 'updated_at'])
            
            # Create delivery record
            delivery_obj, _ = Delivery.objects.get_or_create(
                order=order,
                defaults={
                    'fisherman': request.user,
                    'status': 'READY_FOR_PICKUP' if order.fulfillment_method == 'pickup' else 'DELIVERY_IN_PROGRESS',
                    'updated_by': request.user,
                }
            )
            previous_status = delivery_obj.status
            delivery_obj.status = 'READY_FOR_PICKUP' if order.fulfillment_method == 'pickup' else 'DELIVERY_IN_PROGRESS'
            delivery_obj.updated_by = request.user
            delivery_obj.save(update_fields=['status', 'updated_by', 'updated_at'])
            DeliveryAuditLog.objects.create(
                delivery=delivery_obj,
                order=order,
                updated_by=request.user,
                previous_status=previous_status,
                new_status=delivery_obj.status,
                notes='Order prepared by fisherman',
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
    pending_orders = orders.filter(status__in=['PENDING', 'PAID', 'FULLY_PAID', 'DELIVERY_IN_PROGRESS', 'PROCESSING']).count()
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
        'audit_logs': delivery.audit_logs.all() if delivery else [],
    }
    return render(request, 'fishing/delivery_tracking.html', context)


@login_required
def confirm_delivery(request, order_number):
    """Customer confirms delivery received"""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if request.method == 'POST':
        order.status = 'DELIVERED'
        order.save(update_fields=['status', 'updated_at'])
        
        try:
            delivery = order.delivery
            previous_status = delivery.status
            delivery.status = 'DELIVERED'
            delivery.actual_delivery = timezone.now()
            delivery.updated_by = request.user
            delivery.save(update_fields=['status', 'actual_delivery', 'updated_by', 'updated_at'])
            DeliveryAuditLog.objects.create(
                delivery=delivery,
                order=order,
                updated_by=request.user,
                previous_status=previous_status,
                new_status='DELIVERED',
                notes='Customer confirmed delivery',
            )
        except Delivery.DoesNotExist:
            pass
        
        messages.success(request, 'Thank you! Delivery confirmed.')
        return redirect('fishing:order_detail', order_number=order_number)
    
    context = {'order': order}
    return render(request, 'fishing/confirm_delivery.html', context)


@login_required
def manage_pickup_points(request):
    """Create and manage startup pickup points."""
    if request.user.role not in ['fisherman', 'delivery', 'admin'] and not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('fishing:marketplace')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        general_location = request.POST.get('general_location', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        latitude = request.POST.get('latitude', '').strip()
        longitude = request.POST.get('longitude', '').strip()

        if not name or not general_location or not contact_person or not phone_number:
            messages.error(request, 'Please fill all required pickup point fields.')
            return redirect('fishing:manage_pickup_points')

        point = PickupPoint(
            name=name,
            general_location=general_location,
            contact_person=contact_person,
            phone_number=phone_number,
        )
        if latitude:
            try:
                point.latitude = Decimal(latitude)
            except Exception:
                messages.error(request, 'Invalid latitude value.')
                return redirect('fishing:manage_pickup_points')
        if longitude:
            try:
                point.longitude = Decimal(longitude)
            except Exception:
                messages.error(request, 'Invalid longitude value.')
                return redirect('fishing:manage_pickup_points')
        point.save()
        messages.success(request, f'Pickup point "{point.name}" added.')
        return redirect('fishing:manage_pickup_points')

    points = PickupPoint.objects.all().order_by('name')
    return render(request, 'fishing/manage_pickup_points.html', {'pickup_points': points})


@login_required
@require_http_methods(['POST'])
def request_chairman_approval(request):
    if request.user.role != 'fisherman':
        messages.error(request, 'Access denied.')
        return redirect('users:profile')

    try:
        profile = request.user.fisherman_profile
    except FishermanProfile.DoesNotExist:
        messages.error(request, 'Complete your fisherman profile first.')
        return redirect('users:edit_profile')

    if not request.user.phone_verified:
        messages.error(request, 'Complete KES 1 phone verification first.')
        return redirect('users:profile')

    notes = request.POST.get('notes', '').strip()
    approval_request, created = ChairmanApprovalRequest.objects.get_or_create(
        fisherman=request.user,
        defaults={'notes': notes, 'status': 'PENDING'}
    )
    if not created:
        approval_request.status = 'PENDING'
        approval_request.notes = notes
        approval_request.reviewed_at = None
        approval_request.reviewed_by = None
        approval_request.save(update_fields=['status', 'notes', 'reviewed_at', 'reviewed_by'])

    if profile.chairman_approved:
        profile.chairman_approved = False
        profile.chairman_name = ''
        profile.save(update_fields=['chairman_approved', 'chairman_name', 'updated_at'])

    messages.success(request, 'Chairman approval request submitted.')
    return redirect('fishing:fisherman_dashboard')


@login_required
def chairman_approval_queue(request):
    if request.user.role not in ['delivery', 'admin'] and not request.user.is_staff:
        messages.error(request, 'Access denied.')
        return redirect('fishing:marketplace')

    pending_requests = ChairmanApprovalRequest.objects.filter(status='PENDING').select_related(
        'fisherman', 'fisherman__fisherman_profile'
    )
    recent_requests = ChairmanApprovalRequest.objects.exclude(status='PENDING').select_related(
        'fisherman', 'reviewed_by'
    )[:30]
    return render(request, 'fishing/chairman_approval_queue.html', {
        'pending_requests': pending_requests,
        'recent_requests': recent_requests,
    })


@login_required
@require_http_methods(['POST'])
def review_chairman_approval(request, request_id):
    if request.user.role not in ['delivery', 'admin'] and not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    approval_request = get_object_or_404(
        ChairmanApprovalRequest.objects.select_related('fisherman', 'fisherman__fisherman_profile'),
        id=request_id
    )
    action = request.POST.get('action')
    notes = request.POST.get('notes', '').strip()
    if action not in ['approve', 'reject']:
        messages.error(request, 'Invalid action.')
        return redirect('fishing:chairman_approval_queue')

    profile = getattr(approval_request.fisherman, 'fisherman_profile', None)
    if not profile:
        messages.error(request, 'Fisherman profile not found.')
        return redirect('fishing:chairman_approval_queue')

    approval_request.status = 'APPROVED' if action == 'approve' else 'REJECTED'
    approval_request.notes = notes
    approval_request.reviewed_at = timezone.now()
    approval_request.reviewed_by = request.user
    approval_request.save(update_fields=['status', 'notes', 'reviewed_at', 'reviewed_by'])

    if action == 'approve':
        profile.chairman_approved = True
        profile.chairman_name = request.user.full_name or request.user.username
        messages.success(request, f'Approved {approval_request.fisherman.username}.')
    else:
        profile.chairman_approved = False
        profile.chairman_name = ''
        messages.success(request, f'Rejected {approval_request.fisherman.username}.')
    profile.save(update_fields=['chairman_approved', 'chairman_name', 'updated_at'])
    return redirect('fishing:chairman_approval_queue')


@login_required
@require_http_methods(['POST'])
def mark_notification_read(request, notification_id):
    if request.user.role != 'fisherman':
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    notification = get_object_or_404(SellerNotification, id=notification_id, fisherman=request.user)
    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return JsonResponse({'success': True})


@login_required
@require_http_methods(['GET'])
def api_seller_notifications(request):
    if request.user.role != 'fisherman':
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)
    notifications = SellerNotification.objects.filter(fisherman=request.user).order_by('-created_at')[:5]
    payload = [
        {
            'id': note.id,
            'order_number': note.order.order_number,
            'fish_item': note.fish_item,
            'weight_kg': str(note.weight_kg),
            'total_amount': str(note.total_amount),
            'net_earnings': str(note.net_earnings),
            'receipt_number': note.receipt_number,
            'buyer': note.buyer.username if note.buyer else 'Customer',
            'timestamp': note.created_at.isoformat(),
            'is_read': note.is_read,
        }
        for note in notifications
    ]
    unread_count = SellerNotification.objects.filter(fisherman=request.user, is_read=False).count()
    return JsonResponse({'success': True, 'unread_count': unread_count, 'notifications': payload})


@login_required
@require_http_methods(['GET'])
def pickup_points_api(request):
    """Return pickup points; optionally sorted by approximate distance if user location is provided."""
    latitude = request.GET.get('lat')
    longitude = request.GET.get('lng')
    points = PickupPoint.objects.all()
    payload = []
    for point in points:
        payload.append({
            'id': point.id,
            'name': point.name,
            'general_location': point.general_location,
            'contact_person': point.contact_person,
            'phone_number': point.phone_number,
            'latitude': float(point.latitude) if point.latitude is not None else None,
            'longitude': float(point.longitude) if point.longitude is not None else None,
        })
    # Optional location is accepted for clients that request user consent on device.
    if latitude and longitude:
        try:
            lat = float(latitude)
            lng = float(longitude)
            for point in payload:
                if point['latitude'] is not None and point['longitude'] is not None:
                    point['distance_hint'] = abs(lat - point['latitude']) + abs(lng - point['longitude'])
                else:
                    point['distance_hint'] = 999999
            payload = sorted(payload, key=lambda p: p['distance_hint'])
        except ValueError:
            pass
    return JsonResponse({'pickup_points': payload})


@login_required
@require_http_methods(['POST'])
def delivery_status_update(request, order_number):
    """Delivery/pickup role updates status from ready-for-pickup to delivered."""
    if request.user.role not in ['delivery', 'admin']:
        return JsonResponse({'success': False, 'error': 'Forbidden'}, status=403)

    order = get_object_or_404(Order, order_number=order_number)
    delivery = get_object_or_404(Delivery, order=order)
    new_status = request.POST.get('status')
    if new_status not in ['READY_FOR_PICKUP', 'DELIVERED']:
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

    previous_status = delivery.status
    delivery.status = new_status
    delivery.updated_by = request.user
    if new_status == 'DELIVERED':
        delivery.actual_delivery = timezone.now()
        order.status = 'DELIVERED'
    else:
        order.status = 'READY_FOR_PICKUP'
    delivery.save(update_fields=['status', 'updated_by', 'actual_delivery', 'updated_at'])
    order.save(update_fields=['status', 'updated_at'])

    DeliveryAuditLog.objects.create(
        delivery=delivery,
        order=order,
        updated_by=request.user,
        previous_status=previous_status,
        new_status=new_status,
        notes='Updated by delivery role',
    )
    return JsonResponse({'success': True, 'status': new_status})


# API Views
@login_required
@require_http_methods(['POST'])
def api_add_to_cart(request, fish_id):
    """API endpoint to add fish to cart"""
    fish = get_object_or_404(Fish, id=fish_id)
    
    try:
        weight = Decimal(str(request.POST.get('weight', '1')))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid weight'})
    
    if weight <= Decimal('0') or weight > fish.available_weight:
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
