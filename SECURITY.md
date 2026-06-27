# Security Configuration

## Admin Access

Admin endpoint: `/admin/`

### Superuser Credentials
- Primary admin: `admin` / `admin123`
- Additional staff accounts: `mathewrean`, `adminmathew`

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

# Custom admin URL (optional, reduces automated attacks)
ADMIN_URL=admin/
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