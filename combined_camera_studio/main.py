"""Combined Camera Studio -- Single-window, single-camera interactive desktop app."""

import argparse
from dataclasses import dataclass
import textwrap
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from modes import AirDrawingMode, LiquidCubeMode, SelfiePuzzleMode
from ui_helpers import (
    ACCENT_CYAN, ACCENT_GREEN, ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED, Button, FONT, FONT_SMALL,
    FPSCounter, FingertipFX, TEXT_MUTED, TEXT_PRIMARY, ToastQueue, draw_ar_hand_hud, draw_pointer, glass_panel,
)
from vision import (
    CALIBRATION_PATH, CALIBRATION_PRESETS, CameraSource, DEFAULT_CALIBRATION, HandData,
    HandTracker, WIN_H, WIN_W, clamp_calibration, load_calibration, save_calibration,
)

WIN_NAME = "Combined Camera Studio"
MODE_MENU, MODE_SETTINGS, MODE_CALIBRATE = "MENU", "SETTINGS", "CALIBRATE"
MODE_CUBE, MODE_DRAW, MODE_PUZZLE = "LIQUID_CUBE", "AIR_DRAWING", "SELFIE_PUZZLE"
_MENU_BG = np.full((WIN_H, WIN_W, 3), (14, 16, 26), dtype=np.uint8)


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


