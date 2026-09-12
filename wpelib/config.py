"""Configuracion, deteccion de la biblioteca de Steam y estado persistido en
disco: wallpapers ocultos, listas de rotacion, wallpapers con fallos
conocidos, y el escaneo de la biblioteca local ya descargada."""
import json
import os
import re
import shutil
import subprocess

from PIL import Image

APPID = "431960"
CONF_DIR = os.path.expanduser("~/.config/wallpaperengine-picker")
CONFIG_FILE = os.path.join(CONF_DIR, "config.json")
CURRENT_FILE = os.path.join(CONF_DIR, "current.json")
HIDDEN_FILE = os.path.join(CONF_DIR, "hidden.json")
FAVORITES_FILE = os.path.join(CONF_DIR, "favorites.json")
RECENTS_FILE = os.path.join(CONF_DIR, "recents.json")
UI_STATE_FILE = os.path.join(CONF_DIR, "ui_state.json")
PLAYLISTS_FILE = os.path.join(CONF_DIR, "playlists.json")
KNOWN_BAD_FILE = os.path.join(CONF_DIR, "known_bad.json")
MAX_RECENTS = 100
CACHE_DIR = os.path.expanduser("~/.cache/wallpaperengine-picker/thumbs_v3")
WORKSHOP_THUMB_CACHE = os.path.expanduser("~/.cache/wallpaperengine-picker/workshop_thumbs")
APPLY_SCRIPT = os.path.expanduser("~/.local/bin/wallpaperengine-apply")
THUMB_SIZE = (320, 180)  # 16:9 exacto; debe coincidir con CARD_SIZE en wpelib/ui.py
DEFAULT_ID = "2168640648"
STEAM_API_QUERYFILES = "https://api.steampowered.com/IPublishedFileService/QueryFiles/v1/"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(WORKSHOP_THUMB_CACHE, exist_ok=True)
os.makedirs(CONF_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Configuracion y deteccion de la biblioteca de Steam
# ---------------------------------------------------------------------------

def parse_libraryfolders(vdf_path):
    paths = []
    try:
        with open(vdf_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for match in re.findall(r'"path"\s*"([^"]+)"', content):
            paths.append(match.replace("\\\\", "/"))
    except Exception:
        pass
    return paths


def detect_steam_library():
    candidates = [os.path.expanduser("~/.local/share/Steam"), os.path.expanduser("~/.steam/steam")]
    lib_paths = []
    for base in candidates:
        vdf = os.path.join(base, "steamapps", "libraryfolders.vdf")
        if os.path.isfile(vdf):
            lib_paths.append(base)
            lib_paths.extend(parse_libraryfolders(vdf))

    seen = []
    for p in lib_paths:
        if p not in seen:
            seen.append(p)

    for p in seen:
        if os.path.isdir(os.path.join(p, "steamapps", "workshop", "content", APPID)) or \
           os.path.isdir(os.path.join(p, "steamapps", "common", "wallpaper_engine")):
            return p

    return seen[0] if seen else os.path.expanduser("~/.local/share/Steam")


def load_config():
    cfg = {}
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    changed = False
    if not cfg.get("steam_library") or not os.path.isdir(cfg.get("steam_library", "")):
        cfg["steam_library"] = detect_steam_library()
        changed = True
    if changed:
        save_config(cfg)
    return cfg


def save_config(cfg):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


CONFIG = load_config()
STEAM_LIB = CONFIG["steam_library"]
WORKSHOP_DIR = os.path.join(STEAM_LIB, "steamapps", "workshop", "content", APPID)
ASSETS_DIR = os.path.join(STEAM_LIB, "steamapps", "common", "wallpaper_engine", "assets")


def detect_monitors():
    try:
        out = subprocess.check_output(["xrandr", "--listmonitors"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    lines = out.strip().splitlines()[1:]
    return [line.split()[-1] for line in lines if line.strip()]


def load_current_assignments(monitors):
    assignments = {}
    if os.path.isfile(CURRENT_FILE):
        try:
            with open(CURRENT_FILE, encoding="utf-8") as f:
                assignments = json.load(f)
        except Exception:
            assignments = {}
    for mon in monitors:
        assignments.setdefault(mon, DEFAULT_ID)
    return assignments


def load_known_bad():
    """Ids que hicieron crashear linux-wallpaperengine la ultima vez que se probaron
    (detectado por wallpaperengine-apply, ver known_bad.json)."""
    if os.path.isfile(KNOWN_BAD_FILE):
        try:
            with open(KNOWN_BAD_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def load_hidden_ids():
    if os.path.isfile(HIDDEN_FILE):
        try:
            with open(HIDDEN_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_hidden_ids(ids):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(HIDDEN_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def load_favorite_ids():
    if os.path.isfile(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_favorite_ids(ids):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)


def load_recent_ids():
    """Devuelve los ids aplicados recientemente, mas reciente primero."""
    if os.path.isfile(RECENTS_FILE):
        try:
            with open(RECENTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def record_recent(wid):
    recents = [r for r in load_recent_ids() if r != wid]
    recents.insert(0, wid)
    recents = recents[:MAX_RECENTS]
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(RECENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(recents, f, indent=2)
    return recents


def load_ui_state():
    if os.path.isfile(UI_STATE_FILE):
        try:
            with open(UI_STATE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_ui_state(state):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(UI_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def load_playlists():
    if os.path.isfile(PLAYLISTS_FILE):
        try:
            with open(PLAYLISTS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_playlists(data):
    os.makedirs(CONF_DIR, exist_ok=True)
    with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def unsubscribe_workshop_item(wid):
    """Borra el contenido local del wallpaper y lo quita de cualquier lista de
    rotacion. No es un unsubscribe real en Steam (eso requiere el cliente
    autenticado con tu cuenta); solo limpia lo que tenemos en disco/config."""
    folder = os.path.join(WORKSHOP_DIR, wid)
    if os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)

    thumb = os.path.join(CACHE_DIR, f"{wid}.png")
    if os.path.isfile(thumb):
        os.remove(thumb)

    playlists = load_playlists()
    changed = False
    for data in playlists.values():
        items = data.get("items", [])
        if wid in items:
            data["items"] = [i for i in items if i != wid]
            changed = True
    if changed:
        save_playlists(playlists)

    favorites = load_favorite_ids()
    if wid in favorites:
        favorites.discard(wid)
        save_favorite_ids(favorites)


def build_thumb(preview_path, dest_path):
    try:
        img = Image.open(preview_path)
        img = img.convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        canvas = Image.new("RGB", THUMB_SIZE, (30, 30, 30))
        x = (THUMB_SIZE[0] - img.width) // 2
        y = (THUMB_SIZE[1] - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(dest_path, "PNG")
        return True
    except Exception:
        return False


def load_wallpapers():
    """Devuelve lista de dicts: id, title, thumb (ruta si ya esta en cache, si
    no None), preview_path (para generar la miniatura mas tarde en segundo
    plano), tags, rating, mtime, type. No genera miniaturas aqui (para no
    bloquear la interfaz la primera vez que aparecen wallpapers nuevos);
    eso lo hace el llamador con build_thumb() de forma progresiva."""
    items = []
    if not os.path.isdir(WORKSHOP_DIR):
        return items
    for entry in sorted(os.listdir(WORKSHOP_DIR)):
        folder = os.path.join(WORKSHOP_DIR, entry)
        project_path = os.path.join(folder, "project.json")
        if not os.path.isfile(project_path):
            continue
        try:
            with open(project_path, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            title = data.get("title", entry)
            preview = data.get("preview", "")
            tags = data.get("tags", []) or []
            rating = data.get("contentrating", "Desconocido") or "Desconocido"
            wtype = data.get("type", "Desconocido") or "Desconocido"
        except Exception:
            title, preview, tags, rating, wtype = entry, "", [], "Desconocido", "Desconocido"

        # Wallpaper Engine no es consistente con las mayusculas de "type"
        # ("scene" vs "Scene", "video" vs "Video"...); lo normalizamos aqui
        # una sola vez para que todo el resto de la app compare de forma fiable.
        wtype = wtype.strip().capitalize() if isinstance(wtype, str) and wtype.strip() else "Desconocido"

        thumb_path = os.path.join(CACHE_DIR, f"{entry}.png")
        has_cached_thumb = os.path.isfile(thumb_path)
        preview_path = os.path.join(folder, preview) if preview else ""

        try:
            mtime = os.path.getmtime(folder)
        except OSError:
            mtime = 0

        items.append({
            "id": entry, "title": title,
            "thumb": thumb_path if has_cached_thumb else None,
            "preview_path": preview_path if os.path.isfile(preview_path) else None,
            "tags": tags, "rating": rating, "mtime": mtime, "type": wtype,
        })
    items.sort(key=lambda r: r["title"].lower())
    return items


SORT_OPTIONS = {
    "Mas reciente primero": lambda item: -item["mtime"],
    "Mas antiguo primero": lambda item: item["mtime"],
    "Titulo (A-Z)": lambda item: item["title"].lower(),
    "Titulo (Z-A)": lambda item: item["title"].lower(),
}
SORT_REVERSE = {"Titulo (Z-A)": True}
