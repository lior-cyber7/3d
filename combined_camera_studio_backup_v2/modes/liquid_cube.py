"""3D Liquid Cube mode adapted from Subham503/3D-Liquid-Cube-Simulation (MIT)."""

from typing import Optional, Tuple

import cv2
import numpy as np

from ui_helpers import ACCENT_CYAN, ACCENT_GREEN, ACCENT_RED, Button, TEXT_PRIMARY, glass_panel
from vision import HAND_CONNECTIONS, HandData, LANDMARK_NAMES, WIN_H, WIN_W

N_PARTICLES, GRAVITY, BOUND, DT, DAMPING, VEL_CAP = 350, 35.0, 0.88, 0.028, 0.985, 6.0
REPULSE_R, REPULSE_K, WALL_MARGIN, WALL_K = 0.21, 0.055, 0.10, 14.0

CORNERS = np.array([
    [-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1],
    [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1],
], dtype=float)
EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
FACES = [
    ([4, 5, 6, 7], np.array([0.0, 0.0, 1.0]), (10, 10, 70)),
    ([0, 3, 2, 1], np.array([0.0, 0.0, -1.0]), (10, 10, 50)),
    ([1, 2, 6, 5], np.array([1.0, 0.0, 0.0]), (10, 50, 80)),
    ([0, 4, 7, 3], np.array([-1.0, 0.0, 0.0]), (10, 50, 80)),
    ([3, 7, 6, 2], np.array([0.0, 1.0, 0.0]), (10, 70, 110)),
    ([0, 1, 5, 4], np.array([0.0, -1.0, 0.0]), (10, 70, 110)),
]


def rotation_matrix(ax: float, ay: float, az: float) -> np.ndarray:
    cx, sx = np.cos(np.radians(ax)), np.sin(np.radians(ax))
    cy, sy = np.cos(np.radians(ay)), np.sin(np.radians(ay))
    cz, sz = np.cos(np.radians(az)), np.sin(np.radians(az))
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rz @ ry @ rx


class LiquidSimulation:
    """Vectorized Position-Based Dynamics fluid inside a unit cube."""

    def __init__(self, count: int = N_PARTICLES):
        self.count = count
        self.pos = np.zeros((count, 3), dtype=np.float32)
        self.vel = np.zeros((count, 3), dtype=np.float32)
        self.reset()

    def reset(self):
        self.pos = np.random.uniform(-BOUND * 0.7, BOUND * 0.7, (self.count, 3)).astype(np.float32)
        self.pos[:, 1] = np.random.uniform(-BOUND * 0.8, -0.05, self.count).astype(np.float32)
        self.vel.fill(0.0)

    def _wall_force(self) -> np.ndarray:
        f = np.zeros_like(self.pos)
        for axis in range(3):
            dp, dn = BOUND - self.pos[:, axis], BOUND + self.pos[:, axis]
            cp, cn = dp < WALL_MARGIN, dn < WALL_MARGIN
            if cp.any():
                f[cp, axis] -= WALL_K * (1.0 - dp[cp] / WALL_MARGIN) ** 2
            if cn.any():
                f[cn, axis] += WALL_K * (1.0 - dn[cn] / WALL_MARGIN) ** 2
        return f

    def _repulse(self, pos: np.ndarray) -> np.ndarray:
        diff = pos[:, None, :] - pos[None, :, :]
        dist2 = (diff ** 2).sum(axis=2)
        np.fill_diagonal(dist2, 1e9)
        mask = dist2 < (REPULSE_R ** 2)
        if not mask.any():
            return pos
        dist = np.sqrt(np.where(mask, dist2, np.float32(1.0)))
        over = np.where(mask, np.float32(REPULSE_R) - dist, np.float32(0.0))
        safe = np.where(mask[:, :, None], diff / dist[:, :, None], np.float32(0.0))
        return pos + (safe * (over * np.float32(REPULSE_K * 0.5))[:, :, None]).sum(axis=1)

    def update(self, ax: float, ay: float, az: float):
        R = rotation_matrix(ax, ay, az).astype(np.float32)
        g_local = R.T @ np.array([0.0, -GRAVITY, 0.0], dtype=np.float32)
        self.vel += (g_local + self._wall_force()) * np.float32(DT)
        pred = self._repulse(self.pos + self.vel * np.float32(DT))
        self.vel = (pred - self.pos) / np.float32(DT)

        for axis in range(3):
            hi, lo = pred[:, axis] > BOUND, pred[:, axis] < -BOUND
            self.vel[hi, axis] = -abs(self.vel[hi, axis]) * 0.25
            self.vel[lo, axis] = abs(self.vel[lo, axis]) * 0.25
            pred[hi, axis], pred[lo, axis] = BOUND - 1e-4, -BOUND + 1e-4

        self.vel = np.clip(self.vel * np.float32(DAMPING), -VEL_CAP, VEL_CAP)
        self.pos = pred
        bad = ~np.isfinite(self.pos).all(axis=1)
        if bad.any():
            self.pos[bad] = np.random.uniform(-0.3, 0.3, (bad.sum(), 3)).astype(np.float32)
            self.vel[bad] = 0.0


