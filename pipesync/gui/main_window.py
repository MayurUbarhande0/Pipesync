"""
Main Application Window for PipeSync (Libadwaita / GTK4)
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

import logging
from typing import List, Dict, Optional, Set

from pipesync.constants import (
    APP_NAME,
    QUANTUM_PRESETS,
    DEFAULT_QUANTUM,
    MASTER_SINK_NAME,
)
from pipesync.models import AudioDevice
from pipesync.device_detector import DeviceDetector
from pipesync.optimizer import PipeWireOptimizer
from pipesync.sync_engine import SyncEngine
from pipesync.calibrator import AudioCalibrator
from pipesync.helvum_bridge import HelvumBridge
from pipesync.video_sync import VideoSyncHelper
from pipesync.config import ConfigManager
from pipesync.gui.device_card import DeviceCard
from pipesync.gui.calibration_dialog import CalibrationDialog

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """
    Main Libadwaita window managing multi-device audio synchronization,
    PipeWire latency optimization, and Helvum patchbay integration.
    """

    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title(APP_NAME)
        self.set_default_size(760, 840)

        # Core Services
        self.config = ConfigManager()
        self.detector = DeviceDetector()
        self.optimizer = PipeWireOptimizer()
        self.engine = SyncEngine()
        self.calibrator = AudioCalibrator()
        self.helvum = HelvumBridge()

        self.devices: List[AudioDevice] = []
        self.device_cards: Dict[str, DeviceCard] = {}
        self._known_sink_names: Set[str] = set()

        self._build_ui()
        self.refresh_devices(initial=True)

        # Periodic timer for automatic hotplug detection (every 2.5 seconds)
        self._poll_timer = GLib.timeout_add(2500, self._check_device_hotplug)

        self.connect("close-request", self._on_close)

    def _build_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(root_box)

        # Header Bar
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(
            title=APP_NAME,
            subtitle="Multi-Device Latency Optimizer &amp; Helvum Wrapper",
        )
        header.set_title_widget(title_widget)

        # Refresh button
        refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh audio devices")
        refresh_btn.connect("clicked", lambda b: self.refresh_devices())
        header.pack_start(refresh_btn)

        # Helvum launch button
        if self.helvum.is_available:
            helvum_btn = Gtk.Button.new_with_label("Open Helvum")
            helvum_btn.set_icon_name("network-workgroup-symbolic")
            helvum_btn.add_css_class("flat")
            helvum_btn.set_tooltip_text("Launch Helvum graphical patchbay")
            helvum_btn.connect("clicked", lambda b: self.helvum.launch())
            header.pack_end(helvum_btn)

        root_box.append(header)

        # Scrolled content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        root_box.append(scroll)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(720)
        clamp.set_margin_top(16)
        clamp.set_margin_bottom(24)
        clamp.set_margin_start(16)
        clamp.set_margin_end(16)
        scroll.set_child(clamp)

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp.set_child(content_box)

        # 1. Master Hub Control Banner
        self._build_master_banner(content_box)

        # 2. PipeWire Latency Optimizer Section
        self._build_optimizer_section(content_box)

        # 3. Video Player Synchronization Card
        self._build_video_sync_card(content_box)

        # 4. Active Audio Streams Section
        self._build_active_streams_card(content_box)

        # 5. Connected Devices Section
        self.devices_group = Adw.PreferencesGroup()
        self.devices_group.set_title("Connected Output Devices")
        self.devices_group.set_description(
            "Each device has independent delay compensation so all outputs arrive at listeners' ears in sync."
        )
        content_box.append(self.devices_group)

    def _build_master_banner(self, parent: Gtk.Box):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.add_css_class("card")
        card.set_margin_top(4)

        # Inner padding box
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        inner.set_margin_top(16)
        inner.set_margin_bottom(16)
        inner.set_margin_start(18)
        inner.set_margin_end(18)
        card.append(inner)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        inner.append(top_row)

        hub_info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        hub_info.set_hexpand(True)
        self.hub_title = Gtk.Label(label="Synchronized Broadcast Hub")
        self.hub_title.set_halign(Gtk.Align.START)
        self.hub_title.add_css_class("title-3")
        hub_info.append(self.hub_title)

        self.hub_status = Gtk.Label(label="○ Hub Standby - Click switch to activate")
        self.hub_status.set_halign(Gtk.Align.START)
        self.hub_status.add_css_class("dim-label")
        hub_info.append(self.hub_status)
        top_row.append(hub_info)

        # Master Switch
        self.master_switch = Gtk.Switch()
        self.master_switch.set_valign(Gtk.Align.CENTER)
        self.master_switch.connect("notify::active", self._on_master_switch_toggled)
        top_row.append(self.master_switch)

        # Action Buttons Row
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        inner.append(btn_row)

        # 1-Click Auto Align
        auto_btn = Gtk.Button.new_with_label("Auto-Sync All Devices")
        auto_btn.set_icon_name("emblem-music-symbolic")
        auto_btn.add_css_class("suggested-action")
        auto_btn.add_css_class("pill")
        auto_btn.set_tooltip_text("Automatically calculate delay so wired earphones match Bluetooth")
        auto_btn.connect("clicked", lambda b: self.auto_align_devices())
        btn_row.append(auto_btn)

        # Calibration button
        cal_btn = Gtk.Button.new_with_label("Acoustic Calibrator")
        cal_btn.set_icon_name("audio-volume-high-symbolic")
        cal_btn.add_css_class("pill")
        cal_btn.set_tooltip_text("Launch audio metronome to calibrate delays by ear")
        cal_btn.connect("clicked", lambda b: self.open_calibrator())
        btn_row.append(cal_btn)

        parent.append(card)

    def _build_optimizer_section(self, parent: Gtk.Box):
        opt_group = Adw.PreferencesGroup()
        opt_group.set_title("PipeWire Latency Optimization Layer")
        opt_group.set_description(
            "Lowers PipeWire quantum buffer size to strip out system lag and minimize audio jitter."
        )

        row = Adw.ActionRow()
        row.set_title("Buffer Quantum Profile")
        row.set_subtitle("Controls the underlying PipeWire processing block size")

        state = self.optimizer.get_current_state()

        # Dropdown for quantum
        self.quantum_combo = Gtk.DropDown.new_from_strings([
            "Ultra-Low (128 samples / ~2.7ms)",
            "Low-Latency (256 samples / ~5.3ms) [Recommended]",
            "Balanced (512 samples / ~10.7ms)",
            "Standard (1024 samples / ~21.3ms)",
        ])

        idx_map = {128: 0, 256: 1, 512: 2, 1024: 3}
        self.quantum_combo.set_selected(idx_map.get(state.quantum, 1))
        self.quantum_combo.set_valign(Gtk.Align.CENTER)
        self.quantum_combo.connect("notify::selected", self._on_quantum_selected)
        row.add_suffix(self.quantum_combo)

        opt_group.add(row)
        parent.append(opt_group)

    def _build_video_sync_card(self, parent: Gtk.Box):
        video_group = Adw.PreferencesGroup()
        video_group.set_title("Media Player Video Alignment")
        video_group.set_description(
            "When earphones are synchronized together, use this offset in your player so video matches dialogue."
        )

        self.video_row = Adw.ActionRow()
        self.video_row.set_title("Player Audio Track Delay")
        self.video_row.set_subtitle("Calculating alignment...")

        # Copy buttons
        copy_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        copy_box.set_valign(Gtk.Align.CENTER)

        self.vlc_badge = Gtk.Button(label="VLC: 0ms")
        self.vlc_badge.add_css_class("flat")
        self.vlc_badge.set_tooltip_text("Click to copy VLC audio track delay (Press 'j' in VLC)")
        self.vlc_badge.connect("clicked", lambda b: self._copy_to_clipboard(self.last_vlc_str))
        copy_box.append(self.vlc_badge)

        self.mpv_badge = Gtk.Button(label="MPV: 0.000")
        self.mpv_badge.add_css_class("flat")
        self.mpv_badge.set_tooltip_text("Click to copy MPV audio-delay property")
        self.mpv_badge.connect("clicked", lambda b: self._copy_to_clipboard(self.last_mpv_str))
        copy_box.append(self.mpv_badge)

        self.video_row.add_suffix(copy_box)
        video_group.add(self.video_row)
        parent.append(video_group)

        self.last_vlc_str = "0 ms"
        self.last_mpv_str = "0.000"

    def _build_active_streams_card(self, parent: Gtk.Box):
        self.streams_group = Adw.PreferencesGroup()
        self.streams_group.set_title("Active Audio Applications")
        self.streams_group.set_description(
            "Applications currently playing sound. Direct them to PipeSync to broadcast across your earphones."
        )

        header_row = Adw.ActionRow()
        header_row.set_title("Playback Stream Rerouting")
        header_row.set_subtitle("Direct all active media players into PipeSync Master Hub")

        reroute_btn = Gtk.Button.new_with_label("Route All to PipeSync")
        reroute_btn.set_icon_name("media-playlist-shuffle-symbolic")
        reroute_btn.add_css_class("suggested-action")
        reroute_btn.set_valign(Gtk.Align.CENTER)
        reroute_btn.connect("clicked", lambda b: self._reroute_all_streams())
        header_row.add_suffix(reroute_btn)
        self.streams_group.add(header_row)

        self.stream_rows_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.streams_group.add(self.stream_rows_box)
        parent.append(self.streams_group)

        self._update_active_streams()

    def _update_active_streams(self):
        if not hasattr(self, "stream_rows_box"):
            return
        streams = self.engine.get_active_audio_streams()

        while child := self.stream_rows_box.get_first_child():
            self.stream_rows_box.remove(child)

        if not streams:
            no_stream_row = Adw.ActionRow()
            no_stream_row.set_title("No Active Playback Streams")
            no_stream_row.set_subtitle("Play audio in your browser or media player to see it listed here.")
            self.stream_rows_box.append(no_stream_row)
            return

        for s in streams:
            row = Adw.ActionRow()
            row.set_title(GLib.markup_escape_text(s["app_name"]))
            sub = s["media_title"] if s["media_title"] else "Active playback stream"
            row.set_subtitle(GLib.markup_escape_text(sub))

            badge = Gtk.Label()
            badge.set_valign(Gtk.Align.CENTER)
            badge.set_margin_end(8)
            badge.set_markup("<span foreground='#33d17a'>● Active</span>")
            row.add_suffix(badge)
            self.stream_rows_box.append(row)

    def _reroute_all_streams(self):
        logger.info("Rerouting all active audio streams into PipeSync...")
        self.engine.reroute_active_streams(MASTER_SINK_NAME)
        self._update_active_streams()

    def refresh_devices(self, initial: bool = False):
        """Discovers audio sinks and updates UI."""
        logger.info("Refreshing audio sink devices...")
        sinks = self.detector.get_audio_sinks()

        # Preserve existing user-adjusted delays, volumes, and enabled states
        existing_delays = {d.name: d.compensation_delay_ms for d in self.devices}
        existing_enabled = {d.name: d.enabled for d in self.devices}

        for s in sinks:
            if s.name in existing_delays:
                s.compensation_delay_ms = existing_delays[s.name]
            if s.name in existing_enabled:
                s.enabled = existing_enabled[s.name]

        self.devices = sinks
        self._known_sink_names = {s.name for s in sinks}

        if initial:
            # Auto-align on first launch
            self.detector.calculate_sync_delays(self.devices)
            # If user has saved calibrated offsets in config, apply them
            for s in self.devices:
                saved_delay = self.config.get_calibrated_delay(s.name)
                if saved_delay is not None:
                    s.compensation_delay_ms = saved_delay
                saved_vol = self.config.get_saved_volume(s.name)
                if saved_vol is not None:
                    s.volume = saved_vol

        self._rebuild_device_cards()
        self._update_video_sync_info()

    def _check_device_hotplug(self) -> bool:
        """Periodic check to see if new audio devices were plugged in or removed, and self-heal branches."""
        try:
            # 1. Self-heal any dropped branches
            if self.engine.is_running:
                healed = self.engine.heal_branches()
                if healed > 0:
                    logger.info(f"Self-healed {healed} dropped loopback branch(es)")

            # 2. Check for physical device changes
            sinks = self.detector.get_audio_sinks()
            current_names = {s.name for s in sinks}
            if current_names != self._known_sink_names:
                logger.info("Audio sink configuration changed! Refreshing devices...")
                self.refresh_devices()
                if self.engine.is_running:
                    self.engine.start_sync(self.devices)

            # 3. Update active streams monitor
            self._update_active_streams()
        except Exception as e:
            logger.debug(f"Error checking hotplug/health: {e}")
        return True

    def _rebuild_device_cards(self):
        for card in self.device_cards.values():
            self.devices_group.remove(card)
        self.device_cards.clear()

        if not self.devices:
            row = Adw.ActionRow()
            row.set_title("No Output Devices Found")
            row.set_subtitle("Ensure headphones or speakers are connected to PipeWire.")
            self.devices_group.add(row)
            return

        for dev in self.devices:
            card = DeviceCard(
                device=dev,
                on_delay_changed=self._on_device_delay_changed,
                on_enabled_toggled=self._on_device_enabled_toggled,
                on_test_beep=self._on_device_test_beep,
                on_volume_changed=self._on_device_volume_changed,
                on_mute_toggled=self._on_device_mute_toggled,
            )
            self.devices_group.add(card)
            self.device_cards[dev.name] = card

    def _update_video_sync_info(self):
        info = VideoSyncHelper.calculate_video_offset(self.devices)
        self.video_row.set_subtitle(GLib.markup_escape_text(info["explanation"]))
        self.vlc_badge.set_label(f"VLC: {info['vlc_setting']}")
        self.mpv_badge.set_label(f"MPV: {info['mpv_setting']}")
        self.last_vlc_str = info["vlc_setting"]
        self.last_mpv_str = info["mpv_setting"]

        # Send to MPV if running
        try:
            delay_sec = info["player_audio_delay_ms"] / 1000.0
            VideoSyncHelper.send_mpv_ipc_delay(delay_sec)
        except Exception:
            pass

    def auto_align_devices(self):
        """Calculates optimal delay for all devices to match the slowest device."""
        self.detector.calculate_sync_delays(self.devices)
        for dev in self.devices:
            if dev.name in self.device_cards:
                self.device_cards[dev.name].set_delay_programmatic(dev.compensation_delay_ms)
                if self.engine.is_running:
                    self.engine.update_device_delay(dev.name, dev.compensation_delay_ms)

        self._update_video_sync_info()
        logger.info("Auto-aligned all devices successfully")

    def _on_master_switch_toggled(self, switch, gparam):
        active = switch.get_active()
        if active:
            logger.info("Starting PipeSync Master Hub...")
            success = self.engine.start_sync(self.devices)
            if success:
                active_count = len(self.engine.active_devices)
                self.hub_status.set_text(f"● Broadcasting to {active_count} synchronized devices (Default Sink)")
                self.hub_title.set_text("● Synchronized Broadcast ACTIVE")
            else:
                switch.set_active(False)
                self.hub_status.set_text("✗ Failed to initialize PipeWire broadcast sink")
        else:
            logger.info("Stopping PipeSync Master Hub...")
            self.engine.stop()
            self.hub_status.set_text("○ Hub Standby - Click switch to activate")
            self.hub_title.set_text("Synchronized Broadcast Hub")

    def _on_device_delay_changed(self, device: AudioDevice, delay_ms: float):
        self.config.save_device_delay(device.name, delay_ms)
        if self.engine.is_running:
            self.engine.update_device_delay(device.name, delay_ms)
        self._update_video_sync_info()

    def _on_device_volume_changed(self, device: AudioDevice, vol: float):
        self.config.save_device_volume(device.name, vol)
        self.engine.set_device_volume(device, vol)

    def _on_device_mute_toggled(self, device: AudioDevice, muted: bool):
        self.engine.set_device_mute(device, muted)

    def _on_device_enabled_toggled(self, device: AudioDevice, enabled: bool):
        if self.engine.is_running:
            self.engine.toggle_device_enabled(device)
            active_count = len(self.engine.active_devices)
            self.hub_status.set_text(f"● Broadcasting to {active_count} synchronized devices")
        self._update_video_sync_info()

    def _on_device_test_beep(self, device: AudioDevice):
        logger.info(f"Playing test beep on {device.description}")
        self.calibrator.play_device_beep(device.name)

    def _on_quantum_selected(self, combo, gparam):
        idx = combo.get_selected()
        q_map = {0: 128, 1: 256, 2: 512, 3: 1024}
        target_q = q_map.get(idx, DEFAULT_QUANTUM)
        self.optimizer.set_quantum(target_q)
        logger.info(f"Switched quantum to {target_q}")

    def open_calibrator(self):
        dlg = CalibrationDialog(
            parent_window=self,
            devices=self.devices,
            calibrator=self.calibrator,
            on_delay_updated=self._on_device_delay_changed,
        )
        dlg.present()

    def _copy_to_clipboard(self, text: str):
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)
        logger.info(f"Copied '{text}' to clipboard")

    def _on_close(self, win):
        logger.info("Closing PipeSync...")
        if self._poll_timer:
            GLib.source_remove(self._poll_timer)
            self._poll_timer = None
        self.calibrator.stop_metronome()
        self.engine.stop()
        return False
