# Combined Camera Studio

A unified Windows desktop application combining **Liquid Cube**, **Air Drawing**, and **Selfie Puzzle** into a single OpenCV window with one shared webcam/stream source and one MediaPipe hand tracker.

## Setup (Windows PowerShell)

```powershell
cd combined_camera_studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

You can also pass a camera index, phone-camera stream URL, or video file directly:

```powershell
python main.py --camera 0
python main.py --camera "http://<phone-ip>:<port>/video"
```

## Camera Configuration

- **Local Webcam**: Enter `0` (default), `1`, etc. in **Settings** (`S`) or via `--camera`.
- **Phone / Network Camera**: Start your IP camera app on your phone (e.g. IP Webcam, DroidCam, Camo, or RTSP stream) on the same Wi-Fi network, copy the exact HTTP/MJPEG or RTSP video URL shown by your app (such as `http://192.168.1.45:8080/video` or `rtsp://...`), enter it in **Settings**, and click **Apply Camera** (or press `Enter`).
- If the camera cannot be opened, the app stays open, shows a clear diagnostic banner, and lets you switch to Settings without crashing.

## Controls Summary

### Main Menu
- **Hand**: Point with index finger to highlight a card; **pinch** (thumb + index) to open it.
- **Fallback**: Mouse click any card, or press `1` (Liquid Cube), `2` (Air Drawing), `3` (Selfie Puzzle), `S` (Settings), `Q`/`Esc` (Quit).

### 1. Liquid Cube
- **Open Hand**: Move hand to rotate/tilt the 3D cube with inertia.
- **Closed Fist**: Freeze rotation and settle fluid.
- **Pinch Distance**: Resize cube dynamically.
- **Fallback**: Mouse drag to rotate, mouse wheel or `+`/`-` to resize, `Space` freeze, `R` reset, `M`/`Esc` Menu.

### 2. Air Drawing
- **Index Finger Up**: Draw glowing neon strokes with anti-gravity sparks.
- **Closed Fist**: Pause drawing.
- **Pinch on HUD**: Select colors, toggle Eraser, adjust Brush/Glow, Undo, Clear, Save PNG.
- **Fallback**: Mouse drag to draw, `1`-`8` colors, `E` eraser, `+`/`-` brush, `[`/`]` glow, `U` undo, `C` clear, `S` save, `H` help, `M`/`Esc` Menu.

### 3. Selfie Puzzle
- **Capture Phase**: Pinch-and-drag (or mouse drag) to draw a selection rectangle, release to lock, then pinch/click inside to capture (or `F` / `Quick Selfie`).
- **Play Phase**: Pinch-and-hold a tile to pick it up and release over another tile to swap (or mouse drag-and-drop). Use `Preview` (`P`), `Restart` (`R`), `New Selfie` (`N`), `M`/`Esc` Menu.

## Attribution

All three integrated projects remain licensed under the MIT License. See `LICENSE` and `THIRD_PARTY_NOTICES.md`.
