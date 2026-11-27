# Combined Camera Studio

A unified **Windows desktop Python application** combining **3D Liquid Cube**, **Air Drawing**, and **Selfie Puzzle** into a single OpenCV window (`1280×720`) with one shared camera pipeline, one MediaPipe hand tracker (`640×480` VIDEO mode), interactive calibration, custom gesture actions, and optional AR hand effects.

---

## Folder Contents

```text
combined_camera_studio/
├── main.py                    # App entry point, Main Menu, Calibration [K], Settings [S]
├── vision.py                  # Threaded camera capture, MediaPipe hand tracker, One-Euro filter
├── ui_helpers.py              # Glass HUD panels, buttons, toasts, AR Hand HUD [A], Fingertip FX [V]
├── modes/
│   ├── liquid_cube.py         # Mode 1: 3D shaded cube + 260 fluid particles (ROI bloom)
│   ├── air_drawing.py         # Mode 2: Neon mid-air drawing canvas + PNG export
│   └── selfie_puzzle.py       # Mode 3: 3x3 webcam selfie tile puzzle + live PIP
├── assets/
│   └── hand_landmarker.task   # MediaPipe Hand Landmarker model
├── tests/
│   └── test_studio.py         # 10 unit & integration tests
├── backup_originals/          # Unmodified copies of the 3 integrated source repos
├── requirements.txt
├── LICENSE
└── THIRD_PARTY_NOTICES.md
```

---

## Setup (Windows PowerShell)

Recommended: **Python 3.11** (or 3.10).

```powershell
Expand-Archive -Path .\combined_camera_studio.zip -DestinationPath .\
cd .\combined_camera_studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Launch with a specific webcam index, phone-camera stream URL, or video file:

```powershell
python main.py --camera 0
python main.py --camera "http://<phone-ip>:<port>/video"
```

---

## Modes & Controls

| Mode | Hand Gestures | Keyboard / Mouse Fallback |
| --- | --- | --- |
| **1. Liquid Cube (`1`)** | Open hand moves/rotates cube; Closed fist freezes; Pinch distance resizes | Mouse drag rotates; Wheel / `+` `-` resizes; `Space` freeze; `R` reset |
| **2. Air Drawing (`2`)** | Index finger extended draws; Closed fist stops; Pinch HUD buttons & swatches | Mouse drag draws/erases; `1`–`8` colors; `E` eraser; `+`/`-` size; `[`/`]` glow; `U` undo; `C` clear; `S` save PNG |
| **3. Selfie Puzzle (`3`)** | Pinch-drag capture region, pinch inside to snap; Pinch-drag tiles to swap | Mouse drag crop & tile swap; `F` quick selfie; `P` preview; `R` restart; `N` new selfie |

Global shortcuts: `K` Calibrate · `S` Camera Settings · `A` AR Hand HUD · `V` Fingertip FX · `H` Help · `M` / `Esc` Main Menu · `Q` Quit.

---

## Camera, Calibration & Custom Gestures

- **Local & Network Cameras**: Enter an integer index (`0`, `1`) or any full HTTP/MJPEG/RTSP URL in **Settings (`S`)** (no IP address is hardcoded). Local indices probe `MJPG`, `30 FPS`, and `CAP_PROP_BUFFERSIZE = 1`, logging the actual driver response in Settings alongside threaded latest-frame dropping.
- **Metrics HUD**: Displays **App FPS**, **Hand-Tracking Time (ms)**, and **Camera Stream Rate (FPS)** separately.
- **Calibrate (`K`)**: Tune **Pointer Sensitivity**, **Usable Camera Area** (`60%–100%`), **Pinch Threshold**, **Pinch Stability**, and **One-Euro Cursor Smoothing** (`0.00–0.85`: higher reduces jitter at rest with slight lag; lower feels snappier), or apply **Low / Balanced / High / Reset Default**. Saved locally to `calibration.json`.
- **Custom Gestures** (toggleable & cooldown-protected):
  - **Pinch**: Select menu cards, buttons & drag tiles.
  - **Open Palm**: Pause / Resume in **Air Drawing** and **Selfie Puzzle** *(Liquid Cube uses Open Hand to spin and Fist to freeze)*.
  - **Thumbs-Up**: Show positive confirmation toast.
  - **Peace Sign**: Return to the Main Menu.
- **Optional AR Effects**: Single-pass radial **AR Hand HUD (`A`)** and localized **Fingertip FX (`V`)** can be turned OFF anytime.

---

## Running Tests

```powershell
python -m unittest discover -s tests -v
```

*(Note: Live Windows webcam capture and Wi-Fi phone streaming have not yet been verified on physical Windows hardware; automated tests use synthetic `1280×720` video.)*

---

## Attribution & License

Licensed under the **MIT License**. See [`LICENSE`](./LICENSE) and [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md) for notices covering `3D-Liquid-Cube-Simulation`, `Gesture-Canvas`, `selfie-puzzle-game`, `Hand-AR`, and `Hand-Tracking-AR-UI`.
