"""Ventana principal: sidebar de navegacion (biblioteca/favoritos/recientes/
animados/ocultos/workshop + monitores), cuadricula de tarjetas de wallpapers
locales con filtros combinables, y panel de detalle a la derecha con la
informacion del wallpaper seleccionado."""
import datetime
import os
import subprocess
import threading

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Gdk, Pango

from .config import (
    load_wallpapers, detect_monitors, load_current_assignments, load_hidden_ids,
    save_hidden_ids, load_favorite_ids, save_favorite_ids, load_recent_ids, record_recent,
    load_known_bad, load_playlists, save_playlists, load_ui_state, save_ui_state,
    unsubscribe_workshop_item, build_thumb, SORT_OPTIONS, SORT_REVERSE, APPLY_SCRIPT,
    CACHE_DIR, STEAM_LIB,
)
from .ui import icon_button, open_in_steam, apply_css, WallpaperCard, CARD_SIZE
from .workshop_window import WorkshopBrowserWindow
from .playlist_window import PlaylistWindow

TABS = ["Todos", "Favoritos", "Recientes", "Animados", "Ocultos"]
TAB_LABELS = {
    "Todos": "Biblioteca", "Favoritos": "Favoritos", "Recientes": "Recientes",
    "Animados": "Animados", "Ocultos": "Ocultos",
}
TAB_ICONS = {
    "Todos": "image-x-generic-symbolic", "Favoritos": "starred-symbolic",
    "Recientes": "document-open-recent-symbolic", "Animados": "media-playback-start-symbolic",
    "Ocultos": "view-conceal-symbolic",
}


class FiltersMenuButton(Gtk.MenuButton):
    """Boton unico 'Filtros' con un popover que agrupa etiquetas (deben estar
    todas presentes) y clasificacion (basta con una) en checkboxes."""

    def __init__(self, tag_options, rating_options, on_change=None, initial_ratings=None):
        super().__init__()
        self.on_change = on_change
        self.tag_checks = {}
        self.rating_checks = {}

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(10)

        box.pack_start(Gtk.Label(label="Etiquetas", xalign=0), False, False, 0)
        self.tag_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.pack_start(self.tag_box, False, False, 0)

        box.pack_start(Gtk.Separator(), False, False, 4)

        box.pack_start(Gtk.Label(label="Clasificacion", xalign=0), False, False, 0)
        for opt in rating_options:
            cb = Gtk.CheckButton(label=opt)
            cb.set_active(initial_ratings is not None and opt in initial_ratings)
            cb.connect("toggled", self._on_toggled)
            box.pack_start(cb, False, False, 0)
            self.rating_checks[opt] = cb

        popover = Gtk.Popover()
        popover.add(box)
        self.set_popover(popover)

        self.set_tag_options(tag_options)
        box.show_all()

    def set_tag_options(self, options, checked=None):
        preserve = set(checked) if checked is not None else set(self.get_selected_tags())
        for child in list(self.tag_box.get_children()):
            self.tag_box.remove(child)
        self.tag_checks = {}
        for opt in options:
            cb = Gtk.CheckButton(label=opt)
            cb.set_active(opt in preserve)
            cb.connect("toggled", self._on_toggled)
            self.tag_box.pack_start(cb, False, False, 0)
            self.tag_checks[opt] = cb
        self.tag_box.show_all()
        self._update_label()

    def _on_toggled(self, cb):
        self._update_label()
        if self.on_change:
            self.on_change()

    def get_selected_tags(self):
        return [opt for opt, cb in self.tag_checks.items() if cb.get_active()]

    def get_selected_ratings(self):
        return [opt for opt, cb in self.rating_checks.items() if cb.get_active()]

    def _update_label(self):
        count = len(self.get_selected_tags()) + len(self.get_selected_ratings())
        self.set_label(f"Filtros ({count})" if count else "Filtros")


def _nav_content(icon_name, title, subtitle=None):
    content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    content.pack_start(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON), False, False, 0)
    subtitle_label = None
    if subtitle is not None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.pack_start(Gtk.Label(label=title, xalign=0), False, False, 0)
        subtitle_label = Gtk.Label(label=subtitle, xalign=0)
        subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
        subtitle_label.get_style_context().add_class("dim-label")
        vbox.pack_start(subtitle_label, False, False, 0)
        content.pack_start(vbox, True, True, 0)
    else:
        content.pack_start(Gtk.Label(label=title, xalign=0), True, True, 0)
    return content, subtitle_label


def make_nav_radio(group, icon_name, title, subtitle=None):
    btn = Gtk.RadioButton.new_from_widget(group) if group else Gtk.RadioButton.new(None)
    btn.set_mode(False)
    btn.get_style_context().add_class("wpe-nav-item")
    content, subtitle_label = _nav_content(icon_name, title, subtitle)
    btn.add(content)
    return btn, subtitle_label


