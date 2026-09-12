"""Cliente de la Steam Web API (busqueda en el Workshop de Wallpaper Engine)
y descarga de items con steamcmd."""
import json
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.parse
import urllib.error

from PIL import Image

from .config import STEAM_LIB, WORKSHOP_DIR, THUMB_SIZE, WORKSHOP_THUMB_CACHE, APPID, STEAM_API_QUERYFILES

class SteamApiError(Exception):
    pass


# Categorias de etiquetas conocidas del Workshop de Wallpaper Engine (visibles en su pagina
# de busqueda). La clasificacion de edad no es una etiqueta normal expuesta por la API, asi
# que esa se filtra en el cliente comprobando las etiquetas devueltas por cada resultado.
KNOWN_TAGS = [
    "Abstract", "Animal", "Anime", "CGI", "Cartoon", "Cyberpunk", "Fantasy", "Game",
    "Landscape", "Memes", "Music", "Nature", "Pixel art", "Relaxing", "Retro",
    "Sci-Fi", "Sports", "Technology", "Television", "Unspecified", "Vehicle",
]
RATING_TAGS = ["Everyone", "Questionable", "Mature"]

# Ventanas de tiempo para "mas popular en..." (k_PublishedFileQueryType_RankedByTrend = 3),
# igual que el filtro "Popular esta semana/mes/..." de la pagina web del Workshop.
POPULARITY_OPTIONS = {
    "Mas votados (todo el tiempo)": (0, None),
    "Popular hoy": (3, 1),
    "Popular esta semana": (3, 7),
    "Popular este mes": (3, 30),
    "Popular en medio año": (3, 180),
    "Popular este año": (3, 365),
}


def steam_api_search(api_key, search_text, required_tags=None, query_type=0, days=None, page=1, per_page=50):
    if search_text:
        query_type = 12  # RankedByTextSearch tiene prioridad sobre la popularidad elegida
    params = {
        "key": api_key,
        "appid": APPID,
        "numperpage": str(per_page),
        "page": str(page),
        "query_type": str(query_type),
        "return_vote_data": "false",
        "return_tags": "true",
        "return_short_description": "false",
        "strip_description_bbcode": "true",
    }
    if search_text:
        params["search_text"] = search_text
    for i, tag in enumerate(required_tags or []):
        params[f"requiredtags[{i}]"] = tag
    if required_tags:
        params["match_all_tags"] = "true"
    if days:
        params["days"] = str(days)

    url = STEAM_API_QUERYFILES + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SteamApiError(f"Error HTTP {e.code} de la API de Steam (revisa tu API key)") from e
    except Exception as e:
        raise SteamApiError(f"No se pudo contactar la API de Steam: {e}") from e

    response = data.get("response", {})
    return response.get("total", 0), response.get("publishedfiledetails", [])


def steam_api_search_multi(api_key, search_text, required_tags, ratings, query_type=0, days=None, page=1, per_page=50):
    """Etiquetas: deben estar TODAS presentes (AND). Clasificaciones: basta con UNA (OR) -
    como un item solo tiene una clasificacion, combinarlas exige una llamada por cada una
    (maximo 3) y fusionar resultados, ya que la API no soporta AND-de-ORes en una sola query."""
    required_tags = list(required_tags or [])
    ratings = list(ratings or [])

    if len(ratings) <= 1:
        combined = required_tags + ratings
        return steam_api_search(
            api_key, search_text, required_tags=combined,
            query_type=query_type, days=days, page=page, per_page=per_page,
        )

    per_rating = max(1, per_page // len(ratings))
    total_sum = 0
    merged = []
    seen_ids = set()
    for rating in ratings:
        combined = required_tags + [rating]
        t, items = steam_api_search(
            api_key, search_text, required_tags=combined,
            query_type=query_type, days=days, page=page, per_page=per_rating,
        )
        total_sum += t
        for item in items:
            wid = item.get("publishedfileid")
            if wid and wid not in seen_ids:
                seen_ids.add(wid)
                merged.append(item)
    return total_sum, merged


def download_workshop_thumb(wid, url):
    dest = os.path.join(WORKSHOP_THUMB_CACHE, f"{wid}.png")
    if os.path.isfile(dest):
        return dest
    try:
        tmp_path = dest + ".tmp"
        urllib.request.urlretrieve(url, tmp_path)
        img = Image.open(tmp_path).convert("RGB")
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        canvas = Image.new("RGB", THUMB_SIZE, (30, 30, 30))
        x = (THUMB_SIZE[0] - img.width) // 2
        y = (THUMB_SIZE[1] - img.height) // 2
        canvas.paste(img, (x, y))
        canvas.save(dest, "PNG")
        os.remove(tmp_path)
        return dest
    except Exception:
        return None


def is_already_downloaded(wid):
    return os.path.isfile(os.path.join(WORKSHOP_DIR, wid, "project.json"))


def verify_workshop_download(wid):
    """Comprueba en disco que el wallpaper realmente quedo instalado, en vez de
    fiarse solo del texto que imprime steamcmd. Devuelve (ok, detalle)."""
    folder = os.path.join(WORKSHOP_DIR, wid)
    project_path = os.path.join(folder, "project.json")
    if not os.path.isfile(project_path):
        return False, f"No se encontro {project_path} tras la descarga"
    try:
        with open(project_path, encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        return True, data.get("title", wid)
    except Exception as e:
        return False, f"project.json presente pero ilegible: {e}"


def format_size(num_bytes):
    if not num_bytes:
        return "tamaño desconocido"
    try:
        mb = int(num_bytes) / (1024 * 1024)
    except (TypeError, ValueError):
        return "tamaño desconocido"
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.1f} MB"


def download_workshop_item(wid, log_callback, max_attempts=3):
    if not shutil.which("steamcmd"):
        log_callback("steamcmd no esta instalado. Instalalo (ver README) e intenta de nuevo.\n")
        return False
    cmd = [
        "steamcmd",
        "+force_install_dir", STEAM_LIB,
        "+login", "anonymous",
        "+workshop_download_item", APPID, wid,
        "+quit",
    ]
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            log_callback(f"\nReintentando descarga ({attempt}/{max_attempts}), fallo transitorio comun de steamcmd...\n")
        log_callback(f"Ejecutando: {' '.join(cmd)}\n")
        success = False
        failed = False
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                log_callback(line)
                if "Success. Downloaded item" in line:
                    success = True
                if line.strip().startswith("ERROR!"):
                    failed = True
            proc.wait()
        except Exception as e:
            log_callback(f"Error al ejecutar steamcmd: {e}\n")
            return False

        if success and not failed:
            return True
        if attempt < max_attempts:
            time.sleep(3)

    return False
