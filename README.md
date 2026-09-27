# PipeSync

> **Ultra-Low-Latency Multi-Device Audio Sharing & Optimization Layer for PipeWire & Helvum**

`PipeSync` is an intelligent synchronization engine and patchbay wrapper designed to eliminate delay mismatches when sharing audio across multiple heterogeneous devices (such as **2 wired earphones and 1 Bluetooth earphone**).

---

## 🎯 The Problem

When you connect multiple output devices to PipeWire and route audio to all of them (e.g., using Helvum):
1. **Wired Earphones (3.5mm / USB DAC)** have virtually zero latency (~**5 ms**).
2. **Bluetooth Earphones (A2DP SBC/AAC)** have inherent hardware, packetization, and DSP buffering (~**150 ms – 220 ms**).

### Why Media Player Global Audio Delay Fails
If you try to compensate using your media player's audio delay setting (e.g. VLC / MPV / YouTube):
- The media player shifts the **entire master stream** for *all* outputs.
- If you delay audio by +180ms to match Bluetooth, the wired earphones now lag behind the video by 180ms, while the Bluetooth earphone is pushed back to 360ms!
- A single global media player delay knob **cannot** fix physical latency differences between different hardware sinks.

```
Without PipeSync (Audio Desynchronized):
Audio Source ────────┬───> Wired Earphones   ──> Hits ear at t = 5ms   (Early! Echo!)
                     └───> Bluetooth Earbuds ──> Hits ear at t = 190ms (Late! 185ms desync!)

With PipeSync (Sample-Accurate Time Alignment):
Audio Source ──> [ PipeSync Master Hub ]
                        │
                        ├──[ RAM Buffer: +185ms ]──> Wired Earphone 1  ──> Hits ear at t = 190ms ┐
                        ├──[ RAM Buffer: +182ms ]──> Wired Earphone 2  ──> Hits ear at t = 190ms ┼─ All in 100% sync!
                        └──[ Direct:       +0ms ]──> Bluetooth Earbuds ──> Hits ear at t = 190ms ┘
```

---

## 🚀 Key Features

1. **Per-Device Latency Compensation Engine**
   - Automatically detects connected sinks (Wired, USB DACs, Bluetooth A2DP, HDMI, Internal Speakers).
   - Measures and estimates device base latency.
   - Calculates sample-accurate compensation delays: $\Delta t_i = L_{\max} - L_i$.
   - Slower devices (Bluetooth) receive sound with 0ms extra delay; faster devices (wired) are buffered so sound leaves all earbuds at the exact same physical millisecond.

2. **PipeWire Latency Optimization Layer**
   - Strips out PipeWire's default 1024-sample (~21.3ms) buffering overhead.
   - One-click tuning to **256 samples** (~5.3ms) or **128 samples** (~2.7ms) for ultra-low base engine latency.

3. **Helvum Patchbay Integration**
   - Seamless companion wrapper over `/usr/bin/helvum`.
   - Structures `PipeSync` nodes with descriptive labels and node groupings so they render cleanly in Helvum's patchbay canvas.
   - One-click launch button right in the header bar and CLI (`pipesync helvum`).

4. **Acoustic Metronome & Calibration Tool**
   - Built-in rhythmic reference clicks (100 BPM) with visual beat flasher.
   - Put a wired earphone in your Left ear and a Bluetooth earphone in your Right ear.
   - Slide the delay control until the double-click ("da-dum") converges into a single centered transient!

5. **Media Player Video Alignment Assistant**
   - Once all earphones are synchronized together, their combined arrival latency is $L_{\max}$ (e.g. 190ms).
   - PipeSync displays the exact video track synchronization offset:
     - **VLC**: Audio Track Delay: `-190 ms` (Press `j` in VLC to shift earlier).
     - **MPV**: `audio-delay=-0.190` (Press `Ctrl + -` in MPV or auto-apply via IPC socket).

6. **Dual Interfaces: Modern Libadwaita GUI & Fast CLI**
   - **GUI (`pipesync-gui`)**: Native GNOME/Wayland dark-mode interface with card-based controls, sliders with ms readouts, and visual badges.
   - **CLI (`pipesync`)**: Full-featured terminal interface for scripting and Hyprland keybindings.

---

## 📦 Installation & Setup

### Prerequisites
Make sure PipeWire, PyGObject, and Libadwaita are installed on your Linux distribution:

- **Arch Linux / Manjaro**:
  ```bash
  sudo pacman -S pipewire pipewire-pulse python-gobject libadwaita helvum
  ```
