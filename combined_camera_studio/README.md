# Combined Camera Studio

A unified Windows desktop application combining **Liquid Cube**, **Air Drawing**, and **Selfie Puzzle** into a single OpenCV window (`1280x720`) with one shared webcam/stream source, one MediaPipe hand tracker (`640x480` VIDEO mode), hand calibration, custom gesture actions, and optional fingertip visual effects.

## Setup (Windows PowerShell)

Use Python 3.11 (or 3.10) in Windows PowerShell:

```powershell
Expand-Archive -Path .\combined_camera_studio.zip -DestinationPath .\
cd .\combined_camera_studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Pass a local camera index, phone-camera stream URL, or video file directly if desired:

```powershell
python main.py --camera 0
python main.py --camera "http://<phone-ip>:<port>/video"
```

## Camera & Low-Latency Pipeline

- **Local Webcam**: Enter `0` (default), `1`, etc. in **Settings (`S`)** or via `--camera`. For integer webcam indices, the studio probes `MJPG` + `30 FPS` + `CAP_PROP_BUFFERSIZE = 1` without assuming every driver accepts them, and logs the actual accepted properties in **Settings**.
- **Phone / Network Camera**: Start your IP camera app on your phone on the same Wi-Fi network, enter the full HTTP/MJPEG or RTSP video URL in **Settings**, and click **Apply Camera** (or press `Enter`). No IP address is hardcoded.
- **Stale-Frame Dropping & Metrics**: A background reader thread keeps only the newest available frame so queued stale frames are discarded. The HUD separates **App FPS**, **Hand-Tracking Time (ms)** (`640x480`), and **Camera Stream Rate (FPS)**. Network delay depends on your Wi-Fi link and camera app.

## Calibration, Custom Gestures & Optional HUD Effects

- **Calibrate (`K`)**: Adjust **Pointer Sensitivity**, **Usable Camera Area** (`60%–100%`), **Pinch Threshold** (scale-normalized with release hysteresis), **Pinch Stability**, and **One-Euro Cursor Smoothing** (`0.00–0.85`: higher values reduce jitter at rest while adding slight motion delay), or pick **Low / Balanced / High / Reset Default**. Saved locally to `calibration.json`.
- **Custom Gestures** (toggleable in Calibration, cooldown-protected):
  - **Pinch**: Select menu cards & HUD buttons.
  - **Open Palm**: Pause / Resume (`Air Drawing` & `Selfie Puzzle`). *Mode note: in `Liquid Cube`, Open Hand movement rotates the cube and Closed Fist freezes it.*
  - **Thumbs-Up**: Display a positive confirmation toast.
  - **Peace Sign**: Return to the Main Menu.
- **AR Hand HUD (`A`) & Fingertip FX (`V`)**: Optional single-pass radial AR palm reticle (`Hand-Tracking-AR-UI` visual style) and localized fingertip particle/ripple effects; toggle either OFF anytime in Calibration, the Menu footer, or with `A` / `V`.

## Mode Controls Summary

1. **Liquid Cube (`1`)**: Open hand rotates cube, closed fist freezes (`Space`), pinch distance resizes, mouse drag rotates, `R` resets, `M`/`Esc` Menu.
2. **Air Drawing (`2`)**: Index finger draws, closed fist lifts brush, pinch HUD buttons/colors (`1`-`8` colors, `E` eraser, `+/-` brush, `[/]` glow, `U` undo, `C` clear, `S` save PNG, `H`/`?` help, `M`/`Esc` Menu).
3. **Selfie Puzzle (`3`)**: Pinch-drag (or mouse drag) region then pinch inside to capture (or `F` Quick Selfie); pinch-drag or mouse-drag tiles to swap (`P` preview, `R` restart, `N` new selfie, `M`/`Esc` Menu).

## Attribution

Integrated modes (`3D-Liquid-Cube-Simulation`, `Gesture-Canvas`, `selfie-puzzle-game`) and reference techniques (`Hand-AR`, `Hand-Tracking-AR-UI`) remain licensed under the MIT License. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
