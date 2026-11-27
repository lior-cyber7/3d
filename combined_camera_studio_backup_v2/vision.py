"""Shared camera, MediaPipe hand tracking, calibration storage, and gesture recognition."""

from dataclasses import dataclass, field
import json
import math
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
import numpy as np

WIN_W, WIN_H = 1280, 720
TRACK_W, TRACK_H = 640, 480

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
]
LANDMARK_NAMES = [
    "WRIST", "TH_CMC", "TH_MCP", "TH_IP", "TH_TIP", "IX_MCP", "IX_PIP", "IX_DIP", "IX_TIP",
    "MD_MCP", "MD_PIP", "MD_DIP", "MD_TIP", "RG_MCP", "RG_PIP", "RG_DIP", "RG_TIP",
    "PK_MCP", "PK_PIP", "PK_DIP", "PK_TIP",
]

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MODEL_PATH = os.path.join(ROOT_DIR, "assets", "hand_landmarker.task")
CALIBRATION_PATH = os.path.join(ROOT_DIR, "calibration.json")

CALIBRATION_PRESETS: Dict[str, Dict[str, Any]] = {
    "Low": {"sensitivity": 0.80, "usable_area": 0.95, "pinch_threshold": 0.045, "stability_frames": 3, "smoothing": 0.68},
    "Balanced": {"sensitivity": 1.00, "usable_area": 0.85, "pinch_threshold": 0.055, "stability_frames": 2, "smoothing": 0.45},
    "High": {"sensitivity": 1.25, "usable_area": 0.72, "pinch_threshold": 0.068, "stability_frames": 1, "smoothing": 0.22},
}
DEFAULT_CALIBRATION: Dict[str, Any] = {
    "preset": "Balanced", "sensitivity": 1.00, "usable_area": 0.85,
    "pinch_threshold": 0.055, "stability_frames": 2, "smoothing": 0.45,
    "confidence": 0.65, "fx_enabled": True, "track_w": TRACK_W, "track_h": TRACK_H,
    "gesture_pause": True, "gesture_thumbs": True, "gesture_peace": True,
    "thumbs_phrase": "Great! Action confirmed!",
}


_NUM_BOUNDS = {
    "sensitivity": (0.70, 1.60, 2), "usable_area": (0.60, 1.00, 2),
    "pinch_threshold": (0.030, 0.095, 3), "smoothing": (0.00, 0.85, 2), "confidence": (0.40, 0.90, 2),
}


def clamp_calibration(raw: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(DEFAULT_CALIBRATION)
    if isinstance(raw, dict):
        cfg.update(raw)
    for k, (lo, hi, dec) in _NUM_BOUNDS.items():
        cfg[k] = round(float(np.clip(cfg[k], lo, hi)), dec)
    cfg["stability_frames"] = int(np.clip(int(cfg["stability_frames"]), 1, 5))
    for k in ("fx_enabled", "gesture_pause", "gesture_thumbs", "gesture_peace"):
        cfg[k] = bool(cfg[k])
    cfg["thumbs_phrase"] = str(cfg.get("thumbs_phrase") or DEFAULT_CALIBRATION["thumbs_phrase"])[:48]
    return cfg


def load_calibration(path: str = CALIBRATION_PATH) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return clamp_calibration(json.load(f))
    except Exception:
        return dict(DEFAULT_CALIBRATION)


def save_calibration(cfg: Dict[str, Any], path: str = CALIBRATION_PATH) -> bool:
    try:
        clean = clamp_calibration(cfg)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2)
        return True
    except Exception:
        return False


def parse_camera_source(raw: str) -> Union[int, str]:
    text = (raw or "").strip()
    if not text:
        return 0
    return int(text) if text.isdigit() else text


