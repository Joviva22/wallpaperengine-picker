#!/usr/bin/env bash
# Instala wallpaperengine-picker: instala las dependencias que falten (Arch,
# Debian/Ubuntu, Fedora y openSUSE), detecta tu biblioteca de Steam, crea
# symlinks en ~/.local/bin, un lanzador en el menu de aplicaciones y una
# entrada de autostart de KDE.
set -euo pipefail

REPO_DIR=$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

mkdir -p "$BIN_DIR" "$APPS_DIR" "$AUTOSTART_DIR"

# ---------------------------------------------------------------------------
# Dependencias: se detecta el gestor de paquetes de la distro y se instala lo
# que falte con el. jq/xrandr/python3/GTK3+PyGObject/Pillow/steam tienen
# paquete oficial en Arch, Debian/Ubuntu, Fedora y openSUSE, y se instalan
# solos. El motor `linux-wallpaperengine` y `steamcmd` solo tienen paquete
# listo para instalar en Arch (AUR, via paru/yay); en el resto de distros no
# hay forma fiable de automatizarlo (steamcmd necesita repos/arquitectura
# extra segun la distro, y linux-wallpaperengine no tiene paquete fuera de
# Arch), asi que ahi se avisa con instrucciones en vez de intentarlo.
# ---------------------------------------------------------------------------

if command -v pacman >/dev/null 2>&1; then
    PM=pacman
elif command -v apt-get >/dev/null 2>&1; then
    PM=apt
elif command -v dnf >/dev/null 2>&1; then
    PM=dnf
elif command -v zypper >/dev/null 2>&1; then
    PM=zypper
else
    PM=unknown
fi
echo "Gestor de paquetes detectado: $PM"

declare -A PKG_JQ=([pacman]=jq [apt]=jq [dnf]=jq [zypper]=jq)
declare -A PKG_XRANDR=([pacman]=xorg-xrandr [apt]=x11-xserver-utils [dnf]=xorg-x11-server-utils [zypper]=xrandr)
declare -A PKG_PYTHON=([pacman]=python [apt]=python3 [dnf]=python3 [zypper]=python3)
declare -A PKG_PILLOW=([pacman]=python-pillow [apt]=python3-pil [dnf]=python3-pillow [zypper]=python3-Pillow)
declare -A PKG_STEAM=([pacman]=steam [apt]=steam [dnf]=steam [zypper]=steam)
# Gtk3/PyGObject son varios paquetes segun la distro.
declare -A PKG_GTK3=([pacman]="python-gobject gtk3" [apt]="python3-gi gir1.2-gtk-3.0" [dnf]="python3-gobject gtk3" [zypper]="python3-gobject typelib-1_0-Gtk-3_0 gtk3")

missing_pkgs=()
if [[ "$PM" != unknown ]]; then
    command -v jq >/dev/null 2>&1 || missing_pkgs+=(${PKG_JQ[$PM]})
    command -v xrandr >/dev/null 2>&1 || missing_pkgs+=(${PKG_XRANDR[$PM]})
    command -v python3 >/dev/null 2>&1 || missing_pkgs+=(${PKG_PYTHON[$PM]})
    python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null || missing_pkgs+=(${PKG_GTK3[$PM]})
    python3 -c "from PIL import Image" 2>/dev/null || missing_pkgs+=(${PKG_PILLOW[$PM]})
    command -v steam >/dev/null 2>&1 || missing_pkgs+=(${PKG_STEAM[$PM]})
fi

if [[ ${#missing_pkgs[@]} -gt 0 ]]; then
    echo "Instalando dependencias que faltan (${missing_pkgs[*]})..."
    case "$PM" in
        pacman) sudo pacman -S --needed --noconfirm "${missing_pkgs[@]}" ;;
        apt) sudo apt-get update && sudo apt-get install -y "${missing_pkgs[@]}" ;;
        dnf) sudo dnf install -y "${missing_pkgs[@]}" ;;
        zypper) sudo zypper --non-interactive install "${missing_pkgs[@]}" ;;
    esac
fi

