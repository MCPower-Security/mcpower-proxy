#!/bin/bash
set -e

echo "🔧 Setting up MCPower Security build environment for Linux..."

# Check if we're on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This script is designed for Linux. Please adapt for your platform."
    exit 1
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for Python 3
if ! command_exists python3; then
    echo "❌ Python 3 is not installed."
    echo "Install with: sudo apt-get update && sudo apt-get install python3 python3-pip python3-venv"
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "✅ Found Python $PYTHON_VERSION"

# Navigate to src directory
cd ../../src
if [[ ! -d "." ]]; then
    echo "❌ Source directory not found"
    exit 1
fi

echo "📦 Setting up Python virtual environment..."

# Create virtual environment if it doesn't exist
if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
    echo "✅ Created Python virtual environment"
else
    echo "✅ Python virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/activate
echo "✅ Activated Python virtual environment"

# Upgrade pip
python -m pip install --upgrade pip

# Install Python dependencies
if [[ -f "requirements.txt" ]]; then
    echo "📦 Installing Python dependencies..."
    pip install -r requirements.txt
    echo "✅ Python dependencies installed"
else
    echo "⚠️  requirements.txt not found, skipping Python dependency installation"
fi

# Install Nuitka if not present
if ! pip show nuitka >/dev/null 2>&1; then
    echo "📦 Installing Nuitka..."
    pip install nuitka
    echo "✅ Nuitka installed"
else
    echo "✅ Nuitka already installed"
fi

# Verify critical imports
echo "🔍 Verifying critical imports..."
python -c "import fastmcp; print('✅ fastmcp import successful')"
python -c "import uuid; print('✅ uuid import successful')"

# Navigate back to extension directory
cd ../targets/vsc-extension

# Check for Node.js (should be available in CI)
if ! command_exists node; then
    echo "❌ Node.js is not installed."
    echo "Install with: curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
fi

NODE_VERSION=$(node --version)
echo "✅ Found Node.js $NODE_VERSION"

# Note: Node.js dependencies are handled by CI workflow, not here
echo "📦 Node.js dependencies will be handled by the build system"

# Update Gitleaks rules
echo "📥 Updating Gitleaks rules..."
node scripts/update-gitleaks-rules.mjs || echo "⚠️ Failed to update Gitleaks rules"

echo "✅ Build environment setup completed successfully!"
echo "💡 You can now run: npm run bundle-executables -- --platform=linux"
