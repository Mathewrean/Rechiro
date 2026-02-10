"""Context processors for the FishNet application"""

from fishing.models import Cart


def cart_context(request):
    """Add cart information to all templates"""
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_count = cart.get_total_items()
            cart_total = cart.get_total_price()
        except Cart.DoesNotExist:
            cart_count = 0
            cart_total = 0
    else:
        cart_count = 0
        cart_total = 0
    
    return {
        'cart_count': cart_count,
        'cart_total': cart_total,
    }


def admin_statistics_context(request):
    """Add admin statistics to templates"""
    if request.user.is_authenticated and request.user.is_staff:
        from users.models import User
        from fishing.models import Fish, Order
        
        return {
            'admin_stats': {
                'total_users': User.objects.count(),
                'total_fishermen': User.objects.filter(role='fisherman').count(),
                'total_customers': User.objects.filter(role='customer').count(),
                'total_fish_listings': Fish.objects.count(),
                'total_orders': Order.objects.count(),
            }
        }
    return {}

