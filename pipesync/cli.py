"""
PipeSync Command-Line Interface
"""

import argparse
import sys
import time
import logging

from pipesync.constants import (
    APP_NAME,
    APP_VERSION,
    APP_DESCRIPTION,
    QUANTUM_PRESETS,
    DEFAULT_QUANTUM,
    MASTER_SINK_NAME,
)
from pipesync.device_detector import DeviceDetector
from pipesync.optimizer import PipeWireOptimizer
from pipesync.sync_engine import SyncEngine
from pipesync.calibrator import AudioCalibrator
from pipesync.helvum_bridge import HelvumBridge
from pipesync.video_sync import VideoSyncHelper
from pipesync.config import ConfigManager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ANSI Terminal Colors
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
RESET = "\033[0m"


def print_banner():
    print(f"{BOLD}{CYAN}=== {APP_NAME} v{APP_VERSION} ==={RESET}")
    print(f"{CYAN}{APP_DESCRIPTION}{RESET}\n")


def cmd_status(args):
    """Lists all detected audio sinks, latencies, and PipeWire engine state."""
    print_banner()

    optimizer = PipeWireOptimizer()
    opt_state = optimizer.get_current_state()

    print(f"{BOLD}PipeWire Engine Status:{RESET}")
    ll_badge = f"{GREEN}[LOW-LATENCY ACTIVE]{RESET}" if opt_state.is_low_latency_active else f"{YELLOW}[NORMAL]{RESET}"
    print(f"  • Clock Quantum   : {BOLD}{opt_state.quantum}{RESET} samples {ll_badge}")
    print(f"  • Sample Rate     : {opt_state.rate} Hz")
    print(f"  • Buffer Latency  : {BOLD}{opt_state.buffer_latency_ms:.2f} ms{RESET} per cycle")
    print(f"  • Force Quantum   : {opt_state.force_quantum}")
    print()

    detector = DeviceDetector()
    sinks = detector.get_audio_sinks()
    sinks = detector.calculate_sync_delays(sinks)

    print(f"{BOLD}Detected Audio Output Devices ({len(sinks)}):{RESET}")
    if not sinks:
        print("  No audio sinks found.")
        return

    type_icons = {
        "bluetooth": "📶 [Bluetooth]",
        "wired": "🎧 [Wired]",
        "usb": "⚡ [USB Audio]",
        "speaker": "🔊 [Speaker]",
        "hdmi": "📺 [HDMI/DP]",
        "other": "🔈 [Other]",
    }

    for idx, s in enumerate(sinks, 1):
        type_tag = type_icons.get(s.device_type, "🔈 [Other]")
        codec_str = f" (Codec: {s.codec.upper()})" if s.codec else ""
        print(f"  {BOLD}{idx}. {s.description}{RESET}")
        print(f"     Type           : {CYAN}{type_tag}{codec_str}{RESET}")
        print(f"     Sink Name      : {s.name}")
        print(f"     Hardware Delay : {YELLOW}{s.hardware_latency_ms:.1f} ms{RESET}")
        print(f"     Comp Delay     : {GREEN}+{s.compensation_delay_ms:.1f} ms{RESET}")
        print(f"     Synced Total   : {BOLD}{s.total_latency_ms:.1f} ms{RESET}")
        print()

    # Video Sync info
    v_info = VideoSyncHelper.calculate_video_offset(sinks)
    print(f"{BOLD}Media Player Video Alignment:{RESET}")
    print(f"  • Synchronized Group Arrival : {v_info['group_latency_ms']} ms")
    print(f"  • Recommended VLC Delay      : {BOLD}{CYAN}{v_info['vlc_setting']}{RESET} ({v_info['vlc_hotkey']})")
    print(f"  • Recommended MPV Delay      : {BOLD}{CYAN}{v_info['mpv_setting']}{RESET} ({v_info['mpv_hotkey']})")
    print()


def cmd_optimize(args):
    """Sets PipeWire clock quantum."""
    print_banner()
    optimizer = PipeWireOptimizer()

    target_q = args.quantum
    force = args.force

    if target_q == 0:
        optimizer.restore_defaults()
        print(f"{GREEN}✓ Restored PipeWire defaults (1024 samples / ~21.3ms){RESET}")
        return

    success = optimizer.set_quantum(target_q, force=force)
    if success:
        state = optimizer.get_current_state()
        print(f"{GREEN}✓ Successfully set PipeWire quantum to {target_q} samples{RESET}")
        print(f"  Buffer Latency: {BOLD}{state.buffer_latency_ms:.2f} ms{RESET} at {state.rate} Hz")
    else:
        print(f"{RED}✗ Failed to update PipeWire quantum{RESET}")


