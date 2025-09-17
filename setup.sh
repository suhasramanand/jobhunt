#!/bin/bash

# Job Aggregator Setup Script
echo "🚀 Setting up Job Aggregator..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.11+ first."
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ Python 3 and Node.js are installed"

# Set up Python scraper
echo "📦 Setting up Python scraper..."
cd scraper

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Created Python virtual environment"
fi

# Activate virtual environment and install dependencies
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
echo "✅ Python dependencies installed"

cd ..

# Set up React frontend
echo "📦 Setting up React frontend..."
cd frontend

# Install Node.js dependencies
npm install
echo "✅ Node.js dependencies installed"

# Build the frontend
npm run build
echo "✅ Frontend built successfully"

cd ..

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "📋 Next steps:"
echo "1. Test the scraper: cd scraper && python scrape_jobs.py"
echo "2. Start the frontend: cd frontend && npm start"
echo "3. Deploy to GitHub and enable GitHub Actions"
echo ""
echo "📖 For detailed instructions, see README.md"
