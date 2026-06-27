from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import random
from decimal import Decimal

from users.models import User
from fishing.models import Catch


def setup_google_oauth():
    """Configure Google OAuth in the database."""
    from django.conf import settings
    if not getattr(settings, 'ALLAUTH_INSTALLED', False):
        return
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        return
    from allauth.socialaccount.models import SocialApp
    from django.contrib.sites.models import Site
    app, _ = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google',
            'client_id': client_id,
            'secret': client_secret,
        }
    )
    try:
        site = Site.objects.get_current()
        if not app.sites.filter(id=site.id).exists():
            app.sites.add(site)
    except Site.DoesNotExist:
        pass


def _get_content_models():
    """Get content models if the content app is installed."""
    if "content" not in settings.INSTALLED_APPS:
        return None
    try:
        from content.models import TimelinePost, EducationalContent, PostLike
        return TimelinePost, EducationalContent, PostLike
    except Exception:
        return None


class Command(BaseCommand):
    help = 'Setup sample data for the Sustainable Fishing platform'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=20,
            help='Number of users to create',
        )
        parser.add_argument(
            '--catches',
            type=int,
            default=50,
            help='Number of catch records to create',
        )
        parser.add_argument(
            '--posts',
            type=int,
            default=30,
            help='Number of timeline posts to create',
        )
        parser.add_argument(
            '--educational',
            type=int,
            default=15,
            help='Number of educational content items to create',
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            # Setup Google OAuth
            setup_google_oauth()
            
            # Create superuser if it doesn't exist
            if not User.objects.filter(username='admin').exists():
                admin_user = User.objects.create_superuser(
                    username='admin',
                    email='admin@sustainablefishing.com',
                    password='admin123',
                    full_name='System Administrator',
                    role='admin'
                )
                self.stdout.write(self.style.SUCCESS(f'Created superuser: admin'))
            else:
                admin_user = User.objects.get(username='admin')

            # Create sample users
            self.create_users(options['users'])
            
            # Create sample catches
            self.create_catches(options['catches'])
            
            self.stdout.write(self.style.SUCCESS('Sample data created successfully!'))

    def create_users(self, count):
        """Create sample users"""
        fishermen_names = [
            'John Fisher', 'Maria Santos', 'David Ocean', 'Lisa Wave',
            'Carlos Tide', 'Anna Deep', 'Miguel Shore', 'Sofia Blue',
            'Pedro Coast', 'Elena Marina', 'Roberto Bay', 'Carmen Sea',
            'Juan Reef', 'Isabella Current', 'Diego Anchor'
        ]
        
        customer_names = [
            'Alex Customer', 'Jordan Buyer', 'Taylor Shopper', 'Morgan User',
            'Casey Purchaser', 'Riley Client', 'Avery Buyer', 'Quinn Consumer'
        ]
        
        locations = [
            'Atlantic Coast', 'Pacific Shore', 'Gulf of Mexico', 'Caribbean Sea',
            'Mediterranean', 'Baltic Sea', 'Indian Ocean', 'Arctic Waters',
            'Coral Reef Area', 'Deep Sea Region'
        ]
        
        # Create fishermen
        for i in range(min(len(fishermen_names), count // 2)):
            name = fishermen_names[i]
            username = name.lower().replace(' ', '_')
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@example.com',
                    password='password123',
                    full_name=name,
                    role='fisherman',
                    location=random.choice(locations),
                )
                self.stdout.write(f'Created fisherman: {name}')
        
        # Create customers
        for i in range(min(len(customer_names), count // 2)):
            name = customer_names[i]
            username = name.lower().replace(' ', '_')
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f'{username}@example.com',
                    password='password123',
                    full_name=name,
                    role='customer',
                    location=random.choice(locations),
                )
                self.stdout.write(f'Created customer: {name}')

    def create_catches(self, count):
        """Create sample catch records"""
        fish_types = [
            'Tuna', 'Salmon', 'Cod', 'Mackerel', 'Sardine', 'Anchovy',
            'Bass', 'Snapper', 'Grouper', 'Mahi-mahi', 'Halibut', 'Flounder',
            'Shrimp', 'Lobster', 'Crab', 'Squid'
        ]
        
        locations = [
            'Deep Sea Area A', 'Coastal Zone B', 'Reef Region C', 'Open Ocean D',
            'Fishing Ground E', 'Marine Protected Area F', 'Traditional Spot G'
        ]
        
        statuses = ['sold', 'unsold', 'donated']
        
        fishermen = User.objects.filter(role='fisherman')
        
        for i in range(count):
            catch = Catch.objects.create(
                fisher=random.choice(fishermen),
                fish_type=random.choice(fish_types),
                weight=Decimal(str(random.uniform(0.5, 50.0))),
                location=random.choice(locations),
                catch_date=timezone.now().date() - timedelta(days=random.randint(1, 90)),
                status=random.choice(statuses),
                price=Decimal(str(random.uniform(10.0, 500.0))) if random.choice([True, False]) else None,
                notes=f'Good quality {random.choice(fish_types).lower()} caught in {random.choice(locations)}',
                created_at=timezone.now() - timedelta(days=random.randint(1, 90))
            )
            
self.stdout.write(f'Created {count} catch records')


if __name__ == '__main__':
    pass
