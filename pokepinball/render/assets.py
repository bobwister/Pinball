"""Ressources graphiques partagées : polices, textes stylisés, dégradés, halos."""
import math
from functools import lru_cache

import numpy as np
import pygame

_FONT_FILES = {
    "black": ["segoeuiblack", "arialblack", "impact"],
    "bold": ["segoeuibold", "arialbold", "verdanabold"],
    "semi": ["segoeuisemibold", "segoeui", "arial"],
    "digital": ["bahnschrift", "segoeuisemibold", "arial"],
    "impact": ["impact", "arialblack"],
    "mono": ["consolas", "couriernew"],
}
_font_cache = {}


def font(kind, size):
    key = (kind, int(size))
    f = _font_cache.get(key)
    if f is None:
        path = None
        for name in _FONT_FILES.get(kind, ["arial"]):
            path = pygame.font.match_font(name)
            if path:
                break
        f = pygame.font.Font(path, int(size))
        _font_cache[key] = f
    return f


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_col(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def mul_col(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def add_col(c, d):
    return tuple(max(0, min(255, int(v + d))) for v in c[:3])


# --------------------------------------------------------------------------
# Textes
# --------------------------------------------------------------------------
_text_cache = {}


def text(s, kind, size, color, outline=None, outline_w=0, shadow=None, glow=None, gradient=None,
         cache=True):
    """Rend un texte avec contour épais, ombre portée, dégradé vertical et halo."""
    key = (s, kind, size, color, outline, outline_w, shadow, glow, gradient)
    if cache and key in _text_cache:
        return _text_cache[key]
    f = font(kind, size)
    base = f.render(s, True, color)
    if gradient:
        g = gradient_surface(base.get_width(), base.get_height(), gradient[0], gradient[1])
        ga = pygame.surfarray.pixels_alpha(g)
        ga[:] = pygame.surfarray.array_alpha(base)
        del ga
        base = g
    pad = outline_w + (max(abs(shadow[0]), abs(shadow[1])) if shadow else 0) + (glow[1] if glow else 0) + 2
    w, h = base.get_width() + pad * 2, base.get_height() + pad * 2
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if glow:
        gcol, grad = glow
        gl = f.render(s, True, gcol)
        gsurf = pygame.Surface((w, h), pygame.SRCALPHA)
        gsurf.blit(gl, (pad, pad))
        gsurf = blur(gsurf, max(2, grad // 2))
        out.blit(gsurf, (0, 0))
        out.blit(gsurf, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    if shadow:
        sx, sy, scol = shadow
        sh = f.render(s, True, scol)
        if outline_w:
            for dx, dy in _ring(outline_w):
                out.blit(sh, (pad + dx + sx, pad + dy + sy))
        else:
            out.blit(sh, (pad + sx, pad + sy))
    if outline and outline_w:
        ol = f.render(s, True, outline)
        for dx, dy in _ring(outline_w):
            out.blit(ol, (pad + dx, pad + dy))
    out.blit(base, (pad, pad))
    if cache:
        if len(_text_cache) > 3000:
            _text_cache.clear()
        _text_cache[key] = out
    return out


@lru_cache(maxsize=64)
def _ring(r):
    pts = []
    n = max(8, int(r * 6))
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((int(round(math.cos(a) * r)), int(round(math.sin(a) * r))))
    for rr in range(1, r):
        for i in range(8):
            a = 2 * math.pi * i / 8
            pts.append((int(round(math.cos(a) * rr)), int(round(math.sin(a) * rr))))
    return tuple(set(pts))


def blit_center(dst, src, x, y):
    dst.blit(src, (int(x - src.get_width() / 2), int(y - src.get_height() / 2)))


# --------------------------------------------------------------------------
# Dégradés et flous
# --------------------------------------------------------------------------
def gradient_surface(w, h, top, bottom, horizontal=False):
    w, h = max(1, int(w)), max(1, int(h))
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    n = w if horizontal else h
    t = np.linspace(0.0, 1.0, n)[:, None]
    c1 = np.array(top[:3] + ((top[3],) if len(top) > 3 else (255,)), dtype=np.float32)
    c2 = np.array(bottom[:3] + ((bottom[3],) if len(bottom) > 3 else (255,)), dtype=np.float32)
    cols = (c1 + (c2 - c1) * t).astype(np.uint8)
    rgb = pygame.surfarray.pixels3d(surf)
    a = pygame.surfarray.pixels_alpha(surf)
    if horizontal:
        rgb[:, :, :] = cols[:, None, :3]
        a[:, :] = cols[:, None, 3]
    else:
        rgb[:, :, :] = cols[None, :, :3]
        a[:, :] = cols[None, :, 3]
    del rgb, a
    return surf


def blur(surf, radius):
    """Flou rapide par réduction/agrandissement successifs."""
    if radius <= 0:
        return surf.copy()
    w, h = surf.get_size()
    k = max(1, int(radius))
    sw, sh = max(1, w // k), max(1, h // k)
    small = pygame.transform.smoothscale(surf, (sw, sh))
    small = pygame.transform.smoothscale(small, (max(1, sw // 2 + 1), max(1, sh // 2 + 1)))
    return pygame.transform.smoothscale(small, (w, h))


@lru_cache(maxsize=256)
def _glow_white(r, falloff, core):
    size = r * 2 + 1
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    d = np.sqrt(x * x + y * y) / r
    k = np.clip(1.0 - d, 0.0, 1.0) ** falloff
    if core > 0:
        k = np.clip(k + core * np.clip(1.0 - d * 3, 0, 1), 0, 1)
    v = (k * 255).astype(np.uint8).T
    surf = pygame.Surface((size, size))
    pygame.surfarray.blit_array(surf, np.stack([v.T, v.T, v.T], axis=-1))
    return surf


_glow_cache = {}


def glow(radius, color, falloff=2.0, core=0.0):
    """Sprite de halo radial (additif). Couleur quantifiée pour un cache efficace."""
    r = max(1, int(radius))
    q = tuple(min(255, (int(c) + 7) // 16 * 16) for c in color[:3])
    key = (r, q, falloff, core)
    s = _glow_cache.get(key)
    if s is None:
        s = _glow_white(r, falloff, core).copy()
        s.fill(q, special_flags=pygame.BLEND_MULT)
        if len(_glow_cache) > 3000:
            _glow_cache.clear()
        _glow_cache[key] = s
    return s


@lru_cache(maxsize=256)
def soft_circle(radius, color, alpha=255, edge=1.5):
    """Disque antialiasé (SRCALPHA)."""
    r = max(1, radius)
    size = int(math.ceil(r * 2 + 4))
    c = size / 2.0
    y, x = np.ogrid[0:size, 0:size]
    d = np.sqrt((x + 0.5 - c) ** 2 + (y + 0.5 - c) ** 2)
    a = np.clip((r - d) / edge + 0.5, 0, 1) * alpha
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    surf.fill(color[:3] + (0,))
    pa = pygame.surfarray.pixels_alpha(surf)
    pa[:, :] = a.T.astype(np.uint8)
    del pa
    return surf


def aa_polygon(surf, color, pts, width=0):
    import pygame.gfxdraw as gfx
    ipts = [(int(round(x)), int(round(y))) for x, y in pts]
    if len(ipts) < 3:
        return
    if width == 0:
        gfx.filled_polygon(surf, ipts, color)
        gfx.aapolygon(surf, ipts, color)
    else:
        pygame.draw.polygon(surf, color, ipts, width)


def aa_circle(surf, color, center, r):
    import pygame.gfxdraw as gfx
    x, y = int(round(center[0])), int(round(center[1]))
    r = int(round(r))
    if r <= 0:
        return
    gfx.filled_circle(surf, x, y, r, color)
    gfx.aacircle(surf, x, y, r, color)


def thick_line(surf, color, p1, p2, width):
    """Ligne épaisse antialiasée (polygone + extrémités rondes)."""
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L * width / 2, dx / L * width / 2
    aa_polygon(surf, color, [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])
    aa_circle(surf, color, p1, width / 2)
    aa_circle(surf, color, p2, width / 2)


def noise_texture(w, h, amount=10, seed=1):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amount, (w, h)).astype(np.int16)
    surf = pygame.Surface((w, h))
    arr = np.clip(128 + n, 0, 255).astype(np.uint8)
    pygame.surfarray.blit_array(surf, np.stack([arr] * 3, axis=-1))
    return surf


def bezier(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0]
        y = u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]
        pts.append((x, y))
    return pts


def tint(surf, color):
    """Copie teintée (multiplication)."""
    s = surf.copy()
    s.fill(color[:3] + (255,), special_flags=pygame.BLEND_RGBA_MULT)
    return s
