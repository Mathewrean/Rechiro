#!/bin/bash
set -e

PROJECT_DIR="/mnt/c/Users/SoftClansUser/Desktop/rechiro/Rechiro"
NGROK_CONFIG="$PROJECT_DIR/logs/ngrok.yml"
NGROK_BIN="$PROJECT_DIR/ngrok/ngrok"

if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "ERROR: NGROK_AUTHTOKEN environment variable is not set."
    echo "Get your authtoken from https://dashboard.ngrok.com/get-started/your-authtoken"
    exit 1
fi

cd "$PROJECT_DIR"

# Update ngrok config with auth token
cat > "$NGROK_CONFIG" <<EOF
version: "3"
agent:
  authtoken: "$NGROK_AUTHTOKEN"
  region: "us"
tunnels:
  kuppetsiaya:
    proto: http
    addr: 8000
    hostname: albert-incult-superfluously.ngrok-free.dev
EOF

echo "Starting Django server on port 8000..."
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000 &
DJANGO_PID=$!

sleep 3

echo "Starting ngrok tunnel..."
"$NGROK_BIN" start --config "$NGROK_CONFIG" kuppetsiaya &
NGROK_PID=$!

echo ""
echo "=========================================="
echo "App should be available at:"
echo "https://albert-incult-superfluously.ngrok-free.dev"
echo "=========================================="

wait $DJANGO_PID $NGROK_PID