class CameraSource:
    """Shared VideoCapture using a latest-frame reader for live streams so stale frames are dropped."""

    def __init__(self, source: str = "0", width: int = WIN_W, height: int = WIN_H):
        self.source_str = str(source).strip() or "0"
        self.width, self.height = width, height
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_error = ""
        self.is_live = False
        self.is_file = False
        self.stream_fps = 0.0
        self.buffer_prop_supported = False
        self.buffer_prop_note = "Not opened"
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._cam_stamps: List[float] = []

    def open(self, source: Optional[str] = None) -> bool:
        if source is not None:
            self.source_str = str(source).strip() or "0"
        self.release()
        self.last_error = ""
        parsed = parse_camera_source(self.source_str)
        self.is_file = isinstance(parsed, str) and os.path.isfile(parsed)

        cap = None
        if isinstance(parsed, int) and sys.platform.startswith("win"):
            for backend in (cv2.CAP_DSHOW, cv2.CAP_ANY):
                cand = cv2.VideoCapture(parsed, backend)
                if cand.isOpened():
                    cap = cand
                    break
                cand.release()
        else:
            cand = cv2.VideoCapture(parsed)
            if cand.isOpened():
                cap = cand
            else:
                cand.release()

        if cap is None or not cap.isOpened():
            self.last_error = (
                f"Could not open camera '{self.source_str}'. "
                "Enter a local index (0, 1) or full stream URL (e.g. http://<ip>:<port>/video)."
            )
            return False

        if isinstance(parsed, int):
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        set_ok = bool(cap.set(cv2.CAP_PROP_BUFFERSIZE, 1))
        buf_val = cap.get(cv2.CAP_PROP_BUFFERSIZE)
        self.buffer_prop_supported = bool(set_ok and abs(buf_val - 1.0) < 0.01)
        self.buffer_prop_note = (
            "CAP_PROP_BUFFERSIZE=1 active" if self.buffer_prop_supported
            else f"CAP_PROP_BUFFERSIZE unsupported (val={buf_val:.0f}); latest-frame drop active"
        )

        ok, test_frame = cap.read()
        if not ok or test_frame is None or test_frame.size == 0:
            cap.release()
            self.last_error = f"Connected to '{self.source_str}' but received no frames."
            return False

        self.cap = cap
        self.is_live = True
        self._latest_frame = test_frame
        self._cam_stamps = [time.perf_counter()]
        self.stream_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) if self.is_file else 0.0
        if not self.is_file:
            self._stop_evt.clear()
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
        return True

    def _capture_loop(self):
        misses = 0
        while not self._stop_evt.is_set() and self.cap is not None:
            ok, frame = self.cap.read()
            if ok and frame is not None and frame.size > 0:
                misses = 0
                now = time.perf_counter()
                with self._lock:
                    self._latest_frame = frame
                    self._cam_stamps.append(now)
                    if len(self._cam_stamps) > 20:
                        self._cam_stamps.pop(0)
                    if len(self._cam_stamps) >= 2:
                        dt = self._cam_stamps[-1] - self._cam_stamps[0]
                        self.stream_fps = (len(self._cam_stamps) - 1) / dt if dt > 0 else 0.0
            else:
                misses += 1
                if misses > 45:
                    self.last_error = f"Stream '{self.source_str}' stopped sending frames."
                    self.is_live = False
                    break
                time.sleep(0.005)

    def read_frame(self, flip: bool = True) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.is_live:
            return False, None
        if self.is_file:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            if not ok or frame is None or frame.size == 0:
                return False, None
        else:
            with self._lock:
                frame = self._latest_frame
            if frame is None:
                return False, None
            frame = frame.copy()
        if flip:
            frame = cv2.flip(frame, 1)
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        return True, frame

    def release(self):
        self._stop_evt.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            finally:
                self.cap = None
        self._latest_frame = None
        self.is_live = False
        self.stream_fps = 0.0


class PinchDebouncer:
    """Detects pinch rising edges with stability frames and cooldown."""

    def __init__(self, cooldown_frames: int = 10, stability_frames: int = 1):
        self.cooldown_frames = max(1, int(cooldown_frames))
        self.stability_frames = max(1, int(stability_frames))
        self._was_latched = False
        self._held_count = 0
        self._cooldown = 0

    def update(self, is_pinching: bool) -> bool:
        ready = self._cooldown == 0
        if self._cooldown > 0:
            self._cooldown -= 1
        if is_pinching:
            self._held_count += 1
        else:
            self._held_count = 0
            self._was_latched = False
            return False
        if not self._was_latched and self._held_count >= self.stability_frames:
            self._was_latched = True
            if ready:
                self._cooldown = self.cooldown_frames
                return True
        return False

    def reset(self):
        self._was_latched = False
        self._held_count = 0
        self._cooldown = 0


def classify_hand_pose(pts: List[Tuple[int, int]], palm_px: float, is_pinch: bool) -> str:
    """Rule-based single-hand custom command classifier (PEACE, THUMBS_UP, OPEN_PALM, NONE)."""
    if len(pts) < 21 or palm_px < 12.0 or is_pinch:
        return "NONE"
    wx, wy = pts[0]
    def _d(a: int, b: int) -> float:
        return math.hypot(pts[a][0] - pts[b][0], pts[a][1] - pts[b][1])
    ext = [pts[t][1] < pts[p][1] - 5 and _d(t, 0) > _d(p, 0) * 1.12 for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))]
    curled = [_d(t, 0) < _d(p, 0) * 1.08 for t, p in ((8, 6), (12, 10), (16, 14), (20, 18))]
    thumb_up = pts[4][1] < pts[3][1] - 4 and pts[4][1] < pts[2][1] - 8 and pts[4][1] < pts[5][1] - 6
    if ext[0] and ext[1] and curled[2] and curled[3] and _d(8, 12) > palm_px * 0.18:
        return "PEACE"
    if thumb_up and all(curled):
        return "THUMBS_UP"
    if all(ext) and _d(4, 5) > palm_px * 0.25:
        return "OPEN_PALM"
    return "NONE"


