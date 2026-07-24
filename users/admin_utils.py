"""Context processors for the Rechiro application"""


def cart_context(request):
    """Add cart information to all templates"""
    cart_count = 0
    cart_total = 0
    
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        try:
            from fishing.models import Cart
            cart = Cart.objects.get(user=user)
            cart_count = cart.get_total_items()
            cart_total = cart.get_total_price()
        except Exception:
            cart_count = 0
            cart_total = 0
    
    return {
        'cart_count': cart_count,
        'cart_total': cart_total,
    }


def admin_statistics_context(request):
    """Add admin statistics to templates"""
    result = {}
    user = getattr(request, 'user', None)
    try:
        if user and user.is_authenticated and user.is_staff:
            from users.models import User
            from fishing.models import Fish, Order
            
            result['admin_stats'] = {
                'total_users': User.objects.count(),
                'total_fishermen': User.objects.filter(role='fisherman').count(),
                'total_customers': User.objects.filter(role='customer').count(),
                'total_fish_listings': Fish.objects.count(),
                'total_orders': Order.objects.count(),
            }
    except Exception:
        pass
    return result
