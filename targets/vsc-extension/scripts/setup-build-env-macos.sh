#!/bin/bash
set -e

echo "🔧 Setting up MCPower Security build environment..."

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is designed for macOS. Please adapt for your platform."
    exit 1
fi

# Install Homebrew if not present (for CI environments)
if ! command -v brew &> /dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Add Homebrew to PATH for current session
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# Install or ensure Homebrew Python (required for Nuitka)
if [[ ! -f "/opt/homebrew/bin/python3" ]] && [[ ! -f "/usr/local/bin/python3" ]]; then
    echo "🐍 Installing Homebrew Python (required for Nuitka)..."
    HOMEBREW_NO_AUTO_UPDATE=1 brew install python3
else
    if [[ -f "/opt/homebrew/bin/python3" ]]; then
        PYTHON_VERSION=$(/opt/homebrew/bin/python3 --version 2>&1 | cut -d' ' -f2)
        echo "✅ Homebrew Python $PYTHON_VERSION already installed"
    elif [[ -f "/usr/local/bin/python3" ]]; then
        PYTHON_VERSION=$(/usr/local/bin/python3 --version 2>&1 | cut -d' ' -f2)
        echo "✅ Homebrew Python $PYTHON_VERSION already installed"
    fi
fi

# Setup Python virtual environment for src using Homebrew Python
echo "📁 Setting up Python virtual environment..."
cd ../../src
rm -rf .venv

# Use Homebrew Python specifically (required for Nuitka)
if [[ -f "/opt/homebrew/bin/python3" ]]; then
    /opt/homebrew/bin/python3 -m venv .venv
elif [[ -f "/usr/local/bin/python3" ]]; then
    /usr/local/bin/python3 -m venv .venv
else
    echo "❌ Homebrew Python not found. Nuitka requires Homebrew Python."
    exit 1
fi
source .venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Verify critical imports work
echo "✅ Verifying Python dependencies..."
python -c "import fastmcp; import mcp; print('All Python dependencies work!')" || {
    echo "❌ Python dependency verification failed"
    exit 1
}

cd ../targets/vsc-extension

# Setup Node.js environment for extension
echo "📦 Setting up Node.js environment..."
npm ci

# Update Gitleaks rules
echo "📥 Updating Gitleaks rules..."
node scripts/update-gitleaks-rules.mjs || echo "⚠️ Failed to update Gitleaks rules"

echo "✅ Build environment setup complete!"
echo ""
echo "To build the extension:"
echo "  npm run bundle-executables"
