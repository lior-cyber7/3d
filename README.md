# Combined Camera Studio

A unified **Windows Desktop Python Application** that merges three hand-gesture OpenCV & MediaPipe projects — **3D Liquid Cube**, **Air Drawing**, and **Selfie Puzzle** — into one single-window (`1280×720`) studio powered by one shared camera pipeline, one hand tracker, interactive calibration, custom gestures, and an optional lightweight AR hand HUD.

---

## Features

| Mode / Module | Description | Hand Gestures | Keyboard / Mouse Fallback |
| --- | --- | --- | --- |
| **1. Liquid Cube** | Shaded 3D cube with 260 Position-Based Dynamics fluid particles and ROI-accelerated liquid bloom | Open hand moves/spins cube, Closed fist freezes liquid, Pinch distance resizes | Drag mouse to rotate, Wheel / `+` `-` resize, `Space` freeze, `R` reset |
| **2. Air Drawing** | Persistent neon canvas over live video with stroke smoothing, 8 colors, eraser, glow, undo & PNG save | Index finger up draws, Closed fist lifts brush, Pinch HUD buttons & palette | Drag mouse to draw/erase, `1`–`8` colors, `E` eraser, `U` undo, `C` clear, `S` save |
| **3. Selfie Puzzle** | Capture a live camera crop into a 3×3 shuffled puzzle with live webcam PIP, timer, moves & confetti | Pinch-drag box & pinch inside to capture, Pinch-drag tiles to swap | Drag mouse to crop/swap, `F` quick selfie, `P` preview, `R` restart, `N` new |
| **Calibrate (`K`)** | Live camera ROI box, pinch meter, One-Euro cursor smoothing, Low / Balanced / High presets | Pinch sliders, toggles & preset buttons | Mouse click + `Esc` to save & return |
| **Settings (`S`)** | Switch between local webcam index (`0`, `1`) and phone/IP stream URL, Mirror Flip & Hand Confidence | Pinch controls | Type URL + `Enter` to connect, `Esc` back |

---

## Custom Gestures & Optional HUD Effects

- **Pinch (Thumb + Index)**: Select menu cards, mode buttons, sliders, and drag puzzle tiles (uses palm-normalized scaling + release hysteresis).
- **Peace Sign**: Return to the Main Menu (cooldown-protected).
- **Thumbs-Up**: Display a customizable confirmation toast.
- **Open Palm**: Pause / Resume in **Air Drawing** and **Selfie Puzzle** *(in **Liquid Cube**, Open Hand movement rotates the cube and Closed Fist freezes it)*.
- **AR Hand HUD (`A`) & Fingertip FX (`V`)**: Optional single-pass radial palm reticle and local fingertip particle/ripple effects; toggle either **OFF** anytime in Calibration, the Main Menu footer, or with `A` / `V`.

---

## Repository Structure

```text
.
├── README.md                          # Repository overview & setup guide
├── combined_camera_studio/            # Main Python desktop application
│   ├── main.py                        # Window loop, Main Menu, Calibration [K], Settings [S]
│   ├── vision.py                      # Threaded camera capture, MediaPipe 640x480 tracker, One-Euro filter
│   ├── ui_helpers.py                  # Glass panels, buttons, toasts, AR Hand HUD, Fingertip FX
│   ├── modes/
│   │   ├── liquid_cube.py             # Mode 1: 3D Liquid Cube physics & renderer
│   │   ├── air_drawing.py             # Mode 2: Neon Air Drawing canvas & PNG export
│   │   └── selfie_puzzle.py           # Mode 3: 3x3 Selfie Puzzle game
│   ├── assets/
│   │   └── hand_landmarker.task       # Bundled MediaPipe Hand Landmarker model
│   ├── tests/
│   │   └── test_studio.py             # Automated unit & integration tests (10/10 passing)
│   ├── backup_originals/              # Preserved copies of the 3 source projects
│   ├── requirements.txt
│   ├── LICENSE
│   └── THIRD_PARTY_NOTICES.md
├── combined_camera_studio.zip         # Ready-to-extract Windows package
├── src/                               # Web portal for download & documentation
└── source_extracted/                  # Untouched upstream project checkouts
```

---

## Quick Start (Windows PowerShell — Python 3.11 / 3.10)

```powershell
# If starting from the packaged ZIP:
Expand-Archive -Path .\combined_camera_studio.zip -DestinationPath .\

cd .\combined_camera_studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Launch with a specific webcam index or phone/IP camera stream URL:

```powershell
python main.py --camera 0
python main.py --camera "http://<phone-ip>:<port>/video"
```

---

## Camera Performance & Calibration Notes

- **Latest-Frame Dropping**: Live cameras read on a background thread holding only the newest frame so stale frames do not accumulate. For integer webcam indices, `MJPG`, `30 FPS`, and `CAP_PROP_BUFFERSIZE = 1` are probed and reported honestly in **Settings (`S`)** instead of assuming driver support.
- **Metrics Separation**: The HUD separates **App FPS** (UI/render rate), **Hand-Tracking Time (ms)** (`640×480`), and **Camera Stream Rate (FPS)**; Wi-Fi stream latency depends on network conditions and the phone camera app.
- **One-Euro Smoothing Trade-Off**: Higher smoothing (`0.00–0.85`) steadies jitter while adding slight cursor delay; lower values feel snappier.
- **Verification Scope**: Automated tests (`10/10` passing) and benchmarks were executed headless on Linux using synthetic `1280×720` video; live physical Windows webcam (`DirectShow`) and live Wi-Fi phone stream URL playback have **not** yet been verified on Windows hardware.

---

## Credits & License

Licensed under the **MIT License**. See [`combined_camera_studio/LICENSE`](./combined_camera_studio/LICENSE) and [`combined_camera_studio/THIRD_PARTY_NOTICES.md`](./combined_camera_studio/THIRD_PARTY_NOTICES.md) for full attribution to:

- [3D-Liquid-Cube-Simulation](https://github.com/Subham503/3D-Liquid-Cube-Simulation) — Subham503 (MIT)
- [Gesture-Canvas](https://github.com/RutujaKhule/Gesture-Canvas) — RutujaKhule / GestureCanvas Contributors (MIT)
- [selfie-puzzle-game](https://github.com/krishaagor-source/selfie-puzzle-game) — Krisha Gor (MIT)
- [Hand-AR](https://github.com/CoshkaX/Hand-AR) — Mehmet Akif Çoşkun (MIT reference for One-Euro filter & camera probing)
- [Hand-Tracking-AR-UI](https://github.com/tubakhxn/Hand-Tracking-AR-UI) — Tuba Khan (MIT visual reference for radial AR hand HUD)
