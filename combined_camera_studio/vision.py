"""Shared camera, MediaPipe hand tracking, and gesture helpers."""

from dataclasses import dataclass, field
import math
import os
import sys
from typing import List, Optional, Tuple, Union

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
import numpy as np

WIN_W, WIN_H = 1280, 720

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

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "hand_landmarker.task")


def parse_camera_source(raw: str) -> Union[int, str]:
    """Convert numeric strings like '0' into int indices; keep URLs/paths as str."""
    text = (raw or "").strip()
    if not text:
        return 0
    return int(text) if text.isdigit() else text


class CameraSource:
    """Owns the single shared cv2.VideoCapture across the menu and all modes."""

    def __init__(self, source: str = "0", width: int = WIN_W, height: int = WIN_H):
        self.source_str = str(source).strip() or "0"
        self.width, self.height = width, height
        self.cap: Optional[cv2.VideoCapture] = None
        self.last_error = ""
        self.is_live = False
        self.is_file = False

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

        ok, test_frame = cap.read()
        if not ok or test_frame is None or test_frame.size == 0:
            cap.release()
            self.last_error = (
                f"Connected to '{self.source_str}' but received no frames. "
                "Check that the camera or stream is active and not in use."
            )
            return False

        self.cap = cap
        self.is_live = True
        return True

    def read_frame(self, flip: bool = True) -> Tuple[bool, Optional[np.ndarray]]:
        if self.cap is None or not self.cap.isOpened():
            return False, None
        ok, frame = self.cap.read()
        if (not ok or frame is None) and self.is_file:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
        if not ok or frame is None or frame.size == 0:
            return False, None
        if flip:
            frame = cv2.flip(frame, 1)
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        return True, frame

    def release(self):
        if self.cap is not None:
            try:
                if self.cap.isOpened():
                    self.cap.release()
            finally:
                self.cap = None
                self.is_live = False


class PinchDebouncer:
    """Detects clean pinch rising edges with frame cooldown to prevent double triggers."""

    def __init__(self, cooldown_frames: int = 14):
        self.cooldown_frames = max(1, int(cooldown_frames))
        self._was_pinching = False
        self._cooldown = 0

    def update(self, is_pinching: bool) -> bool:
        ready = self._cooldown == 0
        if self._cooldown > 0:
            self._cooldown -= 1
        started = bool(is_pinching and not self._was_pinching)
        self._was_pinching = bool(is_pinching)
        if started and ready:
            self._cooldown = self.cooldown_frames
            return True
        return False

    def reset(self):
        self._was_pinching = False
        self._cooldown = 0


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


class HandTracker:
    """Single MediaPipe HandLandmarker shared by the menu and all three modes."""

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH, detection_confidence: float = 0.65, pinch_threshold: float = 0.055):
        self.model_path = model_path
        self.detection_confidence = float(detection_confidence)
        self.pinch_threshold = float(pinch_threshold)
        self.debouncer = PinchDebouncer(cooldown_frames=14)
        self._detector = None
        self.load_error = ""
        self._build_detector()

    def _build_detector(self):
        self.close()
        if not os.path.isfile(self.model_path):
            self.load_error = f"Missing MediaPipe model: {self.model_path}"
            return
        try:
            opts = mp_vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=self.model_path),
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
        clamped = float(np.clip(confidence, 0.35, 0.90))
        if abs(clamped - self.detection_confidence) >= 0.04:
            self.detection_confidence = clamped
            self._build_detector()

    def set_pinch_threshold(self, threshold: float):
        self.pinch_threshold = float(np.clip(threshold, 0.025, 0.11))

    def process(self, frame_bgr: np.ndarray) -> HandData:
        if self._detector is None or frame_bgr is None:
            self.debouncer.update(False)
            return HandData()
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        if not result.hand_landmarks:
            self.debouncer.update(False)
            return HandData()

        lm = result.hand_landmarks[0]
        pts = [(int(p.x * w), int(p.y * h)) for p in lm]
        thumb, index = lm[4], lm[8]
        pinch_norm = math.hypot(thumb.x - index.x, thumb.y - index.y)
        pinch_px = math.hypot((thumb.x - index.x) * w, (thumb.y - index.y) * h)
        is_pinch = pinch_norm < self.pinch_threshold
        pinch_started = self.debouncer.update(is_pinch)
        pinch_center = ((pts[4][0] + pts[8][0]) // 2, (pts[4][1] + pts[8][1]) // 2)

        wrist = np.array([lm[0].x, lm[0].y, lm[0].z])
        scale = float(np.linalg.norm(np.array([lm[17].x, lm[17].y, lm[17].z]) - wrist)) + 1e-6
        avg_dist = float(np.mean([np.linalg.norm(np.array([lm[t].x, lm[t].y, lm[t].z]) - wrist) for t in (4, 8, 12, 16, 20)]))
        open_hand = (avg_dist / scale) > 0.28

        idx_up = pts[8][1] < pts[6][1]
        curled = (pts[12][1] >= pts[10][1]) and (pts[16][1] >= pts[14][1]) and (pts[20][1] >= pts[18][1])
        draw_gesture = "DRAW" if (idx_up and curled) else "STOP"

        return HandData(True, lm, pts, pts[8], pinch_center, pinch_norm, pinch_px, is_pinch, pinch_started, open_hand, draw_gesture)

    @staticmethod
    def draw_skeleton(frame: np.ndarray, hand: HandData, bone_color=(255, 220, 40), dot_color=(245, 245, 255)):
        if not hand.detected:
            return
        pts = hand.landmarks_px
        for s, e in HAND_CONNECTIONS:
            cv2.line(frame, pts[s], pts[e], bone_color, 2, cv2.LINE_AA)
        for px, py in pts:
            cv2.circle(frame, (px, py), 4, dot_col := dot_color, -1, cv2.LINE_AA)

    def close(self):
        if self._detector is not None:
            try:
                self._detector.close()
            finally:
                self._detector = None
