#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt pyinstaller

echo "📦 Compilando binario autónomo de AudioDucker para Linux..."
./.venv/bin/python -m PyInstaller \
    --noconfirm \
    --clean \
    --noconsole \
    --onefile \
    --icon=assets/logo.png \
    --add-data "assets:assets" \
    --name "AudioDucker" \
    main.py

cp -f dist/AudioDucker ./AudioDucker
chmod +x ./AudioDucker

echo "✅ Binario Linux generado exitosamente en: ./AudioDucker (y dist/AudioDucker)"