def make_nav_button(icon_name, title):
    btn = Gtk.Button()
    btn.set_relief(Gtk.ReliefStyle.NONE)
    btn.get_style_context().add_class("wpe-nav-item")
    content, _ = _nav_content(icon_name, title)
    btn.add(content)
    return btn


class PickerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Fondos de pantalla")
        self.set_default_size(1400, 860)

        self.monitors = detect_monitors() or ["DP-2"]
        self.assignments = load_current_assignments(self.monitors)

        ui_state = load_ui_state()
        self.target_monitor = ui_state.get("target_monitor") if ui_state.get("target_monitor") in self.monitors else self.monitors[0]
        self.current_tab = ui_state.get("tab") if ui_state.get("tab") in TABS else "Todos"

        self.all_items = []
        self.items_by_id = {}
        self.cards = {}
        self.hidden_ids = load_hidden_ids()
        self.favorite_ids = load_favorite_ids()
        self.recent_ids = load_recent_ids()
        self.known_bad = load_known_bad()
        self.workshop_window = None
        self.playlist_window = None
        self._detail_wid = None
        self.placeholder_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, *CARD_SIZE)
        self.placeholder_pixbuf.fill(0x2f3140ff)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add(root)

        root.pack_start(self._build_sidebar(), False, False, 0)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_border_width(14)
        root.pack_start(content, True, True, 0)

        content.pack_start(self._build_header(ui_state), False, False, 0)
        content.pack_start(self._build_monitor_row(), False, False, 0)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        self.flowbox.set_activate_on_single_click(False)
        self.flowbox.set_row_spacing(14)
        self.flowbox.set_column_spacing(14)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_filter_func(self._filter_func)
        self.flowbox.set_sort_func(self._sort_func)
        self.flowbox.set_min_children_per_line(1)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.connect("selected-children-changed", self.on_selection_changed)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        scrolled.add(self.flowbox)
        content.pack_start(scrolled, True, True, 0)

        content.pack_start(self._build_bottom_bar(), False, False, 0)

        self.detail_revealer = Gtk.Revealer()
        self.detail_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.detail_revealer.set_transition_duration(180)
        self.detail_revealer.add(self._build_detail_panel())
        root.pack_start(self.detail_revealer, False, False, 0)

        self.connect("key-press-event", self.on_key_press)
        self.connect("destroy", self.on_destroy)

        GLib.idle_add(self.populate)

    # -- Construccion de la interfaz ------------------------------------------

    def _build_sidebar(self):
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.set_size_request(230, -1)
        sidebar.set_border_width(12)
        sidebar.get_style_context().add_class("wpe-sidebar")

        self.tab_buttons = {}
        first = None
        for key in TABS:
            btn, _ = make_nav_radio(first, TAB_ICONS[key], TAB_LABELS[key])
            if first is None:
                first = btn
            btn.set_active(key == self.current_tab)
            btn.connect("toggled", self.on_tab_toggled, key)
            sidebar.pack_start(btn, False, False, 0)
            self.tab_buttons[key] = btn

        workshop_btn = make_nav_button("network-workgroup-symbolic", "Workshop")
        workshop_btn.connect("clicked", self.on_open_workshop_browser)
        sidebar.pack_start(workshop_btn, False, False, 0)

        sidebar.pack_start(Gtk.Separator(), False, False, 8)
        monitors_title = Gtk.Label(label="MONITORES", xalign=0)
        monitors_title.get_style_context().add_class("wpe-detail-section-title")
        sidebar.pack_start(monitors_title, False, False, 0)

        self.sidebar_monitor_radios = {}
        self.sidebar_monitor_subtitles = {}
        first_mon = None
        for mon in self.monitors:
            btn, subtitle_label = make_nav_radio(
                first_mon, "video-display-symbolic", mon, subtitle=self._monitor_subtitle(mon)
            )
            if first_mon is None:
                first_mon = btn
            btn.set_active(mon == self.target_monitor)
            btn.connect("toggled", self.on_monitor_nav_toggled, mon)
            sidebar.pack_start(btn, False, False, 0)
            self.sidebar_monitor_radios[mon] = btn
            self.sidebar_monitor_subtitles[mon] = subtitle_label

        sidebar.pack_start(Gtk.Box(), True, True, 0)  # empuja "Ajustes" abajo

        settings_btn = make_nav_button("preferences-system-symbolic", "Ajustes")
        settings_btn.connect("clicked", self.on_open_settings)
        sidebar.pack_start(settings_btn, False, False, 0)

        return sidebar

    def _build_header(self, ui_state):
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar wallpapers... (Ctrl+F)")
        self.search_entry.get_style_context().add_class("wpe-search-big")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self.on_filters_changed)
        header_box.pack_start(self.search_entry, True, True, 0)

        self.filters_btn = FiltersMenuButton(
            [], ["Everyone", "Questionable", "Mature", "Desconocido"],
            on_change=self.on_filters_changed,
            initial_ratings=ui_state.get("ratings", ["Everyone"]),
        )
        header_box.pack_start(self.filters_btn, False, False, 0)

        self.sort_combo = Gtk.ComboBoxText()
        for option in SORT_OPTIONS:
            self.sort_combo.append_text(option)
        saved_sort = ui_state.get("sort")
        sort_options_list = list(SORT_OPTIONS.keys())
        self.sort_combo.set_active(sort_options_list.index(saved_sort) if saved_sort in sort_options_list else 0)
        self.sort_combo.connect("changed", self.on_sort_changed)
        header_box.pack_start(self.sort_combo, False, False, 0)

        return header_box

    def _build_monitor_row(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="MONITOR ACTIVO", xalign=0)
        title.get_style_context().add_class("wpe-detail-section-title")
        box.pack_start(title, False, False, 0)

        chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.monitor_chips = {}
        self.monitor_chip_subtitles = {}
        first = None
        for mon in self.monitors:
            chip, subtitle_label = make_nav_radio(
                first, "video-display-symbolic", mon, subtitle=self._monitor_subtitle(mon)
            )
            if first is None:
                first = chip
            chip.get_style_context().add_class("wpe-chip")
            chip.set_active(mon == self.target_monitor)
            chip.connect("toggled", self.on_monitor_chip_toggled, mon)
            chips_box.pack_start(chip, False, False, 0)
            self.monitor_chips[mon] = chip
            self.monitor_chip_subtitles[mon] = subtitle_label
        box.pack_start(chips_box, False, False, 0)
        return box

    def _build_bottom_bar(self):
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self.status_label = Gtk.Label(label="Cargando...")
        self.status_label.set_halign(Gtk.Align.START)
        bottom_box.pack_start(self.status_label, True, True, 0)

        self.show_hidden_check = Gtk.CheckButton(label="Mostrar ocultos")
        self.show_hidden_check.connect("toggled", self.on_filters_changed)
        bottom_box.pack_start(self.show_hidden_check, False, False, 0)

        rotation_btn = icon_button("Rotacion", "media-playlist-repeat-symbolic")
        rotation_btn.connect("clicked", self.on_open_playlist_window)
        bottom_box.pack_start(rotation_btn, False, False, 0)

        self._build_bulk_actions_menu(bottom_box)

        refresh_btn = icon_button("Actualizar", "view-refresh-symbolic")
        refresh_btn.get_style_context().add_class("suggested-action")
        refresh_btn.connect("clicked", self.on_refresh_clicked)
        bottom_box.pack_end(refresh_btn, False, False, 0)

        return bottom_box

    def _build_bulk_actions_menu(self, bottom_box):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_border_width(8)

        def add_action(label, icon_name, handler):
            btn = icon_button(label, icon_name)
            btn.set_relief(Gtk.ReliefStyle.NONE)

            def _on_click(_btn):
                popover.popdown()
                handler(_btn)

            btn.connect("clicked", _on_click)
            box.pack_start(btn, False, False, 0)

        add_action("Ocultar/Mostrar seleccionados", "list-remove-symbolic", self.on_toggle_hidden_clicked)
        add_action("Desuscribirse (seleccionados)", "user-trash-symbolic", self.on_unsubscribe_clicked)
        box.show_all()
        popover.add(box)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        menu_btn.set_tooltip_text("Acciones en lote sobre la seleccion")
        menu_btn.set_popover(popover)
        bottom_box.pack_start(menu_btn, False, False, 0)

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

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.detail_title = Gtk.Label(xalign=0)
        self.detail_title.set_line_wrap(True)
        self.detail_title.get_style_context().add_class("wpe-detail-title")
        title_row.pack_start(self.detail_title, True, True, 0)
        self.detail_heart = Gtk.ToggleButton()
        self.detail_heart.set_relief(Gtk.ReliefStyle.NONE)
        self.detail_heart.get_style_context().add_class("wpe-heart")
        self.detail_heart.connect("toggled", self._on_detail_heart_toggled)
        title_row.pack_start(self.detail_heart, False, False, 0)
        panel.pack_start(title_row, False, False, 0)

        self.detail_assign_btn = icon_button("Asignar", "emblem-ok-symbolic")
        self.detail_assign_btn.get_style_context().add_class("suggested-action")
        self.detail_assign_btn.connect("clicked", self._on_detail_assign_clicked)
        panel.pack_start(self.detail_assign_btn, False, False, 0)

        preview_btn = icon_button("Vista previa", "view-fullscreen-symbolic")
        preview_btn.connect("clicked", self._on_detail_preview_clicked)
        panel.pack_start(preview_btn, False, False, 0)

        rotation_btn = icon_button("Anadir a rotacion", "media-playlist-repeat-symbolic")
        rotation_btn.connect("clicked", self._on_detail_add_rotation)
        panel.pack_start(rotation_btn, False, False, 0)

        self.detail_hide_btn = icon_button("Ocultar", "list-remove-symbolic")
        self.detail_hide_btn.connect("clicked", self._on_detail_hide_clicked)
        panel.pack_start(self.detail_hide_btn, False, False, 0)

        unsub_btn = icon_button("Desuscribirse", "user-trash-symbolic")
        unsub_btn.connect("clicked", self._on_detail_unsub_clicked)
        panel.pack_start(unsub_btn, False, False, 0)

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

    # -- Carga y cuadricula ---------------------------------------------------

    def populate(self):
        self.known_bad = load_known_bad()
        self.all_items = load_wallpapers()
        self.items_by_id = {item["id"]: item for item in self.all_items}

        all_tags = set()
        pending_thumb_ids = []
        for item in self.all_items:
            all_tags.update(item["tags"])
            if item["thumb"] and os.path.isfile(item["thumb"]):
                try:
                    item["pixbuf"] = GdkPixbuf.Pixbuf.new_from_file(item["thumb"])
                except Exception:
                    item["pixbuf"] = self.placeholder_pixbuf
            else:
                item["pixbuf"] = self.placeholder_pixbuf
                if item.get("preview_path"):
                    pending_thumb_ids.append(item["id"])

        self.filters_btn.set_tag_options(sorted(all_tags, key=str.lower))

        for mon in self.monitors:
            self.update_monitor_label(mon)

        self.rebuild_cards()
        self.status_label.set_text(f"{len(self.all_items)} wallpapers")

        if pending_thumb_ids:
            threading.Thread(target=self._generate_thumbs_thread, args=(pending_thumb_ids,), daemon=True).start()

        return False

    def _generate_thumbs_thread(self, ids):
        for wid in ids:
            item = self.items_by_id.get(wid)
            if not item or not item.get("preview_path"):
                continue
            thumb_path = os.path.join(CACHE_DIR, f"{wid}.png")
            if build_thumb(item["preview_path"], thumb_path):
                GLib.idle_add(self._apply_generated_thumb, wid, thumb_path)

    def _apply_generated_thumb(self, wid, thumb_path):
        item = self.items_by_id.get(wid)
        if not item:
            return False
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(thumb_path)
        except Exception:
            return False
        item["thumb"] = thumb_path
        item["pixbuf"] = pixbuf
        card = self.cards.get(wid)
        if card:
            card.set_pixbuf(pixbuf)
        return False

    def rebuild_cards(self):
        for child in list(self.flowbox.get_children()):
            self.flowbox.remove(child)
        self.cards = {}

        for item in self.all_items:
            card = self._build_card(item)
            self.flowbox.add(card)
            self.cards[item["id"]] = card

        self.flowbox.show_all()
        self.flowbox.invalidate_filter()
        self.flowbox.invalidate_sort()

    def _build_card(self, item):
        wid = item["id"]
        subtitle_parts = []
        if item.get("type") and item["type"] not in ("Desconocido", "Scene"):
            subtitle_parts.append(item["type"])
        if item.get("tags"):
            subtitle_parts.append(item["tags"][0])
        subtitle = " · ".join(subtitle_parts)

        badge = None
        if wid in self.known_bad:
            badge = "⚠ Fallo conocido"
        elif wid in self.hidden_ids:
            badge = "Oculto"

        card = WallpaperCard(
            wid, item["title"], subtitle, item["pixbuf"],
            favorite=wid in self.favorite_ids, badge=badge,
            assigned=(self.assignments.get(self.target_monitor) == wid),
        )
        card.on_assign = self.assign_and_apply
        card.on_preview = self.show_preview
        card.on_toggle_favorite = self.on_card_favorite_toggled
        card.on_context_menu = self.show_context_menu
        return card

    def _refresh_assigned_badges(self):
        current = self.assignments.get(self.target_monitor)
        for wid, card in self.cards.items():
            card.set_assigned(wid == current)

    # -- Filtro y orden del FlowBox ------------------------------------------

    def _passes_tab_filter(self, wid):
        item = self.items_by_id.get(wid, {})
        if self.current_tab == "Favoritos":
            return wid in self.favorite_ids
        if self.current_tab == "Ocultos":
            return wid in self.hidden_ids
        if self.current_tab == "Recientes":
            return wid in self.recent_ids
        if self.current_tab == "Animados":
            # "Scene" puede o no tener movimiento (Wallpaper Engine no expone un
            # flag fiable de estatico/animado); "Video" y "Web" si son siempre
            # dinamicos, asi que la pestana se limita a esos dos tipos.
            return item.get("type") in ("Video", "Web")
        if self.show_hidden_check.get_active():
            return True
        return wid not in self.hidden_ids  # "Todos"

    def _filter_func(self, flowboxchild):
        card = flowboxchild.get_child()
        wid = card.wid
        item = self.items_by_id.get(wid)
        if not item:
            return False
        if not self._passes_tab_filter(wid):
            return False

        query = self.search_entry.get_text().strip().lower()
        if query and query not in item["title"].lower():
            return False

        selected_tags = self.filters_btn.get_selected_tags()
        if selected_tags and not all(t in item["tags"] for t in selected_tags):
            return False

        selected_ratings = self.filters_btn.get_selected_ratings()
        if selected_ratings and item["rating"] not in selected_ratings:
            return False

        return True

    def _sort_func(self, child_a, child_b):
        wid_a, wid_b = child_a.get_child().wid, child_b.get_child().wid

        if self.current_tab == "Recientes":
            order = {wid: i for i, wid in enumerate(self.recent_ids)}
            ia, ib = order.get(wid_a, 10**9), order.get(wid_b, 10**9)
            return -1 if ia < ib else (1 if ia > ib else 0)

        item_a, item_b = self.items_by_id.get(wid_a), self.items_by_id.get(wid_b)
        if not item_a or not item_b:
            return 0
        sort_choice = self.sort_combo.get_active_text() or "Mas reciente primero"
        key_func = SORT_OPTIONS.get(sort_choice, SORT_OPTIONS["Mas reciente primero"])
        reverse = SORT_REVERSE.get(sort_choice, False)
        ka, kb = key_func(item_a), key_func(item_b)
        cmp = -1 if ka < kb else (1 if ka > kb else 0)
        return -cmp if reverse else cmp

    def on_filters_changed(self, *args):
        self.flowbox.invalidate_filter()

    def on_sort_changed(self, combo):
        self.flowbox.invalidate_sort()
        self.save_current_ui_state()

    def on_tab_toggled(self, btn, label):
        if not btn.get_active():
            return
        self.current_tab = label
        self.flowbox.invalidate_filter()
        self.flowbox.invalidate_sort()
        self.save_current_ui_state()

    # -- Monitores y asignacion -----------------------------------------------

    def _monitor_subtitle(self, mon):
        wid = self.assignments.get(mon)
        item = self.items_by_id.get(wid) if wid else None
        return item["title"] if item else (wid or "?")

    def update_monitor_label(self, mon):
        text = self._monitor_subtitle(mon)
        for labels in (getattr(self, "monitor_chip_subtitles", {}), getattr(self, "sidebar_monitor_subtitles", {})):
            label_widget = labels.get(mon)
            if label_widget:
                label_widget.set_text(text)

    def on_monitor_chip_toggled(self, chip, mon):
        if chip.get_active():
            self._set_target_monitor(mon)
            radio = self.sidebar_monitor_radios.get(mon)
            if radio and not radio.get_active():
                radio.set_active(True)

    def on_monitor_nav_toggled(self, radio, mon):
        if radio.get_active():
            self._set_target_monitor(mon)
            chip = self.monitor_chips.get(mon)
            if chip and not chip.get_active():
                chip.set_active(True)

    def _set_target_monitor(self, mon):
        self.target_monitor = mon
        self._refresh_assigned_badges()
        if self._detail_wid:
            self._update_detail_panel(self._detail_wid)
        self.save_current_ui_state()

    def assign_and_apply(self, wid, monitor=None):
        monitor = monitor or self.target_monitor
        self.assignments[monitor] = wid
        self.update_monitor_label(monitor)
        if monitor == self.target_monitor:
            self._refresh_assigned_badges()

        # Una asignacion manual desactiva cualquier rotacion activa en esa pantalla,
        # para que el demonio de rotacion no la sobrescriba mas tarde.
        playlists = load_playlists()
        if playlists.get(monitor, {}).get("enabled"):
            playlists[monitor]["enabled"] = False
            save_playlists(playlists)

        subprocess.Popen([APPLY_SCRIPT, f"{monitor}={wid}"])
        title = self.items_by_id.get(wid, {}).get("title", wid)
        self.status_label.set_text(f"Aplicando en {monitor}: {title}")

        self.recent_ids = record_recent(wid)
        if self.current_tab == "Recientes":
            self.flowbox.invalidate_filter()
        self.flowbox.invalidate_sort()

    def get_selected_ids(self):
        return [child.get_child().wid for child in self.flowbox.get_selected_children()]

    # -- Favoritos, ocultos, desuscribir --------------------------------------

    def on_card_favorite_toggled(self, wid, is_favorite):
        if is_favorite:
            self.favorite_ids.add(wid)
        else:
            self.favorite_ids.discard(wid)
        save_favorite_ids(self.favorite_ids)
        if self.current_tab == "Favoritos":
            self.flowbox.invalidate_filter()
        if wid == self._detail_wid:
            self.detail_heart.handler_block_by_func(self._on_detail_heart_toggled)
            self.detail_heart.set_active(is_favorite)
            self.detail_heart.handler_unblock_by_func(self._on_detail_heart_toggled)
            self._update_detail_heart_icon()

    def on_toggle_hidden_clicked(self, button):
        ids = self.get_selected_ids()
        if not ids:
            self.status_label.set_text("Selecciona uno o mas wallpapers primero")
            return
        currently_hidden = sum(1 for wid in ids if wid in self.hidden_ids)
        make_hidden = currently_hidden < len(ids)
        for wid in ids:
            self._set_hidden(wid, make_hidden)
        save_hidden_ids(self.hidden_ids)
        self.flowbox.invalidate_filter()
        action = "Ocultado(s)" if make_hidden else "Mostrado(s) de nuevo"
        self.status_label.set_text(f"{action}: {len(ids)} wallpaper(s)")

    def _set_hidden(self, wid, hidden):
        if hidden:
            self.hidden_ids.add(wid)
        else:
            self.hidden_ids.discard(wid)
        card = self.cards.get(wid)
        if card:
            card.set_badge("⚠ Fallo conocido" if wid in self.known_bad else ("Oculto" if hidden else None))
        if wid == self._detail_wid:
            self.detail_hide_btn.set_label("Mostrar de nuevo" if hidden else "Ocultar")

    def on_unsubscribe_clicked(self, button):
        ids = self.get_selected_ids()
        if not ids:
            self.status_label.set_text("Selecciona uno o mas wallpapers primero")
            return
        self._unsubscribe_ids(ids)

    def _unsubscribe_ids(self, ids):
        titles = [self.items_by_id.get(wid, {}).get("title", wid) for wid in ids]
        used_on = sorted({mon for mon, vid in self.assignments.items() if vid in ids})
        warning = f"\n\nAviso: hay pantallas usando alguno de estos: {', '.join(used_on)}." if used_on else ""
        names = ", ".join(titles) if len(titles) <= 3 else f"{len(titles)} wallpapers"

        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,
            text="Desuscribirse y borrar" + (" este wallpaper" if len(ids) == 1 else f" {len(ids)} wallpapers"),
        )
        dialog.format_secondary_text(
            f"Se borrara el contenido local de: {names}.{warning}\n\n"
            "Esto NO desuscribe tu cuenta real de Steam (el login anonimo que usa la "
            "descarga no puede hacerlo). Si no quieres que Steam los vuelva a "
            "descargar mas adelante, abrelos en Steam y pulsa 'Unsubscribe' alli con tu cuenta."
        )
        dialog.add_buttons(
            "Cancelar", Gtk.ResponseType.CANCEL,
            "Solo borrar local", Gtk.ResponseType.OK,
            "Borrar y abrir en Steam", Gtk.ResponseType.APPLY,
        )
        response = dialog.run()
        dialog.destroy()

        if response not in (Gtk.ResponseType.OK, Gtk.ResponseType.APPLY):
            return

        for wid in ids:
            unsubscribe_workshop_item(wid)
            self.hidden_ids.discard(wid)
            self.favorite_ids.discard(wid)
        save_hidden_ids(self.hidden_ids)
        save_favorite_ids(self.favorite_ids)
        self.on_refresh_clicked()
        self.status_label.set_text(f"Borrado(s) localmente: {len(ids)} wallpaper(s)")

        if response == Gtk.ResponseType.APPLY:
            for wid in ids:
                open_in_steam(wid)

    # -- Panel de detalle ------------------------------------------------------

    def on_selection_changed(self, flowbox):
        ids = self.get_selected_ids()
        if len(ids) == 1:
            self._update_detail_panel(ids[0])
            self.status_label.set_text(f"{len(self.all_items)} wallpapers")
        else:
            self.detail_revealer.set_reveal_child(False)
            self._detail_wid = None
            if len(ids) > 1:
                self.status_label.set_text(f"{len(self.all_items)} wallpapers · {len(ids)} seleccionados")
            else:
                self.status_label.set_text(f"{len(self.all_items)} wallpapers")

    def _format_date(self, mtime):
        if not mtime:
            return "-"
        try:
            return datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y")
        except Exception:
            return "-"

    def _update_detail_panel(self, wid):
        item = self.items_by_id.get(wid)
        if not item:
            self.detail_revealer.set_reveal_child(False)
            return
        self._detail_wid = wid

        big = None
        if item.get("preview_path") and os.path.isfile(item["preview_path"]):
            try:
                big = GdkPixbuf.Pixbuf.new_from_file_at_scale(item["preview_path"], 272, 153, True)
            except Exception:
                big = None
        self.detail_image.set_from_pixbuf(big or item.get("pixbuf"))

        self.detail_title.set_text(item["title"])

        self.detail_heart.handler_block_by_func(self._on_detail_heart_toggled)
        self.detail_heart.set_active(wid in self.favorite_ids)
        self.detail_heart.handler_unblock_by_func(self._on_detail_heart_toggled)
        self._update_detail_heart_icon()

        self.detail_assign_btn.set_label(f"Asignar a {self.target_monitor}")
        self.detail_hide_btn.set_label("Mostrar de nuevo" if wid in self.hidden_ids else "Ocultar")

        for child in list(self.detail_info_grid.get_children()):
            self.detail_info_grid.remove(child)
        rows = [
            ("Tipo", item.get("type") or "Desconocido"),
            ("Categorias", ", ".join(item.get("tags", [])[:4]) or "-"),
            ("Clasificacion", item.get("rating") or "Desconocido"),
            ("Anadido", self._format_date(item.get("mtime"))),
        ]
        for i, (label, value) in enumerate(rows):
            l1 = Gtk.Label(label=label, xalign=0)
            l1.get_style_context().add_class("dim-label")
            l2 = Gtk.Label(label=value, xalign=0)
            l2.set_line_wrap(True)
            self.detail_info_grid.attach(l1, 0, i, 1, 1)
            self.detail_info_grid.attach(l2, 1, i, 1, 1)
        self.detail_info_grid.show_all()

        for child in list(self.detail_tags_box.get_children()):
            self.detail_tags_box.remove(child)
        for tag in item.get("tags", []):
            chip = Gtk.Label(label=tag)
            chip.get_style_context().add_class("wpe-tag-chip")
            self.detail_tags_box.add(chip)
        self.detail_tags_box.show_all()

        self.detail_revealer.set_reveal_child(True)

    def _update_detail_heart_icon(self):
        icon = "starred-symbolic" if self.detail_heart.get_active() else "non-starred-symbolic"
        self.detail_heart.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))

    def _on_detail_heart_toggled(self, btn):
        if not self._detail_wid:
            return
        self.on_card_favorite_toggled(self._detail_wid, btn.get_active())
        card = self.cards.get(self._detail_wid)
        if card:
            card.set_favorite(btn.get_active())
        self._update_detail_heart_icon()

    def _on_detail_assign_clicked(self, button):
        if self._detail_wid:
            self.assign_and_apply(self._detail_wid)

    def _on_detail_preview_clicked(self, button):
        if self._detail_wid:
            self.show_preview(self._detail_wid)

    def _on_detail_add_rotation(self, button):
        if self._detail_wid:
            self.add_to_rotation(self._detail_wid, self.target_monitor)

    def _on_detail_hide_clicked(self, button):
        if not self._detail_wid:
            return
        wid = self._detail_wid
        self._set_hidden(wid, wid not in self.hidden_ids)
        save_hidden_ids(self.hidden_ids)
        self.flowbox.invalidate_filter()

    def _on_detail_unsub_clicked(self, button):
        if self._detail_wid:
            self._unsubscribe_ids([self._detail_wid])

    # -- Vista previa grande y menu contextual --------------------------------

    def show_preview(self, wid):
        item = self.items_by_id.get(wid)
        if not item:
            return

        dialog = Gtk.Dialog(title=item["title"], transient_for=self, modal=True)
        dialog.set_default_size(720, 500)
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        pixbuf = item.get("pixbuf")
        preview_path = item.get("preview_path")
        big_pixbuf = None
        if preview_path and os.path.isfile(preview_path):
            try:
                big_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(preview_path, 680, 400, True)
            except Exception:
                big_pixbuf = None
        image = Gtk.Image.new_from_pixbuf(big_pixbuf or pixbuf)
        box.add(image)

        info_parts = [item["type"], item["rating"]] + item.get("tags", [])[:4]
        info_label = Gtk.Label(label=" · ".join(p for p in info_parts if p and p != "Desconocido"))
        info_label.get_style_context().add_class("dim-label")
        box.add(info_label)

        assign_btn = icon_button(f"Asignar a {self.target_monitor}", "emblem-ok-symbolic")
        assign_btn.get_style_context().add_class("suggested-action")
        assign_btn.connect("clicked", lambda *_: (self.assign_and_apply(wid), dialog.destroy()))
        box.add(assign_btn)

        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.show_all()
        dialog.run()
        dialog.destroy()

    def show_context_menu(self, card, event, wid):
        menu = Gtk.Menu()

        for mon in self.monitors:
            mi = Gtk.MenuItem(label=f"Asignar a {mon}")
            mi.connect("activate", lambda _mi, m=mon: self.assign_and_apply(wid, monitor=m))
            menu.append(mi)

        menu.append(Gtk.SeparatorMenuItem())

        fav_item = Gtk.CheckMenuItem(label="Favorito")
        fav_item.set_active(wid in self.favorite_ids)
        fav_item.connect("toggled", lambda mi: card.heart_btn.set_active(mi.get_active()))
        menu.append(fav_item)

        preview_item = Gtk.MenuItem(label="Vista previa")
        preview_item.connect("activate", lambda *_: self.show_preview(wid))
        menu.append(preview_item)

        menu.append(Gtk.SeparatorMenuItem())

        rotation_item = Gtk.MenuItem(label=f"Anadir a rotacion ({self.target_monitor})")
        rotation_item.connect("activate", lambda *_: self.add_to_rotation(wid, self.target_monitor))
        menu.append(rotation_item)

        hide_item = Gtk.MenuItem(label="Mostrar de nuevo" if wid in self.hidden_ids else "Ocultar")
        hide_item.connect("activate", lambda *_: self._toggle_hidden_single(wid))
        menu.append(hide_item)

        menu.append(Gtk.SeparatorMenuItem())

        unsub_item = Gtk.MenuItem(label="Desuscribirse")
        unsub_item.connect("activate", lambda *_: self._unsubscribe_ids([wid]))
        menu.append(unsub_item)

        menu.show_all()
        if event is not None:
            menu.popup_at_pointer(event)
        else:
            menu.popup_at_widget(card.menu_btn, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, None)

    def _toggle_hidden_single(self, wid):
        self._set_hidden(wid, wid not in self.hidden_ids)
        save_hidden_ids(self.hidden_ids)
        self.flowbox.invalidate_filter()

    def add_to_rotation(self, wid, monitor):
        playlists = load_playlists()
        data = playlists.setdefault(monitor, {"enabled": False, "interval_minutes": 30, "items": [], "current_index": 0, "last_switch": 0})
        if wid not in data.get("items", []):
            data.setdefault("items", []).append(wid)
            save_playlists(playlists)
            self.status_label.set_text(f"Anadido a la rotacion de {monitor}")
        else:
            self.status_label.set_text("Ya estaba en la rotacion de esa pantalla")

    # -- Ventanas secundarias --------------------------------------------------

    def on_open_workshop_browser(self, button):
        if self.workshop_window is None or not self.workshop_window.get_visible():
            self.workshop_window = WorkshopBrowserWindow(on_downloaded=self.on_refresh_clicked)
            self.workshop_window.show_all()
        else:
            self.workshop_window.present()

    def on_open_playlist_window(self, button):
        if self.playlist_window is None or not self.playlist_window.get_visible():
            self.playlist_window = PlaylistWindow(self.monitors, self.all_items, on_saved=self.on_refresh_clicked)
            self.playlist_window.show_all()
        else:
            self.playlist_window.present()

    def on_open_settings(self, button):
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True, message_type=Gtk.MessageType.INFO,
            text="Ajustes",
        )
        dialog.format_secondary_text(
            f"Biblioteca de Steam: {STEAM_LIB}\n"
            f"Cache de miniaturas: {CACHE_DIR}\n\n"
            "Para cambiar la biblioteca de Steam o la API key de Steam, edita\n"
            "~/.config/wallpaperengine-picker/config.json"
        )
        dialog.add_button("Cerrar", Gtk.ResponseType.CLOSE)
        dialog.run()
        dialog.destroy()

    def on_refresh_clicked(self, *args):
        self.status_label.set_text("Actualizando lista de wallpapers...")
        self.populate()

    # -- Atajos de teclado y persistencia de estado ---------------------------

    def on_key_press(self, widget, event):
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and event.keyval in (Gdk.KEY_f, Gdk.KEY_k):
            self.search_entry.grab_focus()
            return True
        if event.keyval == Gdk.KEY_Escape and self.search_entry.get_text():
            self.search_entry.set_text("")
            return True
        if event.keyval == Gdk.KEY_Delete:
            self.on_toggle_hidden_clicked(None)
            return True
        return False

    def save_current_ui_state(self):
        save_ui_state({
            "tab": self.current_tab,
            "sort": self.sort_combo.get_active_text(),
            "ratings": self.filters_btn.get_selected_ratings(),
            "target_monitor": self.target_monitor,
        })

    def on_destroy(self, widget):
        self.save_current_ui_state()


def main():
    apply_css()
    win = PickerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
