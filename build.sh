#!/usr/bin/env bash
# Build the macOS .app bundle and .dmg with PyInstaller.
# Converts icon.png to icon.icns, packages gui.py, then wraps the app in a dmg.
set -e
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate

APP_NAME="Fal.ai-Seedream5-Layers-To-Save-PSD"

python3 -c "from PIL import Image; Image.open('icon.png').save('icon.icns')"

pyinstaller --noconfirm --windowed \
  --name "$APP_NAME" \
  --icon icon.icns \
  --add-data "icon.png:." \
  gui.py

hdiutil create -volname "$APP_NAME" \
  -srcfolder "dist/$APP_NAME.app" \
  -ov -format UDZO "dist/$APP_NAME.dmg"

echo "Done: dist/$APP_NAME.dmg"