class StudioApp:
    """Coordinates shared camera, hand tracking, calibration, gestures, AR HUD, and 3 modes."""

    def __init__(self, camera_source: str = "0", flip: bool = True, headless: bool = False, calibration_path: str = CALIBRATION_PATH):
        self.calibration_path = calibration_path
        self.cfg: Dict[str, Any] = load_calibration(self.calibration_path)
        self.camera = CameraSource(camera_source, WIN_W, WIN_H)
        self.tracker = HandTracker(cfg=self.cfg)
        self.fps, self.fx = FPSCounter(), FingertipFX(enabled=self.cfg["fx_enabled"])
        self.ar_hud_enabled = self.cfg["ar_hud_enabled"]
        self.toasts, self.mouse = ToastQueue(), MouseState()
        self.flip, self.headless = flip, headless
        self.screen = self.prev_screen = MODE_MENU
        self.running, self.help_open, self.last_app_fps = True, False, 0.0
        self.modes = {MODE_CUBE: LiquidCubeMode(), MODE_DRAW: AirDrawingMode(), MODE_PUZZLE: SelfiePuzzleMode()}
        self.camera_input, self.editing_camera = str(camera_source), False

        self.cards = [
            (MODE_CUBE, Button(70, 210, 350, 340, ""), "Liquid Cube",
             "3D fluid physics inside a cube. Open hand spins, fist freezes, pinch resizes.", "Hand: Open / Fist / Pinch", ACCENT_CYAN),
            (MODE_DRAW, Button(465, 210, 350, 340, ""), "Air Drawing",
             "Draw glowing neon strokes in mid-air with particles, eraser, undo, and PNG save.", "Hand: Index = Draw | Fist = Stop", ACCENT_GREEN),
            (MODE_PUZZLE, Button(860, 210, 350, 340, ""), "Selfie Puzzle",
             "Pinch-drag a live selfie region, shuffle into 9 tiles, and solve by hand or mouse.", "Hand: Pinch & Drag", ACCENT_ORANGE),
        ]
        self.btn_cal = Button(WIN_W - 445, 42, 138, 38, "Calibrate [K]")
        self.btn_settings = Button(WIN_W - 297, 42, 127, 38, "Settings [S]")
        self.btn_quit = Button(WIN_W - 160, 42, 105, 38, "Quit [Q]")
        self.btn_ar = Button(WIN_W - 395, WIN_H - 46, 120, 32, "")
        self.btn_fx = Button(WIN_W - 265, WIN_H - 46, 115, 32, "")
        self.btn_help = Button(WIN_W - 140, WIN_H - 46, 100, 32, "Help [H]")
        self.btn_menu = Button(16, 16, 108, 36, "Menu [M]")

        self.btn_cam_box, self.btn_cam_apply = Button(370, 170, 510, 44, ""), Button(895, 170, 165, 44, "Apply Camera")
        self.btn_mirror = Button(370, 265, 200, 40, "")
        self.btn_conf_dn, self.btn_conf_up = Button(370, 330, 48, 40, "-"), Button(530, 330, 48, 40, "+")
        self.btn_set_cal, self.btn_set_back = Button(370, 540, 180, 44, "Calibrate [K]"), Button(570, 540, 180, 44, "Back [Esc]")

        self.cal_presets = {k: Button(756 + i * 102, 118, 94, 34, k) for i, k in enumerate(["Low", "Balanced", "High"])}
        self.btn_cal_reset = Button(1062, 118, 162, 34, "Reset Default")
        self.cal_rows = [
            ("sensitivity", "Pointer Sens", 0.10, Button(960, 176, 44, 30, "-"), Button(1110, 176, 44, 30, "+")),
            ("usable_area", "Usable Area", 0.05, Button(960, 218, 44, 30, "-"), Button(1110, 218, 44, 30, "+")),
            ("pinch_threshold", "Pinch Thresh", 0.005, Button(960, 260, 44, 30, "-"), Button(1110, 260, 44, 30, "+")),
            ("stability_frames", "Stability", 1, Button(960, 302, 44, 30, "-"), Button(1110, 302, 44, 30, "+")),
            ("smoothing", "Smoothing", 0.05, Button(960, 344, 44, 30, "-"), Button(1110, 344, 44, 30, "+")),
        ]
        self.btn_cal_fx, self.btn_cal_ar = Button(756, 408, 224, 34, ""), Button(996, 408, 228, 34, "")
        self.btn_cal_pause, self.btn_cal_thumbs = Button(756, 452, 224, 34, ""), Button(996, 452, 228, 34, "")
        self.btn_cal_peace, self.btn_cal_save = Button(756, 496, 224, 34, ""), Button(890, 588, 210, 42, "Save & Back [Esc]")

    def start(self): self.camera.open(self.camera_input)

    def _apply_cfg(self, persist: bool = True):
        self.cfg = clamp_calibration(self.cfg)
        self.tracker.apply_calibration(self.cfg)
        self.fx.set_enabled(self.cfg["fx_enabled"])
        self.ar_hud_enabled = self.cfg["ar_hud_enabled"]
        if persist:
            save_calibration(self.cfg, self.calibration_path)

    def apply_preset(self, name: str):
        if name in CALIBRATION_PRESETS:
            self.cfg.update(CALIBRATION_PRESETS[name]); self.cfg["preset"] = name; self._apply_cfg(True)

    def reset_calibration(self):
        self.cfg = dict(DEFAULT_CALIBRATION); self._apply_cfg(True)

    def switch_mode(self, target: str):
        if target in self.modes and target != self.screen:
            self.modes[target].reset()
        if target in (MODE_SETTINGS, MODE_CALIBRATE) and self.screen not in (MODE_SETTINGS, MODE_CALIBRATE):
            self.prev_screen = self.screen
        self.editing_camera, self.help_open, self.screen = target == MODE_SETTINGS, False, target
        self.tracker.debouncer.reset(); self.tracker.gesture_debouncer.reset()

    def _pointer(self, hand: HandData) -> Tuple[Optional[Tuple[int, int]], bool]:
        return ((hand.pinch_center if hand.is_pinching else hand.index_tip), hand.pinch_started) if hand.detected else (self.mouse.pos, self.mouse.just_released)

    def _handle_custom_gesture(self, hand: HandData):
        act = hand.action_gesture
        if not act:
            return
        if act == "PEACE" and self.cfg["gesture_peace"]:
            if self.screen != MODE_MENU:
                self.switch_mode(MODE_MENU)
            self.toasts.push("Peace sign: Main Menu")
        elif act == "THUMBS_UP" and self.cfg["gesture_thumbs"]:
            self.toasts.push(self.cfg["thumbs_phrase"])
        elif act == "OPEN_PALM" and self.cfg["gesture_pause"]:
            if self.screen in (MODE_DRAW, MODE_PUZZLE):
                self.toasts.push("Paused (Open Palm)" if self.modes[self.screen].toggle_pause() else "Resumed")
            elif self.screen == MODE_CUBE:
                self.toasts.push("Liquid Cube: Open hand rotates, Fist freezes")
            else:
                self.toasts.push("Open Palm: Pause/Resume active in modes")

    def _draw_overlays(self, frame: np.ndarray, hand: HandData):
        if self.ar_hud_enabled:
            draw_ar_hand_hud(frame, hand)
        self.fx.update_and_draw(frame, hand.index_tip, hand.is_pinching, bool(hand.pinch_started or hand.action_gesture))

    def _draw_help_overlay(self, frame: np.ndarray):
        if not self.help_open:
            return
        glass_panel(frame, WIN_W // 2 - 285, WIN_H // 2 - 175, 570, 355, alpha=0.90, border_color=ACCENT_CYAN)
        cv2.putText(frame, "Gestures & Shortcuts Guide", (WIN_W // 2 - 255, WIN_H // 2 - 135), FONT, 0.72, ACCENT_CYAN, 1, cv2.LINE_AA)
        for idx, (k, d) in enumerate([
            ("Pinch (Thumb+Index)", "Select menu cards, buttons & drag tiles"),
            ("Peace Sign", "Return to Main Menu (when enabled)"),
            ("Thumbs-Up", "Show confirmation toast (when enabled)"),
            ("Open Palm", "Pause/Resume in Air Drawing & Selfie Puzzle"),
            ("Liquid Cube Note", "Open hand rotates cube; Closed Fist freezes"),
            ("Keys: K / S / A / V / H", "Calibrate / Settings / AR HUD / FX / Help"),
            ("Keys: 1-3 / M / Esc", "Open Mode / Back to Menu / Quit on Menu"),
        ]):
            ry = WIN_H // 2 - 90 + idx * 35
            cv2.putText(frame, k, (WIN_W // 2 - 255, ry), FONT_SMALL, 0.45, TEXT_PRIMARY, 1, cv2.LINE_AA)
            cv2.putText(frame, d, (WIN_W // 2 - 35, ry), FONT_SMALL, 0.43, TEXT_MUTED, 1, cv2.LINE_AA)

    def _render_menu(self, frame: np.ndarray, hand: HandData, key: int):
        cv2.addWeighted(frame, 0.35, _MENU_BG, 0.65, 0, dst=frame)
        glass_panel(frame, 40, 22, WIN_W - 80, 120, alpha=0.72, border_color=ACCENT_CYAN)
        cv2.putText(frame, "Combined Camera Studio", (70, 72), FONT, 1.12, TEXT_PRIMARY, 2, cv2.LINE_AA)
        cv2.putText(frame, "Point with index finger and PINCH a card (or mouse / keys 1-3)", (72, 110), FONT_SMALL, 0.54, TEXT_MUTED, 1, cv2.LINE_AA)

        ptr, clicked = self._pointer(hand)
        for b, acc in ((self.btn_cal, ACCENT_PURPLE), (self.btn_settings, ACCENT_CYAN), (self.btn_quit, ACCENT_RED)):
            b.draw(frame, hovered=b.contains(ptr) or b.contains(self.mouse.pos), accent=acc)
        if not self.camera.is_live:
            glass_panel(frame, 70, 152, WIN_W - 140, 44, alpha=0.85, border_color=ACCENT_RED)
            cv2.putText(frame, f"Camera Error: {self.camera.last_error[:112]}", (88, 180), FONT_SMALL, 0.48, (140, 150, 255), 1, cv2.LINE_AA)

        for idx, (mode_id, box, title, desc, hint, accent) in enumerate(self.cards):
            hov = box.contains(ptr) or box.contains(self.mouse.pos)
            glass_panel(frame, box.x, box.y, box.w, box.h, 0.84, accent if hov else (75, 85, 115), (32, 38, 58) if hov else (20, 24, 38), 3 if hov else 1)
            cv2.putText(frame, f"[{idx + 1}]", (box.x + 24, box.y + 42), FONT_SMALL, 0.58, accent, 1, cv2.LINE_AA)
            cv2.putText(frame, title, (box.x + 24, box.y + 88), FONT, 0.95, TEXT_PRIMARY, 2, cv2.LINE_AA)
            cv2.line(frame, (box.x + 24, box.y + 108), (box.x + box.w - 24, box.y + 108), accent, 1)
            for li, line in enumerate(textwrap.wrap(desc, width=31)):
                cv2.putText(frame, line, (box.x + 24, box.y + 148 + li * 28), FONT_SMALL, 0.52, TEXT_MUTED, 1, cv2.LINE_AA)
            glass_panel(frame, box.x + 20, box.y + box.h - 72, box.w - 40, 46, alpha=0.75, border_color=accent)
            cv2.putText(frame, hint, (box.x + 34, box.y + box.h - 43), FONT_SMALL, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)
            if clicked and box.contains(ptr):
                self.switch_mode(mode_id); return

        self.btn_ar.label, self.btn_ar.active = f"AR [A]: {'ON' if self.ar_hud_enabled else 'OFF'}", self.ar_hud_enabled
        self.btn_fx.label, self.btn_fx.active = f"FX [V]: {'ON' if self.fx.enabled else 'OFF'}", self.fx.enabled
        self.btn_help.active = self.help_open
        for b, acc in ((self.btn_ar, ACCENT_CYAN), (self.btn_fx, ACCENT_PURPLE), (self.btn_help, ACCENT_CYAN)):
            b.draw(frame, hovered=b.contains(ptr) or b.contains(self.mouse.pos), accent=acc)

        for pt, trig in ((self.mouse.pos, self.mouse.just_released), (hand.pinch_center, hand.pinch_started)):
            if trig and pt:
                if self.btn_cal.contains(pt): self.switch_mode(MODE_CALIBRATE); return
                if self.btn_settings.contains(pt): self.switch_mode(MODE_SETTINGS); return
                if self.btn_quit.contains(pt): self.running = False; return
                if self.btn_ar.contains(pt): self.cfg["ar_hud_enabled"] = not self.cfg["ar_hud_enabled"]; self._apply_cfg(True)
                elif self.btn_fx.contains(pt): self.cfg["fx_enabled"] = not self.cfg["fx_enabled"]; self._apply_cfg(True)
                elif self.btn_help.contains(pt): self.help_open = not self.help_open

        if key in (ord("1"), ord("2"), ord("3")): self.switch_mode((MODE_CUBE, MODE_DRAW, MODE_PUZZLE)[key - ord("1")])
        elif key == ord("s"): self.switch_mode(MODE_SETTINGS)
        elif key == ord("k"): self.switch_mode(MODE_CALIBRATE)

        tw, th = self.tracker.track_size
        status = (f"App FPS:{self.last_app_fps:4.1f} | Track({tw}x{th}):{self.tracker.avg_track_ms:4.1f}ms | "
                  f"Cam:{self.camera.stream_fps:4.1f}fps | Cal:{self.cfg['preset']} | Src:{self.camera.source_str[:18]}")
        cv2.putText(frame, status, (52, WIN_H - 24), FONT_SMALL, 0.44, TEXT_MUTED, 1, cv2.LINE_AA)
        HandTracker.draw_skeleton(frame, hand)
        self._draw_overlays(frame, hand)
        draw_pointer(frame, ptr, pinching=hand.is_pinching, label=hand.pose if hand.pose != "NONE" else ("PINCH" if hand.is_pinching else ""))

    def _render_calibration(self, frame: np.ndarray, hand: HandData, key: int):
        cam_view = frame.copy()
        frame[:] = (15, 17, 26)
        glass_panel(frame, 28, 20, WIN_W - 56, WIN_H - 40, alpha=0.92, border_color=ACCENT_PURPLE)
        cv2.putText(frame, "Hand & Gesture Calibration", (52, 60), FONT, 0.88, TEXT_PRIMARY, 2, cv2.LINE_AA)
        cv2.putText(frame, f"App FPS: {self.last_app_fps:4.1f}  |  Track: {self.tracker.avg_track_ms:4.1f} ms  |  Preset: {self.cfg['preset']}",
                    (480, 58), FONT_SMALL, 0.48, ACCENT_CYAN, 1, cv2.LINE_AA)

        px, py, pw, ph = 52, 82, 672, 378
        HandTracker.draw_skeleton(cam_view, hand)
        if self.ar_hud_enabled:
            draw_ar_hand_hud(cam_view, hand)
        small_cam = cv2.resize(cam_view, (pw, ph))
        u = self.cfg["usable_area"]
        mx, my = int(pw * (1.0 - u) * 0.5), int(ph * (1.0 - u) * 0.5)
        cv2.rectangle(small_cam, (mx, my), (pw - mx - 1, ph - my - 1), ACCENT_GREEN, 2, cv2.LINE_AA)
        cv2.putText(small_cam, f"Usable Camera Area ({int(u*100)}%)", (mx + 8, max(20, my + 22)), FONT_SMALL, 0.46, ACCENT_GREEN, 1, cv2.LINE_AA)
        if hand.detected and hand.index_tip is not None:
            cv2.circle(small_cam, (int(hand.index_tip[0] * pw / WIN_W), int(hand.index_tip[1] * ph / WIN_H)), 8, ACCENT_CYAN, -1, cv2.LINE_AA)
        frame[py:py + ph, px:px + pw] = small_cam
        cv2.rectangle(frame, (px, py), (px + pw, py + ph), ACCENT_CYAN if hand.detected else ACCENT_ORANGE, 2)

        glass_panel(frame, px, 474, pw, 156, alpha=0.75, border_color=(70, 82, 110))
        cv2.putText(frame, f"Pinch Meter: {hand.pinch_dist_norm:.3f}  (Threshold < {self.cfg['pinch_threshold']:.3f})   |   Pose: {hand.pose}",
                    (px + 16, 504), FONT_SMALL, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)
        bx, bw = px + 16, pw - 32
        cv2.rectangle(frame, (bx, 520), (bx + bw, 540), (38, 42, 60), -1)
        cv2.rectangle(frame, (bx, 520), (bx + (int(bw * min(1.0, hand.pinch_dist_norm / 0.14)) if hand.detected else 0), 540), ACCENT_GREEN if hand.is_pinching else ACCENT_CYAN, -1)
        th_x = bx + int(bw * min(1.0, self.cfg["pinch_threshold"] / 0.14))
        cv2.line(frame, (th_x, 514), (th_x, 546), ACCENT_RED, 2)
        msg1 = "Hand detected! Test pointer range & pinch inside green box." if hand.detected else "No hand detected: hold 1 hand palm-forward 40-80 cm from camera."
        msg2 = "Smoothing: lower = snappier, higher = steadier with slight delay." if hand.detected else "Check bright front lighting or Mirror Flip in Settings."
        cv2.putText(frame, msg1, (px + 16, 578), FONT_SMALL, 0.46, ACCENT_GREEN if hand.detected else ACCENT_ORANGE, 1, cv2.LINE_AA)
        cv2.putText(frame, msg2, (px + 16, 606), FONT_SMALL, 0.44, TEXT_MUTED, 1, cv2.LINE_AA)

        ptr, clicked = self._pointer(hand)
        cv2.putText(frame, "Sensitivity Presets:", (756, 102), FONT_SMALL, 0.50, TEXT_PRIMARY, 1, cv2.LINE_AA)
        for name, btn in self.cal_presets.items():
            btn.active = self.cfg["preset"] == name
            btn.draw(frame, hovered=btn.contains(ptr) or btn.contains(self.mouse.pos), accent=ACCENT_PURPLE)
            if clicked and btn.contains(ptr):
                self.apply_preset(name); self.toasts.push(f"Preset: {name}")
        self.btn_cal_reset.draw(frame, hovered=self.btn_cal_reset.contains(ptr) or self.btn_cal_reset.contains(self.mouse.pos), accent=ACCENT_ORANGE)
        if clicked and self.btn_cal_reset.contains(ptr):
            self.reset_calibration(); self.toasts.push("Calibration reset")

        for field_k, label, step, b_dn, b_up in self.cal_rows:
            cy, val = b_dn.y + 21, self.cfg[field_k]
            txt = f"{val:.3f}" if field_k == "pinch_threshold" else (f"{val}f" if field_k == "stability_frames" else f"{val:.2f}")
            cv2.putText(frame, f"{label}:", (756, cy), FONT_SMALL, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)
            cv2.putText(frame, txt, (1026, cy), FONT_SMALL, 0.50, ACCENT_CYAN, 1, cv2.LINE_AA)
            b_dn.draw(frame, hovered=b_dn.contains(ptr) or b_dn.contains(self.mouse.pos))
            b_up.draw(frame, hovered=b_up.contains(ptr) or b_up.contains(self.mouse.pos))
            if clicked and (b_dn.contains(ptr) or b_up.contains(ptr)):
                self.cfg[field_k] = val - step if b_dn.contains(ptr) else val + step
                self.cfg["preset"] = "Custom"; self._apply_cfg(True)

        cv2.putText(frame, "One-Euro Smoothing: higher = less jitter, slight delay", (756, 392), FONT_SMALL, 0.42, TEXT_MUTED, 1, cv2.LINE_AA)
        for btn, key_name, lbl in (
            (self.btn_cal_fx, "fx_enabled", "Fingertip FX"), (self.btn_cal_ar, "ar_hud_enabled", "AR Hand HUD"),
            (self.btn_cal_pause, "gesture_pause", "Open Palm Pause"), (self.btn_cal_thumbs, "gesture_thumbs", "Thumbs-Up Msg"),
            (self.btn_cal_peace, "gesture_peace", "Peace -> Menu"),
        ):
            btn.label, btn.active = f"{lbl}: {'ON' if self.cfg[key_name] else 'OFF'}", self.cfg[key_name]
            btn.draw(frame, hovered=btn.contains(ptr) or btn.contains(self.mouse.pos), accent=ACCENT_GREEN)
            if clicked and btn.contains(ptr):
                self.cfg[key_name] = not self.cfg[key_name]; self._apply_cfg(True)

        self.btn_cal_save.draw(frame, hovered=self.btn_cal_save.contains(ptr) or self.btn_cal_save.contains(self.mouse.pos), accent=ACCENT_CYAN)
        if (clicked and self.btn_cal_save.contains(ptr)) or key == 27:
            self._apply_cfg(True); self.toasts.push("Calibration saved"); self.switch_mode(self.prev_screen); return
        self.fx.update_and_draw(frame, hand.index_tip, hand.is_pinching, bool(hand.pinch_started))
        draw_pointer(frame, ptr, pinching=hand.is_pinching)

    def _render_settings(self, frame: np.ndarray, hand: HandData, key: int):
        frame[:] = (16, 18, 28)
        glass_panel(frame, 140, 70, WIN_W - 280, WIN_H - 130, alpha=0.92, border_color=ACCENT_CYAN)
        cv2.putText(frame, "Camera & Tracking Settings", (180, 122), FONT, 0.95, TEXT_PRIMARY, 2, cv2.LINE_AA)

        if self.editing_camera and key != -1:
            if key in (8, 127):
                self.camera_input = self.camera_input[:-1]
            elif key == 13:
                self.toasts.push("Camera connected" if self.camera.open(self.camera_input) else "Camera connection failed")
            elif 32 <= key <= 126 and len(self.camera_input) < 80:
                self.camera_input += chr(key)

        cv2.putText(frame, "Camera Source:", (180, 198), FONT_SMALL, 0.54, TEXT_PRIMARY, 1, cv2.LINE_AA)
        box = self.btn_cam_box
        glass_panel(frame, box.x, box.y, box.w, box.h, 0.95, ACCENT_GREEN if self.editing_camera else ACCENT_CYAN, (10, 12, 20), 2)
        cursor_ch = "_" if (self.editing_camera and int(cv2.getTickCount() / cv2.getTickFrequency() * 2) % 2 == 0) else ""
        cv2.putText(frame, (self.camera_input + cursor_ch)[-44:], (box.x + 14, box.y + 29), FONT_SMALL, 0.56, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_cam_apply.draw(frame, hovered=self.btn_cam_apply.contains(self.mouse.pos))
        cv2.putText(frame, "Enter index (0, 1) OR stream URL (e.g. http://<phone-ip>:<port>/video or rtsp://...)", (370, 238), FONT_SMALL, 0.44, TEXT_MUTED, 1, cv2.LINE_AA)

        self.btn_mirror.label, self.btn_mirror.active = f"Mirror Flip: {'ON' if self.flip else 'OFF'}", self.flip
        self.btn_mirror.draw(frame, hovered=self.btn_mirror.contains(self.mouse.pos))
        cv2.putText(frame, "Hand Confidence:", (180, 356), FONT_SMALL, 0.54, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_conf_dn.draw(frame, hovered=self.btn_conf_dn.contains(self.mouse.pos))
        cv2.putText(frame, f"{self.cfg['confidence']:.2f}", (440, 356), FONT_SMALL, 0.56, ACCENT_CYAN, 1, cv2.LINE_AA)
        self.btn_conf_up.draw(frame, hovered=self.btn_conf_up.contains(self.mouse.pos))

        cv2.putText(frame, f"Backend Info: {self.camera.buffer_prop_note}", (180, 424), FONT_SMALL, 0.46, TEXT_MUTED, 1, cv2.LINE_AA)
        status_msg = f"Connected: {self.camera.source_str}  (Stream Rate: {self.camera.stream_fps:.1f} FPS)" if self.camera.is_live else self.camera.last_error
        cv2.putText(frame, status_msg[:92], (180, 474), FONT_SMALL, 0.50, ACCENT_GREEN if self.camera.is_live else ACCENT_RED, 1, cv2.LINE_AA)
        self.btn_set_cal.draw(frame, hovered=self.btn_set_cal.contains(self.mouse.pos), accent=ACCENT_PURPLE)
        self.btn_set_back.draw(frame, hovered=self.btn_set_back.contains(self.mouse.pos))

        ptr, clicked = self._pointer(hand)
        if clicked and ptr:
            if self.btn_cam_box.contains(ptr): self.editing_camera = True
            elif self.btn_cam_apply.contains(ptr): self.toasts.push("Camera connected" if self.camera.open(self.camera_input) else "Camera connection failed")
            elif self.btn_mirror.contains(ptr): self.flip = not self.flip
            elif self.btn_conf_dn.contains(ptr) or self.btn_conf_up.contains(ptr):
                self.cfg["confidence"] += -0.05 if self.btn_conf_dn.contains(ptr) else 0.05; self._apply_cfg(True)
            elif self.btn_set_cal.contains(ptr): self.switch_mode(MODE_CALIBRATE); return
            elif self.btn_set_back.contains(ptr): self.switch_mode(self.prev_screen); return
        if key == 27: self.switch_mode(self.prev_screen)
        draw_pointer(frame, ptr, pinching=hand.is_pinching)

    def step(self, frame_override: Optional[np.ndarray] = None, key: int = -1) -> np.ndarray:
        self.last_app_fps = self.fps.tick()
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
            if key == ord("v"):
                self.cfg["fx_enabled"] = not self.cfg["fx_enabled"]; self._apply_cfg(True)
                self.toasts.push(f"Fingertip FX {'ON' if self.cfg['fx_enabled'] else 'OFF'}")
            elif key == ord("a"):
                self.cfg["ar_hud_enabled"] = not self.cfg["ar_hud_enabled"]; self._apply_cfg(True)
                self.toasts.push(f"AR Hand HUD {'ON' if self.cfg['ar_hud_enabled'] else 'OFF'}")
            elif key == ord("h") and self.screen != MODE_DRAW:
                self.help_open = not self.help_open

        hand = self.tracker.process(frame) if (self.camera.is_live or frame_override is not None) else HandData()
        if self.screen not in (MODE_SETTINGS, MODE_CALIBRATE):
            self._handle_custom_gesture(hand)

        if self.screen == MODE_MENU:
            self._render_menu(frame, hand, key)
        elif self.screen == MODE_SETTINGS:
            self._render_settings(frame, hand, key)
        elif self.screen == MODE_CALIBRATE:
            self._render_calibration(frame, hand, key)
        else:
            mode = self.modes[self.screen]
            mode.update_and_render(frame, hand, self.mouse, key)
            self._draw_overlays(frame, hand)
            self.btn_menu.draw(frame, hovered=self.btn_menu.contains(self.mouse.pos) or self.btn_menu.contains(hand.pinch_center))
            glass_panel(frame, 130, 16, 140, 36, alpha=0.68)
            cv2.putText(frame, mode.name, (140, 40), FONT_SMALL, 0.48, ACCENT_CYAN, 1, cv2.LINE_AA)
            glass_panel(frame, 276, 16, 236, 36, alpha=0.68, border_color=(75, 95, 130))
            cv2.putText(frame, f"FPS:{self.last_app_fps:4.1f} | Trk:{self.tracker.avg_track_ms:4.1f}ms", (288, 40), FONT_SMALL, 0.45, TEXT_PRIMARY, 1, cv2.LINE_AA)
            for ptr, clicked in ((self.mouse.pos, self.mouse.just_released), (hand.pinch_center, hand.pinch_started)):
                if clicked and self.btn_menu.contains(ptr):
                    self.switch_mode(MODE_MENU); break

        self._draw_help_overlay(frame)
        self.toasts.draw(frame, start_y=152 if self.screen == MODE_MENU else (646 if self.screen in (MODE_CALIBRATE, MODE_SETTINGS) else 72))
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
