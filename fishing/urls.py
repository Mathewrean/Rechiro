from django.urls import path
from . import views

app_name = 'fishing'

urlpatterns = [
    # Marketplace
    path('', views.fish_marketplace, name='marketplace'),
    path('fish/<int:fish_id>/', views.fish_detail, name='fish_detail'),
    
    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:fish_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout
    path('checkout/', views.checkout_initiate, name='checkout_initiate'),
    path('checkout/process/', views.checkout_process, name='checkout_process'),
    
    # Orders
    path('orders/', views.order_list, name='order_list'),
    path('orders/<str:order_number>/', views.order_detail, name='order_detail'),
    
    # M-Pesa Callback
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    
    # Fisherman Dashboard
    path('fisherman/dashboard/', views.fisherman_dashboard, name='fisherman_dashboard'),
    path('fisherman/my-fish/', views.my_fish_listing, name='my_fish_listing'),
    path('fisherman/add-fish/', views.add_fish, name='add_fish'),
    path('fisherman/edit-fish/<int:fish_id>/', views.edit_fish, name='edit_fish'),
    path('fisherman/delete-fish/<int:fish_id>/', views.delete_fish, name='delete_fish'),
    path('fisherman/orders/', views.order_fulfillment, name='order_fulfillment'),
    path('fisherman/orders/<str:order_number>/<int:item_id>/update/', views.update_order_status, name='update_order_status'),
    path('fisherman/notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('fisherman/notifications/api/', views.api_seller_notifications, name='api_seller_notifications'),
    
    # Customer Dashboard
    path('customer/dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/orders/<str:order_number>/tracking/', views.delivery_tracking, name='delivery_tracking'),
    path('customer/orders/<str:order_number>/confirm/', views.confirm_delivery, name='confirm_delivery'),
    path('pickup-points/manage/', views.manage_pickup_points, name='manage_pickup_points'),
    path('customer/pickup-points/', views.pickup_points_api, name='pickup_points_api'),
    path('delivery/orders/<str:order_number>/status/', views.delivery_status_update, name='delivery_status_update'),
    
    # API
    path('api/cart/add/<int:fish_id>/', views.api_add_to_cart, name='api_add_to_cart'),
    path('api/cart/count/', views.api_cart_count, name='api_cart_count'),
    
    # Home
    path('home/', views.marketplace_home, name='home'),
]
