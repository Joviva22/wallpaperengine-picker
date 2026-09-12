"""Widgets y estilos GTK reutilizables: el tema oscuro (CSS), marcos con
titulo, botones con icono, el desplegable de checkboxes multi-seleccion,
chips/pestanas, y la tarjeta de wallpaper (miniatura + favorito + hover)."""
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, Pango

CARD_SIZE = (320, 180)  # 16:9 exacto; debe coincidir con THUMB_SIZE en wpelib/config.py

APP_CSS = """
@define-color wpe_bg #1c1d24;
@define-color wpe_surface #262834;
@define-color wpe_surface_alt #2f3140;
@define-color wpe_border alpha(#ffffff, 0.09);
@define-color wpe_accent #7c6cf0;
@define-color wpe_accent_hover #9384f5;
@define-color wpe_text #eceef5;
@define-color wpe_text_dim #9a9cb5;

window {
    background-color: @wpe_bg;
    color: @wpe_text;
    font-size: 10.5pt;
}

label { color: @wpe_text; }
label.dim-label { color: @wpe_text_dim; }

.wpe-frame-title {
    color: @wpe_accent_hover;
    font-weight: 700;
    padding: 0 4px;
}

frame {
    background-color: @wpe_surface;
    border: 1px solid @wpe_border;
    border-radius: 10px;
    padding: 2px;
}
frame > border { border: none; }

button {
    background-image: none;
    background-color: @wpe_surface_alt;
    color: @wpe_text;
    border: 1px solid @wpe_border;
    border-radius: 8px;
    padding: 6px 12px;
    transition: background-color 150ms ease;
}
button:hover {
    background-color: alpha(@wpe_accent, 0.28);
    border-color: @wpe_accent;
}
button:active { background-color: alpha(@wpe_accent, 0.45); }
button.suggested-action {
    background-color: @wpe_accent;
    color: #ffffff;
    border: none;
}
button.suggested-action:hover { background-color: @wpe_accent_hover; }

entry, spinbutton {
    background-color: @wpe_surface_alt;
    color: @wpe_text;
    border: 1px solid @wpe_border;
    border-radius: 8px;
    padding: 5px 8px;
    caret-color: @wpe_text;
}
entry:focus, spinbutton:focus { border-color: @wpe_accent; }

combobox button {
    background-color: @wpe_surface_alt;
    border: 1px solid @wpe_border;
    border-radius: 8px;
}
combobox window menu, menu {
    background-color: @wpe_surface_alt;
    color: @wpe_text;
    border-radius: 8px;
}

checkbutton, radiobutton { color: @wpe_text; }
checkbutton check, radiobutton radio {
    background-color: @wpe_surface_alt;
    border: 1px solid @wpe_border;
}
checkbutton check:checked, radiobutton radio:checked {
    background-color: @wpe_accent;
    border-color: @wpe_accent;
}

scrolledwindow {
    border: 1px solid @wpe_border;
    border-radius: 10px;
    background-color: @wpe_surface;
}
scrolledwindow undershoot, scrolledwindow overshoot { background: none; }

iconview {
    background-color: transparent;
    color: @wpe_text;
}
iconview .cell {
    border-radius: 10px;
    padding: 4px;
}
iconview .cell:selected {
    background-color: alpha(@wpe_accent, 0.35);
    color: @wpe_text;
}

treeview {
    background-color: @wpe_surface;
    color: @wpe_text;
    border-radius: 8px;
}
treeview:selected {
    background-color: alpha(@wpe_accent, 0.35);
    color: @wpe_text;
}
treeview header button {
    background-color: @wpe_surface_alt;
    border-radius: 0;
}

textview, textview text {
    background-color: @wpe_surface;
    color: @wpe_text_dim;
    border-radius: 8px;
    font-family: monospace;
    font-size: 9pt;
}

progressbar trough { background-color: @wpe_surface_alt; border-radius: 8px; }
progressbar progress { background-color: @wpe_accent; border-radius: 8px; }

/* Cuadricula de tarjetas de wallpaper */
flowbox { background-color: transparent; }
flowboxchild {
    border-radius: 12px;
    padding: 4px;
    border: 2px solid transparent;
    transition: background-color 150ms ease, border-color 150ms ease;
}
flowboxchild:hover { background-color: alpha(@wpe_accent, 0.10); }
flowboxchild:selected {
    background-color: alpha(@wpe_accent, 0.22);
    border-color: @wpe_accent;
}
.wpe-card-title {
    font-weight: 600;
    font-size: 10pt;
}
.wpe-card-subtitle { font-size: 8.5pt; }
.wpe-badge {
    background-color: alpha(#000000, 0.65);
    color: @wpe_text;
    font-size: 8pt;
    padding: 2px 6px;
    border-radius: 6px;
    margin: 6px;
    border: none;
}
button.wpe-heart {
    background-color: alpha(#000000, 0.45);
    border-radius: 999px;
    padding: 4px;
    margin: 6px;
    border: none;
    min-width: 0;
    min-height: 0;
}
button.wpe-heart:checked, button.wpe-heart:checked:hover {
    background-color: alpha(@wpe_accent, 0.85);
}
.wpe-hover-bar {
    background-color: alpha(#000000, 0.6);
    border-radius: 999px;
    padding: 2px;
}
.wpe-hover-bar button {
    min-width: 0;
    min-height: 0;
    padding: 6px;
    border-radius: 999px;
    border: none;
    background-color: transparent;
}
.wpe-hover-bar button:hover { background-color: alpha(@wpe_accent, 0.5); }

/* Chips (monitores) y pestanas (Todos/Favoritos/Recientes/Ocultos) */
button.wpe-chip {
    border-radius: 999px;
    padding: 6px 14px;
}
button.wpe-chip:checked {
    background-color: @wpe_accent;
    color: #ffffff;
    border-color: @wpe_accent;
}
button.wpe-tab {
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 6px 12px;
}
button.wpe-tab:checked {
    border-bottom: 2px solid @wpe_accent;
    color: @wpe_accent_hover;
    background-color: transparent;
}

/* Buscador grande y protagonista */
entry.wpe-search-big {
    font-size: 12pt;
    padding: 10px 14px;
    border-radius: 10px;
}

/* Barra lateral de navegacion */
box.wpe-sidebar {
    background-color: @wpe_surface;
    border-right: 1px solid @wpe_border;
}
button.wpe-nav-item {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px 10px;
}
button.wpe-nav-item:checked {
    background-color: alpha(@wpe_accent, 0.25);
    color: @wpe_accent_hover;
}
button.wpe-nav-item:hover { background-color: alpha(@wpe_accent, 0.10); }

/* Panel de detalle */
box.wpe-detail-panel {
    background-color: @wpe_surface;
    border-left: 1px solid @wpe_border;
}
.wpe-detail-title { font-size: 13pt; font-weight: 700; }
.wpe-detail-section-title {
    color: @wpe_text_dim;
    font-weight: 700;
    font-size: 8.5pt;
}
.wpe-tag-chip {
    background-color: @wpe_surface_alt;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 8.5pt;
}

button.wpe-assigned-badge {
    background-color: @wpe_accent;
    color: #ffffff;
    border-radius: 999px;
    padding: 4px;
    margin: 6px;
    border: none;
    min-width: 0;
    min-height: 0;
}
button.wpe-card-menu {
    background-color: alpha(#000000, 0.45);
    border-radius: 999px;
    padding: 2px;
    margin: 6px;
    border: none;
    min-width: 0;
    min-height: 0;
}
button.wpe-card-menu:hover { background-color: alpha(@wpe_accent, 0.6); }
"""


