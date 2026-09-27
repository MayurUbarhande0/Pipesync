"""
Device Card Widget for Libadwaita GUI
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from typing import Callable, Optional
from pipesync.models import AudioDevice


class DeviceCard(Adw.ExpanderRow):
    """
    An expandable modern card representing a single audio output device
    with latency sliders, volume, mute, and test controls.
    """

    def __init__(
        self,
        device: AudioDevice,
        on_delay_changed: Optional[Callable[[AudioDevice, float], None]] = None,
        on_enabled_toggled: Optional[Callable[[AudioDevice, bool], None]] = None,
        on_test_beep: Optional[Callable[[AudioDevice], None]] = None,
        on_volume_changed: Optional[Callable[[AudioDevice, float], None]] = None,
        on_mute_toggled: Optional[Callable[[AudioDevice, bool], None]] = None,
    ):
        super().__init__()
        self.device = device
        self.on_delay_changed = on_delay_changed
        self.on_enabled_toggled = on_enabled_toggled
        self.on_test_beep = on_test_beep
        self.on_volume_changed = on_volume_changed
        self.on_mute_toggled = on_mute_toggled
        self._delay_debounce_timer: Optional[int] = None
        self._vol_debounce_timer: Optional[int] = None

        self.set_title(GLib.markup_escape_text(device.description))
        self._update_subtitle()
        self.set_expanded(True)

        # Icon prefix
        icon = Gtk.Image.new_from_icon_name(device.icon_name)
        icon.set_icon_size(Gtk.IconSize.LARGE)
        self.add_prefix(icon)

        # Enable switch suffix
        self.switch = Gtk.Switch()
        self.switch.set_active(device.enabled)
        self.switch.set_valign(Gtk.Align.CENTER)
        self.switch.set_tooltip_text("Enable / disable in shared broadcast")
        self.switch.connect("notify::active", self._on_switch_toggled)
        self.add_suffix(self.switch)

        # Test Beep button suffix
        self.test_btn = Gtk.Button.new_from_icon_name("audio-volume-high-symbolic")
        self.test_btn.set_tooltip_text(f"Play test sound to {device.description}")
        self.test_btn.set_valign(Gtk.Align.CENTER)
        self.test_btn.add_css_class("flat")
        self.test_btn.connect("clicked", self._on_test_clicked)
        self.add_suffix(self.test_btn)

        # Build expanded rows
        self._build_delay_row()
        self._build_volume_row()

    def _update_subtitle(self):
        codec_str = f" • Codec: {self.device.codec.upper()}" if self.device.codec else ""
        type_str = self.device.device_type.capitalize()
        status_str = f"Base: {self.device.hardware_latency_ms:.1f}ms • Delay: +{self.device.compensation_delay_ms:.1f}ms • Total: {self.device.total_latency_ms:.1f}ms"
        self.set_subtitle(GLib.markup_escape_text(f"{type_str}{codec_str} | {status_str}"))

    def _build_delay_row(self):
        delay_row = Adw.ActionRow()
        delay_row.set_title("Added Compensation Delay")
        delay_row.set_subtitle("Buffers audio for this output so it hits your ears in sync with others")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)

        # -10ms button
        btn_minus10 = Gtk.Button(label="-10")
        btn_minus10.add_css_class("flat")
        btn_minus10.connect("clicked", lambda b: self._step_delay(-10.0))
        box.append(btn_minus10)

        # -1ms button
        btn_minus1 = Gtk.Button(label="-1")
        btn_minus1.add_css_class("flat")
        btn_minus1.connect("clicked", lambda b: self._step_delay(-1.0))
        box.append(btn_minus1)

        # Scale slider (0 to 500ms)
        self.scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0.0, 500.0, 1.0
        )
        self.scale.set_value(self.device.compensation_delay_ms)
        self.scale.set_size_request(200, -1)
        self.scale.connect("value-changed", self._on_scale_value_changed)
        box.append(self.scale)

        # +1ms button
        btn_plus1 = Gtk.Button(label="+1")
        btn_plus1.add_css_class("flat")
        btn_plus1.connect("clicked", lambda b: self._step_delay(1.0))
        box.append(btn_plus1)

        # +10ms button
        btn_plus10 = Gtk.Button(label="+10")
        btn_plus10.add_css_class("flat")
        btn_plus10.connect("clicked", lambda b: self._step_delay(10.0))
        box.append(btn_plus10)

        # Exact readout label
        self.delay_label = Gtk.Label()
        self.delay_label.set_text(f"+{self.device.compensation_delay_ms:.1f} ms")
        self.delay_label.add_css_class("numeric")
        self.delay_label.add_css_class("heading")
        self.delay_label.set_size_request(80, -1)
        box.append(self.delay_label)

        delay_row.add_suffix(box)
        self.add_row(delay_row)

    def _build_volume_row(self):
        vol_row = Adw.ActionRow()
        vol_row.set_title("Hardware Output Volume")
        vol_row.set_subtitle("Adjusts the real volume for this specific device in PipeWire")

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_valign(Gtk.Align.CENTER)

        # Mute toggle button
        self.mute_btn = Gtk.Button.new_from_icon_name(
            "audio-volume-muted-symbolic" if self.device.muted else "audio-volume-high-symbolic"
        )
        self.mute_btn.add_css_class("flat")
        self.mute_btn.set_tooltip_text("Mute / Unmute device")
        self.mute_btn.connect("clicked", self._on_mute_clicked)
        box.append(self.mute_btn)

        # Volume slider (0.0 to 1.5)
        self.vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.5, 0.01)
        self.vol_scale.set_value(self.device.volume)
        self.vol_scale.set_size_request(200, -1)
        self.vol_scale.connect("value-changed", self._on_vol_changed)
        box.append(self.vol_scale)

        self.vol_label = Gtk.Label(label=f"{int(self.device.volume * 100)}%")
        self.vol_label.add_css_class("numeric")
        self.vol_label.set_size_request(50, -1)
        box.append(self.vol_label)

        vol_row.add_suffix(box)
        self.add_row(vol_row)

    def _step_delay(self, delta: float):
        new_val = max(0.0, min(500.0, self.device.compensation_delay_ms + delta))
        self.scale.set_value(new_val)

    def _on_scale_value_changed(self, scale: Gtk.Scale):
        val = round(scale.get_value(), 1)
        self.device.compensation_delay_ms = val
        self.delay_label.set_text(f"+{val:.1f} ms")
        self._update_subtitle()

        # Debounce the engine update by 120ms to keep dragging smooth and glitch-free
        if self._delay_debounce_timer:
            GLib.source_remove(self._delay_debounce_timer)

        def _fire():
            if self.on_delay_changed:
                self.on_delay_changed(self.device, val)
            self._delay_debounce_timer = None
            return False

        self._delay_debounce_timer = GLib.timeout_add(120, _fire)

    def _on_vol_changed(self, scale: Gtk.Scale):
        vol = round(scale.get_value(), 2)
        self.device.volume = vol
        self.vol_label.set_text(f"{int(vol * 100)}%")

        if self._vol_debounce_timer:
            GLib.source_remove(self._vol_debounce_timer)

        def _fire_vol():
            if self.on_volume_changed:
                self.on_volume_changed(self.device, vol)
            self._vol_debounce_timer = None
            return False

        self._vol_debounce_timer = GLib.timeout_add(50, _fire_vol)

    def _on_mute_clicked(self, btn):
        new_mute = not self.device.muted
        self.device.muted = new_mute
        icon_name = "audio-volume-muted-symbolic" if new_mute else "audio-volume-high-symbolic"
        self.mute_btn.set_icon_name(icon_name)
        if self.on_mute_toggled:
            self.on_mute_toggled(self.device, new_mute)

    def _on_switch_toggled(self, switch, gparam):
        active = switch.get_active()
        self.device.enabled = active
        if self.on_enabled_toggled:
            self.on_enabled_toggled(self.device, active)

    def _on_test_clicked(self, btn):
        if self.on_test_beep:
            self.on_test_beep(self.device)

    def set_delay_programmatic(self, delay_ms: float):
        """Sets the delay value from an external event (e.g. auto-align)."""
        self.device.compensation_delay_ms = delay_ms
        self.scale.set_value(delay_ms)
        self.delay_label.set_text(f"+{delay_ms:.1f} ms")
        self._update_subtitle()
