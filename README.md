# FishNet (Sustainable Fishing)

FishNet is a Django e-commerce platform for direct fish sales from verified fishermen to customers.

It includes:
- Weight-based fish listings (`price_per_kg * weight_kg`)
- M-Pesa Daraja STK checkout with callback validation
- Automatic platform fee accounting (2%) and fisherman net payout (98%)
- Customer order history and fisherman sales dashboard
- Pickup-point and delivery workflow with audit logs
- Email/password authentication plus Google OAuth (via `django-allauth` when installed)

## Tech Stack
- Python / Django
- SQLite (default dev DB)
- M-Pesa Daraja API
- Tailwind (CDN in templates)

## Project Structure
- `sustainable_fishing/` Django settings and root URLs
- `users/` custom user model, auth, profile management
- `fishing/` marketplace, cart, checkout, payment, delivery, dashboards
- `templates/` HTML templates

## Quick Start
1. Clone and enter project:
```bash
git clone https://github.com/Mathewrean/Sustainable_Fishing.git
cd Sustainable_Fishing
```

2. Create and activate virtual env:
```bash
python -m venv fishnet_env
source fishnet_env/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` (example):
```env
DEBUG=True
SECRET_KEY=change-me
ALLOWED_HOSTS=127.0.0.1,localhost

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Daraja
MPESA_CONSUMER_KEY=your-consumer-key
MPESA_CONSUMER_SECRET=your-consumer-secret
MPESA_BUSINESS_SHORT_CODE=174379
MPESA_PASSKEY=your-passkey
MPESA_CALLBACK_URL=https://your-ngrok-url.ngrok-free.app/fishing/mpesa/callback/
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
```

5. Migrate and run:
```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

App URL: `http://127.0.0.1:8000/fishing/home/`

## Running with ngrok (for Daraja callbacks)
In another terminal:
```bash
./ngrok http 8000
```
Use the generated HTTPS URL to set `MPESA_CALLBACK_URL` to:
- `https://<ngrok-domain>/fishing/mpesa/callback/`

## Core Flows

### Fisherman Flow
- Create/edit fish listings with image uploads (supports phone camera capture inputs)
- Configure M-Pesa profile fields in user profile
- View sales dashboard: gross revenue, platform fee, net earnings
- Manage order fulfillment statuses

### Customer Flow
- Browse fish listings and purchase by weight (kg)
- Checkout triggers STK requests tied to listing/fisherman config
- Order is marked paid only after successful callback validation
- Track order and delivery status history

### Delivery / Pickup Flow
- Add/manage pickup points (`/fishing/pickup-points/manage/`)
- Delivery/pickup role can update shipment status
- Delivery status transitions are auditable via `DeliveryAuditLog`

## Authentication
- Username/email + password login
- Google OAuth route: `/accounts/google/login/` (available when `django-allauth` is installed and configured)

## Testing
Run full tests:
```bash
python manage.py test users fishing
```

Run checks:
```bash
python manage.py check
```

## Security Notes
- Keep secrets only in `.env`
- Never commit real API keys or OAuth secrets
- `.env` is git-ignored

## License
MIT License. See `LICENSE`.
