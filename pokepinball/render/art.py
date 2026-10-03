"""Illustrations procédurales : Pokéball, Voltorbe, icônes de types, silhouettes
stylisées des légendaires (chemins de Bézier façon SVG, aucun sprite externe)."""
import math
import re
from functools import lru_cache

import numpy as np
import pygame
import pygame.gfxdraw as gfx

from .assets import blur, lerp_col, mul_col

# ==========================================================================
# Mini-parseur de chemins SVG (M, L, C, Q, Z en coordonnées absolues)
# ==========================================================================
_tok = re.compile(r"[MLCQZ]|-?\d+(?:\.\d+)?")


def path_points(d, steps=14):
    toks = _tok.findall(d)
    pts = []
    i = 0
    cur = (0.0, 0.0)
    cmd = None
    polys = []
    while i < len(toks):
        t = toks[i]
        if t in "MLCQZ":
            cmd = t
            i += 1
            if cmd == "Z":
                if pts:
                    polys.append(pts)
                pts = []
            continue
        if cmd == "M":
            cur = (float(toks[i]), float(toks[i + 1]))
            if pts:
                polys.append(pts)
            pts = [cur]
            i += 2
            cmd = "L"
        elif cmd == "L":
            cur = (float(toks[i]), float(toks[i + 1]))
            pts.append(cur)
            i += 2
        elif cmd == "C":
            p1 = (float(toks[i]), float(toks[i + 1]))
            p2 = (float(toks[i + 2]), float(toks[i + 3]))
            p3 = (float(toks[i + 4]), float(toks[i + 5]))
            for k in range(1, steps + 1):
                s = k / steps
                u = 1 - s
                pts.append((u ** 3 * cur[0] + 3 * u * u * s * p1[0] + 3 * u * s * s * p2[0] + s ** 3 * p3[0],
                            u ** 3 * cur[1] + 3 * u * u * s * p1[1] + 3 * u * s * s * p2[1] + s ** 3 * p3[1]))
            cur = p3
            i += 6
        elif cmd == "Q":
            p1 = (float(toks[i]), float(toks[i + 1]))
            p2 = (float(toks[i + 2]), float(toks[i + 3]))
            for k in range(1, steps + 1):
                s = k / steps
                u = 1 - s
                pts.append((u * u * cur[0] + 2 * u * s * p1[0] + s * s * p2[0],
                            u * u * cur[1] + 2 * u * s * p1[1] + s * s * p2[1]))
            cur = p2
            i += 4
        else:
            i += 1
    if pts:
        polys.append(pts)
    return polys


def _mirror_d(d, cx=100):
    out = []
    toks = _tok.findall(d)
    i = 0
    cmd = None
    while i < len(toks):
        t = toks[i]
        if t in "MLCQZ":
            out.append(t)
            cmd = t
            i += 1
            continue
        x = float(toks[i])
        y = float(toks[i + 1])
        out.append(f"{2 * cx - x:.2f} {y:.2f}")
        i += 2
    return " ".join(out)


# ==========================================================================
# Dessin d'une créature
# ==========================================================================
def P(fill, d, stroke=None, sw=2.0, mirror=False):
    return {"t": "path", "fill": fill, "d": d, "stroke": stroke, "sw": sw, "mirror": mirror}


def E(fill, cx, cy, rx, ry, rot=0.0, stroke=None, sw=2.0, mirror=False):
    return {"t": "ell", "fill": fill, "c": (cx, cy), "r": (rx, ry), "rot": rot, "stroke": stroke, "sw": sw,
            "mirror": mirror}


def S(color, d, sw=3.0, mirror=False):
    """Trait seul (lignes décoratives)."""
    return {"t": "stroke", "stroke": color, "d": d, "sw": sw, "mirror": mirror}


def _ellipse_pts(cx, cy, rx, ry, rot, n=40):
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x, y = math.cos(a) * rx, math.sin(a) * ry
        pts.append((cx + x * c - y * s, cy + x * s + y * c))
    return pts


def _draw_poly(surf, pts, color, k, ox=0, oy=0):
    ip = [(int(round(ox + x * k)), int(round(oy + y * k))) for x, y in pts]
    if len(ip) >= 3:
        gfx.filled_polygon(surf, ip, color)
        gfx.aapolygon(surf, ip, color)


def _stroke_poly(surf, pts, color, w, k, closed=True, ox=0, oy=0):
    ip = [(ox + x * k, oy + y * k) for x, y in pts]
    if closed:
        ip = ip + [ip[0]]
    ww = max(1.0, w * k)
    r = ww / 2
    for (x1, y1), (x2, y2) in zip(ip[:-1], ip[1:]):
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        if L < 1e-6:
            continue
        nx, ny = -dy / L * r, dx / L * r
        q = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        gfx.filled_polygon(surf, [(int(round(a)), int(round(b))) for a, b in q], color)
    for x, y in ip:
        if r >= 1.5:
            gfx.filled_circle(surf, int(round(x)), int(round(y)), int(r), color)