def cmd_start(args):
    """Starts the synchronized multi-device broadcast hub."""
    print_banner()

    optimizer = PipeWireOptimizer()
    if args.quantum:
        optimizer.optimize_for_sharing(args.quantum)

    detector = DeviceDetector()
    sinks = detector.get_audio_sinks()

    if not sinks:
        print(f"{RED}No audio output devices found to synchronize.{RESET}")
        return

    # Filter devices if user specified list
    if args.devices:
        device_names = [d.strip() for d in args.devices.split(",")]
        for s in sinks:
            s.enabled = s.name in device_names or any(d in s.description for d in device_names)
    else:
        # Default behavior: enable all non-speaker/non-HDMI devices or top devices
        # If user has multiple headphones, enable them all!
        for s in sinks:
            s.enabled = True

    sinks = detector.calculate_sync_delays(sinks)
    active_sinks = [s for s in sinks if s.enabled]

    print(f"{BOLD}Starting PipeSync Multi-Device Hub with {len(active_sinks)} outputs:{RESET}")
    for s in active_sinks:
        print(f"  • {s.description} -> Delay: {GREEN}+{s.compensation_delay_ms:.1f} ms{RESET}")
    print()

    engine = SyncEngine()
    success = engine.start_sync(active_sinks)

    if not success:
        print(f"{RED}✗ Failed to start synchronization engine.{RESET}")
        return

    if args.default:
        engine.set_as_default_sink(True)
        print(f"{GREEN}✓ Set PipeSync Master as default system audio output.{RESET}")

    helvum = HelvumBridge()
    if args.helvum:
        print(f"{CYAN}Launching Helvum patchbay...{RESET}")
        helvum.launch()

    # Video offset helper
    v_info = VideoSyncHelper.calculate_video_offset(active_sinks)
    print(f"\n{BOLD}{YELLOW}Notice for Videos / Movies:{RESET}")
    print(f"  {v_info['explanation']}")
    print(f"  VLC: Set Audio Delay to {BOLD}{v_info['vlc_setting']}{RESET}")
    print(f"  MPV: Set Audio Delay to {BOLD}{v_info['mpv_setting']}{RESET}\n")

    print(f"{GREEN}● PipeSync Hub is running! Press Ctrl+C to stop.{RESET}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Stopping PipeSync Hub...{RESET}")
        engine.stop()
        if args.restore_quantum:
            optimizer.restore_defaults()
        print(f"{GREEN}✓ Cleaned up successfully.{RESET}")


def cmd_calibrate(args):
    """Interactive acoustic metronome for delay calibration."""
    print_banner()
    calibrator = AudioCalibrator()
    detector = DeviceDetector()
    sinks = detector.get_audio_sinks()

    print(f"{BOLD}Acoustic Latency Calibrator{RESET}")
    print("This tool sends rhythmic audio pulses to help you calibrate delays.")
    print("Wear both earphones (e.g. Wired in Left ear, Bluetooth in Right ear).\n")

    print(f"{BOLD}Available Target Devices:{RESET}")
    for idx, s in enumerate(sinks, 1):
        print(f"  {idx}. {s.description} ({s.device_type})")
    print(f"  0. PipeSync Master (Synchronized Hub)")

    choice = input(f"\nSelect device to test [default: 0]: ").strip()
    target_sink = MASTER_SINK_NAME
    if choice and choice != "0":
        try:
            sel_idx = int(choice) - 1
            if 0 <= sel_idx < len(sinks):
                target_sink = sinks[sel_idx].name
            else:
                print(f"{YELLOW}Invalid choice; using {MASTER_SINK_NAME}{RESET}")
        except Exception:
            target_sink = MASTER_SINK_NAME

    print(f"\nStarting rhythmic click pulse on '{target_sink}'...")
    print(f"{GREEN}Playing metronome clicks... Press Enter to stop.{RESET}")
    calibrator.start_metronome(interval_sec=0.6, target_sink=target_sink)

    try:
        input()
    finally:
        calibrator.stop_metronome()
        print(f"{GREEN}✓ Calibrator stopped.{RESET}")


