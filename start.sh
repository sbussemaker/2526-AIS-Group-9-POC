#!/bin/bash

echo "=========================================="
echo "  EAI MCP Demo - Startup Script"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
cd client
pip install -q -r requirements.txt
if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo ""

# Start the orchestrator
echo "🚀 Starting orchestrator on http://localhost:5000"
echo ""
echo "Next steps:"
echo "1. Keep this terminal open"
echo "2. Open another terminal and run: cd dashboard && python -m http.server 8080"
echo "3. Open your browser to: http://localhost:8080"
echo ""
echo "=========================================="
echo ""

python orchestrator.py
