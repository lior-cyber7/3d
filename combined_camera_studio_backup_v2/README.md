# Combined Camera Studio

A unified Windows desktop application combining **Liquid Cube**, **Air Drawing**, and **Selfie Puzzle** into a single OpenCV window (`1280x720`) with one shared webcam/stream source, one MediaPipe hand tracker (`640x480` VIDEO mode), hand calibration, custom gesture actions, and optional fingertip visual effects.

## Setup (Windows PowerShell)

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

- **Local Webcam**: Enter `0` (default), `1`, etc. in **Settings (`S`)** or via `--camera`.
- **Phone / Network Camera**: Start your IP camera app on your phone (e.g. IP Webcam, DroidCam, RTSP stream) on the same Wi-Fi network, enter the full video URL in **Settings**, and click **Apply Camera** (or press `Enter`). No IP address is hardcoded.
- **Stale-Frame Dropping & Buffer Check**: Live sources attempt `CAP_PROP_BUFFERSIZE = 1` (and report in **Settings** whether the backend accepted or ignored it) while running a single-slot latest-frame reader thread so stale queued frames are discarded.
- **Performance HUD**: Displays **App FPS**, **Hand-Tracking Time (ms)**, and **Camera Stream FPS** separately.

## Calibration & Custom Gestures

- **Calibrate (`K`)**: Adjust **Pointer Sensitivity**, **Usable Camera Area** (`60%–100%`), **Pinch Threshold**, **Pinch Stability**, and **Cursor Smoothing**, or pick **Low / Balanced / High / Reset Default** presets. Saved locally to `calibration.json`.
- **Custom Gestures** (toggleable in Calibration, cooldown-protected):
  - **Pinch**: Select menu cards & HUD buttons.
  - **Open Palm**: Pause / Resume (`Air Drawing` & `Selfie Puzzle`). *Mode note: in `Liquid Cube`, Open Hand movement rotates the cube and Closed Fist freezes it.*
  - **Thumbs-Up**: Display a positive confirmation message toast.
  - **Peace Sign**: Return to the Main Menu.
- **Fingertip Visual Effects (`V`)**: Lightweight local particle trail and ripple ring on the tracked index fingertip; can be switched OFF anytime.

## Mode Controls Summary

1. **Liquid Cube (`1`)**: Open hand rotates cube, closed fist freezes (`Space`), pinch distance resizes, mouse drag rotates, `R` resets, `M`/`Esc` Menu.
2. **Air Drawing (`2`)**: Index finger draws, closed fist lifts brush, pinch HUD buttons/colors (`1`-`8` colors, `E` eraser, `+/-` brush, `[/]` glow, `U` undo, `C` clear, `S` save PNG, `?` help, `M`/`Esc` Menu).
3. **Selfie Puzzle (`3`)**: Pinch-drag (or mouse drag) region then pinch inside to capture (or `F` Quick Selfie); pinch-drag or mouse-drag tiles to swap (`P` preview, `R` restart, `N` new selfie, `M`/`Esc` Menu).

## Attribution

All three integrated projects remain licensed under the MIT License. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
