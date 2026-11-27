"""Focused tests for Combined Camera Studio: debouncing, calibration, gestures, FX, modes, and shutdown."""

import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO_ROOT not in sys.path:
    sys.path.insert(0, STUDIO_ROOT)

from main import MODE_CALIBRATE, MODE_CUBE, MODE_DRAW, MODE_MENU, MODE_PUZZLE, MODE_SETTINGS, StudioApp
import modes.air_drawing as air_mod
from modes.liquid_cube import BOUND, LiquidSimulation
from modes.selfie_puzzle import BOARD_X, BOARD_Y, PIECE_PX, Puzzle, TILE_GAP
from ui_helpers import FingertipFX, draw_ar_hand_hud
from vision import (
    CameraSource, GestureDebouncer, HandData, HandTracker, PinchDebouncer, WIN_H, WIN_W,
    _OneEuro2D, classify_hand_pose, load_calibration, parse_camera_source, save_calibration,
)


def _make_test_video(path: str, frames: int = 12):
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 15.0, (640, 480))
    for i in range(frames):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(img, (40 + i * 15, 80), (220 + i * 15, 300), (40, 180, 240), -1)
        cv2.circle(img, (450, 240), 60, (200, 90, 255), -1)
        writer.write(img)
    writer.release()


def _synthetic_pose_pts(pose: str):
    """Build 21 synthetic (x, y) landmarks representing PEACE, THUMBS_UP, or OPEN_PALM."""
    pts = [(400, 500)] * 21
    pts[1], pts[2], pts[3], pts[4] = (360, 470), (340, 440), (325, 420), (315, 405)
    pts[5], pts[6], pts[7], pts[8] = (370, 390), (370, 355), (370, 385), (370, 420)
    pts[9], pts[10], pts[11], pts[12] = (400, 385), (400, 350), (400, 380), (400, 415)
    pts[13], pts[14], pts[15], pts[16] = (430, 390), (430, 355), (430, 385), (430, 420)
    pts[17], pts[18], pts[19], pts[20] = (460, 400), (460, 365), (460, 390), (460, 425)
    if pose == "THUMBS_UP":
        pts[2], pts[3], pts[4] = (350, 410), (350, 360), (350, 310)
    elif pose == "PEACE":
        pts[6], pts[7], pts[8] = (365, 340), (360, 290), (355, 250)
        pts[10], pts[11], pts[12] = (410, 340), (420, 290), (430, 250)
    elif pose == "OPEN_PALM":
        pts[2], pts[3], pts[4] = (330, 440), (300, 400), (280, 365)
        for mcp, pip, dip, tip, x in ((5, 6, 7, 8, 365), (9, 10, 11, 12, 400), (13, 14, 15, 16, 435), (17, 18, 19, 20, 470)):
            pts[pip], pts[dip], pts[tip] = (x, 330), (x, 285), (x, 245)
    return pts


