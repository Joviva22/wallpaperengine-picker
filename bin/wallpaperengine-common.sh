#!/usr/bin/env bash
# Funciones compartidas: localizar la biblioteca de Steam y leer/escribir la configuracion.
# Pensado para ser sourceado, no ejecutado directamente.

WPE_CONF_DIR="$HOME/.config/wallpaperengine-picker"
WPE_CONFIG_FILE="$WPE_CONF_DIR/config.json"
WPE_APPID="431960"

wpe_detect_steam_library() {
    local candidates=("$HOME/.local/share/Steam" "$HOME/.steam/steam")
    local lib_paths=()
    local base vdf

    for base in "${candidates[@]}"; do
        vdf="$base/steamapps/libraryfolders.vdf"
        if [[ -f "$vdf" ]]; then
            lib_paths+=("$base")
            while IFS= read -r p; do
                [[ -n "$p" ]] && lib_paths+=("$p")
            done < <(grep -oP '"path"\s*"\K[^"]+' "$vdf" 2>/dev/null | sed 's#\\\\#/#g')
        fi
    done

    local p
    for p in "${lib_paths[@]}"; do
        if [[ -d "$p/steamapps/workshop/content/$WPE_APPID" || -d "$p/steamapps/common/wallpaper_engine" ]]; then
            echo "$p"
            return 0
        fi
    done

    if [[ ${#lib_paths[@]} -gt 0 ]]; then
        echo "${lib_paths[0]}"
        return 0
    fi

    echo "$HOME/.local/share/Steam"
}

# Devuelve la ruta de la biblioteca de Steam a usar, detectandola y guardandola
# en config.json si aun no esta configurada.
wpe_get_steam_library() {
    mkdir -p "$WPE_CONF_DIR"

    if [[ -f "$WPE_CONFIG_FILE" ]]; then
        local existing
        existing=$(jq -r '.steam_library // empty' "$WPE_CONFIG_FILE" 2>/dev/null)
        if [[ -n "$existing" && -d "$existing" ]]; then
            echo "$existing"
            return 0
        fi
    fi

    local detected
    detected=$(wpe_detect_steam_library)

    local tmp
    if [[ -f "$WPE_CONFIG_FILE" ]]; then
        tmp=$(jq --arg lib "$detected" '.steam_library = $lib' "$WPE_CONFIG_FILE")
    else
        tmp=$(jq -n --arg lib "$detected" '{steam_library: $lib}')
    fi
    echo "$tmp" > "$WPE_CONFIG_FILE"

    echo "$detected"
}

wpe_get_config_value() {
    local key="$1"
    [[ -f "$WPE_CONFIG_FILE" ]] || return 1
    jq -r --arg k "$key" '.[$k] // empty' "$WPE_CONFIG_FILE"
}