class GestureDebouncer:
    """Requires brief pose hold + cooldown and latches until release so actions trigger once."""

    def __init__(self, hold_frames: int = 4, cooldown_sec: float = 1.5):
        self.hold_frames = max(1, int(hold_frames))
        self.cooldown_sec = max(0.1, float(cooldown_sec))
        self._cur_pose = "NONE"
        self._count = 0
        self._latched = "NONE"
        self._last_fire: Dict[str, float] = {}

    def update(self, pose: str, now: Optional[float] = None) -> Optional[str]:
        t = time.perf_counter() if now is None else now
        if pose == "NONE":
            self._cur_pose, self._count, self._latched = "NONE", 0, "NONE"
            return None
        if pose == self._cur_pose:
            self._count += 1
        else:
            self._cur_pose, self._count = pose, 1
        if self._count >= self.hold_frames and self._latched != pose:
            if t - self._last_fire.get(pose, -1e9) >= self.cooldown_sec:
                self._latched = pose
                self._last_fire[pose] = t
                return pose
        return None

    def reset(self):
        self._cur_pose, self._count, self._latched = "NONE", 0, "NONE"


@dataclass
class HandData:
    detected: bool = False
    landmarks: list = field(default_factory=list)
    landmarks_px: List[Tuple[int, int]] = field(default_factory=list)
    index_tip: Optional[Tuple[int, int]] = None
    pinch_center: Optional[Tuple[int, int]] = None
    pinch_dist_norm: float = 1.0
    pinch_px: float = 0.0
    is_pinching: bool = False
    pinch_started: bool = False
    is_open_hand: bool = False
    draw_gesture: str = "NO_HAND"
    pose: str = "NONE"
    action_gesture: Optional[str] = None


