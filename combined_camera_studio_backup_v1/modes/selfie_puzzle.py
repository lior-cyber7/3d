"""Selfie Puzzle mode adapted from krishaagor-source/selfie-puzzle-game (MIT)."""

import random
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from ui_helpers import ACCENT_CYAN, ACCENT_GREEN, ACCENT_ORANGE, Button, FONT, FONT_SMALL, TEXT_MUTED, TEXT_PRIMARY, draw_pointer, glass_panel
from vision import HandData, HandTracker, WIN_H, WIN_W

GRID_SIZE, NUM_PIECES = 3, 9
PIECE_PX, TILE_GAP, BOARD_X, BOARD_Y = 190, 6, 60, 76
BOARD_SPAN = GRID_SIZE * PIECE_PX + (GRID_SIZE - 1) * TILE_GAP
PANEL_X = BOARD_X + BOARD_SPAN + 55
PANEL_W = WIN_W - PANEL_X - 45


class Puzzle:
    """Pure 3x3 puzzle model: slicing, shuffling, swapping, and win detection."""

    def __init__(self):
        self.pieces: List[np.ndarray] = []
        self.arrangement: List[int] = list(range(NUM_PIECES))
        self.source_image: Optional[np.ndarray] = None

    def create_from_image(self, image: np.ndarray, piece_size: int = PIECE_PX):
        total = piece_size * GRID_SIZE
        resized = cv2.resize(image, (total, total), interpolation=cv2.INTER_LANCZOS4)
        self.source_image = resized
        self.pieces = [
            resized[r * piece_size:(r + 1) * piece_size, c * piece_size:(c + 1) * piece_size].copy()
            for r in range(GRID_SIZE) for c in range(GRID_SIZE)
        ]
        self.arrangement = list(range(NUM_PIECES))

    def shuffle(self):
        solved = list(range(NUM_PIECES))
        for _ in range(500):
            random.shuffle(self.arrangement)
            if self.arrangement != solved:
                return
        self.arrangement[0], self.arrangement[1] = self.arrangement[1], self.arrangement[0]

    def swap_pieces(self, a: int, b: int):
        if 0 <= a < NUM_PIECES and 0 <= b < NUM_PIECES and a != b:
            self.arrangement[a], self.arrangement[b] = self.arrangement[b], self.arrangement[a]

    def is_solved(self) -> bool:
        return len(self.pieces) == NUM_PIECES and self.arrangement == list(range(NUM_PIECES))

    def correct_count(self) -> int:
        return sum(1 for i, p in enumerate(self.arrangement) if p == i)


