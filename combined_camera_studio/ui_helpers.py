"""Shared OpenCV UI helpers, lightweight AR hand HUD, buttons, FPS counter, toasts, and fingertip FX."""

import math
import random
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

FONT, FONT_SMALL = cv2.FONT_HERSHEY_DUPLEX, cv2.FONT_HERSHEY_SIMPLEX
ACCENT_CYAN, ACCENT_GREEN = (255, 220, 40), (90, 230, 120)
ACCENT_ORANGE, ACCENT_RED, ACCENT_PURPLE = (60, 165, 255), (80, 90, 245), (240, 110, 220)
TEXT_PRIMARY, TEXT_MUTED, PANEL_BG = (238, 240, 248), (155, 160, 180), (18, 20, 30)

_FILL_CACHE: Dict[Tuple[int, int, Tuple[int, int, int]], np.ndarray] = {}
_RADIAL_12 = [(math.cos(i * math.pi / 6.0), math.sin(i * math.pi / 6.0)) for i in range(12)]


def _solid_roi(w: int, h: int, color: Tuple[int, int, int]) -> np.ndarray:
    key = (w, h, tuple(color))
    buf = _FILL_CACHE.get(key)
    if buf is None:
        if len(_FILL_CACHE) > 24:
            _FILL_CACHE.clear()
        buf = np.full((h, w, 3), color, dtype=np.uint8)
        _FILL_CACHE[key] = buf
    return buf


def glass_panel(frame, x: int, y: int, w: int, h: int, alpha: float = 0.62, border_color=ACCENT_CYAN, bg_color=PANEL_BG, border_thickness: int = 1):
    fh, fw = frame.shape[:2]
    x1, y1, x2, y2 = max(0, int(x)), max(0, int(y)), min(fw, int(x + w)), min(fh, int(y + h))
    rw, rh = x2 - x1, y2 - y1
    if rw <= 0 or rh <= 0:
        return
    roi = frame[y1:y2, x1:x2]
    cv2.addWeighted(_solid_roi(rw, rh, bg_color), alpha, roi, 1.0 - alpha, 0, dst=roi)
    if border_thickness > 0:
        cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), border_color, border_thickness, cv2.LINE_AA)


