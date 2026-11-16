#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🎵 Instalando AudioDucker para Linux..."

# 1. Verificar dependencias del sistema (python3-tk, python3-venv, libpulse0)
if command -v apt-get >/dev/null 2>&1; then
    echo "[*] Detectado sistema basado en Debian/Ubuntu. Verificando paquetes base..."
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-venv python3-pip python3-tk pulseaudio-utils libpulse0
elif command -v dnf >/dev/null 2>&1; then
    echo "[*] Detectado sistema basado en Fedora/RHEL. Verificando paquetes base..."
    sudo dnf install -y python3 python3-pip python3-tkinter pulseaudio-utils pulseaudio-libs
elif command -v pacman >/dev/null 2>&1; then
    echo "[*] Detectado sistema basado en Arch Linux. Verificando paquetes base..."
    sudo pacman -Sy --needed --noconfirm python python-pip tk libpulse
fi

# 2. Crear entorno virtual e instalar dependencias Python
if [ ! -d ".venv" ]; then
    echo "[*] Creando entorno virtual (.venv)..."
    python3 -m venv .venv
fi

echo "[*] Instalando dependencias de Python..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

# 3. Crear lanzador en el menú de aplicaciones del usuario
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/audioducker.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=AudioDucker
Comment=Control de volumen automático inteligente para Linux
Exec="$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/main.py"
Path=$SCRIPT_DIR
Icon=$SCRIPT_DIR/assets/logo.png
Terminal=false
Categories=AudioVideo;Audio;Utility;
EOF
chmod +x "$APPS_DIR/audioducker.desktop"

echo "✅ ¡Instalación completada!"
echo "👉 Puedes abrir AudioDucker desde tu menú de aplicaciones o ejecutando:"
echo "   ./.venv/bin/python main.py"