def cmd_helvum(args):
    """Opens the Helvum patchbay with PipeSync."""
    print_banner()
    helvum = HelvumBridge()
    if not helvum.is_available:
        print(f"{RED}✗ Helvum is not installed on this system.{RESET}")
        return

    print(f"{CYAN}Launching Helvum patchbay GUI...{RESET}")
    helvum.launch()


def cmd_stop(args):
    """Stops running PipeSync master sink and loopback branches."""
    print_banner()
    engine = SyncEngine()
    print(f"{YELLOW}Stopping PipeSync master sink and restoring system audio defaults...{RESET}")
    engine.stop()
    print(f"{GREEN}✓ PipeSync stopped and audio outputs restored.{RESET}")


def cmd_streams(args):
    """Lists currently active audio playback applications."""
    print_banner()
    engine = SyncEngine()
    streams = engine.get_active_audio_streams()
    print(f"{BOLD}Active Audio Playback Applications ({len(streams)}):{RESET}")
    if not streams:
        print("  No active audio playback streams found (play audio in browser or media player).")
        return
    for idx, s in enumerate(streams, 1):
        app = s["app_name"]
        title = f" ({s['media_title']})" if s["media_title"] else ""
        sink_str = f"Sink #{s['sink_id']}"
        print(f"  {idx}. {BOLD}{app}{RESET}{title} -> {CYAN}{sink_str}{RESET}")
    print()


def cmd_reroute(args):
    """Reroutes all active audio streams into PipeSync Master Hub."""
    print_banner()
    engine = SyncEngine()
    print(f"{CYAN}Rerouting active audio playback streams to PipeSync Master ({MASTER_SINK_NAME})...{RESET}")
    engine.reroute_active_streams(MASTER_SINK_NAME)
    print(f"{GREEN}✓ All active audio streams redirected to PipeSync.{RESET}")


def main():
    parser = argparse.ArgumentParser(
        prog="pipesync",
        description=APP_DESCRIPTION,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", help="List audio sinks, latencies, and PipeWire quantum")
    p_status.set_defaults(func=cmd_status)

    p_list = subparsers.add_parser("list", help="Alias for status")
    p_list.set_defaults(func=cmd_status)

    # optimize
    p_opt = subparsers.add_parser("optimize", help="Tune PipeWire buffer quantum (low-latency)")
    p_opt.add_argument(
        "quantum",
        type=int,
        choices=[0, 64, 128, 256, 512, 1024],
        help="Buffer size in samples (128: Ultra-Low, 256: Low, 512: Balanced, 1024/0: Default)",
    )
    p_opt.add_argument("--force", action="store_true", help="Force quantum across all nodes")
    p_opt.set_defaults(func=cmd_optimize)

    # start
    p_start = subparsers.add_parser("start", help="Start synchronized multi-device broadcast hub")
    p_start.add_argument("--devices", type=str, help="Comma-separated device names/patterns to include")
    p_start.add_argument("--quantum", type=int, default=DEFAULT_QUANTUM, help=f"Quantum to set (default: {DEFAULT_QUANTUM})")
    p_start.add_argument("--auto", action="store_true", help="Automatically detect and balance all connected headphones")
    p_start.add_argument("--default", action="store_true", help="Set PipeSync as default system audio output")
    p_start.add_argument("--helvum", action="store_true", help="Launch Helvum alongside the sync hub")
    p_start.add_argument("--restore-quantum", action="store_true", help="Restore default quantum on exit")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop synchronized multi-device broadcast hub and restore defaults")
    p_stop.set_defaults(func=cmd_stop)

    # streams
    p_streams = subparsers.add_parser("streams", help="List currently playing audio streams and their destination sinks")
    p_streams.set_defaults(func=cmd_streams)

    # reroute
    p_reroute = subparsers.add_parser("reroute", help="Reroute all active audio playback into PipeSync Master")
    p_reroute.set_defaults(func=cmd_reroute)

    # calibrate
    p_cal = subparsers.add_parser("calibrate", help="Launch interactive acoustic metronome calibrator")
    p_cal.set_defaults(func=cmd_calibrate)

    # helvum
    p_helvum = subparsers.add_parser("helvum", help="Launch Helvum visual patchbay")
    p_helvum.set_defaults(func=cmd_helvum)

    args = parser.parse_args()
    if not args.command:
        # Default to status if no command specified
        cmd_status(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
