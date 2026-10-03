"""Bibliothèque d'effets pour l'écran LCD (fonds animés, textes, particules)."""
import math
import random

import pygame

from .assets import text, glow, mul_col, lerp_col


def ease_out_back(t, s=1.70158):
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = max(0.0, min(1.0, t))
    return t * t * t


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


class Sparks:
    """Système de particules léger pour l'écran."""

    def __init__(self):
        self.p = []

    def burst(self, x, y, n=40, cols=None, speed=(120, 520), life=(0.5, 1.3), g=260, size=(2, 5)):
        cols = cols or [(255, 230, 90), (255, 255, 255), (255, 140, 60)]
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(*speed)
            self.p.append([x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(*life), 0.0,
                           random.choice(cols), random.uniform(*size), g])

    def rain(self, w, n, cols, vy=(60, 200), size=(1, 3)):
        for _ in range(n):
            self.p.append([random.uniform(0, w), -5, random.uniform(-20, 20), random.uniform(*vy),
                           random.uniform(2, 4), 0.0, random.choice(cols), random.uniform(*size), 0])

    def update(self, dt):
        out = []
        for q in self.p:
            q[5] += dt
            if q[5] < q[4]:
                q[3] += q[8] * dt
                q[0] += q[2] * dt
                q[1] += q[3] * dt
                q[2] *= (1 - 0.8 * dt)
                out.append(q)
        self.p = out

    def draw(self, surf, additive=True):
        for x, y, vx, vy, life, age, col, size, g in self.p:
            k = 1 - age / life
            c = mul_col(col, k)
            r = max(1, int(size * (0.5 + 0.5 * k)))
            if additive:
                gl = glow(r * 3, c, falloff=1.6)
                surf.blit(gl, (x - r * 3, y - r * 3), special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(surf, c, (int(x), int(y)), r)


def rays(surf, cx, cy, col, t, n=16, length=900, width=0.12, alpha=60):
    w, h = surf.get_size()
    lay = pygame.Surface((w, h), pygame.SRCALPHA)
    for i in range(n):
        a = t + i * 2 * math.pi / n
        p = [(cx, cy), (cx + math.cos(a - width) * length, cy + math.sin(a - width) * length),
             (cx + math.cos(a + width) * length, cy + math.sin(a + width) * length)]
        pygame.draw.polygon(lay, col + (alpha,), p)
    surf.blit(lay, (0, 0))


def radial_bg(surf, inner, outer):
    w, h = surf.get_size()
    surf.fill(outer)
    g = glow(int(max(w, h) * 0.65), inner, falloff=1.3)
    surf.blit(g, (w / 2 - g.get_width() / 2, h / 2 - g.get_height() / 2), special_flags=pygame.BLEND_ADD)


def big_text(s, size, col, outline=(10, 10, 25), ow=5, kind="black", glow_col=None, grad=None):
    return text(s, kind, size, col, outline=outline, outline_w=ow, shadow=(4, 6, (0, 0, 0)),
                gradient=grad)


def slam(surf, img, cx, cy, t, dur=0.35, start=3.0):
    """Texte qui s'écrase à l'écran (échelle décroissante avec rebond)."""
    if t <= 0:
        return
    k = ease_out_back(t / dur) if t < dur else 1.0
    sc = start + (1.0 - start) * k if t < dur else 1.0
    if t < dur:
        sc = max(0.05, start - (start - 1.0) * ease_out(t / dur))
    im = img if abs(sc - 1.0) < 0.01 else pygame.transform.rotozoom(img, 0, sc)
    a = int(255 * min(1.0, t / (dur * 0.6)))
    im.set_alpha(a)
    surf.blit(im, (cx - im.get_width() / 2, cy - im.get_height() / 2))
    img.set_alpha(255)


def shine(surf, rect, t, speed=1.6, col=(255, 255, 255)):
    """Reflet doux qui balaie un rectangle (bande dégradée)."""
    x0, y0, w, h = rect
    p = (t * speed) % 1.6 - 0.3
    if p < -0.2 or p > 1.2:
        return
    lay = pygame.Surface((int(w), int(h)))
    lay.fill((0, 0, 0))
    cx = p * w
    for i, a in enumerate((10, 18, 26, 18, 10)):
        off = (i - 2) * 16
        pts = [(cx + off - 8, 0), (cx + off + 8, 0), (cx + off - h * 0.5 + 8, h), (cx + off - h * 0.5 - 8, h)]
        pygame.draw.polygon(lay, (a * col[0] // 255, a * col[1] // 255, a * col[2] // 255), pts)
    surf.blit(lay, (x0, y0), special_flags=pygame.BLEND_ADD)


def hp_bar(surf, x, y, w, h, frac, label="PV"):
    frac = max(0.0, min(1.0, frac))
    col = (60, 220, 90) if frac > 0.5 else ((250, 200, 40) if frac > 0.2 else (240, 60, 50))
    pygame.draw.rect(surf, (20, 20, 25), pygame.Rect(x - 3, y - 3, w + 6, h + 6), border_radius=6)
    pygame.draw.rect(surf, (70, 70, 80), pygame.Rect(x, y, w, h), border_radius=4)
    if frac > 0:
        pygame.draw.rect(surf, col, pygame.Rect(x, y, int(w * frac), h), border_radius=4)
        pygame.draw.rect(surf, lerp_col(col, (255, 255, 255), 0.45),
                         pygame.Rect(x + 2, y + 2, max(0, int(w * frac) - 4), max(1, h // 3)), border_radius=3)
    lab = text(label, "black", max(10, h), (255, 220, 60), outline=(0, 0, 0), outline_w=2)
    surf.blit(lab, (x - lab.get_width() - 6, y + h / 2 - lab.get_height() / 2))


def stripes_wipe(surf, t, col=(0, 0, 0), n=12):
    """Transition de combat façon jeux Pokémon (bandes alternées)."""
    w, h = surf.get_size()
    bh = h / n
    k = ease_out(t)
    for i in range(n):
        ww = w * k
        if i % 2 == 0:
            pygame.draw.rect(surf, col, pygame.Rect(0, i * bh, ww, bh + 1))
        else:
            pygame.draw.rect(surf, col, pygame.Rect(w - ww, i * bh, ww, bh + 1))


def textbox(surf, rect, msg, t, cps=40, col=(30, 30, 40)):
    """Boîte de dialogue façon Pokémon avec effet machine à écrire."""
    x, y, w, h = rect
    pygame.draw.rect(surf, (250, 250, 250), pygame.Rect(x, y, w, h), border_radius=10)
    pygame.draw.rect(surf, (60, 90, 170), pygame.Rect(x, y, w, h), 5, border_radius=10)
    pygame.draw.rect(surf, (200, 210, 230), pygame.Rect(x + 7, y + 7, w - 14, h - 14), 2, border_radius=8)
    n = int(t * cps)
    shown = msg[:n]
    lines = shown.split("\n")
    for i, ln in enumerate(lines):
        im = text(ln, "bold", int(h * 0.26), col)
        surf.blit(im, (x + 22, y + 14 + i * h * 0.36))
    if n >= len(msg) and int(t * 3) % 2 == 0:
        pygame.draw.polygon(surf, (200, 40, 40), [(x + w - 34, y + h - 26), (x + w - 20, y + h - 26),
                                                  (x + w - 27, y + h - 16)])