class HandTracker:
    """Single MediaPipe HandLandmarker using 640x480 VIDEO tracking, usable-area mapping, and smoothing."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, cfg: Optional[Dict[str, Any]] = None):
        self.model_path = model_path
        c = clamp_calibration(cfg or DEFAULT_CALIBRATION)
        self.detection_confidence = c["confidence"]
        self.pinch_threshold = c["pinch_threshold"]
        self.sensitivity = c["sensitivity"]
        self.usable_area = c["usable_area"]
        self.smoothing = c["smoothing"]
        self.track_size = (int(c["track_w"]), int(c["track_h"]))
        self.debouncer = PinchDebouncer(cooldown_frames=10, stability_frames=c["stability_frames"])
        self.gesture_debouncer = GestureDebouncer(hold_frames=4, cooldown_sec=1.5)
        self._detector = None
        self._last_ts_ms = 0
        self._smooth_tip: Optional[Tuple[float, float]] = None
        self.last_track_ms = 0.0
        self.avg_track_ms = 0.0
        self.load_error = ""
        self._build_detector()

    def apply_calibration(self, cfg: Dict[str, Any]):
        c = clamp_calibration(cfg)
        self.pinch_threshold = c["pinch_threshold"]
        self.sensitivity = c["sensitivity"]
        self.usable_area = c["usable_area"]
        self.smoothing = c["smoothing"]
        self.debouncer.stability_frames = c["stability_frames"]
        self.set_confidence(c["confidence"])

    def _build_detector(self):
        self.close()
        self._last_ts_ms = 0
        if not os.path.isfile(self.model_path):
            self.load_error = f"Missing MediaPipe model: {self.model_path}"
            return
        try:
            opts = mp_vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=self.model_path),
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=self.detection_confidence,
                min_hand_presence_confidence=self.detection_confidence,
                min_tracking_confidence=self.detection_confidence,
            )
            self._detector = mp_vision.HandLandmarker.create_from_options(opts)
            self.load_error = ""
        except Exception as exc:
            self._detector = None
            self.load_error = f"Hand tracker init failed: {exc}"

    def set_confidence(self, confidence: float):
        clamped = float(np.clip(confidence, 0.40, 0.90))
        if abs(clamped - self.detection_confidence) >= 0.04:
            self.detection_confidence = clamped
            self._build_detector()

    def _map_cursor(self, nx: float, ny: float, w: int, h: int) -> Tuple[int, int]:
        u = max(0.45, self.usable_area)
        mx = float(np.clip(0.5 + ((nx - 0.5) / u) * self.sensitivity, 0.0, 1.0)) * (w - 1)
        my = float(np.clip(0.5 + ((ny - 0.5) / u) * self.sensitivity, 0.0, 1.0)) * (h - 1)
        return int(mx), int(my)

    def _smooth_cursor(self, pt: Tuple[int, int]) -> Tuple[int, int]:
        if self._smooth_tip is None or self.smoothing <= 0.01:
            self._smooth_tip = (float(pt[0]), float(pt[1]))
            return pt
        dist = math.hypot(pt[0] - self._smooth_tip[0], pt[1] - self._smooth_tip[1])
        base = 1.0 - self.smoothing
        alpha = min(1.0, base + (dist / 240.0) * (1.0 - base))
        sx = alpha * pt[0] + (1.0 - alpha) * self._smooth_tip[0]
        sy = alpha * pt[1] + (1.0 - alpha) * self._smooth_tip[1]
        self._smooth_tip = (sx, sy)
        return int(sx), int(sy)

    def process(self, frame_bgr: np.ndarray) -> HandData:
        if self._detector is None or frame_bgr is None:
            self.debouncer.update(False)
            self.gesture_debouncer.update("NONE")
            self._smooth_tip = None
            return HandData()
        t0 = time.perf_counter()
        h, w = frame_bgr.shape[:2]
        tw, th = self.track_size
        small = cv2.resize(frame_bgr, (tw, th), interpolation=cv2.INTER_LINEAR) if (w != tw or h != th) else frame_bgr
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        ts_ms = max(self._last_ts_ms + 1, int(time.perf_counter() * 1000))
        self._last_ts_ms = ts_ms
        result = self._detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        self.last_track_ms = dt_ms
        self.avg_track_ms = dt_ms if self.avg_track_ms == 0.0 else (0.85 * self.avg_track_ms + 0.15 * dt_ms)

        if not result.hand_landmarks:
            self.debouncer.update(False)
            self.gesture_debouncer.update("NONE")
            self._smooth_tip = None
            return HandData()

        lm = result.hand_landmarks[0]
        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
        thumb, index = lm[4], lm[8]
        pinch_norm = math.hypot(thumb.x - index.x, thumb.y - index.y)
        pinch_px = math.hypot((thumb.x - index.x) * w, (thumb.y - index.y) * h)
        is_pinch = pinch_norm < self.pinch_threshold
        pinch_started = self.debouncer.update(is_pinch)

        tip = self._smooth_cursor(self._map_cursor(index.x, index.y, w, h))
        p_ctr = self._map_cursor((thumb.x + index.x) * 0.5, (thumb.y + index.y) * 0.5, w, h)

        wrist = np.array([lm[0].x, lm[0].y, lm[0].z])
        scale = float(np.linalg.norm(np.array([lm[17].x, lm[17].y, lm[17].z]) - wrist)) + 1e-6
        avg_dist = float(np.mean([np.linalg.norm(np.array([lm[t].x, lm[t].y, lm[t].z]) - wrist) for t in (4, 8, 12, 16, 20)]))
        open_hand = (avg_dist / scale) > 0.28

        idx_up = pts[8][1] < pts[6][1]
        curled = (pts[12][1] >= pts[10][1]) and (pts[16][1] >= pts[14][1]) and (pts[20][1] >= pts[18][1])
        draw_gesture = "DRAW" if (idx_up and curled) else "STOP"

        palm_px = math.hypot(pts[17][0] - pts[0][0], pts[17][1] - pts[0][1]) + 1.0
        pose = classify_hand_pose(pts, palm_px, is_pinch)
        action = self.gesture_debouncer.update(pose)
        return HandData(True, lm, pts, tip, p_ctr, pinch_norm, pinch_px, is_pinch, pinch_started, open_hand, draw_gesture, pose, action)

    @staticmethod
    def draw_skeleton(frame: np.ndarray, hand: HandData, bone_color=(255, 220, 40), dot_color=(245, 245, 255)):
        if not hand.detected:
            return
        pts = hand.landmarks_px
        for s, e in HAND_CONNECTIONS:
            cv2.line(frame, pts[s], pts[e], bone_color, 2, cv2.LINE_AA)
        for px, py in pts:
            cv2.circle(frame, (px, py), 4, dot_color, -1, cv2.LINE_AA)

    def close(self):
        if self._detector is not None:
            try:
                self._detector.close()
            finally:
                self._detector = None
