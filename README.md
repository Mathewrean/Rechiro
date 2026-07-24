# Rechiro

Direct marketplace for Lake Victoria fishermen to sell fresh fish to customers via M-Pesa.

## Features
- Weight-based pricing for fish listings
- M-Pesa STK checkout with callback validation
- Email and Google OAuth authentication
- Delivery workflow with tracking
- Phone verification for fishermen via KES 1 STK push

## Tech Stack
- Django 5.x
- PostgreSQL (production) / SQLite (development)
- M-Pesa Daraja API
- Tailwind CSS

## Development Setup

```bash
git clone https://github.com/Mathewrean/Rechiro.git
cd Rechiro

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials

python manage.py migrate
python manage.py runserver
```

App URL: `http://127.0.0.1:8000/fishing/home/`

## Deployment to Render

1. Click "New +" > "Web Service" on Render dashboard
2. Connect your GitHub repository
3. Render auto-detects Python and uses `render.yaml`
4. Set required environment variables in Render dashboard:
   - `MPESA_CONSUMER_KEY`
   - `MPESA_CONSUMER_SECRET`
   - `MPESA_BUSINESS_SHORT_CODE`
   - `MPESA_PASSKEY`
   - `EMAIL_HOST`
   - `EMAIL_HOST_USER`
   - `EMAIL_HOST_PASSWORD`

## Testing
```bash
python manage.py test users fishing
```

## License
MIT