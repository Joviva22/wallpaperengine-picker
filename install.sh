#!/usr/bin/env bash
# Instala wallpaperengine-picker: crea symlinks en ~/.local/bin, un lanzador
# en el menu de aplicaciones y una entrada de autostart de KDE.
set -euo pipefail

REPO_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

mkdir -p "$BIN_DIR" "$APPS_DIR" "$AUTOSTART_DIR"

echo "Comprobando dependencias..."
missing=()
for cmd in linux-wallpaperengine jq xrandr python3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null || missing+=("python-gobject (PyGObject/GTK3)")
python3 -c "from PIL import Image" 2>/dev/null || missing+=("python-pillow")

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Faltan dependencias: ${missing[*]}"
    echo "Instala primero lo indicado en el README y vuelve a ejecutar install.sh"
    exit 1
fi

if ! command -v steamcmd >/dev/null 2>&1; then
    echo "Aviso: 'steamcmd' no esta instalado. La descarga desde el Workshop (API) no funcionara hasta instalarlo."
fi

ln -sf "$REPO_DIR/bin/wallpaperengine-apply" "$BIN_DIR/wallpaperengine-apply"
ln -sf "$REPO_DIR/bin/wallpaperengine-picker" "$BIN_DIR/wallpaperengine-picker"
ln -sf "$REPO_DIR/bin/wallpaperengine-rotate" "$BIN_DIR/wallpaperengine-rotate"
ln -sf "$REPO_DIR/bin/wallpaperengine-tray" "$BIN_DIR/wallpaperengine-tray"
ln -sf "$REPO_DIR/bin/wallpaperengine-autostart" "$BIN_DIR/wallpaperengine-autostart"

if ! python3 -c "import gi; gi.require_version('AyatanaAppIndicator3','0.1')" 2>/dev/null \
   && ! python3 -c "import gi; gi.require_version('AppIndicator3','0.1')" 2>/dev/null; then
    echo "Aviso: sin libayatana-appindicator (ni AppIndicator3), el icono de bandeja usara"
    echo "Gtk.StatusIcon como respaldo, que puede no mostrarse en todos los escritorios."
fi

cat > "$APPS_DIR/wallpaperengine-picker.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Elegir Fondo (Wallpaper Engine)
Comment=Selecciona un fondo animado de tu coleccion de Wallpaper Engine
Exec=$BIN_DIR/wallpaperengine-picker
Icon=preferences-desktop-wallpaper
Terminal=false
Categories=Settings;DesktopSettings;
EOF

cat > "$AUTOSTART_DIR/wallpaperengine-autostart.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Wallpaper Engine Autostart
Comment=Aplica los ultimos fondos animados seleccionados (por pantalla) al iniciar sesion
Exec=$BIN_DIR/wallpaperengine-autostart
Icon=preferences-desktop-wallpaper
X-KDE-autostart-phase=2
Terminal=false
NoDisplay=true
EOF

cat > "$AUTOSTART_DIR/wallpaperengine-rotate.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Wallpaper Engine Rotation Daemon
Comment=Avanza las listas de rotacion de wallpapers configuradas por pantalla
Exec=$BIN_DIR/wallpaperengine-rotate
Icon=preferences-desktop-wallpaper
X-KDE-autostart-phase=2
Terminal=false
NoDisplay=true
EOF

cat > "$AUTOSTART_DIR/wallpaperengine-tray.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Wallpaper Engine Picker (bandeja)
Comment=Icono de bandeja con accesos rapidos (sin abrir la ventana completa)
Exec=$BIN_DIR/wallpaperengine-tray
Icon=preferences-desktop-wallpaper
X-KDE-autostart-phase=2
Terminal=false
NoDisplay=true
EOF

echo "Instalado. Lanza 'wallpaperengine-picker' o buscalo en el menu de aplicaciones como 'Elegir Fondo (Wallpaper Engine)'."
echo "El demonio de rotacion y el icono de bandeja arrancaran solos en el proximo inicio de sesion;"
echo "para probarlos ahora mismo:"
echo "  nohup $BIN_DIR/wallpaperengine-rotate >/dev/null 2>&1 &"
echo "  nohup $BIN_DIR/wallpaperengine-tray >/dev/null 2>&1 &"
