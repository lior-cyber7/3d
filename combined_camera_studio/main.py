"""Combined Camera Studio -- Single-window, single-camera interactive desktop app."""

import argparse
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

from modes import AirDrawingMode, LiquidCubeMode, SelfiePuzzleMode
from ui_helpers import (
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED, Button, FONT, FONT_SMALL,
    FPSCounter, TEXT_MUTED, TEXT_PRIMARY, ToastQueue, draw_pointer, glass_panel,
)
from vision import CameraSource, HandData, HandTracker, WIN_H, WIN_W

WIN_NAME = "Combined Camera Studio"
MODE_MENU, MODE_SETTINGS, MODE_CUBE, MODE_DRAW, MODE_PUZZLE = "MENU", "SETTINGS", "LIQUID_CUBE", "AIR_DRAWING", "SELFIE_PUZZLE"


@dataclass
class MouseState:
    pos: Tuple[int, int] = (0, 0)
    down: bool = False
    just_pressed: bool = False
    just_released: bool = False
    wheel: int = 0

    def end_frame(self):
        self.just_pressed = self.just_released = False
        self.wheel = 0


def _wrap_text(text: str, max_chars: int = 31):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = f"{cur} {w}".strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])


class StudioApp:
    """Coordinates shared camera, hand tracking, menu, settings, and the 3 modes."""

    def __init__(self, camera_source: str = "0", flip: bool = True, headless: bool = False):
        self.camera = CameraSource(camera_source, WIN_W, WIN_H)
        self.tracker = HandTracker()
        self.fps = FPSCounter()
        self.toasts = ToastQueue()
        self.mouse = MouseState()
        self.flip, self.headless = flip, headless
        self.screen = self.prev_screen = MODE_MENU
        self.running = True
        self.modes = {MODE_CUBE: LiquidCubeMode(), MODE_DRAW: AirDrawingMode(), MODE_PUZZLE: SelfiePuzzleMode()}

        self.camera_input = str(camera_source)
        self.editing_camera = False
        self.pinch_threshold = self.tracker.pinch_threshold
        self.confidence = self.tracker.detection_confidence

        self.cards = [
            (MODE_CUBE, Button(70, 210, 350, 340, ""), "Liquid Cube",
             "3D fluid physics inside a cube. Open hand spins, fist freezes, pinch resizes.", "Hand: Open / Fist / Pinch", ACCENT_CYAN),
            (MODE_DRAW, Button(465, 210, 350, 340, ""), "Air Drawing",
             "Draw glowing neon strokes in mid-air with particles, eraser, undo, and PNG save.", "Hand: Index = Draw | Fist = Stop", ACCENT_GREEN),
            (MODE_PUZZLE, Button(860, 210, 350, 340, ""), "Selfie Puzzle",
             "Pinch-drag a live selfie region, shuffle into 9 tiles, and solve by hand or mouse.", "Hand: Pinch & Drag", ACCENT_ORANGE),
        ]
        self.btn_settings = Button(WIN_W - 295, 42, 125, 38, "Settings [S]")
        self.btn_quit = Button(WIN_W - 160, 42, 105, 38, "Quit [Q]")
        self.btn_menu = Button(16, 16, 120, 36, "Menu [M]")

        self.btn_cam_box = Button(370, 175, 510, 44, "")
        self.btn_cam_apply = Button(895, 175, 165, 44, "Apply Camera")
        self.btn_mirror = Button(370, 275, 200, 40, "")
        self.btn_sens_dn, self.btn_sens_up = Button(370, 340, 48, 40, "-"), Button(530, 340, 48, 40, "+")
        self.btn_conf_dn, self.btn_conf_up = Button(370, 405, 48, 40, "-"), Button(530, 405, 48, 40, "+")
        self.btn_set_back = Button(550, 560, 180, 44, "Back [Esc]")

    def start(self):
        self.camera.open(self.camera_input)

    def switch_mode(self, target: str):
        if target in self.modes and target != self.screen:
            self.modes[target].reset()
        if target == MODE_SETTINGS and self.screen != MODE_SETTINGS:
            self.prev_screen, self.editing_camera = self.screen, True
        else:
            self.editing_camera = False
        self.screen = target
        self.tracker.debouncer.reset()

    def _pointer(self, hand: HandData) -> Tuple[Optional[Tuple[int, int]], bool]:
        if hand.detected:
            return (hand.pinch_center if hand.is_pinching else hand.index_tip), hand.pinch_started
        return self.mouse.pos, self.mouse.just_released

    def _render_menu(self, frame: np.ndarray, hand: HandData, key: int):
        frame[:] = (frame.astype(np.float32) * 0.35 + np.array([14, 16, 26], dtype=np.float32) * 0.65).astype(np.uint8)
        glass_panel(frame, 40, 22, WIN_W - 80, 120, alpha=0.70, border_color=ACCENT_CYAN)
        cv2.putText(frame, "Combined Camera Studio", (70, 74), FONT, 1.15, TEXT_PRIMARY, 2, cv2.LINE_AA)
        cv2.putText(frame, "Point with index finger and PINCH a card (or click with mouse / press 1-3)", (72, 112), FONT_SMALL, 0.56, TEXT_MUTED, 1, cv2.LINE_AA)

        self.btn_settings.draw(frame, hovered=self.btn_settings.contains(self.mouse.pos) or self.btn_settings.contains(hand.index_tip))
        self.btn_quit.draw(frame, hovered=self.btn_quit.contains(self.mouse.pos) or self.btn_quit.contains(hand.index_tip), accent=ACCENT_RED)
        if not self.camera.is_live:
            glass_panel(frame, 70, 152, WIN_W - 140, 44, alpha=0.85, border_color=ACCENT_RED)
            cv2.putText(frame, f"Camera Error: {self.camera.last_error[:112]}", (88, 180), FONT_SMALL, 0.48, (140, 150, 255), 1, cv2.LINE_AA)

        ptr, clicked = self._pointer(hand)
        for idx, (mode_id, box, title, desc, hint, accent) in enumerate(self.cards):
            hovered = box.contains(ptr) or box.contains(self.mouse.pos)
            glass_panel(frame, box.x, box.y, box.w, box.h, alpha=0.84, border_color=accent if hovered else (75, 85, 115),
                        bg_color=(32, 38, 58) if hovered else (20, 24, 38), border_thickness=3 if hovered else 1)
            cv2.putText(frame, f"[{idx + 1}]", (box.x + 24, box.y + 42), FONT_SMALL, 0.58, accent, 1, cv2.LINE_AA)
            cv2.putText(frame, title, (box.x + 24, box.y + 88), FONT, 0.95, TEXT_PRIMARY, 2, cv2.LINE_AA)
            cv2.line(frame, (box.x + 24, box.y + 108), (box.x + box.w - 24, box.y + 108), accent, 1)
            for li, line in enumerate(_wrap_text(desc)):
                cv2.putText(frame, line, (box.x + 24, box.y + 148 + li * 28), FONT_SMALL, 0.52, TEXT_MUTED, 1, cv2.LINE_AA)
            glass_panel(frame, box.x + 20, box.y + box.h - 72, box.w - 40, 46, alpha=0.75, border_color=accent)
            cv2.putText(frame, hint, (box.x + 34, box.y + box.h - 43), FONT_SMALL, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)
            if clicked and box.contains(ptr):
                self.switch_mode(mode_id); return

        for pt, trig in ((self.mouse.pos, self.mouse.just_released), (hand.pinch_center, hand.pinch_started)):
            if trig and pt:
                if self.btn_settings.contains(pt):
                    self.switch_mode(MODE_SETTINGS); return
                if self.btn_quit.contains(pt):
                    self.running = False; return

        if key == ord("1"):
            self.switch_mode(MODE_CUBE)
        elif key == ord("2"):
            self.switch_mode(MODE_DRAW)
        elif key == ord("3"):
            self.switch_mode(MODE_PUZZLE)
        elif key == ord("s"):
            self.switch_mode(MODE_SETTINGS)

        cv2.putText(frame, f"Camera: {self.camera.source_str}  |  FPS: {self.fps.tick():4.1f}  |  Pinch Sensitivity: {self.pinch_threshold:.3f}",
                    (70, WIN_H - 26), FONT_SMALL, 0.50, TEXT_MUTED, 1, cv2.LINE_AA)
        HandTracker.draw_skeleton(frame, hand)
        draw_pointer(frame, ptr, pinching=hand.is_pinching, label="PINCH" if hand.is_pinching else "")

    def _render_settings(self, frame: np.ndarray, hand: HandData, key: int):
        frame[:] = (16, 18, 28)
        glass_panel(frame, 140, 70, WIN_W - 280, WIN_H - 130, alpha=0.92, border_color=ACCENT_CYAN)
        cv2.putText(frame, "Camera & Gesture Settings", (180, 122), FONT, 0.95, TEXT_PRIMARY, 2, cv2.LINE_AA)

        if self.editing_camera and key != -1:
            if key in (8, 127):
                self.camera_input = self.camera_input[:-1]
            elif key == 13:
                ok = self.camera.open(self.camera_input)
                self.toasts.push("Camera connected" if ok else "Camera connection failed")
            elif 32 <= key <= 126 and len(self.camera_input) < 80:
                self.camera_input += chr(key)

        cv2.putText(frame, "Camera Source:", (180, 203), FONT_SMALL, 0.56, TEXT_PRIMARY, 1, cv2.LINE_AA)
        box = self.btn_cam_box
        glass_panel(frame, box.x, box.y, box.w, box.h, alpha=0.95, border_color=ACCENT_GREEN if self.editing_camera else ACCENT_CYAN, bg_color=(10, 12, 20), border_thickness=2)
        cursor_ch = "_" if (self.editing_camera and int(cv2.getTickCount() / cv2.getTickFrequency() * 2) % 2 == 0) else ""
        cv2.putText(frame, (self.camera_input + cursor_ch)[-44:], (box.x + 14, box.y + 29), FONT_SMALL, 0.56, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_cam_apply.draw(frame, hovered=self.btn_cam_apply.contains(self.mouse.pos))
        cv2.putText(frame, "Enter local index (0, 1) OR stream URL (e.g. http://<phone-ip>:<port>/video or rtsp://...)", (370, 244), FONT_SMALL, 0.44, TEXT_MUTED, 1, cv2.LINE_AA)

        self.btn_mirror.label, self.btn_mirror.active = f"Mirror Flip: {'ON' if self.flip else 'OFF'}", self.flip
        self.btn_mirror.draw(frame, hovered=self.btn_mirror.contains(self.mouse.pos))

        cv2.putText(frame, "Pinch Sensitivity:", (180, 366), FONT_SMALL, 0.54, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_sens_dn.draw(frame, hovered=self.btn_sens_dn.contains(self.mouse.pos))
        cv2.putText(frame, f"{self.pinch_threshold:.3f}", (436, 366), FONT_SMALL, 0.56, ACCENT_CYAN, 1, cv2.LINE_AA)
        self.btn_sens_up.draw(frame, hovered=self.btn_sens_up.contains(self.mouse.pos))

        cv2.putText(frame, "Hand Confidence:", (180, 431), FONT_SMALL, 0.54, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_conf_dn.draw(frame, hovered=self.btn_conf_dn.contains(self.mouse.pos))
        cv2.putText(frame, f"{self.confidence:.2f}", (440, 431), FONT_SMALL, 0.56, ACCENT_CYAN, 1, cv2.LINE_AA)
        self.btn_conf_up.draw(frame, hovered=self.btn_conf_up.contains(self.mouse.pos))

        status_msg = f"Connected: {self.camera.source_str}" if self.camera.is_live else self.camera.last_error
        cv2.putText(frame, status_msg[:92], (180, 505), FONT_SMALL, 0.50, ACCENT_GREEN if self.camera.is_live else ACCENT_RED, 1, cv2.LINE_AA)
        self.btn_set_back.draw(frame, hovered=self.btn_set_back.contains(self.mouse.pos))

        ptr, clicked = self._pointer(hand)
        if clicked and ptr:
            if self.btn_cam_box.contains(ptr):
                self.editing_camera = True
            elif self.btn_cam_apply.contains(ptr):
                ok = self.camera.open(self.camera_input)
                self.toasts.push("Camera connected" if ok else "Camera connection failed")
            elif self.btn_mirror.contains(ptr):
                self.flip = not self.flip
            elif self.btn_sens_dn.contains(ptr):
                self.pinch_threshold = round(max(0.030, self.pinch_threshold - 0.005), 3); self.tracker.set_pinch_threshold(self.pinch_threshold)
            elif self.btn_sens_up.contains(ptr):
                self.pinch_threshold = round(min(0.100, self.pinch_threshold + 0.005), 3); self.tracker.set_pinch_threshold(self.pinch_threshold)
            elif self.btn_conf_dn.contains(ptr):
                self.confidence = round(max(0.40, self.confidence - 0.05), 2); self.tracker.set_confidence(self.confidence)
            elif self.btn_conf_up.contains(ptr):
                self.confidence = round(min(0.90, self.confidence + 0.05), 2); self.tracker.set_confidence(self.confidence)
            elif self.btn_set_back.contains(ptr):
                self.switch_mode(self.prev_screen); return

        if key == 27:
            self.switch_mode(self.prev_screen)
        draw_pointer(frame, ptr, pinching=hand.is_pinching)

    def step(self, frame_override: Optional[np.ndarray] = None, key: int = -1) -> np.ndarray:
        if frame_override is not None:
            frame = cv2.resize(frame_override, (WIN_W, WIN_H)) if frame_override.shape[:2] != (WIN_H, WIN_W) else frame_override.copy()
        else:
            ok, cam_frame = self.camera.read_frame(flip=self.flip)
            frame = cam_frame if (ok and cam_frame is not None) else np.full((WIN_H, WIN_W, 3), (18, 20, 30), dtype=np.uint8)

        if not (self.screen == MODE_SETTINGS and self.editing_camera):
            if key == ord("q") or (key == 27 and self.screen == MODE_MENU):
                self.running = False; self.mouse.end_frame(); return frame
            if self.screen in self.modes and key in (ord("m"), 27):
                self.switch_mode(MODE_MENU); self.mouse.end_frame(); return frame

        hand = self.tracker.process(frame) if (self.camera.is_live or frame_override is not None) else HandData()
        if self.screen == MODE_MENU:
            self._render_menu(frame, hand, key)
        elif self.screen == MODE_SETTINGS:
            self._render_settings(frame, hand, key)
        else:
            mode = self.modes[self.screen]
            mode.update_and_render(frame, hand, self.mouse, key)
            self.btn_menu.draw(frame, hovered=self.btn_menu.contains(self.mouse.pos) or self.btn_menu.contains(hand.pinch_center))
            glass_panel(frame, 144, 16, 138, 36, alpha=0.68)
            cv2.putText(frame, mode.name, (156, 40), FONT_SMALL, 0.50, ACCENT_CYAN, 1, cv2.LINE_AA)
            for ptr, clicked in ((self.mouse.pos, self.mouse.just_released), (hand.pinch_center, hand.pinch_started)):
                if clicked and self.btn_menu.contains(ptr):
                    self.switch_mode(MODE_MENU); break

        self.toasts.draw(frame)
        self.mouse.end_frame()
        return frame

    def _on_mouse(self, event, x, y, flags, _param):
        self.mouse.pos = (x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mouse.down = self.mouse.just_pressed = True
        elif event == cv2.EVENT_LBUTTONUP:
            self.mouse.down, self.mouse.just_released = False, True
        elif event == cv2.EVENT_MOUSEWHEEL:
            self.mouse.wheel = 1 if flags > 0 else -1

    def run(self):
        self.start()
        cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WIN_NAME, WIN_W, WIN_H)
        cv2.setMouseCallback(WIN_NAME, self._on_mouse)
        try:
            while self.running:
                raw_k = cv2.waitKey(1) & 0xFF
                cv2.imshow(WIN_NAME, self.step(key=-1 if raw_k == 255 else raw_k))
                if cv2.getWindowProperty(WIN_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
        finally:
            self.shutdown()

    def shutdown(self):
        self.tracker.close()
        self.camera.release()
        if not self.headless:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Combined Camera Studio")
    parser.add_argument("--camera", default="0", help="Camera index (e.g. 0) or stream URL / video path")
    parser.add_argument("--no-flip", action="store_true", help="Disable horizontal mirror flip")
    args = parser.parse_args()
    StudioApp(camera_source=args.camera, flip=not args.no_flip).run()


if __name__ == "__main__":
    main()
