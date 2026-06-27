# Security Configuration

## Admin Access

Admin endpoint: `/admin/`

### Superuser Credentials (Production)

Add to Railway environment variables to auto-create admin user on first deploy:
```
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@rechiro.com
ADMIN_PASSWORD=your-secure-password-here
```

The migration `0008_create_admin_user.py` creates the superuser automatically when migrations run.

### Manual Admin Creation

If auto-creation fails, create superuser via Railway console:
```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.create_superuser('admin', 'admin@rechiro.com', 'your-password')
"
```

### Admin Security Hardening

The following security settings can be enabled in `.env` for production:

```env
# Enable HTTPS enforcement (required for production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Optional: HSTS for HTTPS-only sites
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### Allowed Hosts

Ensure your `.env` includes all valid hosts:
```env
ALLOWED_HOSTS=localhost,127.0.0.1,rechiro-production.up.railway.app,your-ngrok-url.ngrok-free.dev
```

## Production Checklist

- [ ] Set strong `SECRET_KEY` (50+ random characters)
- [ ] Set `DEBUG=False`
- [ ] Configure valid `ALLOWED_HOSTS`
- [ ] Enable `SECURE_SSL_REDIRECT=True` for HTTPS
- [ ] Enable `SESSION_COOKIE_SECURE=True`
- [ ] Enable `CSRF_COOKIE_SECURE=True`
- [ ] Configure production email backend (SendGrid/Mailgun recommended)
- [ ] Review `CSRF_TRUSTED_ORIGINS` for deployment domains

## Known Issues

### SMTP on Railway
Railway free tier may block port 587. Consider:
- Using SendGrid or Mailgun
- Setting `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` for dev
- Using `fail_silently=True` in email sending code to prevent crashes
