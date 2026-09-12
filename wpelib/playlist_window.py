"""Ventana de rotacion (playlists) de wallpapers por pantalla."""
import subprocess
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .config import load_playlists, save_playlists, APPLY_SCRIPT
from .ui import labeled_frame, icon_button

class PlaylistWindow(Gtk.Window):
    def __init__(self, monitors, all_items, on_saved=None):
        super().__init__(title="Rotacion de wallpapers")
        self.set_default_size(800, 560)
        self.set_border_width(12)
        self.monitors = monitors
        self.titles_by_id = {item["id"]: item["title"] for item in all_items}
        self.on_saved = on_saved
        self.playlists = load_playlists()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        top_frame = labeled_frame("Configuracion de la pantalla")
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top_box.set_border_width(8)
        top_frame.add(top_box)

        top_box.pack_start(Gtk.Label(label="Pantalla:"), False, False, 0)
        self.monitor_combo = Gtk.ComboBoxText()
        for mon in monitors:
            self.monitor_combo.append_text(mon)
        self.monitor_combo.set_active(0)
        self.monitor_combo.connect("changed", self.on_monitor_changed)
        top_box.pack_start(self.monitor_combo, False, False, 0)

        self.enabled_check = Gtk.CheckButton(label="Activar rotacion en esta pantalla")
        top_box.pack_start(self.enabled_check, False, False, 0)

        top_box.pack_start(Gtk.Label(label="Intervalo (minutos):"), False, False, 0)
        adjustment = Gtk.Adjustment(value=30, lower=1, upper=1440, step_increment=1, page_increment=10)
        self.interval_spin = Gtk.SpinButton(adjustment=adjustment)
        top_box.pack_start(self.interval_spin, False, False, 0)
        vbox.pack_start(top_frame, False, False, 0)

        lists_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(lists_box, True, True, 0)

        avail_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        avail_vbox.pack_start(Gtk.Label(label="Disponibles"), False, False, 0)
        self.avail_search = Gtk.SearchEntry()
        self.avail_search.set_placeholder_text("Buscar...")
        self.avail_search.connect("search-changed", self.on_avail_search_changed)
        avail_vbox.pack_start(self.avail_search, False, False, 0)
        self.avail_store = Gtk.ListStore(str, str)  # titulo, id
        self.avail_filter = self.avail_store.filter_new()
        self.avail_filter.set_visible_func(self.avail_filter_func)
        self.avail_view = Gtk.TreeView(model=self.avail_filter)
        self.avail_view.append_column(Gtk.TreeViewColumn("Titulo", Gtk.CellRendererText(), text=0))
        self.avail_view.set_headers_visible(False)
        avail_scrolled = Gtk.ScrolledWindow()
        avail_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        avail_scrolled.set_shadow_type(Gtk.ShadowType.IN)
        avail_scrolled.add(self.avail_view)
        avail_vbox.pack_start(avail_scrolled, True, True, 0)
        lists_box.pack_start(avail_vbox, True, True, 0)

        mid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        mid_box.set_valign(Gtk.Align.CENTER)
        add_btn = icon_button("Anadir", "go-next-symbolic")
        add_btn.connect("clicked", self.on_add_clicked)
        mid_box.pack_start(add_btn, False, False, 0)
        remove_btn = icon_button("Quitar", "go-previous-symbolic")
        remove_btn.connect("clicked", self.on_remove_clicked)
        mid_box.pack_start(remove_btn, False, False, 0)
        up_btn = icon_button("Subir", "go-up-symbolic")
        up_btn.connect("clicked", self.on_move_up)
        mid_box.pack_start(up_btn, False, False, 0)
        down_btn = icon_button("Bajar", "go-down-symbolic")
        down_btn.connect("clicked", self.on_move_down)
        mid_box.pack_start(down_btn, False, False, 0)
        lists_box.pack_start(mid_box, False, False, 0)

        playlist_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        playlist_vbox.pack_start(Gtk.Label(label="Orden de rotacion"), False, False, 0)
        self.playlist_store = Gtk.ListStore(str, str)  # titulo, id
        self.playlist_view = Gtk.TreeView(model=self.playlist_store)
        self.playlist_view.append_column(Gtk.TreeViewColumn("Titulo", Gtk.CellRendererText(), text=0))
        self.playlist_view.set_headers_visible(False)
        playlist_scrolled = Gtk.ScrolledWindow()
        playlist_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        playlist_scrolled.set_shadow_type(Gtk.ShadowType.IN)
        playlist_scrolled.add(self.playlist_view)
        playlist_vbox.pack_start(playlist_scrolled, True, True, 0)
        lists_box.pack_start(playlist_vbox, True, True, 0)

        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(bottom_box, False, False, 0)
        self.status_label = Gtk.Label(label="")
        self.status_label.set_halign(Gtk.Align.START)
        bottom_box.pack_start(self.status_label, True, True, 0)
        save_btn = icon_button("Guardar y aplicar", "document-save-symbolic")
        save_btn.get_style_context().add_class("suggested-action")
        save_btn.connect("clicked", self.on_save_clicked)
        bottom_box.pack_end(save_btn, False, False, 0)

        for item in sorted(all_items, key=lambda i: i["title"].lower()):
            self.avail_store.append([item["title"], item["id"]])

        self.load_monitor_playlist(monitors[0])

    def avail_filter_func(self, model, iter_, data):
        query = self.avail_search.get_text().strip().lower()
        if not query:
            return True
        return query in (model[iter_][0] or "").lower()

    def on_avail_search_changed(self, entry):
        self.avail_filter.refilter()

    def load_monitor_playlist(self, monitor):
        data = self.playlists.get(monitor, {})
        self.enabled_check.set_active(bool(data.get("enabled", False)))
        self.interval_spin.set_value(data.get("interval_minutes", 30))
        self.playlist_store.clear()
        for wid in data.get("items", []):
            self.playlist_store.append([self.titles_by_id.get(wid, wid), wid])

    def stash_current_monitor(self):
        monitor = self.monitor_combo.get_active_text()
        if not monitor:
            return
        items = [row[1] for row in self.playlist_store]
        previous = self.playlists.get(monitor, {})
        self.playlists[monitor] = {
            "enabled": self.enabled_check.get_active(),
            "interval_minutes": int(self.interval_spin.get_value()),
            "items": items,
            "current_index": previous.get("current_index", 0),
            "last_switch": previous.get("last_switch", 0),
        }

    def on_monitor_changed(self, combo):
        self.stash_current_monitor()
        self.load_monitor_playlist(combo.get_active_text())

    def get_selected_row(self, view):
        model, iter_ = view.get_selection().get_selected()
        return model, iter_

    def on_add_clicked(self, button):
        model, iter_ = self.get_selected_row(self.avail_view)
        if not iter_:
            self.status_label.set_text("Selecciona un wallpaper de la lista de disponibles")
            return
        self.playlist_store.append([model[iter_][0], model[iter_][1]])

    def on_remove_clicked(self, button):
        model, iter_ = self.get_selected_row(self.playlist_view)
        if not iter_:
            self.status_label.set_text("Selecciona un wallpaper de la rotacion para quitarlo")
            return
        model.remove(iter_)

    def on_move_up(self, button):
        model, iter_ = self.get_selected_row(self.playlist_view)
        if not iter_:
            return
        index = model.get_path(iter_).get_indices()[0]
        if index > 0:
            model.move_before(iter_, model.get_iter(index - 1))

    def on_move_down(self, button):
        model, iter_ = self.get_selected_row(self.playlist_view)
        if not iter_:
            return
        next_iter = model.iter_next(iter_)
        if next_iter:
            model.move_after(iter_, next_iter)

    def on_save_clicked(self, button):
        self.stash_current_monitor()
        save_playlists(self.playlists)
        monitor = self.monitor_combo.get_active_text()
        data = self.playlists.get(monitor, {})
        if data.get("enabled") and data.get("items"):
            data["current_index"] = 0
            data["last_switch"] = int(time.time())
            self.playlists[monitor] = data
            save_playlists(self.playlists)
            subprocess.Popen([APPLY_SCRIPT, f"{monitor}={data['items'][0]}"])
            self.status_label.set_text(f"Rotacion guardada y activada en {monitor} ({len(data['items'])} wallpapers)")
        else:
            self.status_label.set_text(f"Configuracion guardada para {monitor} (rotacion desactivada)")
        if self.on_saved:
            self.on_saved()