class TestStudioCore(unittest.TestCase):
    def test_parse_camera_source(self):
        self.assertEqual(parse_camera_source("0"), 0)
        self.assertEqual(parse_camera_source(" 2 "), 2)
        self.assertEqual(parse_camera_source(""), 0)
        self.assertEqual(parse_camera_source("http://192.168.1.50:8080/video"), "http://192.168.1.50:8080/video")
        self.assertEqual(parse_camera_source("rtsp://user:pass@host/stream"), "rtsp://user:pass@host/stream")

    def test_pinch_debouncer_rising_edge_and_cooldown(self):
        deb = PinchDebouncer(cooldown_frames=3, stability_frames=1)
        self.assertTrue(deb.update(True))
        self.assertFalse(deb.update(True))
        self.assertFalse(deb.update(False))
        self.assertFalse(deb.update(True))
        self.assertFalse(deb.update(False))
        self.assertTrue(deb.update(True))

    def test_custom_gestures_and_cooldown(self):
        self.assertEqual(classify_hand_pose(_synthetic_pose_pts("PEACE"), 110.0, False), "PEACE")
        self.assertEqual(classify_hand_pose(_synthetic_pose_pts("THUMBS_UP"), 110.0, False), "THUMBS_UP")
        self.assertEqual(classify_hand_pose(_synthetic_pose_pts("OPEN_PALM"), 110.0, False), "OPEN_PALM")

        gd = GestureDebouncer(hold_frames=3, cooldown_sec=1.5)
        self.assertIsNone(gd.update("THUMBS_UP", now=1.0))
        self.assertIsNone(gd.update("THUMBS_UP", now=1.05))
        self.assertEqual(gd.update("THUMBS_UP", now=1.10), "THUMBS_UP")
        # Holding same pose triggers only once
        self.assertIsNone(gd.update("THUMBS_UP", now=1.15))
        # Releasing and retrying inside 1.5s cooldown stays blocked
        self.assertIsNone(gd.update("NONE", now=1.20))
        for dt in (1.30, 1.35, 1.40):
            self.assertIsNone(gd.update("THUMBS_UP", now=dt))
        # After cooldown elapses, fires once again
        self.assertIsNone(gd.update("NONE", now=2.70))
        self.assertIsNone(gd.update("THUMBS_UP", now=2.75))
        self.assertIsNone(gd.update("THUMBS_UP", now=2.80))
        self.assertEqual(gd.update("THUMBS_UP", now=2.85), "THUMBS_UP")

    def test_calibration_save_reload_presets_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path = os.path.join(tmp, "cal.json")
            vid_path = os.path.join(tmp, "v.avi")
            _make_test_video(vid_path, frames=4)

            app = StudioApp(camera_source=vid_path, headless=True, calibration_path=cfg_path)
            app.apply_preset("High")
            self.assertEqual(app.cfg["preset"], "High")
            self.assertAlmostEqual(app.tracker.usable_area, 0.72)
            app.shutdown()

            reloaded = load_calibration(cfg_path)
            self.assertEqual(reloaded["preset"], "High")
            self.assertAlmostEqual(reloaded["smoothing"], 0.22)

            app2 = StudioApp(camera_source=vid_path, headless=True, calibration_path=cfg_path)
            self.assertEqual(app2.cfg["preset"], "High")
            app2.reset_calibration()
            self.assertEqual(app2.cfg["preset"], "Balanced")
            self.assertAlmostEqual(app2.tracker.smoothing, 0.45)
            save_calibration(app2.cfg, cfg_path)
            self.assertEqual(load_calibration(cfg_path)["preset"], "Balanced")
            app2.shutdown()

    def test_fingertip_fx_toggle(self):
        fx = FingertipFX(enabled=True)
        canvas = np.zeros((200, 200, 3), dtype=np.uint8)
        fx.update_and_draw(canvas, (100, 100), pinching=True, action_pulse=True)
        self.assertGreater(len(fx.particles), 0)
        self.assertGreater(len(fx.ripples), 0)
        self.assertGreater(int(canvas.sum()), 0)

        fx.set_enabled(False)
        self.assertEqual(len(fx.particles), 0)
        self.assertEqual(len(fx.ripples), 0)
        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        fx.update_and_draw(blank, (110, 110), pinching=True, action_pulse=True)
        self.assertEqual(int(blank.sum()), 0)

    def test_one_euro_ar_hud_and_idempotent_close(self):
        euro = _OneEuro2D()
        self.assertEqual(euro.filter((100, 100), 0.50, now=1.00), (100, 100))
        jx, _ = euro.filter((120, 100), 0.70, now=1.033)
        self.assertGreater(jx, 100)
        self.assertLess(jx, 120)
        self.assertEqual(euro.filter((140, 100), 0.0, now=1.066), (140, 100))

        hud_canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        pts = _synthetic_pose_pts("OPEN_PALM")
        draw_ar_hand_hud(hud_canvas, HandData(detected=True, landmarks_px=pts, is_open_hand=True, pose="OPEN_PALM", pinch_dist_norm=0.08))
        self.assertGreater(int(hud_canvas.sum()), 0)

        tracker = HandTracker()
        tracker.close()
        tracker.close()  # Idempotent close must not raise ValueError

    def test_camera_error_and_video_file_lifecycle(self):
        cam = CameraSource("99")
        self.assertFalse(cam.open())
        self.assertFalse(cam.is_live)
        self.assertIn("Could not open camera", cam.last_error)

        with tempfile.TemporaryDirectory() as tmp:
            vid_path = os.path.join(tmp, "sample.avi")
            _make_test_video(vid_path, frames=6)
            cam = CameraSource(vid_path)
            self.assertTrue(cam.open())
            self.assertTrue(cam.is_live)
            for _ in range(10):
                ok, frame = cam.read_frame(flip=True)
                self.assertTrue(ok)
                self.assertEqual(frame.shape, (WIN_H, WIN_W, 3))
            cam.release()
            self.assertFalse(cam.is_live)

    def test_liquid_simulation_stability(self):
        sim = LiquidSimulation()
        for step in range(50):
            sim.update(step * 7.0, step * 11.0, step * 2.0)
        self.assertTrue(np.isfinite(sim.pos).all())
        self.assertTrue((np.abs(sim.pos) <= BOUND + 1e-3).all())

    def test_puzzle_logic(self):
        puz = Puzzle()
        img = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        puz.create_from_image(img, piece_size=100)
        puz.shuffle()
        self.assertFalse(puz.is_solved())
        puz.arrangement = list(range(9))
        puz.swap_pieces(0, 1)
        self.assertEqual(puz.correct_count(), 7)
        puz.swap_pieces(0, 1)
        self.assertTrue(puz.is_solved())

    def test_app_mode_switching_interactions_and_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            vid_path = os.path.join(tmp, "feed.avi")
            cfg_path = os.path.join(tmp, "cal.json")
            _make_test_video(vid_path, frames=8)
            orig_save_dir = air_mod.SAVE_DIR
            air_mod.SAVE_DIR = tmp
            try:
                app = StudioApp(camera_source=vid_path, headless=True, calibration_path=cfg_path)
                app.start()
                self.assertTrue(app.camera.is_live)
                self.assertEqual(app.screen, MODE_MENU)
                self.assertEqual(app.step().shape, (WIN_H, WIN_W, 3))

                # Calibration screen & FX toggle
                app.step(key=ord("k"))
                self.assertEqual(app.screen, MODE_CALIBRATE)
                app.step()
                app.step(key=27)
                self.assertEqual(app.screen, MODE_MENU)
                app.step(key=ord("v"))
                self.assertFalse(app.fx.enabled)
                app.step(key=ord("v"))
                self.assertTrue(app.fx.enabled)
                app.step(key=ord("a"))
                self.assertFalse(app.ar_hud_enabled)
                app.step(key=ord("a"))
                self.assertTrue(app.ar_hud_enabled)

                # 1. Liquid Cube
                app.mouse.pos, app.mouse.just_released = (200, 350), True
                app.step()
                self.assertEqual(app.screen, MODE_CUBE)
                app.step(key=ord(" "))
                self.assertTrue(app.modes[MODE_CUBE].frozen)
                app.step(key=ord("r"))
                self.assertFalse(app.modes[MODE_CUBE].frozen)
                app.step(key=ord("m"))
                self.assertEqual(app.screen, MODE_MENU)

                # 2. Air Drawing + Open Palm pause + Peace return
                app.step(key=ord("2"))
                self.assertEqual(app.screen, MODE_DRAW)
                draw_mode = app.modes[MODE_DRAW]
                app.mouse.pos, app.mouse.down, app.mouse.just_pressed = (400, 300), True, True
                app.step()
                app.mouse.pos = (480, 340)
                app.step()
                app.mouse.down, app.mouse.just_released = False, True
                app.step()
                self.assertGreater(int(draw_mode.strokes.sum()), 0)
                app._handle_custom_gesture(HandData(detected=True, action_gesture="OPEN_PALM"))
                self.assertTrue(draw_mode.paused)
                app._handle_custom_gesture(HandData(detected=True, action_gesture="OPEN_PALM"))
                self.assertFalse(draw_mode.paused)
                app.step(key=ord("s"))
                self.assertTrue(any(f.endswith(".png") for f in os.listdir(tmp)))
                app.step(key=ord("e"))
                self.assertTrue(draw_mode.eraser)
                app.step(key=ord("u"))
                self.assertEqual(int(draw_mode.strokes.sum()), 0)
                app._handle_custom_gesture(HandData(detected=True, action_gesture="PEACE"))
                self.assertEqual(app.screen, MODE_MENU)

                # 3. Selfie Puzzle
                app.step(key=ord("3"))
                self.assertEqual(app.screen, MODE_PUZZLE)
                puz_mode = app.modes[MODE_PUZZLE]
                app.mouse.pos, app.mouse.down, app.mouse.just_pressed = (300, 150), True, True
                app.step()
                app.mouse.pos = (620, 470)
                app.step()
                app.mouse.down, app.mouse.just_released = False, True
                app.step()
                self.assertEqual(puz_mode.cap_state, "locked")
                app.step(key=13)
                self.assertEqual(puz_mode.phase, "PLAY")

                t0 = (BOARD_X + PIECE_PX // 2, BOARD_Y + PIECE_PX // 2)
                t1 = (BOARD_X + PIECE_PX + TILE_GAP + PIECE_PX // 2, BOARD_Y + PIECE_PX // 2)
                app.mouse.pos, app.mouse.down, app.mouse.just_pressed = t0, True, True
                app.step()
                app.mouse.pos, app.mouse.down, app.mouse.just_released = t1, False, True
                app.step()
                self.assertEqual(puz_mode.move_count, 1)
                app.step(key=ord("p"))
                self.assertTrue(puz_mode.show_preview)
                app.step(key=ord("m"))
                self.assertEqual(app.screen, MODE_MENU)

                # Settings & clean exit
                app.step(key=ord("s"))
                self.assertEqual(app.screen, MODE_SETTINGS)
                app.step(key=27)
                self.assertEqual(app.screen, MODE_MENU)
                app.step(key=ord("q"))
                self.assertFalse(app.running)
                app.shutdown()
                self.assertFalse(app.camera.is_live)
                self.assertIsNone(app.tracker._detector)
            finally:
                air_mod.SAVE_DIR = orig_save_dir


if __name__ == "__main__":
    unittest.main()
