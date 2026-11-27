"""Focused tests for Combined Camera Studio: debouncing, camera/video, modes, and shutdown."""

import os
import sys
import tempfile
import unittest

import cv2
import numpy as np

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO_ROOT not in sys.path:
    sys.path.insert(0, STUDIO_ROOT)

from main import MODE_CUBE, MODE_DRAW, MODE_MENU, MODE_PUZZLE, MODE_SETTINGS, StudioApp
import modes.air_drawing as air_mod
from modes.liquid_cube import BOUND, LiquidSimulation
from modes.selfie_puzzle import BOARD_X, BOARD_Y, PIECE_PX, Puzzle, TILE_GAP
from vision import CameraSource, PinchDebouncer, WIN_H, WIN_W, parse_camera_source


def _make_test_video(path: str, frames: int = 12):
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 15.0, (640, 480))
    for i in range(frames):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(img, (40 + i * 15, 80), (220 + i * 15, 300), (40, 180, 240), -1)
        cv2.circle(img, (450, 240), 60, (200, 90, 255), -1)
        writer.write(img)
    writer.release()


class TestStudioCore(unittest.TestCase):
    def test_parse_camera_source(self):
        self.assertEqual(parse_camera_source("0"), 0)
        self.assertEqual(parse_camera_source(" 2 "), 2)
        self.assertEqual(parse_camera_source(""), 0)
        self.assertEqual(parse_camera_source("http://192.168.1.50:8080/video"), "http://192.168.1.50:8080/video")
        self.assertEqual(parse_camera_source("rtsp://user:pass@host/stream"), "rtsp://user:pass@host/stream")

    def test_pinch_debouncer_rising_edge_and_cooldown(self):
        deb = PinchDebouncer(cooldown_frames=3)
        self.assertTrue(deb.update(True))    # fires, cooldown=3
        self.assertFalse(deb.update(True))   # held, cooldown->2
        self.assertFalse(deb.update(False))  # released, cooldown->1
        self.assertFalse(deb.update(True))   # within cooldown, cooldown->0
        self.assertFalse(deb.update(False))  # released, ready now
        self.assertTrue(deb.update(True))    # fires again

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
            _make_test_video(vid_path, frames=8)
            orig_save_dir = air_mod.SAVE_DIR
            air_mod.SAVE_DIR = tmp
            try:
                app = StudioApp(camera_source=vid_path, headless=True)
                app.start()
                self.assertTrue(app.camera.is_live)
                self.assertEqual(app.screen, MODE_MENU)
                self.assertEqual(app.step().shape, (WIN_H, WIN_W, 3))

                # 1. Liquid Cube: click card via mouse, freeze, reset, back to menu
                app.mouse.pos, app.mouse.just_released = (200, 350), True
                app.step()
                self.assertEqual(app.screen, MODE_CUBE)
                app.step(key=ord(" "))
                self.assertTrue(app.modes[MODE_CUBE].frozen)
                app.step(key=ord("r"))
                self.assertFalse(app.modes[MODE_CUBE].frozen)
                app.step(key=ord("m"))
                self.assertEqual(app.screen, MODE_MENU)

                # 2. Air Drawing: draw, save PNG, toggle eraser, undo, clear, back
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
                app.step(key=ord("s"))
                self.assertTrue(any(f.endswith(".png") for f in os.listdir(tmp)))
                app.step(key=ord("e"))
                self.assertTrue(draw_mode.eraser)
                app.step(key=ord("u"))
                self.assertEqual(int(draw_mode.strokes.sum()), 0)
                app.step(key=27)
                self.assertEqual(app.screen, MODE_MENU)

                # 3. Selfie Puzzle: mouse-drag capture -> PLAY -> drag-swap pieces -> back
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

                # Swap tile 0 -> tile 1 via mouse drag
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
