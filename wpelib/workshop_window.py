"""Ventana de busqueda y descarga de wallpapers del Workshop de Steam via API.
Sidebar de filtros (etiquetas/clasificacion/popularidad) + cuadricula de
tarjetas (reutiliza WallpaperCard del panel principal) + panel de detalle a
la derecha, siguiendo el mismo lenguaje visual que la ventana principal
(ver docs/WorkShop.md)."""
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gdk

from .config import CONFIG, save_config, THUMB_SIZE, load_known_bad, load_favorite_ids, save_favorite_ids
from .steam_api import (
    SteamApiError, steam_api_search_multi, download_workshop_thumb, download_workshop_item,
    verify_workshop_download, format_size, KNOWN_TAGS, RATING_TAGS, POPULARITY_OPTIONS,
    is_already_downloaded,
)
from .ui import icon_button, open_in_steam, CheckListButton, WallpaperCard


class WorkshopBrowserWindow(Gtk.Window):
    def __init__(self, on_downloaded):
        super().__init__(title="Buscar en el Workshop de Wallpaper Engine")
        self.set_default_size(1300, 820)
        self.on_downloaded = on_downloaded
        self.results = []
        self.cards = {}
        self.tags_by_id = {}
        self.rating_by_id = {}
        self.filesize_by_id = {}
        self.title_by_id = {}
        self.favorite_ids = load_favorite_ids()
        self.known_bad = load_known_bad()
        self.per_page = 50
        self.current_page = 1
        self.total_results = 0
        self.last_search = None
        self.page_cache = {}
        self.prefetching = set()
        self._selected_wid = None
        self.placeholder_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, *THUMB_SIZE)
        self.placeholder_pixbuf.fill(0x2f3140ff)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(root)

        root.pack_start(self._build_sidebar(), False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_border_width(14)
        root.pack_start(content, True, True, 0)

        content.pack_start(self._build_header(), False, False, 0)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.flowbox.set_activate_on_single_click(False)
        self.flowbox.set_row_spacing(14)
        self.flowbox.set_column_spacing(14)
        self.flowbox.set_homogeneous(True)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        scrolled.add(self.flowbox)
        content.pack_start(scrolled, True, True, 0)

        content.pack_start(self._build_footer(), False, False, 0)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_buffer = self.log_view.get_buffer()
        log_scrolled = Gtk.ScrolledWindow()
        log_scrolled.set_size_request(-1, 100)
        log_scrolled.set_shadow_type(Gtk.ShadowType.IN)
        log_scrolled.add(self.log_view)
        content.pack_start(log_scrolled, False, False, 0)

        self.detail_revealer = Gtk.Revealer()
        self.detail_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.detail_revealer.set_transition_duration(180)
        self.detail_revealer.add(self._build_detail_panel())
        root.pack_start(self.detail_revealer, False, False, 0)

    # -- Construccion de la interfaz ------------------------------------------

    def _build_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.set_size_request(220, -1)
        sidebar.set_border_width(12)
        sidebar.get_style_context().add_class("wpe-sidebar")

        self.tag_filter = CheckListButton("Etiquetas", KNOWN_TAGS)
        sidebar.pack_start(self.tag_filter, False, False, 0)

        sidebar.pack_start(Gtk.Separator(), False, False, 8)
        rating_title = Gtk.Label(label="CLASIFICACION", xalign=0)
        rating_title.get_style_context().add_class("wpe-detail-section-title")
        sidebar.pack_start(rating_title, False, False, 0)

        self.rating_checks = {}
        for opt in RATING_TAGS:
            cb = Gtk.CheckButton(label=opt)
            cb.set_active(opt == "Everyone")
            sidebar.pack_start(cb, False, False, 0)
            self.rating_checks[opt] = cb

        sidebar.pack_start(Gtk.Separator(), False, False, 8)
        pop_title = Gtk.Label(label="POPULARIDAD", xalign=0)
        pop_title.get_style_context().add_class("wpe-detail-section-title")
        sidebar.pack_start(pop_title, False, False, 0)

        self.popularity_radios = {}
        first = None
        for option in POPULARITY_OPTIONS:
            rb = (
                Gtk.RadioButton.new_with_label_from_widget(first, option)
                if first else Gtk.RadioButton.new_with_label(None, option)
            )
            if first is None:
                first = rb
            rb.set_active(option == "Mas votados (todo el tiempo)")
            sidebar.pack_start(rb, False, False, 0)
            self.popularity_radios[option] = rb

        sidebar.pack_start(Gtk.Box(), True, True, 0)
        return sidebar

    def _build_header(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar en el Workshop... (Enter para buscar, vacio = mas votados)")
        self.search_entry.get_style_context().add_class("wpe-search-big")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search_clicked)
        box.pack_start(self.search_entry, True, True, 0)

        search_btn = Gtk.Button()
        search_btn.set_image(Gtk.Image.new_from_icon_name("system-search-symbolic", Gtk.IconSize.BUTTON))
        search_btn.set_tooltip_text("Buscar")
        search_btn.get_style_context().add_class("suggested-action")
        search_btn.connect("clicked", self.on_search_clicked)
        box.pack_start(search_btn, False, False, 0)

        self.prev_btn = Gtk.Button()
        self.prev_btn.set_image(Gtk.Image.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON))
        self.prev_btn.set_tooltip_text("Pagina anterior")
        self.prev_btn.connect("clicked", self.on_prev_page)
        self.prev_btn.set_sensitive(False)
        box.pack_start(self.prev_btn, False, False, 0)

        self.page_label = Gtk.Label(label="")
        box.pack_start(self.page_label, False, False, 0)

        self.next_btn = Gtk.Button()
        self.next_btn.set_image(Gtk.Image.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON))
        self.next_btn.set_tooltip_text("Pagina siguiente")
        self.next_btn.connect("clicked", self.on_next_page)
        self.next_btn.set_sensitive(False)
        box.pack_start(self.next_btn, False, False, 0)

        return box

    def _build_footer(self):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.status_label = Gtk.Label(label="Escribe algo y pulsa buscar, o busca directamente para ver los mas votados.")
        self.status_label.set_halign(Gtk.Align.START)
        box.pack_start(self.status_label, True, True, 0)
        return box

    def _build_detail_panel(self):
        panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        panel.set_size_request(300, -1)
        panel.set_border_width(14)
        panel.get_style_context().add_class("wpe-detail-panel")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        close_btn = Gtk.Button()
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_image(Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON))
        close_btn.connect("clicked", lambda *_: self.flowbox.unselect_all())
        top_row.pack_end(close_btn, False, False, 0)
        panel.pack_start(top_row, False, False, 0)

        self.detail_image = Gtk.Image()
        panel.pack_start(self.detail_image, False, False, 0)

        self.detail_title = Gtk.Label(xalign=0)
        self.detail_title.set_line_wrap(True)
        self.detail_title.get_style_context().add_class("wpe-detail-title")
        panel.pack_start(self.detail_title, False, False, 0)

        self.detail_open_steam_btn = icon_button("Ir a Steam", "applications-internet")
        self.detail_open_steam_btn.get_style_context().add_class("suggested-action")
        self.detail_open_steam_btn.connect("clicked", self._on_detail_open_steam)
        panel.pack_start(self.detail_open_steam_btn, False, False, 0)

        self.detail_download_btn = icon_button("Descargar", "emblem-downloads")
        self.detail_download_btn.connect("clicked", self._on_detail_download)
        panel.pack_start(self.detail_download_btn, False, False, 0)

        panel.pack_start(Gtk.Separator(), False, False, 6)

        info_title = Gtk.Label(label="INFORMACION", xalign=0)
        info_title.get_style_context().add_class("wpe-detail-section-title")
        panel.pack_start(info_title, False, False, 0)

        self.detail_info_grid = Gtk.Grid()
        self.detail_info_grid.set_row_spacing(4)
        self.detail_info_grid.set_column_spacing(10)
        panel.pack_start(self.detail_info_grid, False, False, 0)

        tags_title = Gtk.Label(label="ETIQUETAS", xalign=0)
        tags_title.get_style_context().add_class("wpe-detail-section-title")
        panel.pack_start(tags_title, False, False, 8)

        self.detail_tags_box = Gtk.FlowBox()
        self.detail_tags_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.detail_tags_box.set_max_children_per_line(4)
        self.detail_tags_box.set_min_children_per_line(1)
        panel.pack_start(self.detail_tags_box, False, False, 0)

        return panel

    # -- Filtros (sidebar) -----------------------------------------------------

    def get_selected_ratings(self):
        return [opt for opt, cb in self.rating_checks.items() if cb.get_active()]

    def get_selected_popularity(self):
        for option, rb in self.popularity_radios.items():
            if rb.get_active():
                return option
        return "Mas votados (todo el tiempo)"

    # -- API key ----------------------------------------------------------------

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

    # -- Busqueda y paginacion ---------------------------------------------------

    def on_search_clicked(self, *args):
        api_key = self.get_api_key()
        if not api_key:
            self.status_label.set_text("Necesitas una API key para buscar en el Workshop.")
            return
        query = self.search_entry.get_text().strip()
        required_tags = self.tag_filter.get_selected()
        ratings = self.get_selected_ratings()
        popularity_choice = self.get_selected_popularity()
        query_type, days = POPULARITY_OPTIONS.get(popularity_choice, (0, None))
        if query and popularity_choice != "Mas votados (todo el tiempo)":
            self.status_label.set_text("Buscando (la popularidad por periodo se ignora al buscar por texto)...")

        self.last_search = {
            "api_key": api_key, "query": query, "required_tags": required_tags,
            "ratings": ratings, "query_type": query_type, "days": days,
        }
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
        for child in list(self.flowbox.get_children()):
            self.flowbox.remove(child)
        self.cards = {}
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

        for child in list(self.flowbox.get_children()):
            self.flowbox.remove(child)
        self.cards = {}

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

            subtitle_parts = [format_size(item.get("file_size"))]
            if item_tags:
                subtitle_parts.append(item_tags[0])
            subtitle = " · ".join(subtitle_parts)

            badge = None
            if wid in self.known_bad:
                badge = "⚠ Fallo conocido"
            elif is_already_downloaded(wid):
                badge = "Ya la tienes"

            card = WallpaperCard(
                wid, title, subtitle, pixbuf,
                favorite=wid in self.favorite_ids, badge=badge,
            )
            card.on_assign = self.start_download
            card.on_preview = self._select_wid
            card.on_toggle_favorite = self.on_card_favorite_toggled
            card.on_context_menu = self.show_context_menu
            self.flowbox.add(card)
            self.cards[wid] = card

        self.flowbox.show_all()

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
            self._populate_results(total, results, page)
        return False

    def on_prev_page(self, button):
        if self.current_page > 1:
            self.run_search(self.current_page - 1)

    def on_next_page(self, button):
        self.run_search(self.current_page + 1)

    # -- Seleccion y panel de detalle --------------------------------------------

    def get_selected_ids(self):
        return [child.get_child().wid for child in self.flowbox.get_selected_children()]

    def on_selection_changed(self, flowbox):
        ids = self.get_selected_ids()
        if len(ids) == 1:
            self._select_wid(ids[0])
        else:
            self._selected_wid = None
            self.detail_revealer.set_reveal_child(False)
        for wid, card in self.cards.items():
            card.set_assigned(wid == self._selected_wid)

    def _select_wid(self, wid):
        self._selected_wid = wid
        card = self.cards.get(wid)
        if card:
            child = card.get_parent()
            if child and not child.is_selected():
                self.flowbox.select_child(child)
        self._update_detail_panel(wid)

    def _update_detail_panel(self, wid):
        title = self.title_by_id.get(wid, wid)
        card = self.cards.get(wid)
        pixbuf = card.image.get_pixbuf() if card else self.placeholder_pixbuf
        self.detail_image.set_from_pixbuf(pixbuf)
        self.detail_title.set_text(title)

        for child in list(self.detail_info_grid.get_children()):
            self.detail_info_grid.remove(child)
        rows = [
            ("Tamano", format_size(self.filesize_by_id.get(wid))),
            ("Clasificacion", self.rating_by_id.get(wid, "Desconocido")),
            ("Ya la tienes", "Si" if is_already_downloaded(wid) else "No"),
        ]
        for i, (label, value) in enumerate(rows):
            l1 = Gtk.Label(label=label, xalign=0)
            l1.get_style_context().add_class("dim-label")
            l2 = Gtk.Label(label=str(value), xalign=0)
            l2.set_line_wrap(True)
            self.detail_info_grid.attach(l1, 0, i, 1, 1)
            self.detail_info_grid.attach(l2, 1, i, 1, 1)
        self.detail_info_grid.show_all()

        for child in list(self.detail_tags_box.get_children()):
            self.detail_tags_box.remove(child)
        for tag in self.tags_by_id.get(wid, []):
            chip = Gtk.Label(label=tag)
            chip.get_style_context().add_class("wpe-tag-chip")
            self.detail_tags_box.add(chip)
        self.detail_tags_box.show_all()

        self.detail_download_btn.set_sensitive(not is_already_downloaded(wid))
        self.detail_revealer.set_reveal_child(True)

    def on_card_favorite_toggled(self, wid, is_favorite):
        if is_favorite:
            self.favorite_ids.add(wid)
        else:
            self.favorite_ids.discard(wid)
        save_favorite_ids(self.favorite_ids)

    def show_context_menu(self, card, event, wid):
        menu = Gtk.Menu()

        dl_item = Gtk.MenuItem(label="Descargar")
        dl_item.connect("activate", lambda *_: self.start_download(wid))
        menu.append(dl_item)

        steam_item = Gtk.MenuItem(label="Ir a Steam")
        steam_item.connect("activate", lambda *_: self._open_in_steam(wid))
        menu.append(steam_item)

        menu.append(Gtk.SeparatorMenuItem())

        fav_item = Gtk.CheckMenuItem(label="Favorito")
        fav_item.set_active(wid in self.favorite_ids)
        fav_item.connect("toggled", lambda mi: card.heart_btn.set_active(mi.get_active()))
        menu.append(fav_item)

        menu.show_all()
        if event is not None:
            menu.popup_at_pointer(event)
        else:
            menu.popup_at_widget(card.menu_btn, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, None)

    # -- Descarga -----------------------------------------------------------------

    def _on_detail_open_steam(self, button):
        if self._selected_wid:
            self._open_in_steam(self._selected_wid)

    def _open_in_steam(self, wid):
        open_in_steam(wid)
        self.status_label.set_text(f"Abriendo '{self.title_by_id.get(wid, wid)}' en Steam...")

    def _on_detail_download(self, button):
        if self._selected_wid:
            self.start_download(self._selected_wid)

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
            card = self.cards.get(wid)
            if card:
                card.set_badge("Ya la tienes")
            if wid == self._selected_wid:
                self.detail_download_btn.set_sensitive(False)
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
            self._open_in_steam(wid)
            self.status_label.set_text("Abriendo el item en Steam. Suscribete y luego pulsa 'Refrescar lista' en la ventana principal.")
