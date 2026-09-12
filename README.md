# wallpaperengine-picker-api

Selector grafico de fondos de pantalla animados para Linux, basado en
[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine), con:

> Existe una version hermana sin dependencias externas (sin API ni `steamcmd`), que abre el
> Workshop en el propio Steam para suscribirte: [wallpaperengine-picker-local](https://github.com/Joviva22/wallpaperengine-picker-local).

- Miniaturas reales de cada wallpaper (generadas a partir del preview de Steam Workshop).
- Asignacion de un wallpaper **distinto por cada monitor**.
- Filtros por titulo, etiqueta y clasificacion de contenido (Everyone / Questionable / Mature).
- Busqueda y descarga de nuevos wallpapers **directamente desde el Workshop de Steam**, usando
  la Steam Web API y `steamcmd` (sin necesidad de abrir el cliente de Steam).
- Autostart en KDE Plasma: recuerda la ultima configuracion por pantalla y la reaplica al
  iniciar sesion.

Probado en CachyOS/Arch Linux con KDE Plasma (Wayland) y una GPU NVIDIA, pero deberia
funcionar en cualquier distro basada en Arch con los mismos paquetes.

## Como funciona

`linux-wallpaperengine` es el motor que renderiza las escenas `.pkg`/`scene.json` del
Workshop de Wallpaper Engine (app de Steam `431960`). Este proyecto añade una interfaz
grafica (GTK3) alrededor de ese motor para:

1. Detectar automaticamente donde tienes instalada tu biblioteca de Steam (lee
   `libraryfolders.vdf`, igual que hace el propio Steam).
2. Listar los wallpapers que ya tienes descargados (suscritos via Steam) con sus miniaturas.
3. Permitirte asignar un wallpaper a cada monitor conectado y lanzarlos con un solo proceso
   de `linux-wallpaperengine`.
4. Opcionalmente, buscar mas wallpapers en el Workshop sin salir de la app y descargarlos con
   `steamcmd`.

## Requisitos

Paquetes necesarios (nombres para Arch/CachyOS, vía `pacman`/AUR):

| Paquete | Repo | Para que se usa |
|---|---|---|
| `linux-wallpaperengine-git` | AUR | Motor que renderiza los wallpapers |
| `steam` | multilib/AUR | Cliente de Steam (para suscribirte a wallpapers) |
| `steamcmd` | AUR | Descargar wallpapers del Workshop sin abrir Steam |
| `python-gobject` | oficial | Interfaz grafica (GTK3 desde Python) |
| `gtk3` | oficial | Interfaz grafica |
| `python-pillow` | oficial | Generar las miniaturas |
| `jq` | oficial | Manejo de JSON en los scripts de shell |
| `xorg-xrandr` | oficial | Detectar monitores conectados |

Instalacion con `paru` (o `yay`):

```bash
paru -S linux-wallpaperengine-git steamcmd
sudo pacman -S python-gobject gtk3 python-pillow jq xorg-xrandr
```

Ademas necesitas tener **Wallpaper Engine** (app 431960) instalada en Steam (es de pago,
~4€) y al menos un wallpaper suscrito desde el Workshop, o usar la busqueda integrada de
esta app para descargar uno.

## Instalacion

```bash
git clone <url-de-este-repo> ~/wallpaperengine-picker-api
cd ~/wallpaperengine-picker-api
./install.sh
```

`install.sh`:

- Comprueba que las dependencias esten instaladas.
- Crea symlinks de `bin/wallpaperengine-apply` y `bin/wallpaperengine-picker` en
  `~/.local/bin` (asegurate de que este directorio este en tu `PATH`).
- Crea un lanzador en el menu de aplicaciones: **"Elegir Fondo (Wallpaper Engine)"**.
- Crea una entrada de autostart de KDE que reaplica la ultima configuracion al iniciar
  sesion (solo si ya has aplicado un wallpaper al menos una vez).

Para actualizar despues de hacer `git pull`, no hace falta reinstalar nada: los symlinks
apuntan al repo.

## Uso

Lanza la app desde el menu de aplicaciones o con:

```bash
wallpaperengine-picker
```

- **Buscar / Etiqueta / Clasificacion**: filtran la lista de wallpapers ya descargados.
- **Configurando pantalla**: elige a que monitor se aplicara el siguiente wallpaper que
  selecciones (cada monitor puede tener uno distinto).
- Doble clic en un wallpaper (o boton "Asignar a esta pantalla") lo aplica de inmediato al
  monitor seleccionado, sin afectar a los demas.
- **Refrescar lista**: vuelve a leer la carpeta de Workshop (por si suscribiste algo nuevo
  desde Steam).
- **Buscar en Workshop (API)**: abre una ventana para buscar wallpapers directamente en el
  Workshop de Steam y descargarlos con `steamcmd`. La primera vez pedira tu Steam Web API
  Key (ver abajo).
- **Mostrar ocultos** / **Ocultar/Mostrar**: oculta wallpapers que no quieras ver en la lista
  (por ejemplo, uno que no renderiza bien) sin borrarlos del disco. Se guardan en
  `hidden.json`; activa "Mostrar ocultos" para volver a verlos (marcados como "[Oculto]") y
  poder deshacerlo.
- **Rotacion...**: abre la ventana de listas de rotacion (ver seccion siguiente).

### Rotacion automatica de wallpapers

Cada pantalla puede tener, en vez de un unico wallpaper fijo, una lista de wallpapers que
van rotando solos cada cierto tiempo:

1. Pulsa **"Rotacion..."**, elige la pantalla a configurar.
2. Anade wallpapers desde "Disponibles" a "Orden de rotacion" (boton "Anadir"), reordena con
   "Subir"/"Bajar" y quita los que no quieras con "Quitar".
3. Marca "Activar rotacion en esta pantalla" y ajusta el intervalo en minutos.
4. Pulsa "Guardar y aplicar": aplica el primer wallpaper de la lista de inmediato y guarda la
   configuracion en `~/.config/wallpaperengine-picker/playlists.json`.

Un demonio en segundo plano (`wallpaperengine-rotate`, instalado por `install.sh` como
autostart de KDE) revisa cada 30 segundos si toca avanzar alguna pantalla a su siguiente
wallpaper, asi que la rotacion sigue funcionando aunque cierres la ventana principal.
Asignar manualmente un wallpaper fijo a una pantalla (fuera de la ventana de rotacion)
desactiva automaticamente su rotacion, para que no se pisen entre si.

### Configurar la Steam Web API Key

La busqueda en el Workshop usa la API publica de Steam (`IPublishedFileService/QueryFiles`),
que requiere una API key gratuita asociada a tu cuenta:

1. Ve a <https://steamcommunity.com/dev/apikey> y genera una key (como dominio puedes poner
   `localhost`).
