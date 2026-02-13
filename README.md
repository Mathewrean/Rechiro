# Rechiro (Sustainable Fishing)

Rechiro is a Django marketplace for direct fish sales between verified Lake Victoria fishermen and customers.

## What It Includes
- Weight-based fish listings (`price_per_kg * weight_kg`)
- M-Pesa Daraja STK checkout with callback validation
- Automatic platform fee accounting (2%) and fisherman net payout (98%)
- Customer order history and fisherman sales dashboard
- Delivery workflow with assignment, tracking, and audit logs
- Email/password authentication plus Google OAuth (when `django-allauth` is installed)
- Rechiro branding UI updates across auth, landing, and dashboard pages

## Lake Victoria Fish List
Fish listing options are limited to Lake Victoria species:
- Tilapia (Ngege)
- Nile Perch (Mbuta)
- African Catfish (Semu)
- Dagaa / Omena
- Lungfish (Kamongo)
- Mudfish
- Barbel
- Other (Lake Victoria Species)

## Tech Stack
- Python / Django
- SQLite (default dev DB)
- M-Pesa Daraja API
- Tailwind (CDN in templates)

## Project Structure
- `sustainable_fishing/` Django settings and root URLs
- `users/` user model, auth, profiles, role selection flow
- `fishing/` marketplace, cart, checkout, payment, delivery, dashboards
- `templates/` HTML templates
- `static/branding/` Rechiro brand assets

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
MPESA_CALLBACK_URL=https://your-ngrok-url.ngrok-free.app/api/mpesa/callback/
MPESA_BASE_URL=https://sandbox.safaricom.co.ke
```

5. Migrate and run:
```bash
python manage.py migrate
python manage.py runserver 127.0.0.1:8000 --noreload
```

App URL: `http://127.0.0.1:8000/fishing/home/`

## Run with ngrok
```bash
./ngrok http 8000
```
If using a fixed ngrok URL, configure:
- `MPESA_CALLBACK_URL=https://<your-domain>/api/mpesa/callback/`

## Core Flows

### Fisherman Flow
- Create/edit fish listings (Lake Victoria species)
- Configure M-Pesa profile fields
- View sales metrics and payout breakdown
- Manage order fulfillment updates

### Customer Flow
- Browse fish listings and purchase by kg
- Checkout triggers STK requests
- Order is marked paid only after callback validation
- Track order and delivery progress

### Delivery Flow
- Delivery role manages assigned deliveries
- Status transitions are logged for traceability
- Dashboard tracks assigned/completed/pending/failed deliveries

### Google OAuth Role Flow
- Role is selected only after successful Google authentication
- New social users are routed to `/choose-role/`
- Role is locked after first selection unless changed by admin

## Testing
Run tests:
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
