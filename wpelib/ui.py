"""Widgets y estilos GTK reutilizables: el tema oscuro (CSS), marcos con
titulo, botones con icono, y el desplegable de checkboxes multi-seleccion."""
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk

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
