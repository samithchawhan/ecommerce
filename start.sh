#!/bin/bash
# VOLTA E-Commerce - Start Script

echo "🚀 Starting VOLTA E-Commerce Backend..."
echo ""

# Navigate to backend
cd "$(dirname "$0")/backend"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# Check backend dependencies
python3 -c "import flask, pymongo, dotenv" 2>/dev/null || {
    echo "Installing backend dependencies..."
    pip3 install -r requirements.txt --break-system-packages
}

# Start backend
echo "✅ Backend running at: http://localhost:5000"
echo "✅ Frontend: open frontend/index.html in your browser"
echo ""
echo "Press Ctrl+C to stop."
echo "─────────────────────────────────"
python3 app.py