class SelfiePuzzleMode:
    name = "Selfie Puzzle"

    def __init__(self):
        self.puzzle = Puzzle()
        self.btn_quick = Button(WIN_W - 210, 16, 190, 36, "Quick Selfie [F]")
        self.btn_preview = Button(PANEL_X + 35, 445, PANEL_W - 70, 42, "Preview [P]")
        self.btn_restart = Button(PANEL_X + 35, 497, PANEL_W - 70, 42, "Restart [R]")
        self.btn_new = Button(PANEL_X + 35, 549, PANEL_W - 70, 42, "New Selfie [N]")
        self.reset()

    def reset(self):
        self.phase, self.cap_state = "CAPTURE", "idle"
        self.anchor = self.cur_pt = self.locked_rect = self._input_src = None
        self.start_time, self.completion_time, self.move_count = time.time(), None, 0
        self.is_solved = self.show_preview = False
        self.dragging_pos = self.drag_src = None
        self.drag_offset, self.confetti = (0, 0), []

    def _init_confetti(self):
        self.confetti = [
            [random.uniform(0, WIN_W), random.uniform(-WIN_H, 0), random.uniform(-1.5, 1.5), random.uniform(2.5, 6.0),
             random.randint(6, 12), (random.randint(90, 255), random.randint(90, 255), random.randint(90, 255))]
            for _ in range(75)
        ]

    def _start_puzzle(self, crop: np.ndarray):
        self.puzzle.create_from_image(crop, PIECE_PX)
        self.puzzle.shuffle()
        self.phase, self.start_time, self.completion_time = "PLAY", time.time(), None
        self.move_count, self.is_solved, self.show_preview = 0, False, False
        self.dragging_pos = self.drag_src = None

    def _tile_rect(self, pos: int) -> Tuple[int, int, int, int]:
        r, c = divmod(pos, GRID_SIZE)
        return BOARD_X + c * (PIECE_PX + TILE_GAP), BOARD_Y + r * (PIECE_PX + TILE_GAP), PIECE_PX, PIECE_PX

    def _pos_at(self, pt: Optional[Tuple[int, int]]) -> Optional[int]:
        if pt is None or not (BOARD_X <= pt[0] < BOARD_X + BOARD_SPAN and BOARD_Y <= pt[1] < BOARD_Y + BOARD_SPAN):
            return None
        col, row = (pt[0] - BOARD_X) // (PIECE_PX + TILE_GAP), (pt[1] - BOARD_Y) // (PIECE_PX + TILE_GAP)
        return int(row * GRID_SIZE + col) if (0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE) else None

    def _run_capture_phase(self, frame: np.ndarray, hand: HandData, mouse, key: int):
        clean = frame.copy()
        if key == ord("f") or (mouse.just_released and self.btn_quick.contains(mouse.pos)) or (hand.pinch_started and self.btn_quick.contains(hand.pinch_center)):
            s = min(WIN_W, WIN_H) - 120
            cx, cy = WIN_W // 2, WIN_H // 2
            self._start_puzzle(clean[cy - s // 2:cy + s // 2, cx - s // 2:cx + s // 2])
            return

        if self.cap_state == "idle":
            if hand.is_pinching and hand.pinch_center and not self.btn_quick.contains(hand.pinch_center):
                self.anchor = self.cur_pt = hand.pinch_center
                self.cap_state, self._input_src = "drawing", "hand"
            elif mouse.just_pressed and not self.btn_quick.contains(mouse.pos) and mouse.pos[1] > 60:
                self.anchor = self.cur_pt = mouse.pos
                self.cap_state, self._input_src = "drawing", "mouse"
        elif self.cap_state == "drawing":
            active = (hand.is_pinching and hand.pinch_center) if self._input_src == "hand" else mouse.down
            pt = hand.pinch_center if self._input_src == "hand" else mouse.pos
            if active and pt:
                self.cur_pt = pt
            else:
                x1, x2 = sorted((self.anchor[0], self.cur_pt[0]))
                y1, y2 = sorted((self.anchor[1], self.cur_pt[1]))
                if (x2 - x1) >= 90 and (y2 - y1) >= 90:
                    self.locked_rect = (max(0, x1), max(0, y1), min(WIN_W, x2), min(WIN_H, y2))
                    self.cap_state = "locked"
                else:
                    self.cap_state = "idle"
        elif self.cap_state == "locked" and self.locked_rect:
            x1, y1, x2, y2 = self.locked_rect
            if key in (13, 32):
                self._start_puzzle(clean[y1:y2, x1:x2])
                return
            for pt, clicked in ((hand.pinch_center, hand.pinch_started), (mouse.pos, mouse.just_released)):
                if clicked and pt:
                    if x1 <= pt[0] <= x2 and y1 <= pt[1] <= y2:
                        self._start_puzzle(clean[y1:y2, x1:x2])
                        return
                    elif not self.btn_quick.contains(pt):
                        self.cap_state, self.locked_rect = "idle", None

        if self.cap_state == "drawing" and self.anchor and self.cur_pt:
            x1, x2 = sorted((self.anchor[0], self.cur_pt[0]))
            y1, y2 = sorted((self.anchor[1], self.cur_pt[1]))
            glass_panel(frame, x1, y1, x2 - x1, y2 - y1, alpha=0.20, border_color=ACCENT_ORANGE, bg_color=ACCENT_ORANGE, border_thickness=3)
        elif self.cap_state == "locked" and self.locked_rect:
            x1, y1, x2, y2 = self.locked_rect
            glass_panel(frame, x1, y1, x2 - x1, y2 - y1, alpha=0.18, border_color=ACCENT_GREEN, bg_color=ACCENT_GREEN, border_thickness=3)
            cv2.putText(frame, "Pinch/Click inside to CAPTURE!", ((x1 + x2) // 2 - 140, (y1 + y2) // 2), FONT_SMALL, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

        msg = {
            "idle": "Pinch & drag (or mouse drag) to select selfie region",
            "drawing": "Release to lock selection box",
            "locked": "Pinch/Click inside box to capture | Outside to reset",
        }[self.cap_state]
        glass_panel(frame, 290, 14, WIN_W - 520, 40, alpha=0.65)
        cv2.putText(frame, msg, (308, 40), FONT_SMALL, 0.52, TEXT_PRIMARY, 1, cv2.LINE_AA)
        self.btn_quick.draw(frame, hovered=self.btn_quick.contains(mouse.pos) or self.btn_quick.contains(hand.pinch_center))
        HandTracker.draw_skeleton(frame, hand)
        draw_pointer(frame, hand.pinch_center if hand.is_pinching else hand.index_tip, pinching=hand.is_pinching)

    def _run_play_phase(self, frame: np.ndarray, hand: HandData, mouse, key: int):
        cam_pip = frame.copy()
        if key == ord("r"):
            self._start_puzzle(self.puzzle.source_image); return
        if key == ord("n"):
            self.reset(); return
        if key == ord("p"):
            self.show_preview = not self.show_preview

        cursor = (hand.pinch_center if hand.is_pinching else hand.index_tip) if hand.detected else mouse.pos
        for ptr, clicked in ((mouse.pos, mouse.just_released), (hand.pinch_center, hand.pinch_started)):
            if clicked and ptr:
                if self.btn_preview.contains(ptr):
                    self.show_preview = not self.show_preview
                elif self.btn_restart.contains(ptr):
                    self._start_puzzle(self.puzzle.source_image); return
                elif self.btn_new.contains(ptr):
                    self.reset(); return

        if not self.is_solved:
            if self.dragging_pos is None:
                if hand.pinch_started and hand.pinch_center and (p := self._pos_at(hand.pinch_center)) is not None:
                    rx, ry, _, _ = self._tile_rect(p)
                    self.dragging_pos, self.drag_src, self.drag_offset = p, "hand", (hand.pinch_center[0] - rx, hand.pinch_center[1] - ry)
                elif mouse.just_pressed and (p := self._pos_at(mouse.pos)) is not None:
                    rx, ry, _, _ = self._tile_rect(p)
                    self.dragging_pos, self.drag_src, self.drag_offset = p, "mouse", (mouse.pos[0] - rx, mouse.pos[1] - ry)
            else:
                still_held = hand.is_pinching if self.drag_src == "hand" else mouse.down
                drop_pt = (hand.pinch_center or hand.index_tip) if self.drag_src == "hand" else mouse.pos
                if not still_held:
                    target = self._pos_at(drop_pt)
                    if target is not None and target != self.dragging_pos:
                        self.puzzle.swap_pieces(self.dragging_pos, target)
                        self.move_count += 1
                        if self.puzzle.is_solved():
                            self.is_solved, self.completion_time = True, time.time()
                            self._init_confetti()
                    self.dragging_pos = self.drag_src = None

        frame[:] = (15, 17, 26)
        glass_panel(frame, BOARD_X - 8, BOARD_Y - 8, BOARD_SPAN + 16, BOARD_SPAN + 16, alpha=0.95, border_color=(55, 65, 95), bg_color=(24, 28, 44))
        for pos in range(NUM_PIECES):
            if pos == self.dragging_pos:
                continue
            x, y, w, h = self._tile_rect(pos)
            piece_idx = self.puzzle.arrangement[pos]
            frame[y:y + h, x:x + w] = self.puzzle.pieces[piece_idx]
            cv2.rectangle(frame, (x, y), (x + w, y + h), ACCENT_GREEN if piece_idx == pos else (60, 68, 95), 2, cv2.LINE_AA)

        if self.dragging_pos is not None and cursor is not None:
            dx = int(np.clip(cursor[0] - self.drag_offset[0], 8, WIN_W - PIECE_PX - 8))
            dy = int(np.clip(cursor[1] - self.drag_offset[1], 8, WIN_H - PIECE_PX - 8))
            frame[dy:dy + PIECE_PX, dx:dx + PIECE_PX] = self.puzzle.pieces[self.puzzle.arrangement[self.dragging_pos]]
            cv2.rectangle(frame, (dx, dy), (dx + PIECE_PX, dy + PIECE_PX), ACCENT_CYAN, 3, cv2.LINE_AA)

        if self.show_preview and self.puzzle.source_image is not None:
            frame[BOARD_Y:BOARD_Y + BOARD_SPAN, BOARD_X:BOARD_X + BOARD_SPAN] = cv2.resize(self.puzzle.source_image, (BOARD_SPAN, BOARD_SPAN))
            cv2.putText(frame, "PREVIEW", (BOARD_X + 14, BOARD_Y + 34), FONT, 0.85, (255, 255, 255), 2, cv2.LINE_AA)

        glass_panel(frame, PANEL_X, BOARD_Y - 8, PANEL_W, BOARD_SPAN + 16, alpha=0.92, border_color=(55, 65, 95), bg_color=(22, 26, 40))
        pip_w = PANEL_W - 110
        pip_h = int(pip_w * 9 / 16)
        pip_x, pip_y = PANEL_X + (PANEL_W - pip_w) // 2, BOARD_Y + 12
        HandTracker.draw_skeleton(cam_pip, hand)
        frame[pip_y:pip_y + pip_h, pip_x:pip_x + pip_w] = cv2.resize(cam_pip, (pip_w, pip_h))
        cv2.rectangle(frame, (pip_x, pip_y), (pip_x + pip_w, pip_y + pip_h), ACCENT_CYAN if hand.detected else (70, 80, 110), 1)

        mins, secs = divmod(int((self.completion_time or time.time()) - self.start_time), 60)
        cv2.putText(frame, f"Time: {mins:02d}:{secs:02d}   Moves: {self.move_count}", (PANEL_X + 35, pip_y + pip_h + 36), FONT_SMALL, 0.62, TEXT_PRIMARY, 1, cv2.LINE_AA)
        cv2.putText(frame, f"Correct: {self.puzzle.correct_count()}/9", (PANEL_X + 35, pip_y + pip_h + 66), FONT_SMALL, 0.56, ACCENT_GREEN if self.is_solved else TEXT_MUTED, 1, cv2.LINE_AA)

        self.btn_preview.active = self.show_preview
        for btn in (self.btn_preview, self.btn_restart, self.btn_new):
            btn.draw(frame, hovered=btn.contains(cursor))
        cv2.putText(frame, "Pinch & drag tiles to swap (or mouse drag)", (PANEL_X + 35, BOARD_Y + BOARD_SPAN - 14), FONT_SMALL, 0.45, TEXT_MUTED, 1, cv2.LINE_AA)

        if self.is_solved:
            glass_panel(frame, BOARD_X, BOARD_Y + BOARD_SPAN // 2 - 90, BOARD_SPAN, 180, alpha=0.82, border_color=ACCENT_GREEN)
            for c in self.confetti:
                c[0] += c[2]; c[1] += c[3]
                if c[1] > WIN_H:
                    c[1], c[0] = -10, random.uniform(0, WIN_W)
                cv2.circle(frame, (int(c[0]), int(c[1])), c[4] // 2, c[5], -1)
            cv2.putText(frame, "PUZZLE SOLVED!", (BOARD_X + 115, BOARD_Y + BOARD_SPAN // 2 - 15), FONT, 1.25, ACCENT_GREEN, 2, cv2.LINE_AA)
            cv2.putText(frame, f"Time {mins:02d}:{secs:02d}  |  Moves {self.move_count}  |  Press R or N", (BOARD_X + 90, BOARD_Y + BOARD_SPAN // 2 + 38), FONT_SMALL, 0.62, TEXT_PRIMARY, 1, cv2.LINE_AA)

        if hand.detected and cursor is not None:
            draw_pointer(frame, cursor, pinching=hand.is_pinching)

    def update_and_render(self, frame: np.ndarray, hand: HandData, mouse, key: int) -> Optional[str]:
        if self.phase == "CAPTURE":
            self._run_capture_phase(frame, hand, mouse, key)
            if self.phase == "PLAY":
                self._run_play_phase(frame, hand, mouse, -1)
        else:
            self._run_play_phase(frame, hand, mouse, key)
        return None
