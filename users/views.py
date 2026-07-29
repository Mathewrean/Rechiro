from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
import logging

from .models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile
from .forms import (
    UserRegistrationForm, UserLoginForm, ProfileUpdateForm, PasswordChangeForm,
    FishermanProfileForm, CustomerProfileForm, BeachChairmanProfileForm
)
from fishing.models import Fish, Order


def csrf_failure_view(request, reason=""):
    """Custom handler for CSRF failures to keep login flow usable."""
    messages.error(
        request,
        "Security token expired or was rejected. Please refresh the page and try logging in again."
    )
    return redirect('users:login')


def register_view(request):
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        return redirect('users:profile')
    
    form = None
    try:
        if request.method == 'POST':
            form = UserRegistrationForm(request.POST)
            if form.is_valid():
                try:
                    user = form.save()
                except Exception as e:
                    messages.error(request, f'Account creation failed: {str(e)}')
                    form = UserRegistrationForm()
                else:
                    username = form.cleaned_data.get('username')

                    messages.success(request, f'Account created successfully for {username}! You are now logged in.')

                    # Auto-login new users and redirect to the appropriate dashboard.
                    login(request, user)
                    role_redirect_map = {
                        'fisherman': 'fishing:fisherman_dashboard',
                        'customer': 'fishing:customer_dashboard',
                        'delivery': 'fishing:delivery_dashboard',
                        'chairman': 'fishing:chairman_approval_queue',
                    }
                    return redirect(role_redirect_map.get(user.role, 'fishing:home'))
            else:
                messages.error(request, 'Registration failed. Please check the form.')
        else:
            try:
                form = UserRegistrationForm()
            except Exception:
                form = UserRegistrationForm()
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception("Production failure in register_view:")
        messages.error(request, f'An error occurred: {str(e)}')
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Register - Rechiro'
    }
    return render(request, 'users/register.html', context)


