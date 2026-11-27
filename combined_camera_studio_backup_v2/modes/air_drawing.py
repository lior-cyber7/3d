"""Air Drawing mode adapted from RutujaKhule/Gesture-Canvas (MIT)."""

import math
import os
import random
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ui_helpers import ACCENT_CYAN, ACCENT_GREEN, Button, FONT_SMALL, TEXT_MUTED, TEXT_PRIMARY, ToastQueue, draw_pointer, glass_panel
from vision import HandData, HandTracker, WIN_H, WIN_W

SAVE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")

COLOR_PALETTE = [
    ("Neon Cyan", (255, 220, 40)), ("Neon Magenta", (230, 60, 255)),
    ("Neon Green", (80, 255, 120)), ("Neon Yellow", (40, 235, 255)),
    ("Neon Orange", (30, 130, 255)), ("Electric Blue", (255, 120, 40)),
    ("Hot Pink", (150, 60, 255)), ("Pure White", (255, 255, 255)),
]


class _Particles:
    def __init__(self, w: int, h: int):
        self.w, self.h, self.items = w, h, []

    def emit(self, pt: Tuple[int, int], bgr, count: int = 3):
        if len(self.items) >= 350:
            return
        for _ in range(count):
            ang, spd, life = random.uniform(0, 2 * math.pi), random.uniform(0.6, 2.2), random.randint(18, 36)
            self.items.append([float(pt[0]), float(pt[1]), math.cos(ang) * spd, math.sin(ang) * spd - 0.4, life, life, bgr, random.randint(1, 3)])

    def spawn_ambient(self):
        if len(self.items) < 350 and random.random() < 0.30:
            life = random.randint(20, 65)
            self.items.append([random.uniform(0, self.w), random.uniform(0, self.h), random.uniform(-0.3, 0.3), random.uniform(-0.6, -0.1), life, life, random.choice(COLOR_PALETTE)[1], 1])

    def update_and_render(self) -> np.ndarray:
        layer = np.zeros((self.h, self.w, 3), dtype=np.uint8)
        alive = []
        for p in self.items:
            p[0] += p[2]
            p[1] += p[3]
            p[3] -= 0.03
            p[2] *= 0.98
            p[4] -= 1
            if p[4] > 0:
                alive.append(p)
                if 0 <= p[0] < self.w and 0 <= p[1] < self.h:
                    col = tuple(int(c * (p[4] / p[5])) for c in p[6])
                    cv2.circle(layer, (int(p[0]), int(p[1])), p[7], col, -1, lineType=cv2.LINE_AA)
        self.items = alive
        return layer