class Button:
    def __init__(self, x: int, y: int, w: int, h: int, label: str, active: bool = False):
        self.x, self.y, self.w, self.h, self.label, self.active = int(x), int(y), int(w), int(h), label, active

    def contains(self, pt: Optional[Tuple[int, int]]) -> bool:
        return pt is not None and self.x <= pt[0] <= self.x + self.w and self.y <= pt[1] <= self.y + self.h

    def draw(self, frame, hovered: bool = False, accent=ACCENT_CYAN):
        hot = hovered or self.active
        glass_panel(frame, self.x, self.y, self.w, self.h, 0.80, accent if hot else (85, 95, 125), (42, 52, 78) if hot else (24, 28, 42), 2 if hot else 1)
        (tw, th), _ = cv2.getTextSize(self.label, FONT_SMALL, 0.48, 1)
        cv2.putText(frame, self.label, (self.x + (self.w - tw) // 2, self.y + (self.h + th) // 2 - 2), FONT_SMALL, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)


def draw_pointer(frame, pt: Optional[Tuple[int, int]], pinching: bool = False, label: str = ""):
    if pt is None:
        return
    color = ACCENT_GREEN if pinching else ACCENT_CYAN
    cv2.circle(frame, pt, 11 if pinching else 14, color, 2, cv2.LINE_AA)
    cv2.circle(frame, pt, 4, (255, 255, 255) if pinching else color, -1, cv2.LINE_AA)
    if label:
        cv2.putText(frame, label, (pt[0] + 16, pt[1] + 5), FONT_SMALL, 0.45, color, 1, cv2.LINE_AA)


def draw_ar_hand_hud(frame, hand) -> None:
    """Single-pass radial HUD near tracked palm (inspired by Hand-Tracking-AR-UI, MIT; zero full-frame copies)."""
    if not hand.detected or len(hand.landmarks_px) < 21:
        return
    pts = hand.landmarks_px
    palm = pts[9]
    col = ACCENT_GREEN if hand.is_pinching else ACCENT_CYAN
    cv2.ellipse(frame, palm, (58, 58), 0, -40, 220, col, 2, cv2.LINE_AA)
    cv2.ellipse(frame, palm, (42, 42), 0, 0, 360, (70, 85, 120), 1, cv2.LINE_AA)
    for cx, sy in _RADIAL_12:
        cv2.line(frame, (int(palm[0] + 52 * cx), int(palm[1] + 52 * sy)),
                 (int(palm[0] + 62 * cx), int(palm[1] + 62 * sy)), col, 1, cv2.LINE_AA)
    pinch_deg = int(np.clip((1.0 - hand.pinch_dist_norm / 0.14) * 360.0, 20, 360))
    cv2.ellipse(frame, palm, (30, 30), -90, 0, pinch_deg, ACCENT_ORANGE, 2, cv2.LINE_AA)
    for ti in (4, 8, 12, 16, 20):
        cv2.line(frame, palm, pts[ti], (130, 175, 190), 1, cv2.LINE_AA)
        cv2.circle(frame, pts[ti], 5, ACCENT_ORANGE if ti == 8 else col, -1, cv2.LINE_AA)
    tag = hand.pose if hand.pose != "NONE" else ("PINCH" if hand.is_pinching else ("OPEN" if hand.is_open_hand else "FIST"))
    cv2.putText(frame, tag, (palm[0] + 46, palm[1] - 46), FONT_SMALL, 0.44, ACCENT_ORANGE if hand.is_pinching else TEXT_PRIMARY, 1, cv2.LINE_AA)


class FingertipFX:
    """Lightweight localized fingertip particle trail and ripple ring (no full-screen passes)."""

    def __init__(self, enabled: bool = True):
        self.enabled, self.particles, self.ripples, self._last_pt = bool(enabled), [], [], None

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.particles.clear(); self.ripples.clear(); self._last_pt = None

    def update_and_draw(self, frame, pt: Optional[Tuple[int, int]], pinching: bool = False, action_pulse: bool = False):
        if not self.enabled:
            return
        if pt is not None:
            if action_pulse and len(self.ripples) < 3:
                self.ripples.append([int(pt[0]), int(pt[1]), 10.0, 10, ACCENT_GREEN if pinching else ACCENT_PURPLE])
            if (self._last_pt is None or abs(pt[0] - self._last_pt[0]) + abs(pt[1] - self._last_pt[1]) >= 4) and len(self.particles) < 24:
                col = ACCENT_GREEN if pinching else random.choice((ACCENT_CYAN, ACCENT_ORANGE, (240, 190, 90)))
                self.particles.append([float(pt[0]), float(pt[1]), random.uniform(-0.8, 0.8), random.uniform(-1.1, 0.4), 10, 10, col])
            self._last_pt = pt
        else:
            self._last_pt = None

        alive_p = []
        for p in self.particles:
            p[0] += p[2]; p[1] += p[3]; p[4] -= 1
            if p[4] > 0:
                alive_p.append(p)
                t = p[4] / p[5]
                cv2.circle(frame, (int(p[0]), int(p[1])), max(1, int(3.5 * t)), tuple(int(c * t) for c in p[6]), -1, cv2.LINE_AA)
        self.particles = alive_p

        alive_r = []
        for r in self.ripples:
            r[2] += 2.8; r[3] -= 1
            if r[3] > 0:
                alive_r.append(r)
                cv2.circle(frame, (r[0], r[1]), int(r[2]), tuple(int(c * (r[3] / 10.0)) for c in r[4]), 2 if r[3] > 5 else 1, cv2.LINE_AA)
        self.ripples = alive_r


class FPSCounter:
    def __init__(self, window_size: int = 20):
        self.window_size, self._stamps = window_size, []

    def tick(self) -> float:
        self._stamps = (self._stamps + [time.perf_counter()])[-self.window_size:]
        if len(self._stamps) < 2:
            return 0.0
        dt = self._stamps[-1] - self._stamps[0]
        return (len(self._stamps) - 1) / dt if dt > 0 else 0.0


class ToastQueue:
    def __init__(self, lifetime: float = 2.2):
        self.lifetime, self._items = lifetime, []

    def push(self, text: str):
        self._items.append([text, time.time() + self.lifetime])

    def draw(self, frame, start_y: int = 72):
        now = time.time()
        self._items = [it for it in self._items if it[1] > now]
        w, y = frame.shape[1], start_y
        for msg, _ in self._items[-3:]:
            (tw, _), _ = cv2.getTextSize(msg, FONT_SMALL, 0.52, 1)
            pw, x = tw + 30, (w - (tw + 30)) // 2
            glass_panel(frame, x, y, pw, 34, alpha=0.76, border_color=ACCENT_GREEN)
            cv2.putText(frame, msg, (x + 15, y + 22), FONT_SMALL, 0.52, TEXT_PRIMARY, 1, cv2.LINE_AA)
            y += 40