def login_view(request):
    """Handle user login"""
    google_oauth_enabled = False
    try:
        from allauth.socialaccount.models import SocialApp
        google_oauth_enabled = SocialApp.objects.filter(provider='google').exists()
    except Exception:
        pass
    user = getattr(request, 'user', None)
    if user and user.is_authenticated:
        role_redirect_map = {
            'fisherman': 'fishing:fisherman_dashboard',
            'customer': 'fishing:customer_dashboard',
            'delivery': 'fishing:delivery_dashboard',
            'chairman': 'fishing:chairman_approval_queue',
        }
        return redirect(role_redirect_map.get(user.role, 'fishing:home'))
    
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        try:
            form = UserLoginForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                if user is not None:
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.full_name or user.username}!')
                # Redirect to appropriate dashboard based on role
                if not next_url:
                    role_redirect_map = {
                        'fisherman': 'fishing:fisherman_dashboard',
                        'customer': 'fishing:customer_dashboard',
                        'delivery': 'fishing:delivery_dashboard',
                        'chairman': 'fishing:chairman_approval_queue',
                    }
                    next_url = role_redirect_map.get(getattr(user, 'role', ''), 'fishing:home')
                return redirect(next_url)
            else:
                messages.error(request, 'Login failed. Please double-check your username and password.')
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.exception("Production failure in login_view:")
            messages.error(request, 'An error occurred during login. Please try again.')
        form = UserLoginForm()
    else:
        form = UserLoginForm()
    
    context = {
        'form': form,
        'title': 'Login - Rechiro',
        'google_oauth_enabled': google_oauth_enabled,
        'next': next_url,
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
    user = request.user

    if user.role == 'fisherman':
        profile = user.get_fisherman_profile()
        fish_listings = Fish.objects.filter(fisherman=user)
        recent_catches = list(fish_listings.order_by('-created_at')[:5])
        total_catches = fish_listings.count()
        from fishing.models import OrderItem
        total_sales = sum(
            item.total_price for item in OrderItem.objects.filter(
                fish__fisherman=user,
                order__status__in=['PAID', 'DELIVERED']
            )
        )
        context = {
            'user': user,
            'profile': profile,
            'fish_listings': fish_listings[:5],
            'total_listings': fish_listings.count(),
            'total_sales': total_sales,
            'total_catches': total_catches,
            'recent_catches': recent_catches,
            'title': f'{user.full_name or user.username} - Profile'
        }
    else:
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
    chairman_form = None

    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if user.role == 'fisherman':
            fisherman_profile, _ = FishermanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'landing_site': user.location or '',
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
        elif user.role == 'chairman':
            chairman_profile, _ = BeachChairmanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'beach_name': user.location or '',
                    'phone': user.phone or '',
                    'notes': '',
                }
            )
            chairman_form = BeachChairmanProfileForm(
                request.POST,
                instance=chairman_profile,
                prefix='chair',
            )
            profiles_valid = chairman_form.is_valid()
        else:
            profiles_valid = True

        if form.is_valid() and profiles_valid:
            form.save()
            if fisherman_form:
                fisherman_form.save()
            if customer_form:
                customer_form.save()
            if chairman_form:
                chairman_form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('users:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
        if user.role == 'fisherman':
            fisherman_profile, _ = FishermanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': user.phone or '',
                    'landing_site': user.location or '',
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
        elif user.role == 'chairman':
            chairman_profile, _ = BeachChairmanProfile.objects.get_or_create(
                user=user,
                defaults={
                    'beach_name': user.location or '',
                    'phone': user.phone or '',
                    'notes': '',
                }
            )
            chairman_form = BeachChairmanProfileForm(instance=chairman_profile, prefix='chair')
    
    context = {
        'form': form,
        'fisherman_form': fisherman_form,
        'customer_form': customer_form,
        'chairman_form': chairman_form,
        'title': 'Edit Profile - Rechiro'
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
        'title': 'Change Password - Rechiro'
    }
    return render(request, 'users/change_password.html', context)


@login_required
def dashboard_view(request):
    """Dashboard view redirecting to role-specific dashboards"""
    user = request.user

    if request.session.get('needs_role_selection') or not user.role:
        return redirect('/choose-role/')

    if user.role == 'fisherman':
        return redirect('fishing:fisherman_dashboard')
    elif user.role == 'customer':
        return redirect('fishing:customer_dashboard')
    elif user.role == 'delivery':
        return redirect('fishing:delivery_dashboard')
    elif user.role == 'chairman':
        return redirect('fishing:chairman_approval_queue')
    else:
        # Admin or other roles
        return redirect('users:profile')


@login_required
def choose_role_view(request):
    if request.user.role and not request.session.get('needs_role_selection'):
        messages.info(request, 'Role is already set. Contact admin to change account role.')
        return redirect('users:dashboard')

    if request.method == 'POST':
        selected_role = request.POST.get('role', '').strip()
        allowed_roles = {'fisherman', 'customer', 'delivery'}
        if selected_role not in allowed_roles:
            messages.error(request, 'Invalid role selection.')
            return redirect('users:choose_role')

        user = request.user
        user.role = selected_role
        user.save(update_fields=['role'])
        _ensure_role_profile(user)
        needs_role_selection = request.session.get('needs_role_selection')
        request.session['needs_role_selection'] = False

        messages.success(request, f'Role selected: {user.get_role_display()}')
        return redirect('users:dashboard')

    return render(request, 'users/choose_role.html', {'title': 'Choose Role - Rechiro'})


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
            from fishing.models import OrderItem
            fish_listings = Fish.objects.filter(fisherman=user)
            stats = {
                'total_listings': fish_listings.count(),
                'available_listings': fish_listings.filter(status='available').count(),
                'total_sales': sum(item.total_price for item in OrderItem.objects.filter(
                    fish__fisherman=user,
                    order__status__in=['PAID', 'DELIVERED']
                )),
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
        context['title'] = 'Edit Profile - Rechiro'
        return context