class AirDrawingMode:
    name = "Air Drawing"

    def __init__(self):
        self.strokes = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)
        self.particles = _Particles(WIN_W, WIN_H)
        self.toasts = ToastQueue()
        self.color_idx, self.eraser, self.thickness, self.glow = 0, False, 7, 5
        self.help_visible = self.paused = self._has_ink = False
        self._undo_stack: List[np.ndarray] = []
        self._drawing = False
        self._smooth_pt = self._last_pt = self._snapshot = None

        self.btn_brush_dn = Button(WIN_W - 600, 16, 42, 34, "B-")
        self.btn_brush_up = Button(WIN_W - 552, 16, 42, 34, "B+")
        self.btn_glow_dn = Button(WIN_W - 500, 16, 42, 34, "G-")
        self.btn_glow_up = Button(WIN_W - 452, 16, 42, 34, "G+")
        self.btn_eraser = Button(WIN_W - 400, 16, 86, 34, "Eraser [E]")
        self.btn_undo = Button(WIN_W - 306, 16, 74, 34, "Undo [U]")
        self.btn_clear = Button(WIN_W - 224, 16, 76, 34, "Clear [C]")
        self.btn_save = Button(WIN_W - 140, 16, 72, 34, "Save [S]")
        self.btn_help = Button(WIN_W - 60, 16, 44, 34, "?")
        self.toolbar = [self.btn_brush_dn, self.btn_brush_up, self.btn_glow_dn, self.btn_glow_up,
                        self.btn_eraser, self.btn_undo, self.btn_clear, self.btn_save, self.btn_help]

        sw, gap = 36, 12
        sx = (WIN_W - (len(COLOR_PALETTE) * sw + (len(COLOR_PALETTE) - 1) * gap)) // 2
        self.swatches = [(sx + i * (sw + gap), WIN_H - sw - 26, sw, sw) for i in range(len(COLOR_PALETTE))]

    def reset(self):
        self._end_stroke()
        self.particles.items.clear()
        self.paused = False

    def toggle_pause(self) -> bool:
        self.paused = not self.paused
        if self.paused:
            self._end_stroke()
        return self.paused

    def _begin_stroke(self, pt: Tuple[int, int]):
        self._snapshot = self.strokes.copy()
        self._smooth_pt = self._last_pt = pt
        self._drawing = True
        self._has_ink = True
        col = (0, 0, 0) if self.eraser else COLOR_PALETTE[self.color_idx][1]
        cv2.circle(self.strokes, pt, max(2, (self.thickness * 2 if self.eraser else self.thickness) // 2), col, -1, lineType=cv2.LINE_AA)

    def _extend_stroke(self, pt: Tuple[int, int]) -> Tuple[int, int]:
        sx = int(0.55 * pt[0] + 0.45 * self._smooth_pt[0])
        sy = int(0.55 * pt[1] + 0.45 * self._smooth_pt[1])
        self._smooth_pt = (sx, sy)
        steps = max(1, int(math.hypot(sx - self._last_pt[0], sy - self._last_pt[1]) // 6) + 1)
        col = (0, 0, 0) if self.eraser else COLOR_PALETTE[self.color_idx][1]
        thick = self.thickness * 2 if self.eraser else self.thickness
        for i in range(1, steps + 1):
            t = i / steps
            nxt = (int(self._last_pt[0] + (sx - self._last_pt[0]) * t), int(self._last_pt[1] + (sy - self._last_pt[1]) * t))
            cv2.line(self.strokes, self._last_pt, nxt, col, thick, lineType=cv2.LINE_AA)
            self._last_pt = nxt
        return self._smooth_pt

    def _end_stroke(self):
        if self._drawing and self._snapshot is not None:
            self._undo_stack = (self._undo_stack + [self._snapshot])[-25:]
        self._drawing = False
        self._smooth_pt = self._last_pt = self._snapshot = None

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        self.strokes = self._undo_stack.pop()
        self._has_ink = bool(self.strokes.any())
        return True

    def clear(self):
        self._undo_stack = (self._undo_stack + [self.strokes.copy()])[-25:]
        self.strokes.fill(0)
        self._has_ink = False

    def save_png(self, composite: np.ndarray) -> str:
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, f"air_drawing_{time.strftime('%Y%m%d_%H%M%S')}.png")
        cv2.imwrite(path, composite)
        return path

    def _handle_button(self, pt: Tuple[int, int], composite_for_save: np.ndarray) -> bool:
        for i, (x, y, w, h) in enumerate(self.swatches):
            if x <= pt[0] <= x + w and y <= pt[1] <= y + h:
                self.color_idx, self.eraser = i, False
                self.toasts.push(f"Color: {COLOR_PALETTE[i][0]}")
                return True
        if self.btn_brush_dn.contains(pt):
            self.thickness = max(2, self.thickness - 2)
        elif self.btn_brush_up.contains(pt):
            self.thickness = min(40, self.thickness + 2)
        elif self.btn_glow_dn.contains(pt):
            self.glow = max(0, self.glow - 1)
        elif self.btn_glow_up.contains(pt):
            self.glow = min(10, self.glow + 1)
        elif self.btn_eraser.contains(pt):
            self.eraser = not self.eraser
            self.toasts.push("Eraser ON" if self.eraser else "Brush ON")
        elif self.btn_undo.contains(pt):
            self.toasts.push("Undo" if self.undo() else "Nothing to undo")
        elif self.btn_clear.contains(pt):
            self.clear()
            self.toasts.push("Canvas cleared")
        elif self.btn_save.contains(pt):
            self.toasts.push(f"Saved {os.path.basename(self.save_png(composite_for_save))}")
        elif self.btn_help.contains(pt):
            self.help_visible = not self.help_visible
        else:
            return False
        return True

    def update_and_render(self, frame: np.ndarray, hand: HandData, mouse, key: int) -> Optional[str]:
        if key == ord("c"):
            self.clear(); self.toasts.push("Canvas cleared")
        elif key == ord("u"):
            self.toasts.push("Undo" if self.undo() else "Nothing to undo")
        elif key == ord("e"):
            self.eraser = not self.eraser; self.toasts.push("Eraser ON" if self.eraser else "Brush ON")
        elif key == ord("h"):
            self.help_visible = not self.help_visible
        elif key in (ord("+"), ord("=")):
            self.thickness = min(40, self.thickness + 2)
        elif key in (ord("-"), ord("_")):
            self.thickness = max(2, self.thickness - 2)
        elif key == ord("]"):
            self.glow = min(10, self.glow + 1)
        elif key == ord("["):
            self.glow = max(0, self.glow - 1)
        elif ord("1") <= key <= ord("8"):
            self.color_idx, self.eraser = key - ord("1"), False

        if self._has_ink and self.glow > 0:
            small = cv2.resize(self.strokes, (WIN_W // 2, WIN_H // 2), interpolation=cv2.INTER_AREA)
            k = 1 + 2 * max(1, self.glow // 2)
            glow_up = cv2.resize(cv2.GaussianBlur(small, (k, k), 0), (WIN_W, WIN_H), interpolation=cv2.INTER_LINEAR)
            bloom = cv2.addWeighted(self.strokes, 1.0, glow_up, 0.35 + 0.09 * self.glow, 0)
            composite = cv2.add(frame, bloom)
        elif self._has_ink:
            composite = cv2.add(frame, self.strokes)
        else:
            composite = frame

        clicked_toolbar = any(
            self._handle_button(ptr, composite)
            for ptr, clicked in ((mouse.pos, mouse.just_released), (hand.pinch_center, hand.pinch_started))
            if clicked and ptr is not None
        )
        if key == ord("s"):
            self.toasts.push(f"Saved {os.path.basename(self.save_png(composite))}")

        cursor_pt, is_draw_active = None, False
        in_hud = lambda pt: pt[1] <= 62 or pt[1] >= WIN_H - 68
        if not self.paused and hand.detected and hand.index_tip is not None:
            cursor_pt = hand.index_tip
            if hand.draw_gesture == "DRAW" and not in_hud(cursor_pt):
                is_draw_active = True
                cursor_pt = self._extend_stroke(cursor_pt) if self._drawing else (self._begin_stroke(cursor_pt) or cursor_pt)
                if not self.eraser:
                    self.particles.emit(cursor_pt, COLOR_PALETTE[self.color_idx][1])
            elif self._drawing:
                self._end_stroke()
        elif not self.paused and mouse.down and not clicked_toolbar and not in_hud(mouse.pos):
            cursor_pt, is_draw_active = mouse.pos, True
            cursor_pt = self._extend_stroke(cursor_pt) if self._drawing else (self._begin_stroke(cursor_pt) or cursor_pt)
            if not self.eraser:
                self.particles.emit(cursor_pt, COLOR_PALETTE[self.color_idx][1])
        else:
            if self._drawing:
                self._end_stroke()
            cursor_pt = hand.index_tip if hand.detected else mouse.pos

        self.particles.spawn_ambient()
        frame[:] = cv2.add(composite, self.particles.update_and_render())
        HandTracker.draw_skeleton(frame, hand)
        if cursor_pt is not None:
            rad = max(6, self.thickness * 2 if self.eraser else self.thickness)
            col = (80, 90, 245) if self.eraser else (ACCENT_GREEN if is_draw_active else ACCENT_CYAN)
            cv2.circle(frame, cursor_pt, rad, col, 2, cv2.LINE_AA)
            cv2.circle(frame, cursor_pt, 2, col, -1, cv2.LINE_AA)
        if hand.detected and hand.pinch_center and hand.is_pinching:
            draw_pointer(frame, hand.pinch_center, pinching=True)

        self.btn_eraser.active = self.eraser
        for btn in self.toolbar:
            btn.draw(frame, hovered=btn.contains(mouse.pos) or btn.contains(hand.index_tip))

        col_name, col_bgr = COLOR_PALETTE[self.color_idx]
        glass_panel(frame, 16, 68, 268, 56, alpha=0.58)
        cv2.circle(frame, (36, 96), 9, (90, 90, 100) if self.eraser else col_bgr, -1, cv2.LINE_AA)
        cv2.putText(frame, f"{'PAUSED' if self.paused else ('ERASER' if self.eraser else col_name)} | B:{self.thickness} G:{self.glow}", (54, 92), FONT_SMALL, 0.45, TEXT_PRIMARY, 1, cv2.LINE_AA)
        cv2.putText(frame, "OPEN PALM: resume" if self.paused else ("INDEX: draw | FIST: stop" if hand.detected else "Mouse drag or show hand"), (54, 112), FONT_SMALL, 0.40, TEXT_MUTED, 1, cv2.LINE_AA)

        sx, sy = self.swatches[0][0], self.swatches[0][1]
        glass_panel(frame, sx - 12, sy - 8, self.swatches[-1][0] + self.swatches[-1][2] - sx + 24, 62, alpha=0.52)
        for i, (x, y, w, h) in enumerate(self.swatches):
            cv2.rectangle(frame, (x, y), (x + w, y + h), COLOR_PALETTE[i][1], -1, cv2.LINE_AA)
            is_sel = i == self.color_idx and not self.eraser
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255) if is_sel else (80, 85, 100), 2 if is_sel else 1, cv2.LINE_AA)
            cv2.putText(frame, str(i + 1), (x + 13, y + h + 14), FONT_SMALL, 0.38, TEXT_MUTED, 1, cv2.LINE_AA)

        if self.help_visible:
            glass_panel(frame, WIN_W // 2 - 230, WIN_H // 2 - 155, 460, 310, alpha=0.88)
            cv2.putText(frame, "Air Drawing & Gesture Controls", (WIN_W // 2 - 205, WIN_H // 2 - 122), cv2.FONT_HERSHEY_DUPLEX, 0.64, ACCENT_CYAN, 1, cv2.LINE_AA)
            for idx, (k_txt, desc) in enumerate([
                ("Index / Mouse Drag", "Draw neon stroke"),
                ("Closed Fist", "Lift brush (stop stroke)"),
                ("Open Palm / Peace", "Pause-Resume / Back to Menu"),
                ("Thumbs-Up / Pinch", "Confirm Toast / Select HUD"),
                ("1-8 / E / V", "Color / Eraser / Fingertip FX"),
                ("+/- or [/]", "Brush size / Glow intensity"),
                ("U / C / S / M", "Undo / Clear / Save / Menu"),
            ]):
                ry = WIN_H // 2 - 84 + idx * 32
                cv2.putText(frame, k_txt, (WIN_W // 2 - 205, ry), FONT_SMALL, 0.46, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame, desc, (WIN_W // 2 - 10, ry), FONT_SMALL, 0.45, TEXT_MUTED, 1, cv2.LINE_AA)

        self.toasts.draw(frame)
        return None
