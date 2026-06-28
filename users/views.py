from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.conf import settings
import logging
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView, DetailView, ListView
from decimal import Decimal
import importlib.util

from .models import User, FishermanProfile, CustomerProfile, BeachChairmanProfile, PhoneVerificationTransaction
from .forms import (
    UserRegistrationForm, UserLoginForm, ProfileUpdateForm, PasswordChangeForm,
    FishermanProfileForm, CustomerProfileForm, BeachChairmanProfileForm
)
from fishing.models import Fish, Order


def _ensure_role_profile(user):
    if user.role == 'fisherman':
        FishermanProfile.objects.get_or_create(
            user=user,
            defaults={
                'phone': user.phone or '',
                'landing_site': user.location or '',
                'location': user.location or '',
                'contact_details': '',
            }
        )
    elif user.role == 'customer':
        CustomerProfile.objects.get_or_create(
            user=user,
            defaults={
                'phone': user.phone or '',
                'delivery_location': user.location or '',
                'delivery_address': '',
                'preferred_fulfillment': 'delivery',
            }
        )


def _build_email_verification_link(request, user):
    signer = TimestampSigner()
    token = signer.sign(user.pk)
    return request.build_absolute_uri(
        reverse_lazy('users:verify_email', kwargs={'token': token})
    )


def _send_email_verification_link(request, user):
    verify_link = _build_email_verification_link(request, user)
    try:
        send_mail(
            subject='Verify your Rechiro account email',
            message=f'Hello {user.full_name or user.username}, verify your email: {verify_link}',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@rechiro.com'),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send verification email to {user.email}: {e}")
    return verify_link


def _get_content_models():
    if "content" not in settings.INSTALLED_APPS:
        return None
    if importlib.util.find_spec("content") is None:
        return None
    try:
        from content.models import TimelinePost, EducationalContent
    except Exception:
        return None
    return TimelinePost, EducationalContent


def _initiate_phone_verification_stk(user):
    from fishing.mpesa_service import initiate_stk_push
    verification_ref = f"PHONE-VERIFY-{user.id}"
    stk_result = initiate_stk_push(
        phone_number=user.phone,
        amount=1,
        order_number=verification_ref,
        transaction_type='CustomerPayBillOnline',
    )
    if stk_result.get('success'):
        PhoneVerificationTransaction.objects.create(
            user=user,
            phone_number=user.phone,
            amount=Decimal('1.00'),
            merchant_request_id=stk_result.get('merchant_request_id', ''),
            checkout_request_id=stk_result.get('checkout_request_id', ''),
            status='PENDING',
        )
    return stk_result


def csrf_failure_view(request, reason=""):
    """Custom handler for CSRF failures to keep login flow usable."""
    messages.error(
        request,
        "Security token expired or was rejected. Please refresh the page and try logging in again."
    )
    return redirect('users:login')


def register_view(request):
    """Handle user registration"""
    if request.user.is_authenticated:
        return redirect('users:profile')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')

            # Lightweight email verification for all users.
            try:
                verify_link = _send_email_verification_link(request, user)
                if settings.DEBUG:
                    messages.info(request, f'Email verification link (dev): {verify_link}')
            except Exception:
                pass

            # Seller phone ownership verification: KES 1 STK push.
            if user.role == 'fisherman':
                stk_result = _initiate_phone_verification_stk(user)
                if stk_result.get('success'):
                    messages.info(
                        request,
                        'Account created. Complete the KES 1 phone verification STK push to activate seller listing access.'
                    )
                else:
                    messages.warning(
                        request,
                        f'Account created, but phone verification STK failed: {stk_result.get("error", "Unknown error")}'
                    )
            else:
                messages.info(request, 'Account created. Please verify your email before checkout.')

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
        form = UserRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Register - Rechiro'
    }
    return render(request, 'users/register.html', context)


