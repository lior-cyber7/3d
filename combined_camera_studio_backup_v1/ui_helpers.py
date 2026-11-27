"""Shared OpenCV UI drawing helpers, buttons, FPS counter, and toast queue."""

import time
from typing import Optional, Tuple

import cv2

FONT = cv2.FONT_HERSHEY_DUPLEX
FONT_SMALL = cv2.FONT_HERSHEY_SIMPLEX

ACCENT_CYAN = (255, 220, 40)
ACCENT_GREEN = (90, 230, 120)
ACCENT_ORANGE = (60, 165, 255)
ACCENT_RED = (80, 90, 245)
TEXT_PRIMARY = (238, 240, 248)
TEXT_MUTED = (155, 160, 180)
PANEL_BG = (18, 20, 30)


def glass_panel(frame, x: int, y: int, w: int, h: int, alpha: float = 0.62, border_color=ACCENT_CYAN, bg_color=PANEL_BG, border_thickness: int = 1):
    """Draw a translucent dark panel clipped safely to frame bounds."""
    fh, fw = frame.shape[:2]
    x1, y1 = max(0, int(x)), max(0, int(y))
    x2, y2 = min(fw, int(x + w)), min(fh, int(y + h))
    if x2 <= x1 or y2 <= y1:
        return
    roi = frame[y1:y2, x1:x2]
    overlay = roi.copy()
    overlay[:] = bg_color
    cv2.addWeighted(overlay, alpha, roi, 1.0 - alpha, 0, dst=roi)
    if border_thickness > 0:
        cv2.rectangle(frame, (x1, y1), (x2 - 1, y2 - 1), border_color, border_thickness, cv2.LINE_AA)


class Button:
    """Interactive rectangular button usable with both hand-pinch and mouse clicks."""

    def __init__(self, x: int, y: int, w: int, h: int, label: str, active: bool = False):
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)
        self.label = label
        self.active = active

    def contains(self, pt: Optional[Tuple[int, int]]) -> bool:
        return pt is not None and self.x <= pt[0] <= self.x + self.w and self.y <= pt[1] <= self.y + self.h

    def draw(self, frame, hovered: bool = False, accent=ACCENT_CYAN):
        bg = (42, 52, 78) if (hovered or self.active) else (24, 28, 42)
        border = accent if (hovered or self.active) else (85, 95, 125)
        glass_panel(frame, self.x, self.y, self.w, self.h, alpha=0.80, border_color=border, bg_color=bg, border_thickness=2 if (hovered or self.active) else 1)
        (tw, th), _ = cv2.getTextSize(self.label, FONT_SMALL, 0.52, 1)
        cv2.putText(frame, self.label, (self.x + (self.w - tw) // 2, self.y + (self.h + th) // 2 - 2), FONT_SMALL, 0.52, TEXT_PRIMARY, 1, cv2.LINE_AA)


def draw_pointer(frame, pt: Optional[Tuple[int, int]], pinching: bool = False, label: str = ""):
    if pt is None:
        return
    color = ACCENT_GREEN if pinching else ACCENT_CYAN
    cv2.circle(frame, pt, 11 if pinching else 14, color, 2, cv2.LINE_AA)
    cv2.circle(frame, pt, 4, (255, 255, 255) if pinching else color, -1, cv2.LINE_AA)
    if label:
        cv2.putText(frame, label, (pt[0] + 16, pt[1] + 5), FONT_SMALL, 0.45, color, 1, cv2.LINE_AA)


class FPSCounter:
    def __init__(self, window_size: int = 20):
        self.window_size = window_size
        self._stamps = []

    def tick(self) -> float:
        now = time.time()
        self._stamps.append(now)
        if len(self._stamps) > self.window_size:
            self._stamps.pop(0)
        if len(self._stamps) < 2:
            return 0.0
        dt = self._stamps[-1] - self._stamps[0]
        return (len(self._stamps) - 1) / dt if dt > 0 else 0.0


class ToastQueue:
    def __init__(self, lifetime: float = 2.4):
        self.lifetime = lifetime
        self._items = []

    def push(self, text: str):
        self._items.append([text, time.time() + self.lifetime])

    def draw(self, frame, start_y: int = 76):
        now = time.time()
        self._items = [item for item in self._items if item[1] > now]
        if not self._items:
            return
        w, y = frame.shape[1], start_y
        for msg, _ in self._items[-3:]:
            (tw, _), _ = cv2.getTextSize(msg, FONT_SMALL, 0.55, 1)
            pw = tw + 32
            x = (w - pw) // 2
            glass_panel(frame, x, y, pw, 34, alpha=0.72, border_color=ACCENT_GREEN)
            cv2.putText(frame, msg, (x + 16, y + 22), FONT_SMALL, 0.55, TEXT_PRIMARY, 1, cv2.LINE_AA)
            y += 40