def render_layers(layers, size, outline=(20, 20, 30), outline_w=2.2, shade=True, box=200):
    ss = 2
    S2 = size * ss
    k = S2 / box
    surf = pygame.Surface((S2, S2), pygame.SRCALPHA)
    # 1) contour global (silhouette épaissie)
    if outline:
        sil = pygame.Surface((S2, S2), pygame.SRCALPHA)
        for L in layers:
            for pts, closed in _layer_polys(L):
                if L["t"] == "stroke":
                    _stroke_poly(sil, pts, outline + (255,), L["sw"] + outline_w * 2, k, closed=False)
                else:
                    _draw_poly(sil, pts, outline + (255,), k)
                    _stroke_poly(sil, pts, outline + (255,), outline_w * 2, k)
        surf.blit(sil, (0, 0))
    # 2) remplissages
    for L in layers:
        for pts, closed in _layer_polys(L):
            if L["t"] == "stroke":
                _stroke_poly(surf, pts, L["stroke"] + (255,), L["sw"], k, closed=False)
                continue
            if L.get("fill") is not None:
                _draw_poly(surf, pts, L["fill"] + (255,), k)
            if L.get("stroke") is not None:
                _stroke_poly(surf, pts, L["stroke"] + (255,), L["sw"], k)
    if shade:
        _shade(surf)
    return pygame.transform.smoothscale(surf, (size, size))


def _layer_polys(L):
    out = []
    t = L["t"]
    if t in ("path", "stroke"):
        ds = [L["d"]] + ([_mirror_d(L["d"])] if L.get("mirror") else [])
        for d in ds:
            for poly in path_points(d):
                out.append((poly, t != "stroke"))
    elif t == "ell":
        cx, cy = L["c"]
        rx, ry = L["r"]
        out.append((_ellipse_pts(cx, cy, rx, ry, L["rot"]), True))
        if L.get("mirror"):
            out.append((_ellipse_pts(200 - cx, cy, rx, ry, -L["rot"]), True))
    return out


