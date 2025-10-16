#!/bin/bash
set -e

echo "🧪 Testing GitHub Build Workflow Locally"
echo "========================================"

# Navigate to extension directory
cd "$(dirname "$0")/targets/vsc-extension"

echo ""
echo "✅ Step 1: Setup Build Environment"
npm run setup-build-env:macos

echo ""
echo "✅ Step 2: Bundle Executables"
npm run bundle-executables:macos

echo ""
echo "✅ Step 3: Compile TypeScript"
npm run compile:vsc-extension

echo ""
echo "✅ Step 4: Package Extension"
npm run package:vsc-extension

echo ""
echo "🎉 Build Complete!"
echo ""
echo "Generated files:"
ls -lh *.vsix
ls -lh executables/mcpower-*

echo ""
echo "📦 To test the extension:"
echo "  code --install-extension $(ls -t *.vsix | head -1)"
echo ""
echo "Or in Cursor:"
echo "  Open Extensions → ... → Install from VSIX → Select the .vsix file"