def login_view(request):
    """Handle user login"""
    def _ensure_google_social_app():
        if not getattr(settings, 'ALLAUTH_INSTALLED', False):
            return False
        client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
        client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
        if not client_id or not client_secret:
            return False
        try:
            from allauth.socialaccount.models import SocialApp
            from django.contrib.sites.models import Site
        except Exception:
            return False
        app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': client_id,
                'secret': client_secret,
            }
        )
        updated_fields = []
        if app.client_id != client_id:
            app.client_id = client_id
            updated_fields.append('client_id')
        if app.secret != client_secret:
            app.secret = client_secret
            updated_fields.append('secret')
        if updated_fields:
            app.save(update_fields=updated_fields)
        try:
            site = Site.objects.get_current()
            if not app.sites.filter(id=site.id).exists():
                app.sites.add(site)
        except Exception:
            return True
        return True

    google_oauth_enabled = False
    if getattr(settings, 'ALLAUTH_INSTALLED', False):
        if _ensure_google_social_app():
            google_oauth_enabled = True
        else:
            try:
                from allauth.socialaccount.models import SocialApp
                google_oauth_enabled = SocialApp.objects.filter(provider='google').exists()
            except Exception:
                google_oauth_enabled = False

    if request.user.is_authenticated:
        role_redirect_map = {
            'fisherman': 'fishing:fisherman_dashboard',
            'customer': 'fishing:customer_dashboard',
            'delivery': 'fishing:delivery_dashboard',
            'chairman': 'fishing:chairman_approval_queue',
        }
        return redirect(role_redirect_map.get(request.user.role, 'fishing:home'))
    
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                login(request, user)
                if not user.email_verified:
                    messages.warning(request, 'Please verify your email to unlock full purchase features.')
                messages.success(request, f'Welcome back, {user.full_name or user.username}!')
            # Redirect to appropriate dashboard based on role
            if not next_url:
                role_redirect_map = {
                    'fisherman': 'fishing:fisherman_dashboard',
                    'customer': 'fishing:customer_dashboard',
                    'delivery': 'fishing:delivery_dashboard',
                    'chairman': 'fishing:chairman_approval_queue',
                }
                next_url = role_redirect_map.get(user.role, 'fishing:home')
            return redirect(next_url)
        else:
            messages.error(request, 'Login failed. Please double-check your username and password.')
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
    """Display user profile"""
    user = request.user
    content_models = _get_content_models()
    total_posts = None
    total_educational = None
    recent_posts = None
    educational_content = None
    if content_models:
        TimelinePost, EducationalContent = content_models
        total_posts = TimelinePost.objects.filter(author=user).count()
        total_educational = EducationalContent.objects.filter(author=user).count()
        recent_posts = TimelinePost.objects.filter(author=user).order_by('-created_at')[:5]
        educational_content = EducationalContent.objects.filter(author=user).order_by('-created_at')[:5]
    
    email_verify_link = ''
    if not user.email_verified and settings.DEBUG and user.email:
        email_verify_link = _build_email_verification_link(request, user)

    if user.role == 'fisherman':
        # Get fisherman stats
        profile = user.get_fisherman_profile()
        fish_listings = Fish.objects.filter(fisherman=user)
        recent_catches = fish_listings.order_by('-created_at')[:5]
        total_catches = fish_listings.count()
        total_sales = sum(item.total_price for item in user.sold_items.all() if item.order.status in ['PAID', 'DELIVERED'])
        context = {
            'user': user,
            'profile': profile,
            'fish_listings': fish_listings[:5],
            'total_listings': fish_listings.count(),
            'total_sales': total_sales,
            'total_catches': total_catches,
            'recent_catches': recent_catches,
            'total_posts': total_posts,
            'recent_posts': recent_posts,
            'total_educational': total_educational,
            'educational_content': educational_content,
            'email_verify_link': email_verify_link,
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
            'total_catches': None,
            'recent_catches': None,
            'total_posts': total_posts,
            'recent_posts': recent_posts,
            'total_educational': total_educational,
            'educational_content': educational_content,
            'email_verify_link': email_verify_link,
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

        if needs_role_selection:
            if user.email and not user.email_verified:
                try:
                    verify_link = _send_email_verification_link(request, user)
                    if settings.DEBUG:
                        messages.info(request, f'Email verification link (dev): {verify_link}')
                    messages.success(request, 'Verification email sent. Check your inbox.')
                except Exception:
                    messages.error(request, 'Failed to send verification email. Try again.')

            if selected_role == 'fisherman':
                if user.phone:
                    stk_result = _initiate_phone_verification_stk(user)
                    if stk_result.get('success'):
                        messages.info(
                            request,
                            'Complete the KES 1 phone verification STK push to activate seller listing access.'
                        )
                    else:
                        messages.warning(
                            request,
                            f"Phone verification STK failed: {stk_result.get('error', 'Unknown error')}"
                        )
                else:
                    messages.warning(
                        request,
                        'Add a phone number in your profile to complete fisherman phone verification.'
                    )
        messages.success(request, f'Role selected: {user.get_role_display()}')
        return redirect('users:dashboard')

    return render(request, 'users/choose_role.html', {'title': 'Choose Role - Rechiro'})


def verify_email_view(request, token):
    """Verify user email via signed token."""
    signer = TimestampSigner()
    try:
        user_id = signer.unsign(token, max_age=60 * 60 * 24 * 7)  # 7 days
        user = User.objects.get(pk=user_id)
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        messages.success(request, 'Email verified successfully. You can now purchase with confidence.')
        # Refresh session user if currently logged in
        if request.user.is_authenticated and request.user.pk == user.pk:
            request.user.refresh_from_db()
    except (BadSignature, SignatureExpired, User.DoesNotExist):
        messages.error(request, 'Invalid or expired verification link.')
    if request.user.is_authenticated:
        return redirect('users:email_verification')
    return redirect('users:login')


@login_required
@require_http_methods(['POST'])
def resend_email_verification_view(request):
    user = request.user
    if user.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('users:email_verification')
    if not user.email:
        messages.error(request, 'Add an email address in your profile first.')
        return redirect('users:edit_profile')
    try:
        verify_link = _send_email_verification_link(request, user)
        if settings.DEBUG:
            messages.info(request, f'Email verification link (dev): {verify_link}')
        else:
            messages.success(request, 'Verification email sent. Check your inbox.')
    except Exception:
        if settings.DEBUG:
            verify_link = _build_email_verification_link(request, user)
            messages.info(request, f'Email verification link (dev): {verify_link}')
        else:
            messages.warning(request, 'Email could not be sent. Contact support.')
    return redirect('users:email_verification')


@login_required
def email_verification_view(request):
    verify_link = ''
    if not request.user.email_verified and settings.DEBUG and request.user.email:
        verify_link = _build_email_verification_link(request, request.user)
    return render(
        request,
        'users/email_verification.html',
        {
            'email_verify_link': verify_link,
            'title': 'Email Verification - Rechiro',
        }
    )


@login_required
def phone_verification_view(request):
    latest_txn = PhoneVerificationTransaction.objects.filter(user=request.user).order_by('-created_at').first()
    return render(
        request,
        'users/phone_verification.html',
        {
            'latest_txn': latest_txn,
            'title': 'Phone Verification - Rechiro',
        }
    )


@login_required
@require_http_methods(['POST'])
def resend_phone_verification_view(request):
    user = request.user
    if user.role not in ['fisherman', 'customer']:
        messages.error(request, 'Phone verification is only required for fishermen and customers.')
        return redirect('users:profile')
    if user.phone_verified:
        messages.info(request, 'Your phone is already verified.')
        return redirect('users:phone_verification')
    if not user.phone:
        messages.error(request, 'Add a phone number in your profile first.')
        return redirect('users:edit_profile')
    stk_result = _initiate_phone_verification_stk(user)
    if stk_result.get('success'):
        messages.success(request, 'KES 1 verification STK push sent. Complete it on your phone.')
    else:
        messages.error(request, f'Failed to send verification STK push: {stk_result.get("error", "Unknown error")}')
    return redirect('users:phone_verification')


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
        context['title'] = 'Edit Profile - Rechiro'
        return context