def _shade(surf):
    """Éclairage : lumière en haut à gauche, ombre en bas à droite + liseré."""
    w, h = surf.get_size()
    rgb = pygame.surfarray.pixels3d(surf)
    a = pygame.surfarray.array_alpha(surf).astype(np.float32) / 255.0
    yy, xx = np.meshgrid(np.linspace(0, 1, h), np.linspace(0, 1, w))
    light = 1.18 - 0.42 * (0.55 * xx + 0.75 * yy)
    # liseré lumineux : bords de la silhouette (alpha flou - alpha)
    small = pygame.transform.smoothscale(surf, (max(1, w // 6), max(1, h // 6)))
    bl = pygame.transform.smoothscale(small, (w, h))
    ab = pygame.surfarray.array_alpha(bl).astype(np.float32) / 255.0
    rim = np.clip((a - ab) * 1.6, 0, 1) * (1.0 - yy) * 0.55
    f = rgb.astype(np.float32) * light[:, :, None] + rim[:, :, None] * 255
    rgb[:] = np.clip(f, 0, 255).astype(np.uint8)
    del rgb


# ==========================================================================
# Légendaires (boîte 200 x 200)
# ==========================================================================
def _articuno():
    B = (125, 195, 250); L = (175, 225, 255); D = (55, 105, 210); W = (225, 245, 255)
    return [
        P(D, "M 98 112 C 70 125 45 150 12 186 C 40 168 58 156 78 146 C 66 162 58 178 52 197 "
             "C 74 172 90 148 106 124 Z"),
        P((95, 160, 230), "M 96 96 C 80 62 58 36 26 14 C 44 36 40 44 52 54 C 38 50 28 48 14 45 "
                          "C 32 60 44 66 58 72 C 44 74 34 76 22 80 C 44 90 70 98 96 108 Z"),
        E(B, 120, 110, 31, 15, -14),
        E(W, 124, 116, 19, 7, -14),
        P(L, "M 108 98 C 103 62 100 32 112 4 C 116 24 119 30 126 38 C 126 25 131 14 142 7 "
             "C 139 30 141 40 147 50 C 152 40 159 33 170 30 C 161 56 150 80 132 104 Z"),
        S(W, "M 116 30 C 118 55 122 75 126 96", 2.0),
        S(W, "M 140 22 C 138 50 134 72 130 98", 2.0),
        P(D, "M 145 79 C 140 61 128 51 110 45 C 127 58 131 66 135 74 C 124 66 113 64 101 65 "
             "C 118 75 129 81 141 87 Z"),
        E(L, 153, 89, 13, 12),
        P((120, 125, 150), "M 163 86 L 180 91 L 164 96 Z"),
        E((170, 20, 40), 157, 86, 2.6, 2.6),
    ]


def _zapdos():
    Y = (255, 222, 45); Yd = (225, 175, 15); O = (245, 140, 40); K = (35, 30, 30)
    return [
        P(Yd, "M 100 96 L 70 72 L 72 60 L 48 57 L 54 44 L 26 42 L 38 30 L 8 24 L 47 16 L 40 6 "
              "L 75 18 L 72 7 L 96 30 L 99 17 L 112 52 Z"),
        P(Y, "M 96 112 L 58 120 L 74 128 L 42 141 L 71 143 L 54 162 L 85 149 L 82 167 L 104 126 Z"),
        E(Y, 120, 112, 29, 16, -8),
        P(Y, "M 116 98 L 112 60 L 99 52 L 112 45 L 104 29 L 120 34 L 120 13 L 133 30 L 141 6 "
             "L 146 31 L 162 16 L 159 42 L 181 34 L 166 60 L 188 62 L 161 81 L 140 103 Z"),
        P(K, "M 124 72 L 148 44 L 152 47 L 128 76 Z"),
        P(K, "M 130 84 L 166 62 L 168 66 L 133 88 Z"),
        P(K, "M 118 66 L 125 35 L 129 36 L 122 68 Z"),
        P(O, "M 112 124 L 108 152 L 116 152 L 119 126 Z"),
        P(O, "M 126 124 L 125 154 L 132 154 L 131 125 Z"),
        P(Y, "M 140 96 L 149 70 L 158 81 L 164 60 L 168 80 L 182 73 L 173 93 L 160 106 Z"),
        P(O, "M 168 88 L 192 96 L 166 101 Z"),
        E(K, 163, 87, 2.6, 2.6),
    ]


def _moltres():
    Y = (255, 196, 60); O = (250, 130, 30); R = (240, 70, 30); F = (255, 235, 120)
    return [
        P(R, "M 96 112 C 70 120 50 140 22 150 C 44 153 55 151 66 146 C 50 161 42 174 28 188 "
             "C 60 174 82 156 104 126 Z"),
        P(O, "M 100 96 C 85 70 64 60 38 55 C 54 50 60 45 62 37 C 49 40 37 34 28 24 C 49 27 60 24 70 17 "
             "C 61 14 57 7 57 0 C 75 12 93 31 110 62 Z"),
        E(Y, 118, 112, 29, 14, -10),
        P((255, 170, 45), "M 112 100 C 110 70 112 44 126 24 C 126 39 131 45 139 48 C 137 34 141 19 153 9 "
                          "C 153 28 157 38 166 42 C 169 30 176 21 190 19 C 179 45 160 76 135 105 Z"),
        P(F, "M 126 40 C 128 58 128 78 124 96 C 132 80 138 62 140 46 Z"),
        P(F, "M 154 30 C 150 52 144 70 136 90 C 148 74 158 56 164 40 Z"),
        P(R, "M 146 80 C 141 62 131 55 119 50 C 131 48 139 50 145 56 C 141 45 136 38 129 30 "
             "C 147 38 157 55 156 78 Z"),
        E(Y, 151, 90, 12, 11),
        P((205, 165, 105), "M 160 88 L 179 93 L 160 98 Z"),
        E((40, 20, 20), 155, 87, 2.4, 2.4),
    ]


def _quadruped(body, legs, extra_back, head, face, eye_xy, tail):
    return tail + extra_back + [
        P(mul_col(legs[0], 0.8), "M 62 118 L 55 162 L 68 166 L 71 158 L 77 124 Z"),
        P(mul_col(legs[0], 0.8), "M 128 120 L 135 165 L 148 168 L 145 160 L 140 120 Z"),
        body,
        P(legs[0], "M 76 122 L 79 165 L 91 168 L 89 160 L 89 125 Z"),
        P(legs[0], "M 140 118 L 152 160 L 163 163 L 158 155 L 150 115 Z"),
    ] + head + face + [E((200, 20, 30), eye_xy[0], eye_xy[1], 2.6, 2.3)]


def _raikou():
    Y = (250, 205, 70); K = (45, 35, 50); Pu = (125, 85, 170); W = (225, 232, 255)
    body = P(Y, "M 50 110 C 50 85 75 75 105 78 C 130 80 146 86 150 100 C 152 120 140 130 110 132 "
                "C 85 134 55 130 50 110 Z")
    stripes = [P(K, "M 75 81 L 85 95 L 80 105 L 90 118 L 86 121 L 76 107 L 80 96 L 71 83 Z"),
               P(K, "M 100 80 L 108 95 L 104 106 L 112 120 L 108 123 L 99 108 L 103 96 L 96 81 Z"),
               P(K, "M 124 82 L 130 94 L 127 104 L 133 116 L 129 118 L 123 105 L 126 95 L 120 84 Z")]
    mane = [P(Pu, "M 58 86 C 50 60 74 48 90 57 C 95 38 121 38 126 57 C 142 48 166 60 152 82 "
                  "C 140 86 120 80 105 82 C 90 84 74 92 58 86 Z"),
            P((160, 120, 200), "M 75 70 C 80 60 92 58 98 64 C 104 54 116 54 120 64 C 112 66 90 70 75 70 Z")]
    tail = [P(W, "M 54 100 L 28 80 L 37 77 L 16 56 L 41 70 L 35 73 L 58 92 Z")]
    head = [P(Y, "M 140 90 C 145 72 165 68 178 78 C 188 85 190 98 182 104 C 172 110 155 108 145 104 Z")]
    face = [P(K, "M 158 76 C 170 72 183 78 188 88 L 175 86 Z"),
            P((50, 60, 120), "M 148 76 L 157 58 L 165 72 L 175 60 L 177 79 Z"),
            P((245, 245, 245), "M 176 104 L 180 113 L 183 103 Z")]
    q = _quadruped(body, [Y], mane, head, face, (171, 87), tail)
    return q[:5] + stripes + q[5:]


def _entei():
    Br = (196, 112, 62); Br2 = (170, 92, 52); C = (238, 228, 208); Yl = (240, 200, 90); K = (55, 45, 45)
    body = P(Br, "M 45 110 C 45 85 70 75 105 78 C 135 80 150 90 152 105 C 152 125 135 132 105 133 "
                 "C 75 134 48 130 45 110 Z")
    mane = [P(C, "M 52 90 L 58 64 L 72 78 L 80 52 L 93 73 L 104 46 L 113 71 L 126 50 L 131 75 L 147 60 "
                 "L 144 86 C 120 92 85 94 52 90 Z")]
    tail = [P(C, "M 48 102 C 32 96 24 84 27 68 C 35 80 44 88 56 92 Z")]
    head = [P(Br, "M 140 92 C 145 75 165 70 180 80 C 190 88 190 100 182 106 C 170 112 152 110 144 104 Z")]
    face = [P(Yl, "M 158 78 L 192 88 L 179 95 L 160 91 Z"),
            P((205, 205, 215), "M 147 79 L 154 57 L 162 72 L 170 53 L 175 77 Z"),
            P(C, "M 168 101 C 158 110 148 117 136 118 C 150 108 157 104 163 97 Z"),
            P(K, "M 66 160 L 54 160 L 55 166 L 68 166 Z"), P(K, "M 134 160 L 147 160 L 148 168 L 135 165 Z")]
    return _quadruped(body, [Br2], mane, head, face, (170, 88), tail)


def _suicune():
    B = (105, 192, 246); W = (242, 250, 255); Pu = (165, 115, 220); Pu2 = (135, 90, 200)
    body = P(B, "M 50 108 C 52 88 75 80 105 82 C 132 84 146 92 148 106 C 148 122 132 128 105 129 "
                "C 78 130 50 126 50 108 Z")
    ribbons = [P(Pu, "M 72 86 C 50 76 30 82 8 60 C 30 70 45 68 60 73 C 45 60 34 48 18 26 "
                     "C 45 48 62 62 84 82 Z"),
               P(Pu2, "M 75 84 C 86 60 112 54 138 70 C 122 72 106 78 96 90 Z")]
    tail = [P(W, "M 52 100 C 36 92 24 95 10 104 C 22 86 40 82 58 92 Z")]
    head = [P(B, "M 138 92 C 142 78 160 72 175 80 C 186 87 187 99 180 104 C 168 110 150 108 142 102 Z")]
    face = [P(W, "M 150 80 C 150 56 166 40 188 34 C 177 50 173 60 173 76 Z"),
            P((200, 240, 255), "M 160 72 L 166 66 L 172 72 L 166 78 Z")]
    diamonds = [P(W, "M 82 92 L 90 102 L 82 112 L 74 102 Z"), P(W, "M 110 92 L 118 102 L 110 112 L 102 102 Z")]
    q = _quadruped(body, [B], ribbons, head, face, (169, 89), tail)
    return q[:5] + diamonds + q[5:]


def _lugia():
    W = (236, 241, 252); Bl = (60, 92, 175); G = (190, 198, 222)
    return [
        P(W, "M 86 92 C 60 70 30 56 4 60 C 19 70 24 76 27 86 C 14 86 7 93 2 101 C 20 99 30 101 38 105 "
             "C 28 111 22 119 20 130 C 45 116 65 111 86 113 Z", mirror=True),
        S(G, "M 70 82 C 50 74 30 70 14 72", 2.0, mirror=True),
        S(G, "M 66 96 C 48 96 32 98 18 104", 2.0, mirror=True),
        P(W, "M 96 168 C 90 184 95 194 100 200 C 105 194 110 184 104 168 Z"),
        P(Bl, "M 100 186 L 88 196 L 100 192 L 112 196 Z"),
        P(W, "M 85 90 C 85 74 115 74 115 90 C 125 120 118 160 100 176 C 82 160 75 120 85 90 Z"),
        E(Bl, 100, 110, 9, 4.5), E(Bl, 100, 125, 8, 4), E(Bl, 100, 139, 7, 3.5),
        P(W, "M 92 86 C 90 66 92 51 100 40 C 108 51 110 66 108 86 Z"),
        P(Bl, "M 100 60 L 96 66 L 104 66 Z"), P(Bl, "M 100 70 L 96 76 L 104 76 Z"),
        P(W, "M 87 42 C 87 27 113 27 113 42 C 113 53 107 59 100 59 C 93 59 87 53 87 42 Z"),
        E(Bl, 93, 42, 4.6, 2.8, 20), E(Bl, 107, 42, 4.6, 2.8, -20),
        E((250, 250, 255), 93, 42, 1.6, 1.4), E((250, 250, 255), 107, 42, 1.6, 1.4),
    ]


def _hooh():
    R = (220, 50, 45); R2 = (180, 30, 35); Gd = (255, 205, 60); Gr = (70, 185, 100); W = (250, 248, 235)
    return [
        P(Gr, "M 96 116 C 70 132 46 160 16 190 C 42 176 58 168 74 160 C 64 174 58 186 54 199 "
              "C 76 178 92 156 106 128 Z"),
        P(W, "M 100 120 C 84 140 72 160 60 186 C 78 166 90 150 104 130 Z"),
        P(R2, "M 98 96 C 82 64 60 40 28 20 C 44 40 42 48 54 56 C 40 54 30 52 16 50 C 34 64 46 70 60 76 "
              "C 46 78 36 80 24 84 C 46 94 72 100 98 108 Z"),
        E(R, 120, 110, 30, 16, -12),
        E((255, 228, 140), 124, 117, 18, 7, -12),
        P(R, "M 108 98 C 103 62 100 30 112 2 C 116 22 119 28 126 36 C 126 22 131 12 142 5 "
             "C 139 28 141 38 147 48 C 152 38 159 31 170 28 C 161 56 150 80 132 104 Z"),
        P(Gd, "M 112 6 C 116 22 119 28 126 36 C 124 28 120 18 112 6 Z"),
        P(W, "M 142 5 C 139 22 140 32 144 42 C 146 30 146 18 142 5 Z"),
        P(Gr, "M 170 28 C 164 40 158 48 150 56 C 160 50 166 42 170 28 Z"),
        P(Gd, "M 146 80 C 140 62 130 52 112 46 C 128 58 132 66 136 74 C 125 66 114 64 102 65 "
              "C 120 75 130 81 142 87 Z"),
        E(R, 153, 90, 13, 12),
        P(Gd, "M 163 86 L 181 91 L 164 97 Z"),
        E((40, 20, 20), 157, 87, 2.6, 2.6),
    ]


def _groudon():
    R = (218, 62, 50); G = (192, 182, 170); W = (245, 245, 240); K = (35, 22, 22); Y = (255, 220, 70)
    return [
        P(G, "M 70 52 L 60 30 L 80 44 L 84 22 L 96 42 L 104 22 L 112 42 L 124 24 L 128 46 L 142 32 L 132 56 Z"),
        P(R, "M 46 86 C 24 102 18 122 23 138 L 40 132 C 38 117 46 106 60 99 Z", mirror=True),
        P(W, "M 22 138 L 18 148 L 27 141 L 30 151 L 34 140 L 40 147 L 40 132 Z", mirror=True),
        P(R, "M 60 60 C 60 34 140 34 140 60 C 160 90 165 140 146 170 L 132 192 L 111 176 L 89 176 "
             "L 68 192 L 54 170 C 35 140 40 90 60 60 Z"),
        P(G, "M 80 82 C 80 70 120 70 120 82 C 125 112 120 142 100 152 C 80 142 75 112 80 82 Z"),
        P(G, "M 55 72 L 32 58 L 52 88 Z", mirror=True),
        P(K, "M 58 84 L 49 112 L 54 113 L 63 86 Z", mirror=True),
        P(K, "M 66 150 L 60 172 L 65 173 L 71 151 Z", mirror=True),
        P(R, "M 74 52 C 71 26 129 26 126 52 C 121 64 79 64 74 52 Z"),
        P(G, "M 74 50 C 80 58 120 58 126 50 C 120 64 80 64 74 50 Z"),
        E(Y, 88, 45, 6, 3.6, 10), E(Y, 112, 45, 6, 3.6, -10),
        E(K, 89, 45, 2, 2.4), E(K, 111, 45, 2, 2.4),
        S(K, "M 92 56 C 96 58 104 58 108 56", 1.6),
    ]


def _kyogre():
    B = (42, 86, 205); B2 = (30, 60, 160); W = (238, 242, 250); R = (230, 45, 70); Y = (255, 225, 90)
    return [
        P(B2, "M 46 110 C 20 122 6 144 0 170 C 22 164 42 154 62 128 Z", mirror=True),
        S(R, "M 40 124 C 26 136 16 148 10 160", 2.4, mirror=True),
        P(B, "M 28 100 C 28 56 172 56 172 100 C 172 136 28 136 28 100 Z"),
        P(W, "M 48 112 C 70 132 130 132 152 112 C 130 120 70 120 48 112 Z"),
        P(B, "M 94 64 L 100 46 L 106 64 Z"),
        S(R, "M 52 86 C 62 72 76 70 84 80", 2.6, mirror=True),
        S(R, "M 60 98 C 72 90 82 92 88 100", 2.2, mirror=True),
        S(R, "M 92 70 C 96 66 104 66 108 70", 2.2),
        E(Y, 76, 96, 6, 4.5, -10), E(Y, 124, 96, 6, 4.5, 10),
        E((20, 20, 30), 77, 96, 2.3, 2.3), E((20, 20, 30), 123, 96, 2.3, 2.3),
    ]


def _rayquaza():
    G = (55, 165, 95); G2 = (40, 125, 70); Y = (250, 215, 60); R = (220, 50, 50)
    # corps serpentin généré procéduralement
    layers = []
    pts = []
    n = 80
    for i in range(n + 1):
        t = i / n
        x = 100 + 62 * math.sin(t * math.pi * 2.2 + 3.6) * (0.55 + 0.45 * t) + 30 * (t - 0.5)
        y = 186 - 148 * t + 10 * math.sin(t * math.pi * 4.4)
        pts.append((x, y))
    for i, (x, y) in enumerate(pts):
        r = 3.5 + 10.5 * (i / n) ** 0.6
        layers.append(E(G2 if i % 2 else G, x, y, r, r))
        if i % 9 == 4 and i > 6:
            layers.append(E(Y, x, y, r * 0.55, r * 0.35, 30))
    hx, hy = pts[-1]
    layers += [
        P(G, f"M {hx - 8} {hy + 6} L {hx - 32} {hy - 22} L {hx - 4} {hy - 6} Z"),
        P(G, f"M {hx - 4} {hy - 2} L {hx - 34} {hy - 34} L {hx + 2} {hy - 10} Z"),
        P(G, f"M {hx - 10} {hy - 10} C {hx - 6} {hy - 22} {hx + 18} {hy - 20} {hx + 28} {hy - 6} "
             f"C {hx + 30} {hy + 4} {hx + 10} {hy + 12} {hx - 8} {hy + 8} Z"),
        S(Y, f"M {hx - 2} {hy + 2} C {hx + 8} {hy + 6} {hx + 18} {hy + 4} {hx + 26} {hy - 2}", 1.8),
        E((255, 230, 80), hx + 10, hy - 9, 3, 2.2),
        E((20, 20, 20), hx + 10.5, hy - 9, 1.2, 1.6),
        S(R, f"M {hx - 6} {hy - 14} L {hx + 6} {hy - 14}", 1.6),
    ]
    return layers


def _mew():
    Pk = (255, 175, 212); Pk2 = (240, 140, 190); Bl = (70, 140, 230)
    return [
        P(Pk2, "M 112 142 C 150 150 176 120 170 80 C 166 58 176 44 188 46 C 178 52 176 64 180 82 "
               "C 186 128 156 160 110 152 Z"),
        E(Pk, 186, 48, 7, 10, 20),
        E(Pk, 100, 130, 19, 24),
        E(Pk2, 86, 158, 7, 10, 20), E(Pk2, 114, 158, 7, 10, -20),
        P(Pk, "M 82 120 C 72 118 66 124 64 132 C 72 128 78 128 86 128 Z", mirror=True),
        P(Pk, "M 72 64 L 64 34 L 88 54 Z", mirror=True),
        E(Pk, 100, 80, 34, 30),
        E((255, 255, 255), 86, 82, 8, 11), E((255, 255, 255), 114, 82, 8, 11),
        E(Bl, 88, 84, 6, 9), E(Bl, 112, 84, 6, 9),
        E((255, 255, 255), 86, 80, 2.2, 2.6), E((255, 255, 255), 110, 80, 2.2, 2.6),
        S((200, 90, 140), "M 96 98 C 98 100 102 100 104 98", 1.4),
    ]


def _mewtwo():
    G = (206, 196, 226); Pu = (150, 88, 196); Gd = (170, 160, 195)
    return [
        P(Pu, "M 116 156 C 150 160 176 148 182 120 C 186 100 176 86 166 84 C 172 100 170 118 156 128 "
              "C 142 138 126 140 112 140 Z"),
        P(G, "M 82 150 C 70 160 66 178 70 196 L 86 196 C 86 180 90 168 96 160 Z", mirror=True),
        P(G, "M 84 92 C 64 100 56 118 52 138 C 58 140 62 138 64 134 C 66 120 74 110 86 106 Z", mirror=True),
        E(G, 56, 140, 5, 5, mirror=True),
        P(G, "M 84 80 C 84 70 116 70 116 80 C 124 110 122 140 112 158 L 88 158 C 78 140 76 110 84 80 Z"),
        P(Pu, "M 88 120 C 90 112 110 112 112 120 C 114 138 110 152 100 156 C 90 152 86 138 88 120 Z"),
        S(Gd, "M 104 50 C 116 54 118 66 110 78", 4.2),
        P(G, "M 90 76 L 110 76 L 108 84 L 92 84 Z"),
        P(G, "M 86 46 C 86 28 114 28 114 46 C 114 57 108 63 100 63 C 92 63 86 57 86 46 Z"),
        P(G, "M 88 34 L 82 22 L 94 30 Z", mirror=True),
        E(Pu, 93, 46, 4, 2.4, 15), E(Pu, 107, 46, 4, 2.4, -15),
        E((255, 255, 255), 93, 46, 1.3, 1.1), E((255, 255, 255), 107, 46, 1.3, 1.1),
    ]


CREATURES = {
    "articuno": _articuno, "zapdos": _zapdos, "moltres": _moltres,
    "raikou": _raikou, "entei": _entei, "suicune": _suicune,
    "lugia": _lugia, "hooh": _hooh,
    "groudon": _groudon, "kyogre": _kyogre, "rayquaza": _rayquaza,
    "mew": _mew, "mewtwo": _mewtwo,
}


@lru_cache(maxsize=64)
def creature(key, size, flip=False):
    fn = CREATURES.get(key)
    if fn is None:
        return pygame.Surface((size, size), pygame.SRCALPHA)
    s = render_layers(fn(), size)
    if flip:
        s = pygame.transform.flip(s, True, False)
    return s


@lru_cache(maxsize=64)
def creature_silhouette(key, size, color):
    s = creature(key, size).copy()
    s.fill(color + (255,), special_flags=pygame.BLEND_RGBA_MIN)
    s.fill(color + (0,), special_flags=pygame.BLEND_RGB_MAX)
    return s


@lru_cache(maxsize=96)
def creature_aura(key, size, color, radius=10, intensity=1.0):
    """Halo coloré autour de la créature, prémultiplié (fond noir) pour BLEND_ADD."""
    base = creature(key, size)
    pad = radius * 2
    W = size + pad * 2
    a = np.zeros((W, W), dtype=np.float32)
    a[pad:pad + size, pad:pad + size] = pygame.surfarray.array_alpha(base).astype(np.float32) / 255.0
    m = pygame.Surface((W, W))
    v = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    pygame.surfarray.blit_array(m, np.stack([v, v, v], axis=-1))
    m = blur(m, radius)
    arr = pygame.surfarray.array3d(m).astype(np.float32)[:, :, 0] / 255.0
    arr = np.clip(arr * 2.2 * intensity, 0, 1)
    out = pygame.Surface((W, W))
    rgb = np.stack([arr * color[0], arr * color[1], arr * color[2]], axis=-1).astype(np.uint8)
    pygame.surfarray.blit_array(out, rgb)
    return out


def sphere_shade(surf, cx, cy, r, light=(-0.45, -0.55, 0.70), amb=0.42, spec=0.55):
    """Ombrage sphérique (diffus + spéculaire) d'un disque déjà dessiné."""
    w, h = surf.get_size()
    rgb = pygame.surfarray.pixels3d(surf)
    xs = (np.arange(w) + 0.5 - cx) / r
    ys = (np.arange(h) + 0.5 - cy) / r
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    d2 = X * X + Y * Y
    inside = d2 < 1.0
    Z = np.sqrt(np.clip(1.0 - d2, 0, 1))
    L = np.array(light, dtype=np.float32)
    L = L / np.linalg.norm(L)
    diff = np.clip(X * L[0] + Y * L[1] + Z * L[2], 0, 1)
    # spéculaire (Blinn) : demi-vecteur avec la vue (0,0,1)
    H = L + np.array([0, 0, 1.0])
    H = H / np.linalg.norm(H)
    sp = np.clip(X * H[0] + Y * H[1] + Z * H[2], 0, 1) ** 40 * spec
    k = amb + (1.0 - amb) * diff
    f = rgb.astype(np.float32) * k[:, :, None] + (sp * 255)[:, :, None]
    rim = np.clip((d2 - 0.82) / 0.18, 0, 1) * 0.25
    f = f * (1 - rim[:, :, None])
    out = np.where(inside[:, :, None], np.clip(f, 0, 255), rgb)
    rgb[:] = out.astype(np.uint8)
    del rgb


# ==========================================================================
# Pokéball
# ==========================================================================
def draw_pokeball(surf, cx, cy, r, angle=0.0, open_=0.0, glow_btn=0.0, top=(230, 30, 40),
                  bottom=(245, 245, 245), band=(25, 25, 30), button=(250, 250, 250), shading=True):
    """Pokéball vue de dessus, inclinable (angle en degrés), capot ouvrable."""
    size = int(r * 2 + 8)
    k = 3
    S = size * k
    tmp = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S / 2
    R = r * k
    # ombre interne / fond
    pygame.draw.circle(tmp, band, (c, c), R)
    pygame.draw.circle(tmp, bottom, (c, c), R - 2 * k)
    # moitié haute
    top_rect = pygame.Rect(0, 0, S, c - R * 0.09)
    hs = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(hs, top, (c, c), R - 2 * k)
    hs.fill((0, 0, 0, 0), pygame.Rect(0, int(c - R * 0.09), S, S))
    if open_ > 0.01:
        # intérieur lumineux visible quand le capot s'ouvre
        inner = pygame.Surface((S, S), pygame.SRCALPHA)
        pygame.draw.circle(inner, (255, 250, 220), (c, c), R * 0.8)
        tmp.blit(inner, (0, 0))
        off = int(-R * 0.55 * open_)
        tmp.blit(hs, (0, off))
    else:
        tmp.blit(hs, (0, 0))
    # bande noire
    pygame.draw.rect(tmp, band, pygame.Rect(c - R + 2 * k, c - R * 0.09, (R - 2 * k) * 2, R * 0.18))
    # bouton
    pygame.draw.circle(tmp, band, (c, c), R * 0.30)
    bc = lerp_col(button, (255, 255, 160), glow_btn)
    pygame.draw.circle(tmp, bc, (c, c), R * 0.21)
    pygame.draw.circle(tmp, mul_col(bc, 0.82), (c, c), R * 0.21, max(1, k))
    if shading:
        sphere_shade(tmp, c, c, R - 1)
    img = pygame.transform.smoothscale(tmp, (size, size))
    if angle:
        img = pygame.transform.rotozoom(img, angle, 1.0)
    surf.blit(img, (cx - img.get_width() / 2, cy - img.get_height() / 2))


@lru_cache(maxsize=32)
def pokeball_sprite(r, glow_btn=0.0, open_=0.0, top=(230, 30, 40)):
    size = int(r * 2 + 10)
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    draw_pokeball(s, size / 2, size / 2, r, 0, open_, glow_btn, top=top)
    return s


@lru_cache(maxsize=16)
def voltorb_cap(r, flash=False):
    """Chapeau de bumper façon Voltorbe (vu de dessus)."""
    size = int(r * 2 + 6)
    k = 3
    S = size * k
    tmp = pygame.Surface((S, S), pygame.SRCALPHA)
    c = S / 2
    R = r * k
    red = (255, 70, 70) if flash else (215, 35, 40)
    pygame.draw.circle(tmp, (20, 20, 25), (c, c), R)
    pygame.draw.circle(tmp, (250, 250, 250) if not flash else (255, 255, 230), (c, c), R - 2 * k)
    half = pygame.Surface((S, S), pygame.SRCALPHA)
    pygame.draw.circle(half, red, (c, c), R - 2 * k)
    half.fill((0, 0, 0, 0), pygame.Rect(0, int(c), S, S))
    tmp.blit(half, (0, 0))
    pygame.draw.rect(tmp, (20, 20, 25), pygame.Rect(c - R, c - R * 0.06, 2 * R, R * 0.12))
    # yeux en colère sur la moitié rouge
    for sx in (-1, 1):
        ex, ey = c + sx * R * 0.36, c - R * 0.36
        pygame.draw.ellipse(tmp, (255, 255, 255), pygame.Rect(ex - R * 0.17, ey - R * 0.13, R * 0.34, R * 0.26))
        pygame.draw.circle(tmp, (15, 15, 15), (ex + sx * R * 0.03, ey + R * 0.02), R * 0.07)
        pygame.draw.line(tmp, (15, 15, 15), (ex - R * 0.2 * sx, ey - R * 0.2), (ex + R * 0.16 * sx, ey - R * 0.1),
                         max(2, int(R * 0.07)))
    sphere_shade(tmp, c, c, R - 1, amb=0.5)
    return pygame.transform.smoothscale(tmp, (size, size))


# ==========================================================================
# Icônes de types
# ==========================================================================
def type_icon(ptype, size, color=(255, 255, 255)):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    k = size / 100.0
    c = color + (255,)

    def poly(pts):
        gfx.filled_polygon(s, [(int(x * k), int(y * k)) for x, y in pts], c)
        gfx.aapolygon(s, [(int(x * k), int(y * k)) for x, y in pts], c)

    t = ptype
    if t == "Feu":
        for pl in path_points("M 50 5 C 60 30 85 40 80 70 C 78 88 64 96 50 96 C 34 96 20 86 20 68 "
                              "C 20 50 34 44 36 26 C 44 36 46 44 48 50 C 56 36 54 20 50 5 Z"):
            poly(pl)
    elif t == "Eau":
        for pl in path_points("M 50 4 C 62 30 82 48 82 66 C 82 84 68 96 50 96 C 32 96 18 84 18 66 "
                              "C 18 48 38 30 50 4 Z"):
            poly(pl)
    elif t == "Électrik":
        poly([(60, 2), (22, 56), (46, 56), (36, 98), (78, 40), (54, 40), (66, 2)])
    elif t == "Glace":
        for a in range(0, 180, 60):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            pygame.draw.line(s, c, (50 * k - 44 * k * ca, 50 * k - 44 * k * sa),
                             (50 * k + 44 * k * ca, 50 * k + 44 * k * sa), max(2, int(9 * k)))
        pygame.draw.circle(s, c, (int(50 * k), int(50 * k)), int(12 * k))
    elif t == "Plante":
        for pl in path_points("M 15 85 C 15 40 50 10 90 10 C 90 55 60 88 15 85 Z"):
            poly(pl)
    elif t == "Psy":
        pygame.draw.circle(s, c, (int(50 * k), int(50 * k)), int(40 * k), max(2, int(10 * k)))
        pygame.draw.circle(s, c, (int(50 * k), int(50 * k)), int(14 * k))
    elif t == "Dragon":
        poly([(50, 4), (66, 36), (96, 30), (74, 58), (84, 96), (50, 74), (16, 96), (26, 58), (4, 30), (34, 36)])
    elif t == "Sol":
        poly([(4, 80), (30, 30), (46, 52), (64, 18), (96, 80)])
    elif t == "Vol":
        for pl in path_points("M 10 70 C 30 30 60 20 92 18 C 76 30 70 40 66 52 C 56 52 46 60 40 72 Z"):
            poly(pl)
    elif t == "Roche":
        poly([(20, 80), (12, 44), (40, 14), (76, 18), (90, 52), (72, 86)])
    elif t == "Spectre":
        for pl in path_points("M 20 90 L 20 45 C 20 15 80 15 80 45 L 80 90 L 68 78 L 56 90 L 44 78 L 32 90 Z"):
            poly(pl)
    elif t == "Combat":
        pygame.draw.rect(s, c, pygame.Rect(18 * k, 30 * k, 64 * k, 52 * k), border_radius=int(14 * k))
    elif t == "Ténèbres":
        pygame.draw.circle(s, c, (int(50 * k), int(50 * k)), int(40 * k))
        pygame.draw.circle(s, (0, 0, 0, 0), (int(64 * k), int(40 * k)), int(34 * k))
    elif t == "Fée":
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = 46 if i % 2 == 0 else 20
            pts.append((50 + math.cos(a) * rr, 52 + math.sin(a) * rr))
        poly(pts)
    elif t == "Insecte":
        pygame.draw.ellipse(s, c, pygame.Rect(26 * k, 20 * k, 48 * k, 66 * k))
    elif t == "Poison":
        pygame.draw.circle(s, c, (int(50 * k), int(56 * k)), int(32 * k))
        pygame.draw.circle(s, c, (int(70 * k), int(20 * k)), int(12 * k))
    elif t == "Acier":
        pts = [(50 + math.cos(math.radians(a)) * 44, 50 + math.sin(math.radians(a)) * 44) for a in range(0, 360, 60)]
        poly(pts)
        pygame.draw.circle(s, (0, 0, 0, 0), (int(50 * k), int(50 * k)), int(16 * k))
    else:
        pygame.draw.circle(s, c, (int(50 * k), int(50 * k)), int(36 * k))
    return s


# ==========================================================================
# Logo
# ==========================================================================
def logo(width, subtitle=True):
    from .assets import text
    big = text("POKÉMON", "black", int(width * 0.2), (255, 214, 30), outline=(40, 80, 170),
               outline_w=max(3, int(width * 0.018)), shadow=(4, 6, (15, 30, 80)),
               gradient=((255, 238, 90), (255, 176, 20)))
    w = width
    h = big.get_height() + (int(width * 0.13) if subtitle else 0)
    s = pygame.Surface((max(w, big.get_width()), h), pygame.SRCALPHA)
    s.blit(big, ((s.get_width() - big.get_width()) // 2, 0))
    if subtitle:
        sub = text("PINBALL — LÉGENDES", "digital", int(width * 0.07), (235, 240, 255),
                   outline=(30, 40, 80), outline_w=3, gradient=((255, 255, 255), (170, 190, 230)))
        s.blit(sub, ((s.get_width() - sub.get_width()) // 2, big.get_height() - int(width * 0.045)))
    return s