2. Pegala cuando la app te la pida al abrir "Buscar en Workshop (API)", **o** guardala tu
   mismo sin que pase por ningun chat/terminal compartido:

   ```bash
   mkdir -p ~/.config/wallpaperengine-picker
   python3 - <<'EOF'
   import json, os, getpass
   p = os.path.expanduser('~/.config/wallpaperengine-picker/config.json')
   cfg = json.load(open(p)) if os.path.exists(p) else {}
   cfg['steam_api_key'] = getpass.getpass('Pega tu Steam Web API Key: ').strip()
   json.dump(cfg, open(p, 'w'), indent=2)
   os.chmod(p, 0o600)
   print('Guardado.')
   EOF
   ```

La key se guarda en `~/.config/wallpaperengine-picker/config.json` (permisos `600`).

### Descarga via Workshop (como funciona por dentro)

La descarga usa `steamcmd` con login anonimo:

```bash
steamcmd +force_install_dir <tu_biblioteca_de_steam> \
         +login anonymous \
         +workshop_download_item 431960 <id_del_wallpaper> \
         +quit
```

Esto funciona para la mayoria del contenido del Workshop de Wallpaper Engine sin necesidad
de iniciar sesion con tu cuenta real. Si algun item en concreto no se puede descargar asi,
sigue pudiendo suscribirte a el desde el propio Steam (el boton "Refrescar lista" recogera
cualquier wallpaper que hayas suscrito por ese medio).

## Configuracion

Todo el estado vive en `~/.config/wallpaperengine-picker/`:

- `config.json`: ruta detectada de tu biblioteca de Steam (`steam_library`) y tu API key
  (`steam_api_key`). Si tienes varias bibliotecas de Steam, edita `steam_library` a mano si
  la deteccion automatica elige la que no es.
- `current.json`: ultima asignacion aplicada, `{ "NOMBRE_PANTALLA": "id_wallpaper", ... }`.
  Es lo que usa el autostart para restaurar tu configuracion al iniciar sesion.
- `wallpaperengine_PANTALLA.log` y `pid_PANTALLA.pid` (uno por cada monitor): salida y PID del
  proceso `linux-wallpaperengine` de esa pantalla (util para ver por que un wallpaper concreto
  no carga o hace crashear el motor).
- `hidden.json`: lista de ids de wallpapers ocultos.
- `playlists.json`: listas de rotacion por pantalla, `{ "PANTALLA": {"enabled": bool,
  "interval_minutes": N, "items": [id, ...], "current_index": N, "last_switch": epoch} }`.
  La edita la ventana "Rotacion..." y la lee el demonio `wallpaperengine-rotate`.

Las miniaturas se cachean en `~/.cache/wallpaperengine-picker/` (se pueden borrar sin
problema, se regeneran solas).

## Notas y limitaciones

- Cada pantalla corre en su **propio proceso** `linux-wallpaperengine` (PID guardado en
  `~/.config/wallpaperengine-picker/pid_PANTALLA.pid`, log en `wallpaperengine_PANTALLA.log`).
  Esto aisla los fallos: algunas escenas del Workshop hacen crashear el motor (excepciones
  C++ no capturadas al parsear un `scene.json` incompatible); con procesos separados, solo se
  cae la pantalla afectada y las demas siguen funcionando. Cambiar el wallpaper de una
  pantalla solo reinicia el proceso de esa pantalla, sin tocar las demas.
- El escalado se fija en `fill` + `clamp border`, que suele evitar bordes negros o
  estiramientos raros en la mayoria de resoluciones. Si un wallpaper en concreto se ve mal,
  puede deberse a que la escena en si no esta pensada para tu resolucion/aspecto.
- Probado sobre Wayland (KWin) usando XWayland para `xrandr`; en un compositor puramente
  wlroots (Sway, Hyprland...) puedes pasar `--layer background` a `linux-wallpaperengine`
  directamente si lo necesitas (no expuesto aun en la interfaz).

## Licencia

MIT. `linux-wallpaperengine` tiene su propia licencia (ver su repositorio); el contenido del
Workshop pertenece a sus respectivos autores.
