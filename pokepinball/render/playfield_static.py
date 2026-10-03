"""Construction des couches statiques du plateau (sur-échantillonnées 2x)."""
import math
import random

import numpy as np
import pygame

from ..config import PF_SCALE, PF_PIX_W, PF_PIX_H, PF_W, PF_H
from .assets import text, gradient_surface, blur, glow, soft_circle, mul_col, aa_polygon, thick_line
from . import art
from .layout import INSERTS, RING_C, RING_R

SS = 2
K = PF_SCALE * SS          # mm → pixels sur-échantillonnés


def M(x, y):
    return (x * K, y * K)


def MP(pts):
    return [M(x, y) for x, y in pts]


def _poly(surf, color, pts):
    aa_polygon(surf, color, MP(pts))


def _line(surf, color, p1, p2, w_mm):
    thick_line(surf, color, M(*p1), M(*p2), max(1.0, w_mm * K))


def _polyline(surf, color, pts, w_mm, closed=False):
    seq = list(pts) + ([pts[0]] if closed else [])
    for a, b in zip(seq[:-1], seq[1:]):
        _line(surf, color, a, b, w_mm)


def _down(surf):
    return pygame.transform.smoothscale(surf, (PF_PIX_W, PF_PIX_H))


def _offset(pts, d):
    """Décale une polyligne de d (mm) sur sa normale gauche."""
    out = []
    n = len(pts)
    for i in range(n):
        x, y = pts[i][0], pts[i][1]
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        L = math.hypot(dx, dy) or 1e-6
        out.append((x - dy / L * d, y + dx / L * d))
    return out


