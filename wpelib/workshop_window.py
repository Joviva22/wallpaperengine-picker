"""Ventana de busqueda y descarga de wallpapers del Workshop de Steam via API."""
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib

from .config import CONFIG, save_config, THUMB_SIZE, load_known_bad
from .steam_api import (
    SteamApiError, steam_api_search_multi, download_workshop_thumb, download_workshop_item,
    verify_workshop_download, format_size, KNOWN_TAGS, RATING_TAGS, POPULARITY_OPTIONS,
    is_already_downloaded,
)
from .ui import labeled_frame, icon_button, open_in_steam, CheckListButton

class WorkshopBrowserWindow(Gtk.Window):
    def __init__(self, on_downloaded):
        super().__init__(title="Buscar en el Workshop de Wallpaper Engine")
        self.set_default_size(1000, 750)
        self.set_border_width(12)
        self.on_downloaded = on_downloaded
        self.results = []
        self.tags_by_id = {}
        self.rating_by_id = {}
        self.filesize_by_id = {}
        self.title_by_id = {}
        self.known_bad = load_known_bad()
        self.per_page = 50
        self.current_page = 1
        self.total_results = 0
        self.last_search = None
        self.page_cache = {}
        self.prefetching = set()
        self.placeholder_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, *THUMB_SIZE)
        self.placeholder_pixbuf.fill(0x2f3140ff)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        search_frame = labeled_frame("Buscar en el Workshop")
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_box.set_border_width(8)
        search_frame.add(search_box)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Palabras clave (vacio = mas votados)...")
        self.search_entry.connect("activate", self.on_search_clicked)
        search_box.pack_start(self.search_entry, True, True, 0)

        self.tag_filter = CheckListButton("Etiquetas", KNOWN_TAGS)
        search_box.pack_start(self.tag_filter, False, False, 0)

        self.rating_filter = CheckListButton("Clasificacion", RATING_TAGS, initially_checked=["Everyone"])
        search_box.pack_start(self.rating_filter, False, False, 0)

        search_box.pack_start(Gtk.Label(label="Popularidad:"), False, False, 0)
        self.popularity_combo = Gtk.ComboBoxText()
        for option in POPULARITY_OPTIONS:
            self.popularity_combo.append_text(option)
        self.popularity_combo.set_active(0)
        search_box.pack_start(self.popularity_combo, False, False, 0)

        search_btn = icon_button("Buscar", "system-search-symbolic")
        search_btn.get_style_context().add_class("suggested-action")
        search_btn.connect("clicked", self.on_search_clicked)
        search_box.pack_start(search_btn, False, False, 0)
        vbox.pack_start(search_frame, False, False, 0)

        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)  # pixbuf, title, id

        self.icon_view = Gtk.IconView(model=self.store)
        self.icon_view.set_pixbuf_column(0)
        self.icon_view.set_text_column(1)
        self.icon_view.set_item_width(THUMB_SIZE[0] + 20)
        self.icon_view.set_item_padding(6)
        self.icon_view.set_row_spacing(10)
        self.icon_view.set_column_spacing(10)
        self.icon_view.set_margin(8)
        self.icon_view.connect("item-activated", self.on_item_activated)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        scrolled.add(self.icon_view)
        vbox.pack_start(scrolled, True, True, 0)

        pagination_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pagination_box.set_halign(Gtk.Align.CENTER)
        self.prev_btn = icon_button("Pagina anterior", "go-previous-symbolic")
        self.prev_btn.connect("clicked", self.on_prev_page)
        self.prev_btn.set_sensitive(False)
        pagination_box.pack_start(self.prev_btn, False, False, 0)
        self.page_label = Gtk.Label(label="")
        pagination_box.pack_start(self.page_label, False, False, 0)
        self.next_btn = icon_button("Pagina siguiente", "go-next-symbolic")
        self.next_btn.set_image_position(Gtk.PositionType.RIGHT)
        self.next_btn.connect("clicked", self.on_next_page)
        self.next_btn.set_sensitive(False)
        pagination_box.pack_start(self.next_btn, False, False, 0)
        vbox.pack_start(pagination_box, False, False, 0)

        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(bottom_box, False, False, 0)
        self.status_label = Gtk.Label(label="Escribe algo y pulsa Buscar, o busca directamente para ver los mas votados.")
        self.status_label.set_halign(Gtk.Align.START)
        bottom_box.pack_start(self.status_label, True, True, 0)
        download_btn = icon_button("Descargar seleccionado", "emblem-downloads")
        download_btn.get_style_context().add_class("suggested-action")
        download_btn.connect("clicked", self.on_download_clicked)
        bottom_box.pack_end(download_btn, False, False, 0)

        open_steam_btn = icon_button("Ir a Steam", "applications-internet")
        open_steam_btn.connect("clicked", self.on_open_selected_in_steam)
        bottom_box.pack_end(open_steam_btn, False, False, 0)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_buffer = self.log_view.get_buffer()
        log_scrolled = Gtk.ScrolledWindow()
        log_scrolled.set_size_request(-1, 120)
        log_scrolled.add(self.log_view)
        vbox.pack_start(log_scrolled, False, False, 0)

    def get_api_key(self):
        key = CONFIG.get("steam_api_key")
        if key:
            return key
        dialog = Gtk.Dialog(title="Steam Web API Key requerida", transient_for=self, modal=True)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OK, Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_spacing(6)
        box.set_border_width(10)
        box.add(Gtk.Label(label="Genera una clave gratuita en:\nhttps://steamcommunity.com/dev/apikey\n(usa 'localhost' como dominio)"))
        entry = Gtk.Entry()
        entry.set_visibility(False)
        box.add(entry)
        dialog.show_all()
        response = dialog.run()
        key = entry.get_text().strip()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and key:
            CONFIG["steam_api_key"] = key
            save_config(CONFIG)
            return key
        return None

    def append_log(self, text):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text)
        self.log_view.scroll_to_iter(self.log_buffer.get_end_iter(), 0, False, 0, 0)

    def on_search_clicked(self, *args):
        api_key = self.get_api_key()
        if not api_key:
            self.status_label.set_text("Necesitas una API key para buscar en el Workshop.")
            return
        query = self.search_entry.get_text().strip()
        required_tags = self.tag_filter.get_selected()
        ratings = self.rating_filter.get_selected()
        popularity_choice = self.popularity_combo.get_active_text()
        query_type, days = POPULARITY_OPTIONS.get(popularity_choice, (0, None))
        if query and popularity_choice != "Mas votados (todo el tiempo)":
            self.status_label.set_text("Buscando (la popularidad por periodo se ignora al buscar por texto)...")

        self.last_search = {
            "api_key": api_key, "query": query, "required_tags": required_tags,
            "ratings": ratings, "query_type": query_type, "days": days,
        }
        # Nueva busqueda: la cache de paginas de la busqueda anterior ya no vale.
        self.page_cache = {}
        self.prefetching = set()
        self.run_search(page=1)

    def run_search(self, page):
        if not self.last_search:
            return
        self.current_page = page

        if page in self.page_cache:
            total, results = self.page_cache[page]
            self._populate_results(total, results, page)
            return

        self.status_label.set_text(f"Buscando (pagina {page})...")
        self.store.clear()
        self.tags_by_id.clear()
        self.rating_by_id.clear()
        self.prev_btn.set_sensitive(False)
        self.next_btn.set_sensitive(False)
        params = dict(self.last_search)
        threading.Thread(target=self._search_thread, args=(params, page), daemon=True).start()

    def _search_thread(self, params, page):
        try:
            total, results = steam_api_search_multi(
                params["api_key"], params["query"],
                required_tags=params["required_tags"], ratings=params["ratings"],
                query_type=params["query_type"], days=params["days"],
                page=page, per_page=self.per_page,
            )
        except SteamApiError as e:
            GLib.idle_add(self.status_label.set_text, str(e))
            return
        GLib.idle_add(self._populate_results, total, results, page)

    def _populate_results(self, total, results, page):
        was_cached = page in self.page_cache
        self.page_cache[page] = (total, results)
        self.results = results
        self.total_results = total
        self.store.clear()
        for item in results:
            wid = item.get("publishedfileid", "")
            title = item.get("title", wid)
            preview_url = item.get("preview_url", "")
            item_tags = [t.get("tag", "") for t in item.get("tags", []) or []]
            self.tags_by_id[wid] = item_tags
            rating = next((r for r in RATING_TAGS if r in item_tags), "Desconocido")
            self.rating_by_id[wid] = rating
            self.filesize_by_id[wid] = item.get("file_size")
            self.title_by_id[wid] = title

            pixbuf = self.placeholder_pixbuf
            if preview_url:
                thumb_path = download_workshop_thumb(wid, preview_url)
                if thumb_path:
                    try:
                        pixbuf = GdkPixbuf.Pixbuf.new_from_file(thumb_path)
                    except Exception:
                        pixbuf = self.placeholder_pixbuf

            size_text = format_size(item.get("file_size"))
            display_title = f"{title} ({size_text})"
            if wid in self.known_bad:
                display_title = f"[⚠ Fallo conocido] {display_title}"
            if is_already_downloaded(wid):
                display_title = f"[Ya la tienes] {display_title}"
            self.store.append([pixbuf, display_title, wid])

        total_pages = max(1, -(-total // self.per_page)) if total else 1
        cached_note = " (precargada)" if was_cached else ""
        self.page_label.set_text(f"Pagina {page} de {total_pages} ({total} resultados)")
        self.prev_btn.set_sensitive(page > 1)
        self.next_btn.set_sensitive(page < total_pages)
        self.status_label.set_text(f"{len(results)} resultados en esta pagina{cached_note}")

        # Precarga la pagina siguiente en segundo plano (datos + miniaturas) para que
        # "Pagina siguiente" sea instantaneo cuando llegues a ella.
        if page < total_pages:
            self._prefetch_page(page + 1)
        return False

    def _prefetch_page(self, page):
        if page in self.page_cache or page in self.prefetching or not self.last_search:
            return
        self.prefetching.add(page)
        params = dict(self.last_search)
        threading.Thread(target=self._prefetch_thread, args=(params, page), daemon=True).start()

    def _prefetch_thread(self, params, page):
        try:
            total, results = steam_api_search_multi(
                params["api_key"], params["query"],
                required_tags=params["required_tags"], ratings=params["ratings"],
                query_type=params["query_type"], days=params["days"],
                page=page, per_page=self.per_page,
            )
        except SteamApiError:
            GLib.idle_add(self.prefetching.discard, page)
            return
        # Calienta la cache de miniaturas aqui mismo, en el hilo de fondo.
        for item in results:
            wid = item.get("publishedfileid", "")
            preview_url = item.get("preview_url", "")
            if preview_url:
                download_workshop_thumb(wid, preview_url)
        GLib.idle_add(self._store_prefetched, page, total, results)

    def _store_prefetched(self, page, total, results):
        self.page_cache[page] = (total, results)
        self.prefetching.discard(page)
        if page == self.current_page:
            # Si mientras se precargaba llegaste a esta pagina por otra via, muestrala.
            self._populate_results(total, results, page)
        return False

    def on_prev_page(self, button):
        if self.current_page > 1:
            self.run_search(self.current_page - 1)

    def on_next_page(self, button):
        self.run_search(self.current_page + 1)

    def get_selected_id(self):
        selected = self.icon_view.get_selected_items()
        if not selected:
            return None
        iter_ = self.store.get_iter(selected[0])
        return self.store[iter_][2]

    def on_item_activated(self, icon_view, path):
        iter_ = self.store.get_iter(path)
        wid = self.store[iter_][2]
        self.start_download(wid)

    def on_download_clicked(self, button):
        wid = self.get_selected_id()
        if not wid:
            self.status_label.set_text("Selecciona un wallpaper de los resultados primero")
            return
        self.start_download(wid)

    def on_open_selected_in_steam(self, button):
        wid = self.get_selected_id()
        if not wid:
            self.status_label.set_text("Selecciona un wallpaper de los resultados primero")
            return
        open_in_steam(wid)
        self.status_label.set_text(f"Abriendo '{self.title_by_id.get(wid, wid)}' en Steam...")

    def start_download(self, wid):
        title = self.title_by_id.get(wid, wid)
        size_text = format_size(self.filesize_by_id.get(wid))
        self.status_label.set_text(f"Descargando {title} ({size_text})...")
        self.append_log(f"\n--- Descargando {title} [{wid}] - {size_text} ---\n")
        threading.Thread(target=self._download_thread, args=(wid,), daemon=True).start()

    def _download_thread(self, wid):
        ok = download_workshop_item(wid, lambda line: GLib.idle_add(self.append_log, line))
        GLib.idle_add(self._download_done, wid, ok)

    def _download_done(self, wid, steamcmd_ok):
        title = self.title_by_id.get(wid, wid)
        verified, detail = verify_workshop_download(wid) if steamcmd_ok else (False, None)

        if verified:
            self.status_label.set_markup(f"<span foreground='#2ecc71'>Descarga confirmada: {GLib.markup_escape_text(title)}</span>")
            self.append_log(f"--- Verificado en disco: {title} listo para usar ---\n")
            self.show_result_dialog(
                Gtk.MessageType.INFO, "Descarga completada",
                f"'{title}' se descargo correctamente y ya esta disponible en la lista principal.",
            )
            if self.on_downloaded:
                self.on_downloaded()
        else:
            reason = "steamcmd no confirmo la descarga (revisa el log)" if not steamcmd_ok else detail
            self.status_label.set_markup(f"<span foreground='#e74c3c'>Fallo la descarga: {GLib.markup_escape_text(title)}</span>")
            self.append_log(f"--- Descarga fallida o no verificada: {reason} ---\n")
            self.show_failed_download_dialog(wid, title, reason)
        return False

    def show_result_dialog(self, message_type, title, text):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=message_type,
            buttons=Gtk.ButtonsType.OK, text=title,
        )
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()

    def show_failed_download_dialog(self, wid, title, reason):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.ERROR,
            text="La descarga no se pudo confirmar",
        )
        dialog.format_secondary_text(
            f"'{title}' no aparece instalado tras la descarga.\n\nMotivo: {reason}\n\n"
            "steamcmd con login anonimo a veces no puede descargar un item concreto (por ejemplo "
            "si necesita tu cuenta real). Puedes abrirlo en Steam y suscribirte ahi en su lugar."
        )
        dialog.add_buttons(
            "Abrir en Steam", Gtk.ResponseType.APPLY,
            Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE,
        )
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.APPLY:
            open_in_steam(wid)
            self.status_label.set_text("Abriendo el item en Steam. Suscribete y luego pulsa 'Refrescar lista' en la ventana principal.")
