#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
BUILD_ENV="$PROJECT_DIR/.build-venv"
BUILD_PYTHON="$BUILD_ENV/bin/python"
DIST_DIR="$PROJECT_DIR/dist/linux"
INSTALL_DIR="$HOME/.local/share/tron-lightcycle"
DESKTOP_DIR="$HOME/.local/share/applications"

cd "$PROJECT_DIR"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' "No se encontro Python 3. Instala Python 3.10 o posterior y vuelve a intentarlo." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    printf '%s\n' "Se requiere Python 3.10 o posterior." >&2
    exit 1
fi

if ! "$PYTHON" -c 'import tkinter' >/dev/null 2>&1; then
    printf '%s\n' "Falta Tkinter. En Debian/Ubuntu puedes instalarlo con: sudo apt install python3-tk" >&2
    exit 1
fi

if ! "$PYTHON" -c 'import venv' >/dev/null 2>&1; then
    printf '%s\n' "Falta el modulo venv. En Debian/Ubuntu puedes instalarlo con: sudo apt install python3-venv" >&2
    exit 1
fi

if [ ! -x "$BUILD_PYTHON" ]; then
    "$PYTHON" -m venv "$BUILD_ENV"
fi

"$BUILD_PYTHON" -m pip install --upgrade pip pyinstaller
mkdir -p "$PROJECT_DIR/build/linux/specs" "$DIST_DIR"

"$BUILD_PYTHON" -m PyInstaller --clean --noconfirm --onefile --windowed \
    --name TronCliente \
    --distpath "$DIST_DIR" \
    --workpath "$PROJECT_DIR/build/linux/client" \
    --specpath "$PROJECT_DIR/build/linux/specs" \
    "$PROJECT_DIR/client.py"

"$BUILD_PYTHON" -m PyInstaller --clean --noconfirm --onefile \
    --name TronServidor \
    --distpath "$DIST_DIR" \
    --workpath "$PROJECT_DIR/build/linux/server" \
    --specpath "$PROJECT_DIR/build/linux/specs" \
    "$PROJECT_DIR/server.py"

mkdir -p "$INSTALL_DIR" "$DESKTOP_DIR"
install -m 755 "$DIST_DIR/TronCliente" "$INSTALL_DIR/TronCliente"
install -m 755 "$DIST_DIR/TronServidor" "$INSTALL_DIR/TronServidor"

cat > "$DESKTOP_DIR/tron-lightcycle.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Tron Lightcycle Arena
Comment=Cliente multijugador de Tron
Exec="$INSTALL_DIR/TronCliente"
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=true
EOF

cat > "$DESKTOP_DIR/tron-lightcycle-server.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Tron Lightcycle Server
Comment=Iniciar el servidor multijugador de Tron
Exec="$INSTALL_DIR/TronServidor"
Icon=applications-games
Terminal=true
Categories=Game;Network;
EOF

chmod 755 "$DESKTOP_DIR/tron-lightcycle.desktop" "$DESKTOP_DIR/tron-lightcycle-server.desktop"

printf '\n%s\n' "Instalacion completada." \
    "Cliente: busca Tron Lightcycle Arena en el menu de aplicaciones (sin terminal)." \
    "Servidor: busca Tron Lightcycle Server; se abrira una terminal para mostrar su estado." \
    "Ejecutables tambien disponibles en: $DIST_DIR" \
    "Permite conexiones TCP entrantes al puerto 5050 en el firewall del servidor."
