"""Ventana principal: lista de wallpapers locales con miniaturas, filtros,
asignacion por monitor, y accesos a las ventanas de Workshop y rotacion."""
import os
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib

from .config import (
    load_wallpapers, detect_monitors, load_current_assignments, load_hidden_ids,
    save_hidden_ids, load_known_bad, load_playlists, save_playlists,
    unsubscribe_workshop_item, SORT_OPTIONS, SORT_REVERSE, APPLY_SCRIPT, THUMB_SIZE,
)
from .ui import labeled_frame, icon_button, CheckListButton, open_in_steam, apply_css
from .workshop_window import WorkshopBrowserWindow
from .playlist_window import PlaylistWindow

class PickerWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Elegir Fondo de Pantalla")
        self.set_default_size(1080, 780)
        self.set_border_width(12)

        self.monitors = detect_monitors() or ["DP-2"]
        self.assignments = load_current_assignments(self.monitors)
        self.target_monitor = self.monitors[0]
        self.all_items = []
        self.titles_by_id = {}
        self.tags_by_id = {}
        self.rating_by_id = {}
        self.hidden_ids = load_hidden_ids()
        self.known_bad = load_known_bad()
        self.workshop_window = None
        self.playlist_window = None

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # --- Fila de busqueda y filtros ---
        filter_frame = labeled_frame("Buscar y filtrar")
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_box.set_border_width(8)
        filter_frame.add(filter_box)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Buscar por titulo...")
        self.search_entry.connect("search-changed", self.refilter)
        filter_box.pack_start(self.search_entry, True, True, 0)

        self.tag_filter = CheckListButton("Etiquetas", [], on_change=self.refilter)
        filter_box.pack_start(self.tag_filter, False, False, 0)

        self.rating_filter = CheckListButton(
            "Clasificacion", ["Everyone", "Questionable", "Mature", "Desconocido"],
            on_change=self.refilter, initially_checked=["Everyone"],
        )
        filter_box.pack_start(self.rating_filter, False, False, 0)

        filter_box.pack_start(Gtk.Label(label="Ordenar por:"), False, False, 0)
        self.sort_combo = Gtk.ComboBoxText()
        for option in SORT_OPTIONS:
            self.sort_combo.append_text(option)
        self.sort_combo.set_active(0)
        self.sort_combo.connect("changed", self.on_sort_changed)
        filter_box.pack_start(self.sort_combo, False, False, 0)

        self.show_hidden_check = Gtk.CheckButton(label="Mostrar ocultos")
        self.show_hidden_check.connect("toggled", self.on_show_hidden_toggled)
        filter_box.pack_start(self.show_hidden_check, False, False, 0)

        vbox.pack_start(filter_frame, False, False, 0)

        # --- Fila de asignacion por monitor ---
        monitor_frame = labeled_frame("Asignacion por monitor")
        monitor_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        monitor_box.set_border_width(8)
        monitor_frame.add(monitor_box)

        self.monitor_labels = {}
        first_radio = None
        for mon in self.monitors:
            chip = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            radio = Gtk.RadioButton.new_with_label_from_widget(first_radio, mon) if first_radio else Gtk.RadioButton.new_with_label(None, mon)
            if first_radio is None:
                first_radio = radio
            radio.connect("toggled", self.on_target_monitor_toggled, mon)
            chip.pack_start(radio, False, False, 0)
            assigned_label = Gtk.Label(label=f"({self.assignments.get(mon, '?')})")
            assigned_label.set_halign(Gtk.Align.START)
            assigned_label.get_style_context().add_class("dim-label")
            chip.pack_start(assigned_label, False, False, 0)
            monitor_box.pack_start(chip, False, False, 0)
            self.monitor_labels[mon] = assigned_label
        vbox.pack_start(monitor_frame, False, False, 0)

        # --- Vista de iconos ---
        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)  # pixbuf, title, id
        self.filter_model = self.store.filter_new()
        self.filter_model.set_visible_func(self.filter_func)

        self.icon_view = Gtk.IconView(model=self.filter_model)
        self.icon_view.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
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

        # --- Barra inferior ---
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vbox.pack_start(button_box, False, False, 0)

        self.status_label = Gtk.Label(label="Cargando...")
        self.status_label.set_halign(Gtk.Align.START)
        button_box.pack_start(self.status_label, True, True, 0)

        workshop_btn = icon_button("Buscar en Workshop (API)", "system-search-symbolic")
        workshop_btn.connect("clicked", self.on_open_workshop_browser)
        button_box.pack_end(workshop_btn, False, False, 0)

        refresh_btn = icon_button("Refrescar lista", "view-refresh-symbolic")
        refresh_btn.connect("clicked", self.on_refresh_clicked)
        button_box.pack_end(refresh_btn, False, False, 0)

        assign_btn = icon_button("Asignar a esta pantalla", "emblem-ok-symbolic")
        assign_btn.get_style_context().add_class("suggested-action")
        assign_btn.connect("clicked", self.on_assign_clicked)
        button_box.pack_end(assign_btn, False, False, 0)

        hide_btn = icon_button("Ocultar/Mostrar", "list-remove-symbolic")
        hide_btn.connect("clicked", self.on_toggle_hidden_clicked)
        button_box.pack_end(hide_btn, False, False, 0)

        playlist_btn = icon_button("Rotacion...", "media-playlist-repeat-symbolic")
        playlist_btn.connect("clicked", self.on_open_playlist_window)
        button_box.pack_end(playlist_btn, False, False, 0)

        unsubscribe_btn = icon_button("Desuscribirse", "user-trash-symbolic")
        unsubscribe_btn.connect("clicked", self.on_unsubscribe_clicked)
        button_box.pack_end(unsubscribe_btn, False, False, 0)

        self.placeholder_pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, *THUMB_SIZE)
        self.placeholder_pixbuf.fill(0x2f3140ff)

        GLib.idle_add(self.populate)

    def populate(self):
        self.known_bad = load_known_bad()
        self.all_items = load_wallpapers()
        all_tags = set()
        for item in self.all_items:
            wid = item["id"]
            self.titles_by_id[wid] = item["title"]
            self.tags_by_id[wid] = item["tags"]
            self.rating_by_id[wid] = item["rating"]
            all_tags.update(item["tags"])

            if item["thumb"] and os.path.isfile(item["thumb"]):
                try:
                    item["pixbuf"] = GdkPixbuf.Pixbuf.new_from_file(item["thumb"])
                except Exception:
                    item["pixbuf"] = self.placeholder_pixbuf
            else:
                item["pixbuf"] = self.placeholder_pixbuf

        self.tag_filter.set_options(sorted(all_tags, key=str.lower))

        for mon in self.monitors:
            self.update_monitor_label(mon)

        self.rebuild_store()
        self.status_label.set_text(f"{len(self.all_items)} wallpapers")
        return False

    def update_monitor_label(self, mon):
        wid = self.assignments.get(mon)
        title = self.titles_by_id.get(wid, wid or "?")
        self.monitor_labels[mon].set_text(f"({title})")

    def rebuild_store(self):
        sort_choice = self.sort_combo.get_active_text() or "Titulo (A-Z)"
        key_func = SORT_OPTIONS.get(sort_choice, SORT_OPTIONS["Titulo (A-Z)"])
        ordered = sorted(self.all_items, key=key_func, reverse=SORT_REVERSE.get(sort_choice, False))
        self.store.clear()
        for item in ordered:
            title = item["title"]
            if item["id"] in self.known_bad:
                title = f"[⚠ Fallo conocido] {title}"
            if item["id"] in self.hidden_ids:
                title = f"[Oculto] {title}"
            self.store.append([item["pixbuf"], title, item["id"]])

    def on_sort_changed(self, combo):
        self.rebuild_store()

    def filter_func(self, model, iter_, data):
        wid = model[iter_][2]

        if wid in self.hidden_ids and not self.show_hidden_check.get_active():
            return False

        query = self.search_entry.get_text().strip().lower()
        if query and query not in (model[iter_][1] or "").lower():
            return False

        selected_tags = self.tag_filter.get_selected()
        if selected_tags:
            item_tags = self.tags_by_id.get(wid, [])
            if not all(t in item_tags for t in selected_tags):
                return False

        selected_ratings = self.rating_filter.get_selected()
        if selected_ratings and self.rating_by_id.get(wid) not in selected_ratings:
            return False

        return True

    def refilter(self, *args):
        self.filter_model.refilter()

    def on_show_hidden_toggled(self, check):
        self.refilter()

    def on_toggle_hidden_clicked(self, button):
        ids = self.get_selected_ids()
        if not ids:
            self.status_label.set_text("Selecciona uno o mas wallpapers primero")
            return
        # Si la mayoria no estan ocultos, se ocultan todos; si ya lo estaban, se muestran.
        currently_hidden = sum(1 for wid in ids if wid in self.hidden_ids)
        make_hidden = currently_hidden < len(ids)
        for wid in ids:
            if make_hidden:
                self.hidden_ids.add(wid)
            else:
                self.hidden_ids.discard(wid)
        save_hidden_ids(self.hidden_ids)
        self.rebuild_store()
        self.refilter()
        action = "Ocultado(s)" if make_hidden else "Mostrado(s) de nuevo"
        self.status_label.set_text(f"{action}: {len(ids)} wallpaper(s)")

    def on_unsubscribe_clicked(self, button):
        ids = self.get_selected_ids()
        if not ids:
            self.status_label.set_text("Selecciona uno o mas wallpapers primero")
            return

        titles = [self.titles_by_id.get(wid, wid) for wid in ids]
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
        save_hidden_ids(self.hidden_ids)
        self.on_refresh_clicked()
        self.status_label.set_text(f"Borrado(s) localmente: {len(ids)} wallpaper(s)")

        if response == Gtk.ResponseType.APPLY:
            for wid in ids:
                open_in_steam(wid)

    def on_target_monitor_toggled(self, radio, mon):
        if radio.get_active():
            self.target_monitor = mon

    def get_selected_ids(self):
        selected = self.icon_view.get_selected_items()
        ids = []
        for path in selected:
            iter_ = self.filter_model.get_iter(path)
            ids.append(self.filter_model[iter_][2])
        return ids

    def get_selected_id(self):
        ids = self.get_selected_ids()
        return ids[0] if ids else None

    def assign_and_apply(self, wid):
        self.assignments[self.target_monitor] = wid
        self.update_monitor_label(self.target_monitor)

        # Una asignacion manual desactiva cualquier rotacion activa en esa pantalla,
        # para que el demonio de rotacion no la sobrescriba mas tarde.
        playlists = load_playlists()
        if playlists.get(self.target_monitor, {}).get("enabled"):
            playlists[self.target_monitor]["enabled"] = False
            save_playlists(playlists)

        # Solo se reinicia el proceso de la pantalla que cambio; las demas siguen
        # corriendo sin interrupcion (cada pantalla es un proceso independiente).
        subprocess.Popen([APPLY_SCRIPT, f"{self.target_monitor}={wid}"])
        self.status_label.set_text(f"Aplicando en {self.target_monitor}: {self.titles_by_id.get(wid, wid)}")

    def on_item_activated(self, icon_view, path):
        iter_ = self.filter_model.get_iter(path)
        wid = self.filter_model[iter_][2]
        self.assign_and_apply(wid)

    def on_assign_clicked(self, button):
        ids = self.get_selected_ids()
        if not ids:
            self.status_label.set_text("Selecciona un wallpaper primero")
        elif len(ids) > 1:
            self.status_label.set_text("Selecciona un unico wallpaper para asignarlo a una pantalla")
        else:
            self.assign_and_apply(ids[0])

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

    def on_refresh_clicked(self, *args):
        self.status_label.set_text("Actualizando lista de wallpapers...")

        self.store.clear()
        self.titles_by_id.clear()
        self.tags_by_id.clear()
        self.rating_by_id.clear()

        # set_options() en populate() preserva las etiquetas ya marcadas.
        self.populate()
        self.refilter()


def main():
    apply_css()
    win = PickerWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
