"""
Interactive Acoustic Calibration Dialog
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from typing import List, Callable, Optional
from pipesync.models import AudioDevice
from pipesync.calibrator import AudioCalibrator


class CalibrationDialog(Adw.Window):
    """
    Modal dialog providing an acoustic metronome and visual beat flasher
    to let users calibrate millisecond delay by ear.
    """

    def __init__(
        self,
        parent_window: Gtk.Window,
        devices: List[AudioDevice],
        calibrator: AudioCalibrator,
        on_delay_updated: Optional[Callable[[AudioDevice, float], None]] = None,
    ):
        super().__init__()
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_title("Acoustic Latency Calibrator")
        self.set_default_size(520, 560)

        self.devices = devices
        self.calibrator = calibrator
        self.on_delay_updated = on_delay_updated
        self._pulse_timer: Optional[int] = None

        self._build_ui()
        self.connect("close-request", self._on_close)

    def _build_ui(self):
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(content)

        # Header bar
        header = Adw.HeaderBar()
        content.append(header)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        content.append(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(500)
        clamp.set_margin_top(20)
        clamp.set_margin_bottom(20)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        scroll.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        clamp.set_child(box)

        # Visual Flash / Pulse Circle
        pulse_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pulse_box.set_halign(Gtk.Align.CENTER)

        self.pulse_circle = Gtk.Box()
        self.pulse_circle.set_size_request(64, 64)
        self.pulse_circle.add_css_class("card")
        self.pulse_circle.set_halign(Gtk.Align.CENTER)
        self._set_pulse_active(False)
        pulse_box.append(self.pulse_circle)

        pulse_label = Gtk.Label(label="Acoustic Reference Pulse")
        pulse_label.add_css_class("caption")
        pulse_box.append(pulse_label)
        box.append(pulse_box)

        # Instructions Group
        instr_group = Adw.PreferencesGroup()
        instr_group.set_title("How to Calibrate")
        instr_row = Adw.ActionRow()
        instr_row.set_title("1. Wear both earphones simultaneously")
        instr_row.set_subtitle("e.g. Put Wired Earphone in Left ear, and Bluetooth Earbud in Right ear.")
        instr_group.add(instr_row)

        instr_row2 = Adw.ActionRow()
        instr_row2.set_title("2. Start the Metronome &amp; Listen")
        instr_row2.set_subtitle("If unaligned, you will hear a double click ('da-dum').")
        instr_group.add(instr_row2)

        instr_row3 = Adw.ActionRow()
        instr_row3.set_title("3. Adjust Delay Slider")
        instr_row3.set_subtitle("Slide until both clicks merge into a single, sharp transient centered in your head.")
        instr_group.add(instr_row3)
        box.append(instr_group)

        # Metronome Controls Group
        metro_group = Adw.PreferencesGroup()
        metro_group.set_title("Calibration Metronome")

        self.metro_btn = Gtk.Button()
        self.metro_btn.set_label("Start Calibration Metronome")
        self.metro_btn.add_css_class("suggested-action")
        self.metro_btn.add_css_class("pill")
        self.metro_btn.set_size_request(-1, 48)
        self.metro_btn.connect("clicked", self._toggle_metronome)
        metro_group.add(self.metro_btn)
        box.append(metro_group)

        # Device Fine Tuning
        dev_group = Adw.PreferencesGroup()
        dev_group.set_title("Adjust Device Latency Offset")

        for dev in self.devices:
            if not dev.enabled:
                continue
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(dev.description))
            row.set_subtitle(f"Base: {dev.hardware_latency_ms:.1f}ms")

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 400.0, 1.0)
            scale.set_value(dev.compensation_delay_ms)
            scale.set_size_request(150, -1)

            lbl = Gtk.Label(label=f"+{dev.compensation_delay_ms:.0f}ms")
            lbl.set_size_request(55, -1)
            lbl.add_css_class("numeric")

            def _on_change(s, d=dev, l=lbl):
                val = round(s.get_value(), 1)
                d.compensation_delay_ms = val
                l.set_text(f"+{val:.0f}ms")
                if self.on_delay_updated:
                    self.on_delay_updated(d, val)

            scale.connect("value-changed", _on_change)

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.append(scale)
            row_box.append(lbl)
            row.add_suffix(row_box)
            dev_group.add(row)

        box.append(dev_group)

    def _set_pulse_active(self, active: bool):
        if active:
            self.pulse_circle.set_css_classes(["card", "suggested-action"])
        else:
            self.pulse_circle.set_css_classes(["card"])

    def _toggle_metronome(self, btn):
        if self.calibrator.is_metronome_active:
            self.calibrator.stop_metronome()
            self.metro_btn.set_label("Start Calibration Metronome")
            self.metro_btn.remove_css_class("destructive-action")
            self.metro_btn.add_css_class("suggested-action")
            if self._pulse_timer:
                GLib.source_remove(self._pulse_timer)
                self._pulse_timer = None
            self._set_pulse_active(False)
        else:
            self.calibrator.start_metronome(interval_sec=0.6)
            self.metro_btn.set_label("Stop Calibration Metronome")
            self.metro_btn.remove_css_class("suggested-action")
            self.metro_btn.add_css_class("destructive-action")

            # Pulse the visual circle
            def _pulse_loop():
                if not self.calibrator.is_metronome_active:
                    self._set_pulse_active(False)
                    return False
                self._set_pulse_active(True)
                GLib.timeout_add(100, lambda: (self._set_pulse_active(False), False)[1])
                return True

            self._pulse_timer = GLib.timeout_add(600, _pulse_loop)

    def _on_close(self, win):
        self.calibrator.stop_metronome()
        if self._pulse_timer:
            GLib.source_remove(self._pulse_timer)
            self._pulse_timer = None
        return False