def apply_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(APP_CSS.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    Gtk.StyleContext.add_provider_for_screen(
        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def labeled_frame(title):
    frame = Gtk.Frame()
    label = Gtk.Label()
    label.set_markup(f"<b>{GLib.markup_escape_text(title)}</b>")
    label.get_style_context().add_class("wpe-frame-title")
    frame.set_label_widget(label)
    frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
    return frame


def open_in_steam(wid):
    try:
        subprocess.Popen(["xdg-open", f"steam://url/CommunityFilePage/{wid}"])
    except Exception:
        subprocess.Popen(["xdg-open", f"https://steamcommunity.com/sharedfiles/filedetails/?id={wid}"])


def icon_button(label, icon_name):
    btn = Gtk.Button.new_with_label(label)
    btn.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))
    btn.set_always_show_image(True)
    return btn


def chip_button(label):
    btn = Gtk.ToggleButton(label=label)
    btn.get_style_context().add_class("wpe-chip")
    return btn


def make_tab_group(labels):
    """Fila de botones tipo 'pestana' con seleccion exclusiva (radio buttons sin
    el circulo indicador). Devuelve (widget_fila, {etiqueta: boton})."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
    buttons = {}
    first = None
    for label in labels:
        btn = (
            Gtk.RadioButton.new_with_label_from_widget(first, label)
            if first else Gtk.RadioButton.new_with_label(None, label)
        )
        if first is None:
            first = btn
        btn.set_mode(False)
        btn.get_style_context().add_class("wpe-tab")
        box.pack_start(btn, False, False, 0)
        buttons[label] = btn
    return box, buttons


class WallpaperCard(Gtk.EventBox):
    """Tarjeta de un wallpaper para la cuadricula: miniatura (con favorito,
    insignia de asignado/oculto/fallo, boton de menu y acciones rapidas al
    pasar el raton, todo superpuesto SOLO sobre la imagen) y debajo el
    titulo/subtitulo. Doble clic asigna; clic derecho o el boton "..." abren
    el menu contextual."""

    def __init__(self, wid, title, subtitle, pixbuf, favorite=False, badge=None, assigned=False):
        super().__init__()
        self.wid = wid
        self.on_assign = None
        self.on_preview = None
        self.on_toggle_favorite = None
        self.on_context_menu = None

        self.set_visible_window(False)
        self.add_events(
            Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
        )

        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.add(card_box)

        # --- Overlay SOLO sobre la miniatura ---
        image_overlay = Gtk.Overlay()
        self.image = Gtk.Image.new_from_pixbuf(pixbuf)
        image_overlay.add(self.image)

        self.assigned_btn = Gtk.Button()
        self.assigned_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.assigned_btn.set_image(Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.BUTTON))
        self.assigned_btn.get_style_context().add_class("wpe-assigned-badge")
        self.assigned_btn.set_halign(Gtk.Align.START)
        self.assigned_btn.set_valign(Gtk.Align.START)
        self.assigned_btn.set_sensitive(False)
        self.assigned_btn.set_tooltip_text("Asignado a la pantalla activa")
        self.assigned_btn.set_no_show_all(True)
        image_overlay.add_overlay(self.assigned_btn)

        self.badge_label = Gtk.Label()
        self.badge_label.set_halign(Gtk.Align.START)
        self.badge_label.set_valign(Gtk.Align.END)
        self.badge_label.get_style_context().add_class("wpe-badge")
        self.badge_label.set_no_show_all(True)
        image_overlay.add_overlay(self.badge_label)

        self.heart_btn = Gtk.ToggleButton()
        self.heart_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.heart_btn.get_style_context().add_class("wpe-heart")
        self.heart_btn.set_halign(Gtk.Align.END)
        self.heart_btn.set_valign(Gtk.Align.START)
        self.heart_btn.set_active(favorite)
        self._update_heart_icon()
        self.heart_btn.connect("toggled", self._on_heart_toggled)
        image_overlay.add_overlay(self.heart_btn)

        self.menu_btn = Gtk.Button()
        self.menu_btn.set_relief(Gtk.ReliefStyle.NONE)
        self.menu_btn.get_style_context().add_class("wpe-card-menu")
        self.menu_btn.set_image(Gtk.Image.new_from_icon_name("view-more-symbolic", Gtk.IconSize.BUTTON))
        self.menu_btn.set_halign(Gtk.Align.END)
        self.menu_btn.set_valign(Gtk.Align.END)
        self.menu_btn.connect("clicked", self._on_menu_clicked)
        image_overlay.add_overlay(self.menu_btn)

        self.hover_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.hover_bar.set_halign(Gtk.Align.CENTER)
        self.hover_bar.set_valign(Gtk.Align.CENTER)
        self.hover_bar.get_style_context().add_class("wpe-hover-bar")

        preview_btn = Gtk.Button()
        preview_btn.set_image(Gtk.Image.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON))
        preview_btn.set_tooltip_text("Vista previa")
        preview_btn.connect("clicked", lambda *_: self.on_preview and self.on_preview(self.wid))
        self.hover_bar.pack_start(preview_btn, False, False, 0)

        assign_btn = Gtk.Button()
        assign_btn.set_image(Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.BUTTON))
        assign_btn.set_tooltip_text("Asignar a la pantalla seleccionada")
        assign_btn.connect("clicked", lambda *_: self.on_assign and self.on_assign(self.wid))
        self.hover_bar.pack_start(assign_btn, False, False, 0)

        self.hover_bar.set_no_show_all(True)
        self.hover_bar.hide()
        image_overlay.add_overlay(self.hover_bar)

        card_box.pack_start(image_overlay, False, False, 0)

        # --- Titulo y subtitulo, debajo de la imagen ---
        self.title_label = Gtk.Label(label=title)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_max_width_chars(1)
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.get_style_context().add_class("wpe-card-title")
        card_box.pack_start(self.title_label, False, False, 0)

        self.subtitle_label = Gtk.Label(label=subtitle)
        self.subtitle_label.set_halign(Gtk.Align.START)
        self.subtitle_label.get_style_context().add_class("dim-label")
        self.subtitle_label.get_style_context().add_class("wpe-card-subtitle")
        card_box.pack_start(self.subtitle_label, False, False, 0)

        self.set_badge(badge)
        self.set_assigned(assigned)

        self.connect("enter-notify-event", self._on_enter)
        self.connect("leave-notify-event", self._on_leave)
        self.connect("button-press-event", self._on_button_press)

    def _on_enter(self, widget, event):
        self.hover_bar.show()
        return False

    def _on_leave(self, widget, event):
        self.hover_bar.hide()
        return False

    def _on_button_press(self, widget, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            if self.on_assign:
                self.on_assign(self.wid)
            return True
        if event.button == 3:
            if self.on_context_menu:
                self.on_context_menu(self, event, self.wid)
            return True
        return False

    def _on_menu_clicked(self, button):
        if self.on_context_menu:
            self.on_context_menu(self, None, self.wid)

    def _on_heart_toggled(self, btn):
        self._update_heart_icon()
        if self.on_toggle_favorite:
            self.on_toggle_favorite(self.wid, btn.get_active())

    def _update_heart_icon(self):
        icon = "starred-symbolic" if self.heart_btn.get_active() else "non-starred-symbolic"
        self.heart_btn.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON))

    def set_pixbuf(self, pixbuf):
        self.image.set_from_pixbuf(pixbuf)

    def set_badge(self, text):
        if text:
            self.badge_label.set_text(text)
            self.badge_label.show()
        else:
            self.badge_label.hide()

    def set_assigned(self, value):
        self.assigned_btn.set_visible(bool(value))

    def set_favorite(self, value):
        self.heart_btn.set_active(value)


class CheckListButton(Gtk.MenuButton):
    """Boton desplegable con checkboxes para elegir varias opciones a la vez."""

    def __init__(self, title, options, on_change=None, initially_checked=None):
        super().__init__()
        self.title = title
        self.on_change = on_change
        self.checks = {}

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.box.set_border_width(8)
        popover = Gtk.Popover()
        popover.add(self.box)
        self.set_popover(popover)

        self.set_options(options, checked=initially_checked)

    def set_options(self, options, checked=None):
        preserve = set(checked) if checked is not None else set(self.get_selected())
        for child in list(self.box.get_children()):
            self.box.remove(child)
        self.checks = {}
        for opt in options:
            cb = Gtk.CheckButton(label=opt)
            cb.set_active(opt in preserve)
            cb.connect("toggled", self._on_toggled)
            self.box.pack_start(cb, False, False, 0)
            self.checks[opt] = cb
        self.box.show_all()
        self._update_label()

    def _on_toggled(self, cb):
        self._update_label()
        if self.on_change:
            self.on_change()

    def _update_label(self):
        selected = self.get_selected()
        if not selected:
            text = f"{self.title}: Todas"
        elif len(selected) <= 2:
            text = f"{self.title}: {', '.join(selected)}"
        else:
            text = f"{self.title}: {len(selected)} seleccionadas"
        self.set_label(text)

    def get_selected(self):
        return [opt for opt, cb in self.checks.items() if cb.get_active()]
