#!/usr/bin/env python
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sustainable_fishing.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
admin_password = 'RechiroAdmin2024!'
if User.objects.filter(username='admin').exists():
    admin = User.objects.get(username='admin')
    admin.set_password(admin_password)
    admin.is_staff = True
    admin.is_superuser = True
    admin.email = 'admin@rechiro.com'
    admin.save()
    print(f'Admin password updated to: {admin_password}')
else:
    User.objects.create_superuser(username='admin', email='admin@rechiro.com', password=admin_password)
    print(f'Superuser created: admin/{admin_password}')