- **Fedora**:
  ```bash
  sudo dnf install pipewire pipewire-pulseaudio python3-gobject libadwaita helvum
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt install pipewire pipewire-pulse python3-gi gir1.2-adw-1 helvum
  ```

### Install PipeSync
Clone the repository and install with `pip`:
```bash
git clone https://github.com/MayurUbarhande0/Pipesync.git
cd pipesync
pip install .
```

To run the GUI:
```bash
pipesync-gui
```
*(Also available in your desktop app launcher as **PipeSync**)*

To run the CLI:
```bash
pipesync status
```

---

## 🛠️ Usage Guide

### 1. Graphical Interface (`pipesync-gui`)

1. Open **PipeSync** from your application launcher or run `pipesync-gui`.
2. Connect your earphones (e.g., your wired earphones + Bluetooth earbuds).
3. Click **"Auto-Sync All Devices"**:
   - PipeSync automatically calculates the compensation delay needed for each earphone.
4. Toggle the **"Synchronized Broadcast Active"** switch at the top.
5. In your audio app (Spotify, Firefox, VLC), select **"PipeSync: Multi-Device Broadcast"** as the sound output.
6. Click **"Open Helvum"** at any time to inspect or customize patchbay wiring.

### 2. Command-Line Interface (`pipesync`)

#### View connected devices, latencies, and quantum:
```bash
pipesync status
```

#### Optimize PipeWire buffer size (e.g. 256 samples / 5.3ms):
```bash
pipesync optimize 256
```

#### Start the synchronized hub with auto-alignment:
```bash
pipesync start --auto --default
```

#### Launch the Acoustic Metronome Calibrator:
```bash
pipesync calibrate
```

#### Open Helvum patchbay with PipeSync:
```bash
pipesync helvum
```

#### View active media players and audio streams:
```bash
pipesync streams
```

#### Pull all active playback streams into PipeSync:
```bash
pipesync reroute
```

#### Stop and restore default PipeWire settings:
```bash
pipesync stop
```

---

## 🎬 Synchronizing with Video (Movies, YouTube, Gaming)

When listening to video across mixed headphones:
1. PipeSync aligns all headphones to match the Bluetooth delay (e.g. 185ms).
2. Because all headphones are in 100% sync with each other, simply advance the audio track in your player:
   - **In VLC**: Tools $\rightarrow$ Track Synchronization $\rightarrow$ Audio track synchronization: set to `-185 ms` (or press `j` key).
   - **In MPV**: Press `Ctrl + -` or launch with `mpv --audio-delay=-0.185 video.mp4`.
3. **Result**: Video dialogue matches actors' lips, and all listeners on both wired and Bluetooth earphones hear the sound at the exact same instant!

---

## 🧪 Testing

A complete unit test suite is included in `tests/`:
```bash
python3 -m unittest discover -s tests -v
```

---

## 📂 Project Structure

```
pipesync/
├── README.md                           # Documentation and usage guide
├── pyproject.toml                      # Modern packaging specification
├── setup.py                            # Setuptools installation script
├── LICENSE                             # MIT License
├── .gitignore                          # Git ignore rules
├── bin/
│   ├── pipesync                        # Terminal CLI executable
│   └── pipesync-gui                    # Libadwaita / GTK4 GUI executable
├── data/
│   ├── org.pipewire.PipeSync.desktop   # Desktop launcher entry
│   └── calibration_tick.wav            # Generated high-precision audio pulse
├── pipesync/
│   ├── constants.py                    # Quantum presets, codec latencies
│   ├── models.py                       # AudioDevice, OptimizerState models
│   ├── device_detector.py              # PipeWire sink discovery & classifier
│   ├── optimizer.py                    # Quantum buffer optimizer (pw-metadata)
│   ├── sync_engine.py                  # Master sink & dynamic loopback manager
│   ├── calibrator.py                   # Acoustic metronome & click generator
│   ├── video_sync.py                   # Media player offset calculator (MPV/VLC)
│   ├── helvum_bridge.py                # Helvum supervisor & patchbay launcher
│   ├── config.py                       # Persistent profile & settings store
│   ├── cli.py                          # Terminal UI & commands
│   └── gui/
│       ├── app.py                      # Libadwaita Application entry
│       ├── main_window.py              # Primary application window
│       ├── device_card.py              # Expandable device card with sliders
│       └── calibration_dialog.py       # Visual & acoustic calibrator modal
└── tests/                              # Unit test suite
```