# ==========================================================================
class StaticLayers:
    def __init__(self, table):
        self.table = table
        W, H = int(PF_PIX_W * SS), int(PF_PIX_H * SS)
        self.W, self.H = W, H
        rnd = random.Random(7)
        self.rnd = rnd
        base = pygame.Surface((W, H))
        self._background(base)
        self._zones(base)
        self._ring(base)
        self._labels(base)
        self._island(base)
        self._inserts_off(base)
        self._ramp_shadows(base)
        self._walls(base)
        self._holes(base)
        self.base = _down(base).convert()
        top = pygame.Surface((W, H), pygame.SRCALPHA)
        self._ramps(top)
        self._apron(top)
        self.top = _down(top).convert_alpha()
        self.lamp_sprites = self._lamp_sprites()
        self.gi_mask = self._gi_mask()

    # ------------------------------------------------------------------
    def _background(self, s):
        W, H = self.W, self.H
        g = gradient_surface(W, H // 2, (16, 22, 64), (40, 22, 86))
        s.blit(g, (0, 0))
        g2 = gradient_surface(W, H - H // 2, (40, 22, 86), (14, 10, 34))
        s.blit(g2, (0, H // 2))
        # nébuleuses colorées
        for (x, y, r, c) in ((241, 690, 260, (90, 40, 150)), (120, 300, 220, (30, 70, 160)),
                             (380, 240, 180, (120, 90, 20)), (241, 950, 200, (110, 30, 70)),
                             (60, 760, 160, (20, 90, 140)), (430, 780, 160, (140, 40, 40))):
            gl = glow(int(r * K), c, falloff=1.6)
            s.blit(gl, (x * K - gl.get_width() / 2, y * K - gl.get_height() / 2), special_flags=pygame.BLEND_ADD)
        # étoiles
        for _ in range(420):
            x, y = self.rnd.uniform(0, PF_W), self.rnd.uniform(0, PF_H)
            b = self.rnd.uniform(60, 220)
            r = self.rnd.choice((1, 1, 1, 2, 2, 3))
            pygame.draw.circle(s, (b, b, min(255, b + 30)), M(x, y), r)
        # trame d'impression légère
        noise = np.random.default_rng(3).normal(0, 5, (W, H)).astype(np.int16)
        arr = pygame.surfarray.pixels3d(s)
        arr[:] = np.clip(arr.astype(np.int16) + noise[:, :, None], 0, 255).astype(np.uint8)
        del arr

    def _zones(self, s):
        # sol des orbites : métal sombre + chevrons
        ov = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        lane_l = [(0, 470), (47, 470), (47, 200)] + [
            (200 + 153 * math.cos(math.radians(a)), 200 + 153 * math.sin(math.radians(a)))
            for a in range(180, 256, 5)] + [(300, 75), (300, 0), (0, 0)]
        _poly(ov, (10, 18, 40, 150), lane_l)
        _poly(ov, (10, 18, 40, 150), [(437, 470), (485, 470), (485, 0), (300, 0), (300, 75), (437, 80)])
        # zone des bumpers : électrique
        _poly(ov, (90, 70, 10, 120), [(300, 75), (437, 80), (437, 470), (366, 470), (366, 410), (300, 382)])
        s.blit(ov, (0, 0))
        for i in range(9):
            y = 470 - i * 30
            if y < 220:
                break
            for x in (22,):
                _poly(s, (40, 70, 140), [(x - 10, y), (x, y - 10), (x + 10, y), (x + 10, y + 5), (x, y - 5),
                                         (x - 10, y + 5)])
            _poly(s, (140, 60, 50), [(461 - 10, y), (461, y - 10), (461 + 10, y), (461 + 10, y + 5), (461, y - 5),
                                     (461 - 10, y + 5)])
        # éclairs dans la zone bumpers
        for (x, y) in ((318, 300), (420, 280), (340, 120), (395, 360)):
            pts = [(x, y - 26), (x - 9, y + 2), (x - 1, y + 2), (x - 7, y + 26), (x + 10, y - 5), (x + 2, y - 5),
                   (x + 8, y - 26)]
            _poly(s, (150, 120, 20), pts)
        # rayons depuis le bas
        rays = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        cx, cy = 241, 1080
        for i in range(-7, 8):
            a = math.radians(-90 + i * 11)
            a2 = math.radians(-90 + i * 11 + 4)
            p = [(cx, cy), (cx + math.cos(a) * 700, cy + math.sin(a) * 700),
                 (cx + math.cos(a2) * 700, cy + math.sin(a2) * 700)]
            _poly(rays, (255, 255, 255, 10), p)
        s.blit(rays, (0, 0))
        # bande décorative au-dessus des slingshots
        for side in (-1, 1):
            cx = 241 + side * 128
            for j in range(4):
                y = 760 + j * 9
                _line(s, (60 + 30 * j, 40, 110 + 20 * j), (cx - 30, y), (cx + 30, y - side * 6), 2.4)

    def _ring(self, s):
        cx, cy = RING_C
        # filigrane Pokéball géant
        wm = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        R = 128
        pygame.draw.circle(wm, (200, 40, 60, 60), M(cx, cy), R * K)
        pygame.draw.rect(wm, (0, 0, 0, 0), pygame.Rect(0, int((cy - 4) * K), self.W, self.H))
        pygame.draw.circle(wm, (230, 230, 255, 26), M(cx, cy), R * K, 0)
        half = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        pygame.draw.circle(half, (220, 40, 60, 70), M(cx, cy), R * K)
        half.fill((0, 0, 0, 0), pygame.Rect(0, int((cy - 5) * K), self.W, self.H))
        wm.blit(half, (0, 0))
        pygame.draw.rect(wm, (10, 10, 20, 120), pygame.Rect(int((cx - R) * K), int((cy - 6) * K),
                                                           int(2 * R * K), int(12 * K)))
        s.blit(wm, (0, 0))
        # anneaux lumineux
        for rr, col, w in ((RING_R + 21, (160, 120, 255), 1.6), (RING_R - 21, (160, 120, 255), 1.4),
                           (RING_R + 27, (90, 70, 160), 0.8), (RING_R, (60, 40, 110), 30)):
            pygame.draw.circle(s, col, M(cx, cy), rr * K, max(1, int(w * K)))
        # traits radiaux
        for i in range(36):
            a = math.radians(i * 10)
            p1 = (cx + math.cos(a) * (RING_R + 30), cy + math.sin(a) * (RING_R + 30))
            p2 = (cx + math.cos(a) * (RING_R + 36), cy + math.sin(a) * (RING_R + 36))
            _line(s, (120, 100, 200), p1, p2, 0.8)
        lab = text("LÉGENDES", "black", int(9 * K), (220, 210, 255), outline=(40, 20, 80), outline_w=3)
        s.blit(lab, (cx * K - lab.get_width() / 2, (cy + RING_R + 30) * K))

    def _labels(self, s):
        def lab(t, x, y, size, col=(240, 240, 255), angle=0, kind="black"):
            img = text(t, kind, int(size * K), col, outline=(10, 10, 30), outline_w=max(2, int(0.8 * K)))
            if angle:
                img = pygame.transform.rotozoom(img, angle, 1.0)
            s.blit(img, (x * K - img.get_width() / 2, y * K - img.get_height() / 2))

        lab("POKÉ RADAR", 26, 700, 6.5, (120, 255, 150), angle=-72)
        lab("TEAM ROCKET", 456, 700, 6.5, (255, 110, 110), angle=72)
        lab("HAUTES HERBES", 241, 474, 6.0, (150, 255, 160))
        lab("SPINNER", 22, 380, 4.6, (255, 230, 120), angle=90)
        lab("ATTRAPEZ-LES TOUS !", 241, 812, 8.0, (255, 220, 70))
        lab("BONUS", 241, 850, 5.5, (255, 220, 120))
        for x, t in ((326, "1"), (372, "2"), (417.5, "3")):
            pass

    def _island(self, s):
        isl = self.table.island
        lay = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        # ombre portée
        sh = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        _poly(sh, (0, 0, 0, 170), [(x + 4, y + 6) for x, y in isl])
        sh = blur(sh, int(5 * K))
        s.blit(sh, (0, 0))
        # plastique illustré
        _poly(lay, (255, 255, 255, 255), isl)
        art_s = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        art_s.blit(gradient_surface(self.W, int(480 * K), (26, 40, 110), (60, 30, 120)), (0, 0))
        # montagnes du Mont Argenté
        for (pts, col) in (
            ([(40, 470), (40, 330), (90, 250), (120, 290), (160, 210), (205, 300), (240, 240), (300, 330),
              (300, 470)], (40, 50, 120)),
            ([(40, 470), (40, 380), (80, 330), (130, 380), (170, 320), (220, 370), (300, 360), (300, 470)],
             (30, 36, 90)),
        ):
            _poly(art_s, col + (255,), pts)
        for (x, y) in ((90, 250), (160, 210), (240, 240)):
            _poly(art_s, (220, 230, 255, 255), [(x, y), (x - 12, y + 18), (x - 4, y + 14), (x, y + 20),
                                                (x + 5, y + 13), (x + 12, y + 18)])
        for _ in range(60):
            x, y = self.rnd.uniform(50, 300), self.rnd.uniform(40, 220)
            pygame.draw.circle(art_s, (230, 230, 255, 255), M(x, y), self.rnd.choice((1, 2, 2, 3)))
        lug = art.creature("lugia", int(150 * K))
        lug.set_alpha(70)
        art_s.blit(lug, M(70, 120))
        art_s.blit(lay, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(art_s, (0, 0))
        # biseau lumineux
        _polyline(s, (120, 150, 255), isl, 2.2, closed=True)
        _polyline(s, (200, 215, 255), [(x - 0.6, y - 0.6) for x, y in isl], 0.8, closed=True)

    def _inserts_off(self, s):
        for ins in INSERTS:
            self._draw_insert(s, ins, lit=False)

    def _insert_poly(self, ins):
        x, y, w, h = ins.x, ins.y, ins.w, ins.h
        a = math.radians(ins.angle)
        ca, sa = math.cos(a), math.sin(a)

        def rot(px, py):
            return (x + px * ca - py * sa, y + px * sa + py * ca)
        if ins.shape == "arrow":
            pts = [(0, -h / 2), (w / 2, -h / 2 + w * 0.55), (w * 0.22, -h / 2 + w * 0.55), (w * 0.22, h / 2),
                   (-w * 0.22, h / 2), (-w * 0.22, -h / 2 + w * 0.55), (-w / 2, -h / 2 + w * 0.55)]
            pts = [(0, -h / 2), (w / 2, -h / 2 + w * 0.62), (w * 0.26, -h / 2 + w * 0.5), (w * 0.26, h / 2),
                   (-w * 0.26, h / 2), (-w * 0.26, -h / 2 + w * 0.5), (-w / 2, -h / 2 + w * 0.62)]
            return [rot(px, py) for px, py in pts]
        if ins.shape == "rect":
            r = min(w, h) * 0.3
            return [rot(px, py) for px, py in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        return None

    def _draw_insert(self, s, ins, lit=False):
        col = ins.base
        dim = mul_col(col, 0.28)
        rim = mul_col(col, 0.55)
        if ins.shape == "circle":
            r = ins.w / 2
            pygame.draw.circle(s, (8, 8, 14), M(ins.x, ins.y), (r + 1.1) * K)
            pygame.draw.circle(s, dim, M(ins.x, ins.y), r * K)
            g = soft_circle(r * K * 0.6, mul_col(col, 0.45), 150, edge=r * K * 0.5)
            s.blit(g, (ins.x * K - g.get_width() / 2, ins.y * K - g.get_height() / 2 - r * K * 0.2))
            pygame.draw.circle(s, rim, M(ins.x, ins.y), r * K, max(1, int(0.6 * K)))
        else:
            poly = self._insert_poly(ins)
            _poly(s, (8, 8, 14), _offset(poly + [poly[0]], -1.0)[:-1] if False else poly)
            grown = [(ins.x + (px - ins.x) * 1.12, ins.y + (py - ins.y) * 1.12) for px, py in poly]
            _poly(s, (8, 8, 14), grown)
            _poly(s, dim, poly)
            _polyline(s, rim, poly, 0.7, closed=True)
        self._insert_decor(s, ins, (255, 255, 255) if lit else mul_col(col, 0.75))

    def _insert_decor(self, s, ins, col):
        if ins.icon:
            if ins.icon.startswith("leg:"):
                key = ins.icon[4:]
                size = int(ins.w * K * 0.9)
                img = art.creature(key, size)
                img = img.copy()
                img.set_alpha(150)
                s.blit(img, (ins.x * K - size / 2, ins.y * K - size / 2))
            elif ins.icon.startswith("type:"):
                size = int(ins.w * K * 0.6)
                img = art.type_icon(ins.icon[5:], size, col)
                s.blit(img, (ins.x * K - size / 2, ins.y * K - size / 2))
            elif ins.icon == "pokeball":
                art.draw_pokeball(s, ins.x * K, ins.y * K, ins.w * K * 0.38, shading=False,
                                  top=mul_col((230, 40, 50), 0.6), bottom=(110, 110, 120))
            elif ins.icon == "radar":
                pygame.draw.circle(s, col, M(ins.x, ins.y), ins.w * K * 0.28, max(1, int(0.5 * K)))
                pygame.draw.circle(s, col, M(ins.x, ins.y), ins.w * K * 0.08)
            elif ins.icon == "R":
                im = text("R", "black", int(ins.w * K * 0.7), col)
                s.blit(im, (ins.x * K - im.get_width() / 2, ins.y * K - im.get_height() / 2))
        if ins.label and ins.shape != "arrow":
            im = text(ins.label, "black", int(ins.label_size * K), col)
            if ins.shape == "rect" and ins.h > ins.w:
                im = pygame.transform.rotate(im, 90)
            s.blit(im, (ins.x * K - im.get_width() / 2, ins.y * K - im.get_height() / 2))
        if ins.shape == "arrow" and ins.label:
            im = text(ins.label, "black", int(5.6 * K), (235, 235, 255), outline=(10, 10, 30), outline_w=2)
            im = pygame.transform.rotozoom(im, -ins.angle, 1.0)
            a = math.radians(ins.angle)
            lx, ly = ins.x - math.sin(a) * -26, ins.y + math.cos(a) * 26
            s.blit(im, (lx * K - im.get_width() / 2, ly * K - im.get_height() / 2))

    def _ramp_shadows(self, s):
        sh = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for path in self.table.world.ramps:
            pts = [(x + h * 0.25, y + h * 0.4) for x, y, h in path.pts]
            _polyline(sh, (0, 0, 0, 150), pts, 40)
        s.blit(blur(sh, int(7 * K)), (0, 0))

    def _walls(self, s):
        tb = self.table
        sh = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        for pts, style, rad in tb.walls:
            _polyline(sh, (0, 0, 0, 200), [(x + 2.5, y + 4) for x, y in pts], rad * 2 + 3)
        for x, y, r, st in tb.posts:
            pygame.draw.circle(sh, (0, 0, 0, 200), M(x + 2.5, y + 4), (r + 1.5) * K)
        s.blit(blur(sh, int(2.5 * K)), (0, 0))
        # séparateurs (inlane guides) remplis
        for poly in (tb.sep_l, [(2 * 241 - x, y) for x, y in tb.sep_l]):
            _poly(s, (36, 40, 62), poly)
            _polyline(s, (170, 180, 210), poly, 2.4, closed=True)
            _polyline(s, (235, 240, 255), [(x - 0.4, y - 0.4) for x, y in poly], 0.7, closed=True)
        # slingshots (plastiques)
        for nm in ("sling_l", "sling_r"):
            e = tb.by_name[nm]
            tri = [e.a, e.b, e.c]
            _poly(s, (250, 210, 40), tri)
            inner = [(sum(p[0] for p in tri) / 3 + (p[0] - sum(q[0] for q in tri) / 3) * 0.72,
                      sum(p[1] for p in tri) / 3 + (p[1] - sum(q[1] for q in tri) / 3) * 0.72) for p in tri]
            _poly(s, (255, 236, 120), inner)
            cx = sum(p[0] for p in tri) / 3
            cy = sum(p[1] for p in tri) / 3
            bolt = [(cx + 3, cy - 18), (cx - 6, cy + 2), (cx + 0, cy + 2), (cx - 4, cy + 18), (cx + 7, cy - 4),
                    (cx + 1, cy - 4), (cx + 6, cy - 18)]
            _poly(s, (40, 30, 10), bolt)
        for pts, style, rad in tb.walls:
            if style == "metal":
                col, hi = (150, 158, 180), (235, 240, 255)
            elif style == "rubber":
                col, hi = (25, 25, 25), (90, 90, 90)
            else:
                col, hi = (110, 130, 200), (210, 220, 255)
            _polyline(s, col, pts, rad * 2)
            _polyline(s, hi, [(x - rad * 0.3, y - rad * 0.3) for x, y in pts], max(0.6, rad * 0.5))
        for x, y, r, st in tb.posts:
            pygame.draw.circle(s, (20, 20, 22), M(x, y), r * K)
            pygame.draw.circle(s, (70, 70, 75), M(x - r * 0.25, y - r * 0.25), r * 0.45 * K)
            pygame.draw.circle(s, (210, 210, 225), M(x, y), r * 0.42 * K)
            pygame.draw.circle(s, (255, 255, 255), M(x - 0.6, y - 0.6), r * 0.18 * K)
        # couloir de lancement
        _poly(s, (22, 24, 36), [(488, 330), (520, 300), (520, 1150), (488, 1150)])
        for j in range(18):
            y = 1080 - j * 40
            _line(s, (50, 56, 80), (492, y), (516, y - 8), 1.0)

    def _holes(self, s):
        tb = self.table
        sc = tb.scoop
        pygame.draw.circle(s, (180, 190, 210), M(sc.x, sc.y), 15 * K)
        pygame.draw.circle(s, (5, 5, 8), M(sc.x, sc.y), 12.5 * K)
        g = soft_circle(10 * K, (0, 0, 0), 255, edge=5 * K)
        s.blit(g, (sc.x * K - g.get_width() / 2, sc.y * K - g.get_height() / 2))
        # emplacements des cibles tombantes
        for t in tb.grass.targets:
            (x1, y1), (x2, y2) = t.p1, t.p2
            pygame.draw.rect(s, (8, 10, 12), pygame.Rect(int((x1 - 4) * K), int((y1 - 5) * K),
                                                          int((x2 - x1 + 8) * K), int(10 * K)))
        # kickback
        kb = tb.kickback
        pygame.draw.circle(s, (12, 12, 16), M(kb.x, kb.y + 10), 9 * K)
        # trous de couloir (rollovers)
        for e in tb.elements:
            if e.kind == "rollover":
                pygame.draw.line(s, (200, 205, 220), M(e.x, e.y - 7), M(e.x, e.y + 7), max(2, int(1.4 * K)))

    # ------------------------------------------------------------------
    def _ramps(self, s):
        tb = self.table
        for ramp, plastic_end in ((tb.ramp_l, 8), (tb.ramp_r, 8)):
            path = ramp.path
            pts = [(x, y) for x, y, h in path.pts]
            col = ramp.color
            plast = pts[:plastic_end + 1]
            # plastique translucide
            left = _offset(plast, 25)
            right = _offset(plast, -25)
            body = left + right[::-1]
            _poly(s, col + (70,), body)
            _polyline(s, mul_col(col, 1.25) + (220,), left, 2.2)
            _polyline(s, mul_col(col, 1.25) + (220,), right, 2.2)
            _polyline(s, (255, 255, 255, 160), _offset(plast, 22), 0.7)
            # rabat métallique d'entrée
            e1, e2 = ramp.entry
            _line(s, (200, 205, 220, 255), (e1[0], e1[1] + 4), (e2[0], e2[1] + 4), 3.0)
            # flèches imprimées sur la rampe
            for i in range(1, min(6, len(plast) - 1)):
                (x1, y1), (x2, y2) = plast[i], plast[i + 1]
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                dx, dy = x2 - x1, y2 - y1
                L = math.hypot(dx, dy) or 1
                ux, uy = dx / L, dy / L
                tri = [(mx + ux * 7, my + uy * 7), (mx - ux * 4 - uy * 7, my - uy * 4 + ux * 7),
                       (mx - ux * 4 + uy * 7, my - uy * 4 - ux * 7)]
                _poly(s, (255, 255, 255, 120), tri)
            # rail métallique (retour)
            wire = pts[plastic_end - 1:]
            for d in (-7.5, 7.5):
                rail = _offset(wire, d)
                _polyline(s, (90, 95, 110, 255), rail, 2.6)
                _polyline(s, (235, 240, 255, 255), [(x - 0.4, y - 0.5) for x, y in rail], 0.9)
            for i in range(1, len(wire) - 1, 1):
                a = _offset(wire[i - 1:i + 2], 9)[1]
                b = _offset(wire[i - 1:i + 2], -9)[1]
                _line(s, (160, 165, 180, 255), a, b, 1.4)
            name = "LUGIA" if ramp.name == "ramp_l" else "HO-OH"
            im = text(name, "black", int(7 * K), (255, 255, 255), outline=mul_col(col, 0.5), outline_w=3)
            i = 2
            (x1, y1), (x2, y2) = plast[i], plast[i + 1]
            ang = math.degrees(math.atan2(-(y2 - y1), x2 - x1))
            im = pygame.transform.rotozoom(im, ang - 180 if ang > 90 or ang < -90 else ang, 1.0)
            im.set_alpha(200)
            s.blit(im, (((x1 + x2) / 2) * K - im.get_width() / 2, ((y1 + y2) / 2) * K - im.get_height() / 2))

    def _apron(self, s):
        y0 = 1086
        pts = [(0, y0 + 10), (132, y0), (132, 1080), (350, 1080), (350, y0), (485, y0 + 10), (485, 1150),
               (0, 1150)]
        pts = [(0, 1094), (128, 1094), (150, 1084), (332, 1084), (354, 1094), (485, 1094), (485, 1150), (0, 1150)]
        sh = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        _poly(sh, (0, 0, 0, 160), [(x, y - 6) for x, y in pts])
        s.blit(blur(sh, int(4 * K)), (0, 0))
        g = gradient_surface(self.W, int(70 * K), (40, 46, 72), (18, 20, 32))
        mask = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        _poly(mask, (255, 255, 255, 255), pts)
        layer = pygame.Surface((self.W, self.H), pygame.SRCALPHA)
        layer.blit(g, (0, int(1080 * K)))
        layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(layer, (0, 0))
        _polyline(s, (190, 200, 230, 255), pts, 1.2, closed=True)
        lg = art.logo(int(150 * K), subtitle=False)
        lg = pygame.transform.smoothscale(lg, (int(lg.get_width() * 0.62), int(lg.get_height() * 0.62)))
        s.blit(lg, (241 * K - lg.get_width() / 2, 1093 * K))
        for cx, title, lines in ((62, "COMMENT JOUER", ["RADAR → LÉGENDAIRE", "HERBES → CAPTURE", "3 CAPTURES → SAFARI"]),
                                 (420, "OBJECTIF", ["11 LÉGENDAIRES", "+ MEW", "→ MEWTWO !"])):
            _poly(s, (230, 225, 200, 255), [(cx - 52, 1100), (cx + 52, 1100), (cx + 52, 1140), (cx - 52, 1140)])
            t = text(title, "black", int(5.2 * K), (180, 30, 40))
            s.blit(t, (cx * K - t.get_width() / 2, 1102 * K))
            for j, ln in enumerate(lines):
                t = text(ln, "bold", int(4.2 * K), (30, 30, 40))
                s.blit(t, (cx * K - t.get_width() / 2, (1111 + j * 8.5) * K))

    # ------------------------------------------------------------------
    def _lamp_sprites(self):
        """Sprites RVB (fond noir) des inserts allumés, en blanc → teintés au rendu."""
        out = {}
        for ins in INSERTS:
            r = max(ins.w, ins.h) * 0.75 + 6
            size = int(r * 2 * K)
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            ox, oy = ins.x - r, ins.y - r

            def MM(x, y):
                return ((x - ox) * K, (y - oy) * K)
            if ins.shape == "circle":
                rr = ins.w / 2
                pygame.draw.circle(surf, (235, 235, 235, 255), MM(ins.x, ins.y), rr * K)
                g = soft_circle(rr * K * 0.55, (255, 255, 255), 255, edge=rr * K * 0.6)
                surf.blit(g, (MM(ins.x, ins.y)[0] - g.get_width() / 2, MM(ins.x, ins.y)[1] - g.get_height() / 2))
            else:
                poly = self._insert_poly(ins)
                aa_polygon(surf, (235, 235, 235, 255), [MM(x, y) for x, y in poly])
            # décor (icône / texte) en surimpression sombre pour rester lisible
            dec = pygame.Surface((size, size), pygame.SRCALPHA)
            save_x, save_y = ins.x, ins.y
            ins.x, ins.y = ins.x - ox, ins.y - oy
            self._insert_decor(dec, ins, (255, 255, 255))
            ins.x, ins.y = save_x, save_y
            if ins.icon and ins.icon.startswith("leg:"):
                surf.blit(dec, (0, 0))
            img = pygame.transform.smoothscale(surf, (max(1, size // SS), max(1, size // SS)))
            rgb = pygame.Surface(img.get_size())
            rgb.fill((0, 0, 0))
            rgb.blit(img, (0, 0))
            out[ins.name] = (rgb, (ins.x - r) * PF_SCALE, (ins.y - r) * PF_SCALE)
        return out

    def _gi_mask(self):
        """Masque basse résolution de l'éclairage général (sous les plastiques)."""
        w, h = PF_PIX_W // 4, PF_PIX_H // 4
        s = pygame.Surface((w, h))
        s.fill((0, 0, 0))
        k = PF_SCALE / 4
        tb = self.table
        spots = [(p[0], p[1]) for e in (tb.by_name["sling_l"], tb.by_name["sling_r"]) for p in (e.a, e.b, e.c)]
        spots += [(x, y) for x, y, r, st in tb.posts]
        spots += [(46, 812), (436, 812), (241, 1000), (60, 470), (420, 470), (241, 300), (370, 200),
                  (22, 300), (462, 300), (241, 40), (100, 120), (380, 60)]
        for x, y in spots:
            g = glow(int(18 * k * 4) // 2 + 6, (90, 90, 90), falloff=1.5)
            s.blit(g, (x * k - g.get_width() / 2, y * k - g.get_height() / 2), special_flags=pygame.BLEND_ADD)
        return s
