from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView, DetailView, ListView

from .models import User, FishermanProfile, CustomerProfile
from .forms import UserRegistrationForm, UserLoginForm, ProfileUpdateForm, PasswordChangeForm, FishermanProfileForm, CustomerProfileForm
from fishing.models import Fish, Order


def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('users:profile')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created successfully for {username}! Please log in to continue.')
            return redirect('users:login')
    else:
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Register - FishNet'
    }
    return render(request, 'users/register.html', context)


def login_view(request):
    """Handle user login"""
    if request.user.is_authenticated:
        return redirect('users:profile')
    
    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.full_name or user.username}!')
                next_url = request.GET.get('next')
                # Redirect to appropriate dashboard based on role
                if not next_url:
                    if user.role == 'fisherman':
                        next_url = 'fishing:fisherman_dashboard'
                    else:
                        next_url = 'fishing:customer_dashboard'
                return redirect(next_url)
    else:
        form = UserLoginForm()
    
    context = {
        'form': form,
        'title': 'Login - FishNet'
    }
    return render(request, 'users/login.html', context)


@login_required
def logout_view(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')


@login_required
def profile_view(request):
    """Display user profile"""
    user = request.user
    
    if user.role == 'fisherman':
        # Get fisherman stats
        profile = user.get_fisherman_profile()
        fish_listings = Fish.objects.filter(fisherman=user)
        total_sales = sum(item.total_price for item in user.sold_items.all() if item.order.status in ['PAID', 'DELIVERED'])
        context = {
            'user': user,
            'profile': profile,
            'fish_listings': fish_listings[:5],
            'total_listings': fish_listings.count(),
            'total_sales': total_sales,
            'title': f'{user.full_name or user.username} - Profile'
        }
    else:
        # Get customer stats
        profile = user.get_customer_profile()
        orders = Order.objects.filter(customer=user)
        total_orders = orders.count()
        completed_orders = orders.filter(status='DELIVERED').count()
        context = {
            'user': user,
            'profile': profile,
            'orders': orders[:5],
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'title': f'{user.full_name or user.username} - Profile'
        }
    
    return render(request, 'users/profile.html', context)


@login_required
def edit_profile_view(request):
    """Handle profile editing"""
    user = request.user
    fisherman_form = None
    customer_form = None

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if user.role == 'fisherman':
            fisherman_profile, _ = FishermanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'location': user.location or '',
                    'contact_details': '',
                }
            )
            fisherman_form = FishermanProfileForm(
                request.POST,
                instance=fisherman_profile,
                prefix='fisher',
            )
            profiles_valid = fisherman_form.is_valid()
        elif user.role == 'customer':
            customer_profile, _ = CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'delivery_location': user.location or '',
                    'delivery_address': '',
                    'preferred_fulfillment': 'delivery',
                }
            )
            customer_form = CustomerProfileForm(
                request.POST,
                instance=customer_profile,
                prefix='customer',
            )
            profiles_valid = customer_form.is_valid()
        else:
            profiles_valid = True

        if form.is_valid() and profiles_valid:
            form.save()
            if fisherman_form:
                fisherman_form.save()
            if customer_form:
                customer_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('users:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
        if user.role == 'fisherman':
            fisherman_profile, _ = FishermanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'location': user.location or '',
                    'contact_details': '',
                }
            )
            fisherman_form = FishermanProfileForm(instance=fisherman_profile, prefix='fisher')
        elif user.role == 'customer':
            customer_profile, _ = CustomerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'delivery_location': user.location or '',
                    'delivery_address': '',
                    'preferred_fulfillment': 'delivery',
                }
            )
            customer_form = CustomerProfileForm(instance=customer_profile, prefix='customer')
    
    context = {
        'form': form,
        'fisherman_form': fisherman_form,
        'customer_form': customer_form,
        'title': 'Edit Profile - FishNet'
    }
    return render(request, 'users/edit_profile.html', context)


@login_required
def change_password_view(request):
    """Handle password change"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('users:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    context = {
        'form': form,
        'title': 'Change Password - FishNet'
    }
    return render(request, 'users/change_password.html', context)


@login_required
def dashboard_view(request):
    """Dashboard view redirecting to role-specific dashboards"""
    user = request.user
    
    if user.role == 'fisherman':
        return redirect('fishing:fisherman_dashboard')
    elif user.role == 'customer':
        return redirect('fishing:customer_dashboard')
    else:
        # Admin or other roles
        return redirect('users:profile')


@login_required
@require_http_methods(['POST'])
def delete_account_view(request):
    """Handle account deletion"""
    user = request.user
    
    # Log out the user
    logout(request)
    
    # Delete the user account
    user.delete()
    
    messages.success(request, 'Your account has been deleted successfully.')
    return redirect('users:login')


# API-style views for AJAX requests
@login_required
@csrf_exempt
def api_user_stats(request):
    """API endpoint for user statistics"""
    if request.method == 'GET':
        user = request.user
        if user.role == 'fisherman':
            fish_listings = Fish.objects.filter(fisherman=user)
            stats = {
                'total_listings': fish_listings.count(),
                'available_listings': fish_listings.filter(status='available').count(),
                'total_sales': sum(item.total_price for item in user.sold_items.all()),
                'member_since': user.created_at.strftime('%B %Y'),
                'role': user.get_role_display(),
                'location': user.location,
            }
        else:
            orders = Order.objects.filter(customer=user)
            stats = {
                'total_orders': orders.count(),
                'pending_orders': orders.filter(status__in=['PENDING', 'PAID']).count(),
                'completed_orders': orders.filter(status='DELIVERED').count(),
                'member_since': user.created_at.strftime('%B %Y'),
                'role': user.get_role_display(),
                'location': user.location,
            }
        return JsonResponse(stats)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Class-based view for updating user profile"""
    model = User
    form_class = ProfileUpdateForm
    template_name = 'users/edit_profile.html'
    success_url = reverse_lazy('users:profile')
    
    def get_object(self):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, 'Your profile has been updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Profile - FishNet'
        return context