if ! command -v linux-wallpaperengine >/dev/null 2>&1; then
    if [[ "$PM" == pacman ]]; then
        aur_helper=""
        command -v paru >/dev/null 2>&1 && aur_helper=paru
        [[ -z "$aur_helper" ]] && command -v yay >/dev/null 2>&1 && aur_helper=yay
        if [[ -n "$aur_helper" ]]; then
            echo "Instalando linux-wallpaperengine-git desde AUR con $aur_helper..."
            "$aur_helper" -S --needed --noconfirm linux-wallpaperengine-git
        else
            echo "Necesitas un helper de AUR (paru o yay) para instalar linux-wallpaperengine-git."
            echo "Instala paru/yay primero, o instala el paquete a mano, y vuelve a ejecutar install.sh"
            exit 1
        fi
    else
        echo "'linux-wallpaperengine' no esta instalado y tu distro no tiene un paquete listo para el."
        echo "Compilalo desde las fuentes: https://github.com/Almamu/linux-wallpaperengine"
        echo "(necesitaras cmake, un compilador de C++, y sus dependencias de desarrollo: SDL2, GLEW,"
        echo "GLFW, libmpv, FreeImage... consulta el README de ese repo para la lista exacta)."
        exit 1
    fi
fi

if ! command -v steamcmd >/dev/null 2>&1; then
    case "$PM" in
        pacman)
            aur_helper=""
            command -v paru >/dev/null 2>&1 && aur_helper=paru
            [[ -z "$aur_helper" ]] && command -v yay >/dev/null 2>&1 && aur_helper=yay
            if [[ -n "$aur_helper" ]]; then
                echo "Instalando steamcmd desde AUR con $aur_helper..."
                "$aur_helper" -S --needed --noconfirm steamcmd
            else
                echo "Aviso: sin paru/yay no se puede instalar 'steamcmd' (AUR). La descarga desde el Workshop"
                echo "via API no funcionara hasta instalarlo a mano; puedes seguir usando 'Abrir Workshop en Steam'."
            fi
            ;;
        apt)
            echo "Instalando steamcmd (necesita el repositorio multiverse/non-free y arquitectura i386)..."
            sudo dpkg --add-architecture i386
            sudo add-apt-repository -y multiverse 2>/dev/null || true
            echo steam steam/question select "I AGREE" | sudo debconf-set-selections
            echo steam steam/license note '' | sudo debconf-set-selections
            sudo apt-get update
            if ! DEBIAN_FRONTEND=noninteractive sudo apt-get install -y steamcmd; then
                echo "Aviso: no se pudo instalar 'steamcmd' automaticamente. La descarga desde el Workshop via"
                echo "API no funcionara hasta instalarlo a mano; puedes seguir usando 'Abrir Workshop en Steam'."
            fi
            ;;
        *)
            echo "Aviso: tu distro no tiene un paquete conocido para 'steamcmd'. La descarga desde el Workshop"
            echo "via API no funcionara hasta instalarlo a mano (ver https://developer.valvesoftware.com/wiki/SteamCMD);"
            echo "puedes seguir usando 'Abrir Workshop en Steam' sin el."
            ;;
    esac
fi

echo "Comprobando dependencias..."
missing=()
for cmd in linux-wallpaperengine jq xrandr python3; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null || missing+=("python-gobject (PyGObject/GTK3)")
python3 -c "from PIL import Image" 2>/dev/null || missing+=("python-pillow")

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Faltan dependencias tras el intento de instalacion: ${missing[*]}"
    echo "Instalalas manualmente segun el README y vuelve a ejecutar install.sh"
    exit 1
fi

# ---------------------------------------------------------------------------
# Deteccion de la biblioteca de Steam: funciona con solo tener el cliente de
# Steam configurado (~/.local/share/Steam o ~/.steam/steam con
# libraryfolders.vdf), aunque Wallpaper Engine (la app 431960) todavia no este
# instalada ni tengas ningun wallpaper suscrito -- en ese caso simplemente
# elige la primera biblioteca que encuentre, y se podra descargar/asignar
# wallpapers en cuanto te suscribas a alguno.
# ---------------------------------------------------------------------------

source "$REPO_DIR/bin/wallpaperengine-common.sh"
echo "Buscando tu biblioteca de Steam..."
steam_lib=$(wpe_get_steam_library)
if [[ -d "$steam_lib/steamapps/workshop/content/$WPE_APPID" ]]; then
    echo "Biblioteca de Steam: $steam_lib (ya tiene wallpapers descargados)"
elif [[ -d "$steam_lib/steamapps" ]]; then
    echo "Biblioteca de Steam: $steam_lib (aun sin wallpapers -- suscribete a alguno desde la pestana Workshop)"
else
    echo "Aviso: no se encontro ninguna biblioteca de Steam (~/.local/share/Steam o ~/.steam/steam)."
    echo "Instala y abre Steam al menos una vez antes de usar la app."
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