class LiquidCubeMode:
    name = "Liquid Cube"

    def __init__(self):
        self.cx, self.cy, self.focal = 720, 360, 28.0
        self.liquid = LiquidSimulation()
        self.btn_freeze = Button(WIN_W - 315, 16, 150, 36, "Freeze [Space]")
        self.btn_reset = Button(WIN_W - 155, 16, 135, 36, "Reset [R]")
        self.reset()

    def reset(self):
        self.ax, self.ay, self.az = 15.0, 25.0, 0.0
        self.spin_x = self.spin_y = 0.0
        self.half_edge = 5.8
        self.prev_centroid: Optional[np.ndarray] = None
        self.pinch_buf = []
        self.frozen = False
        self._mouse_last: Optional[Tuple[int, int]] = None
        self.liquid.reset()

    def toggle_pause(self) -> bool:
        self.frozen = not self.frozen
        return self.frozen

    def _project(self, pts3d: np.ndarray):
        return [(int(self.cx + x * self.focal), int(self.cy - y * self.focal)) for x, y, _ in pts3d]

    def _draw_cube(self, frame: np.ndarray, R: np.ndarray):
        pts3d = (CORNERS * self.half_edge) @ R.T
        p2 = self._project(pts3d)
        xs, ys = [p[0] for p in p2], [p[1] for p in p2]
        x1, y1 = max(0, min(xs) - 4), max(0, min(ys) - 4)
        x2, y2 = min(WIN_W, max(xs) + 5), min(WIN_H, max(ys) + 5)
        if x2 > x1 and y2 > y1:
            roi = frame[y1:y2, x1:x2]
            overlay = roi.copy()
            for fi in sorted(range(len(FACES)), key=lambda i: np.mean(pts3d[FACES[i][0]], axis=0)[2]):
                verts, local_n, col = FACES[fi]
                if (R @ local_n)[2] >= 0:
                    cv2.fillPoly(overlay, [np.array([(p2[v][0] - x1, p2[v][1] - y1) for v in verts], dtype=np.int32)], col)
            cv2.addWeighted(overlay, 0.25, roi, 0.75, 0, dst=roi)
        for s, e in EDGES:
            cv2.line(frame, p2[s], p2[e], (15, 20, 30), 2, cv2.LINE_AA)

    def _draw_liquid(self, frame: np.ndarray, R: np.ndarray):
        pts = (self.liquid.pos * self.half_edge) @ R.T
        p2 = self._project(pts)
        depths, speeds = pts[:, 2], np.linalg.norm(self.liquid.vel, axis=1)
        d_min, d_max = float(depths.min()), float(depths.max()) + 1e-5
        s_min, s_max = float(speeds.min()), float(speeds.max()) + 1e-5

        pad = int(self.half_edge * self.focal * 1.9) + 28
        rx1, ry1, rx2, ry2 = max(0, self.cx - pad), max(0, self.cy - pad), min(WIN_W, self.cx + pad), min(WIN_H, self.cy + pad)
        rw, rh = rx2 - rx1, ry2 - ry1
        if rw <= 0 or rh <= 0:
            return

        glow = np.zeros((rh, rw, 3), dtype=np.uint8)
        spec = np.zeros((rh, rw, 3), dtype=np.uint8)
        for i in np.argsort(depths):
            px, py = p2[i][0] - rx1, p2[i][1] - ry1
            if not (0 <= px < rw and 0 <= py < rh):
                continue
            d = (depths[i] - d_min) / (d_max - d_min)
            s = (speeds[i] - s_min) / (s_max - s_min)
            cv2.circle(glow, (px, py), int(np.clip(11 - d * 5, 5, 13)),
                       (int(np.clip(180 + d * 75, 100, 255)), int(np.clip(35 + s * 170 + d * 60, 0, 215)), int(np.clip(12 + s * 75, 0, 95))), -1)
            if d <= 0.6:
                br = int(np.clip(180 + s * 75, 100, 255))
                cv2.circle(spec, (px, py), 2, (br, br, br), -1)

        glow_blur = cv2.GaussianBlur(glow, (13, 13), 5)
        roi = frame[ry1:ry2, rx1:rx2]
        mask = glow_blur.sum(axis=2) > 15
        if mask.any():
            blended = cv2.addWeighted(roi, 0.28, glow_blur, 0.72, 0)
            roi[mask] = blended[mask]
        cv2.addWeighted(roi, 1.0, spec, 0.70, 0, dst=roi)

    def _draw_hand_telemetry(self, frame: np.ndarray, hand: HandData, centroid: np.ndarray):
        pts = hand.landmarks_px
        bone_col = ACCENT_GREEN if hand.is_open_hand else ACCENT_RED
        dot_col = (120, 255, 170) if hand.is_open_hand else (120, 120, 255)
        for s, e in HAND_CONNECTIONS:
            cv2.line(frame, pts[s], pts[e], bone_col, 2, cv2.LINE_AA)
        for px, py in pts:
            cv2.circle(frame, (px, py), 4, dot_col, -1, cv2.LINE_AA)
        for ti in (8, 12, 16, 20):
            cv2.circle(frame, pts[ti], 9, ACCENT_CYAN, 2, cv2.LINE_AA)
        cv2.drawMarker(frame, (int(centroid[0]), int(centroid[1])), (0, 255, 180), cv2.MARKER_CROSS, 20, 2, cv2.LINE_AA)

        glass_panel(frame, 16, 68, 210, 495, alpha=0.58, border_color=bone_col)
        cv2.putText(frame, "HAND LANDMARKS", (26, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.44, bone_col, 1, cv2.LINE_AA)
        for i, lm in enumerate(hand.landmarks):
            cv2.putText(frame, f"{i:02d} {LANDMARK_NAMES[i]:<6} {lm.x:.2f} {lm.y:.2f}",
                        (24, 112 + i * 21), cv2.FONT_HERSHEY_SIMPLEX, 0.34, (175, 230, 185), 1, cv2.LINE_AA)

    def update_and_render(self, frame: np.ndarray, hand: HandData, mouse, key: int) -> Optional[str]:
        if key == ord(" "):
            self.frozen = not self.frozen
        elif key == ord("r"):
            self.reset()
        elif key in (ord("+"), ord("=")):
            self.half_edge = float(np.clip(self.half_edge + 0.4, 3.0, 9.0))
        elif key in (ord("-"), ord("_")):
            self.half_edge = float(np.clip(self.half_edge - 0.4, 3.0, 9.0))

        for ptr, clicked in ((mouse.pos, mouse.just_released), (hand.pinch_center, hand.pinch_started)):
            if clicked and ptr is not None:
                if self.btn_freeze.contains(ptr):
                    self.frozen = not self.frozen
                elif self.btn_reset.contains(ptr):
                    self.reset()

        self.btn_freeze.active = self.frozen
        centroid = None
        if hand.detected and not self.frozen:
            self.pinch_buf = (self.pinch_buf + [hand.pinch_px])[-5:]
            self.half_edge = float(np.clip(np.mean(self.pinch_buf) * 0.022, 3.0, 9.0))
            centroid = np.mean([hand.landmarks_px[i] for i in (8, 12, 16, 20)], axis=0)
            if hand.is_open_hand and self.prev_centroid is not None:
                dx, dy = centroid[0] - self.prev_centroid[0], centroid[1] - self.prev_centroid[1]
                dx, dy = (0.0 if abs(dx) < 3.5 else dx), (0.0 if abs(dy) < 3.5 else dy)
                dpp = float(np.clip(0.35 + ((dx * dx + dy * dy) ** 0.5) * 0.05, 0.35, 1.8))
                self.spin_y = self.spin_y * 0.88 + (dx * dpp) * 0.12
                self.spin_x = self.spin_x * 0.88 + (dy * dpp) * 0.12
            elif not hand.is_open_hand:
                self.spin_x *= 0.85
                self.spin_y *= 0.85
                self.prev_centroid = None
            if hand.is_open_hand:
                self.prev_centroid = centroid
        else:
            self.prev_centroid = None
            decay = 0.85 if (self.frozen or (hand.detected and not hand.is_open_hand)) else 0.94
            self.spin_x *= decay
            self.spin_y *= decay

        if mouse.down and not self.btn_freeze.contains(mouse.pos) and not self.btn_reset.contains(mouse.pos):
            if self._mouse_last is not None:
                self.spin_y = (mouse.pos[0] - self._mouse_last[0]) * 0.65
                self.spin_x = (mouse.pos[1] - self._mouse_last[1]) * 0.65
            self._mouse_last = mouse.pos
        else:
            self._mouse_last = None
        if mouse.wheel != 0:
            self.half_edge = float(np.clip(self.half_edge + mouse.wheel * 0.4, 3.0, 9.0))

        if not self.frozen:
            self.ay, self.ax = (self.ay + self.spin_y) % 360.0, (self.ax + self.spin_x) % 360.0
            self.az = self.ay * 0.08
            self.liquid.update(self.ax, self.ay, self.az)

        R = rotation_matrix(self.ax, self.ay, self.az)
        self._draw_cube(frame, R)
        self._draw_liquid(frame, R)
        if hand.detected:
            self._draw_hand_telemetry(frame, hand, centroid if centroid is not None else np.mean([hand.landmarks_px[i] for i in (8, 12, 16, 20)], axis=0))

        self.btn_freeze.draw(frame, hovered=self.btn_freeze.contains(mouse.pos))
        self.btn_reset.draw(frame, hovered=self.btn_reset.contains(mouse.pos))
        state_txt = "FROZEN" if self.frozen else ("OPEN: rotate | PINCH: resize | FIST: freeze" if hand.detected else "Show hand or drag mouse to rotate")
        glass_panel(frame, 240, WIN_H - 46, WIN_W - 260, 34, alpha=0.58)
        cv2.putText(frame, f"{state_txt}   |   Angle X:{self.ax:.0f} Y:{self.ay:.0f}   Size:{self.half_edge:.1f}",
                    (256, WIN_H - 23), cv2.FONT_HERSHEY_SIMPLEX, 0.48, TEXT_PRIMARY, 1, cv2.LINE_AA)
        return None
