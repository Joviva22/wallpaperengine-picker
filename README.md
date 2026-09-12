# wallpaperengine-picker-api

Selector grafico de fondos de pantalla animados para Linux, basado en
[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine), con:

> Existe una version hermana sin dependencias externas (sin API ni `steamcmd`), que abre el
> Workshop en el propio Steam para suscribirte: [wallpaperengine-picker-local](https://github.com/Joviva22/wallpaperengine-picker-local).

- Interfaz con **sidebar + cuadricula + panel de detalle** (Biblioteca / Favoritos / Recientes
  / Animados / Ocultos / Workshop), miniaturas reales en 16:9, y una tarjeta por wallpaper con
  favorito, insignias y acciones al pasar el raton.
- Asignacion de un wallpaper **distinto por cada monitor**, con vista previa grande, menu
  contextual, y atajos de teclado.
- Filtros combinables por titulo, etiqueta (Y) y clasificacion de contenido (O) — Everyone /
  Questionable / Mature.
- Busqueda y descarga de nuevos wallpapers **directamente desde el Workshop de Steam**, usando
  la Steam Web API y `steamcmd` (sin necesidad de abrir el cliente de Steam), con la misma
  interfaz de sidebar/cuadricula/detalle.
- Favoritos y "Recientes" (historial de lo ultimo aplicado), ocultar sin borrar, y
  desuscribirse (borra local + opcion de completar el unsubscribe real en Steam).
- Rotacion automatica de wallpapers por pantalla (con presets de intervalo, rellenar con
  favoritos, orden aleatorio) mediante un demonio en segundo plano.
- Icono de bandeja del sistema con accesos rapidos, y deteccion automatica de wallpapers que
  hacen crashear el motor.
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
| `libayatana-appindicator` | oficial | Icono de bandeja (opcional; sin ella cae a `Gtk.StatusIcon`) |

Instalacion con `paru` (o `yay`):

```bash
paru -S linux-wallpaperengine-git steamcmd
sudo pacman -S python-gobject gtk3 python-pillow jq xorg-xrandr
```

Ademas necesitas tener **Wallpaper Engine** (app 431960) instalada en Steam (es de pago,
~4€) y al menos un wallpaper suscrito desde el Workshop, o usar la busqueda integrada de
esta app para descargar uno.

## Estructura del proyecto

```
bin/
  wallpaperengine-picker       # lanzador delgado (resuelve el repo y llama a wpelib)
  wallpaperengine-apply        # aplica wallpapers, un proceso por pantalla
  wallpaperengine-rotate       # demonio de rotacion automatica
  wallpaperengine-tray         # icono de bandeja
  wallpaperengine-common.sh    # deteccion de la biblioteca de Steam (bash)
wpelib/                        # la app en Python, en modulos:
  config.py                    # config, deteccion de Steam, estado persistido
  steam_api.py                 # busqueda/descarga via Steam Web API + steamcmd
  ui.py                        # tema CSS y widgets reutilizables
  workshop_window.py           # ventana de busqueda del Workshop
  playlist_window.py           # ventana de listas de rotacion
  main_window.py               # ventana principal
```

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

Lanza la app desde el menu de aplicaciones ("Elegir Fondo (Wallpaper Engine)") o con:

```bash
wallpaperengine-picker
```

La ventana principal ("Fondos de pantalla") se organiza en tres zonas:

### Sidebar (izquierda)

- **Biblioteca / Favoritos / Recientes / Animados / Ocultos**: pestañas de navegacion.
  Biblioteca es la vista por defecto (todo lo descargado, sin lo oculto); Animados filtra a
  wallpapers de tipo Video o Web (los unicos que Wallpaper Engine garantiza que se mueven —
  una escena "Scene" puede o no tener movimiento y no hay forma fiable de saberlo de
  antemano).
- **Workshop**: abre la ventana de busqueda del Workshop (ver mas abajo).
- **Monitores**: lista de pantallas conectadas, cada una con el titulo del wallpaper que
  tiene puesto ahora mismo. Clicar una la marca como "pantalla activa" (a la que se aplicara
  el siguiente wallpaper que elijas); lo mismo hacen los chips "MONITOR ACTIVO" arriba del
  todo en el panel central.
- **Ajustes**: muestra la ruta detectada de tu biblioteca de Steam y donde se cachean las
  miniaturas.

### Panel central

- Buscador grande (`Ctrl+F` o `Ctrl+K` le da el foco, `Esc` lo vacia), un boton **"Filtros
  (N)"** que despliega etiquetas (deben coincidir todas) y clasificacion (basta una), y un
  combo de orden.
- Cada tarjeta muestra la miniatura en 16:9, un corazon de favorito, una insignia si esta
  oculta o si crasheo el motor ("[⚠ Fallo conocido]"), y un check morado si es el wallpaper
  actual de la pantalla activa. Al pasar el raton aparecen botones de vista previa y asignar
  directamente sobre la miniatura; hay tambien un boton "..." que abre el mismo menu que el
  clic derecho (asignar a cada monitor, favorito, vista previa, anadir a rotacion,
  ocultar/mostrar, desuscribirse).
- Doble clic en una tarjeta la aplica de inmediato a la pantalla activa.
- Puedes seleccionar **varios wallpapers a la vez** (Ctrl+clic o arrastrando) y usar el menu
  de acciones en lote (icono "⋮" de la barra inferior) para ocultarlos/desuscribirlos juntos;
  `Supr` oculta la seleccion actual.
- Barra inferior: contador de resultados/seleccion, **"Mostrar ocultos"** (los incluye tambien
  dentro de "Biblioteca", ademas de en su propia pestaña), **"Rotacion"**, el menu de acciones
  en lote, y **"Actualizar"** (vuelve a leer la carpeta del Workshop, por si suscribiste algo
  nuevo desde Steam).

### Panel de detalle (derecha)

Se despliega al seleccionar una tarjeta: vista previa grande, titulo, favorito, botones
"Asignar a `<pantalla activa>`" / "Vista previa" / "Anadir a rotacion" / "Ocultar" /
"Desuscribirse", y una seccion de informacion (tipo, categorias, clasificacion, fecha de
descarga) con las etiquetas del wallpaper debajo.

### Buscar en el Workshop

La ventana de busqueda ("Workshop" en la sidebar) usa el mismo lenguaje visual: sidebar con
Etiquetas (deben coincidir todas), Clasificacion y Popularidad (Todo el tiempo / Hoy / Semana
/ Mes / Medio año / Año — mas votados o en tendencia segun la que elijas), un buscador grande
con paginacion junto a el, y una cuadricula de tarjetas identica a la de la biblioteca. El
tamaño del archivo y si ya lo tienes descargado se muestran como texto/insignia separados del
titulo (no mezclados como antes). Al seleccionar un resultado se abre el panel de detalle con
**"Ir a Steam"** (accion principal — deja que tu cuenta real se encargue, mas fiable) y
**"Descargar"** (usa `steamcmd` con login anonimo, ver mas abajo); tambien puedes marcar
resultados como favoritos antes de descargarlos. La pagina siguiente se precarga en segundo
plano para que "Pagina siguiente" sea practicamente instantaneo.

### Icono de bandeja

`wallpaperengine-tray` (autostart) añade un icono a la bandeja del sistema con accesos
rapidos sin abrir la ventana completa: wallpaper aleatorio por pantalla, pausar/reanudar la
rotacion automatica, y un enlace para abrir el selector completo. Usa
`libayatana-appindicator` si esta disponible; si no, cae a `Gtk.StatusIcon` (puede no
mostrarse en todos los escritorios).

### Desuscribirse y borrar

"Desuscribirse" borra el contenido local (y su cache de miniaturas) de los wallpapers
seleccionados y los quita de cualquier lista de rotacion. El login anonimo que usa la
descarga por API **no puede** desuscribir tu cuenta real de Steam (esa suscripcion vive en
el servidor, ligada a tu cuenta), asi que el dialogo te deja elegir "Borrar y abrir en
Steam" para completar el desuscribir de verdad alli si no quieres que se vuelva a
sincronizar mas adelante.

### Deteccion de wallpapers problematicos

Algunas escenas del Workshop hacen que `linux-wallpaperengine` termine con una excepcion
C++ no capturada (o un segfault) al intentar renderizarlas. Cada vez que se aplica un
wallpaper, `wallpaperengine-apply` vigila el proceso durante unos segundos: si muere con una
de esas señales tipicas, guarda el id en `known_bad.json` y la app lo marca como
"[⚠ Fallo conocido]" tanto en la lista local como en los resultados del Workshop. Si vuelves
a probar ese mismo id y esta vez no crashea, la marca se quita sola.

### Rotacion automatica de wallpapers

Cada pantalla puede tener, en vez de un unico wallpaper fijo, una lista de wallpapers que
van rotando solos cada cierto tiempo:

1. Pulsa **"Rotacion"** (barra inferior), elige la pantalla a configurar.
2. Anade wallpapers desde "Disponibles" a "Orden de rotacion" (boton "Anadir"), reordena con
   "Subir"/"Bajar" y quita los que no quieras con "Quitar". "Rellenar con favoritos" anade de
   golpe todo lo que tengas marcado con corazon; "Aleatorizar orden" baraja la lista actual.
3. Marca "Activar rotacion en esta pantalla" y ajusta el intervalo en minutos (o usa uno de
   los presets: 15 min / 30 min / 1 hora / 1 dia).
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
2. Pegala cuando la app te la pida al abrir "Workshop" desde la sidebar, **o** guardala tu
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
sigue pudiendo suscribirte a el desde el propio Steam (el boton "Actualizar" de la ventana
principal recogera cualquier wallpaper que hayas suscrito por ese medio).

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
- `favorites.json`: lista de ids marcados con favorito (compartida entre la biblioteca local
  y los resultados del Workshop).
- `recents.json`: ids aplicados recientemente, mas reciente primero (hasta 100), para la
  pestaña "Recientes".
- `ui_state.json`: pestaña, orden y filtro de clasificacion activos, y la pantalla activa —
  se restauran solos al reabrir la app.
- `playlists.json`: listas de rotacion por pantalla, `{ "PANTALLA": {"enabled": bool,
  "interval_minutes": N, "items": [id, ...], "current_index": N, "last_switch": epoch} }`.
  La edita la ventana "Rotacion..." y la lee el demonio `wallpaperengine-rotate`.
- `known_bad.json`: ids que hicieron crashear el motor, `{ "id": {"screen": ..., "detected_at":
  ...} }`. La escribe `wallpaperengine-apply`, la lee la app para marcarlos en la lista.
- `rotation_paused`: si existe (archivo vacio), el demonio de rotacion no avanza ninguna
  pantalla. Lo crea/borra el icono de bandeja al pulsar "Pausar/Reanudar rotacion".

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
- La pestaña "Animados" solo detecta tipos `Video`/`Web`; una escena `Scene` puede tener
  movimiento (parallax, particulas...) y no aparecera ahi porque `project.json` no expone
  ningun flag fiable de estatico/animado para ese tipo.
- No hay alternancia real cuadricula/lista, las etiquetas del panel de detalle son de solo
  lectura, y no se muestra la resolucion del wallpaper (Wallpaper Engine no la expone de
  forma fiable en `project.json`). La ventana no tiene una barra de titulo/logo propios;
  usa la del gestor de ventanas.

## Roadmap de diseño

La interfaz sigue el rediseño propuesto en [`docs/Mejoras.md`](docs/Mejoras.md) (ventana
principal: sidebar, cuadricula de tarjetas, panel de detalle) y en
[`docs/WorkShop.md`](docs/WorkShop.md) (misma distribucion aplicada a la busqueda del
Workshop). Las desviaciones conocidas respecto a esas propuestas estan listadas en "Notas y
limitaciones" arriba.

## Licencia

MIT. `linux-wallpaperengine` tiene su propia licencia (ver su repositorio); el contenido del
Workshop pertenece a sus respectivos autores.
