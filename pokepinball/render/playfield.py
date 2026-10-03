"""Rendu dynamique du plateau : lampes, éléments animés, billes, bloom, effets."""
import math
import random

import pygame

from ..config import PF_SCALE, PF_PIX_W, PF_PIX_H, BALL_R
from .assets import glow, soft_circle, text, mul_col, lerp_col, aa_polygon, thick_line
from . import art
from .art import sphere_shade
from .layout import INSERTS, RING_C
from .playfield_static import StaticLayers

S = PF_SCALE


def P(x, y):
    return (x * S, y * S)


# --------------------------------------------------------------------------
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max", "col", "size", "kind", "g")

    def __init__(self, x, y, vx, vy, life, col, size, kind="spark", g=0.0):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max = life
        self.col = col
        self.size = size
        self.kind = kind
        self.g = g


class Popup:
    def __init__(self, x, y, txt, col):
        self.x, self.y = x, y
        self.img = text(txt, "black", 15, col, outline=(10, 10, 20), outline_w=2)
        self.t = 0.0


# --------------------------------------------------------------------------
def make_ball_sprite(r_px):
    k = 4
    size = int(math.ceil(r_px * 2 + 2))
    S2 = size * k
    s = pygame.Surface((S2, S2), pygame.SRCALPHA)
    c = S2 / 2
    R = r_px * k
    # acier poli : environnement sombre en bas, clair en haut
    for i in range(int(R), 0, -1):
        t = i / R
        col = lerp_col((215, 220, 235), (95, 100, 120), t)
        pygame.draw.circle(s, col, (c, c + R * 0.12 * (1 - t)), i)
    pygame.draw.circle(s, (0, 0, 0, 0), (c, c), R + 4, 4)
    mask = pygame.Surface((S2, S2), pygame.SRCALPHA)
    pygame.draw.circle(mask, (255, 255, 255, 255), (c, c), R)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    sphere_shade(s, c, c, R, amb=0.55, spec=0.9)
    # reflet de fenêtre (bandeau lumineux)
    hl = soft_circle(R * 0.28, (255, 255, 255), 230, edge=R * 0.18)
    s.blit(hl, (c - R * 0.38 - hl.get_width() / 2, c - R * 0.42 - hl.get_height() / 2))
    band = pygame.Surface((S2, S2), pygame.SRCALPHA)
    pygame.draw.ellipse(band, (255, 255, 255, 50), pygame.Rect(c - R * 0.8, c + R * 0.25, R * 1.6, R * 0.35))
    band.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    s.blit(band, (0, 0))
    return pygame.transform.smoothscale(s, (size, size))


def make_flipper_sprite(fl, color=(248, 248, 252), rubber=(215, 30, 40)):
    """Flipper dessiné horizontalement, pivot au centre du sprite."""
    k = 4
    L = fl.length * S
    r1, r2 = fl.r1 * S, fl.r2 * S
    half = int(math.ceil(L + r2 + 3))
    size = half * 2
    S2 = size * k
    s = pygame.Surface((S2, S2), pygame.SRCALPHA)
    c = S2 / 2

    def shape(rr1, rr2, col):
        b = (rr1 - rr2) / L
        a = math.sqrt(max(0.0, 1 - b * b))
        pts = []
        for i in range(0, 181, 6):
            ang = math.radians(90 + i)
            pts.append((c + math.cos(ang) * rr1 * k, c + math.sin(ang) * rr1 * k))
        for i in range(0, 181, 6):
            ang = math.radians(-90 + i)
            pts.append((c + L * k + math.cos(ang) * rr2 * k, c + math.sin(ang) * rr2 * k))
        aa_polygon(s, col, pts)
    shape(r1, r2, rubber)
    shape(r1 - 1.6, r2 - 1.6, color)
    # dégradé de volume
    hi = pygame.Surface((S2, S2), pygame.SRCALPHA)
    pygame.draw.line(hi, (255, 255, 255, 120), (c, c - r1 * k * 0.35), (c + L * k, c - r2 * k * 0.35),
                     max(2, int(r2 * k * 0.4)))
    s.blit(hi, (0, 0))
    # logo Pokéball sur le pivot
    art.draw_pokeball(s, c, c, r1 * k * 0.62, shading=True)
    return pygame.transform.smoothscale(s, (size, size))


# ==========================================================================
class PlayfieldRenderer:
    def __init__(self, table):
        self.table = table
        self.static = StaticLayers(table)
        self.surface = pygame.Surface((PF_PIX_W, PF_PIX_H)).convert()
        self.light = pygame.Surface((PF_PIX_W // 4, PF_PIX_H // 4)).convert()
        self.ball_img = make_ball_sprite(BALL_R * S)
        self.ball_shadow = soft_circle(BALL_R * S * 1.05, (0, 0, 0), 140, edge=4)
        self.flip_img = {side: make_flipper_sprite(f) for side, f in table.flippers.items()}
        self.flip_shadow = {}
        for side, img in self.flip_img.items():
            sh = img.copy()
            sh.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MIN)
            sh.set_alpha(120)
            self.flip_shadow[side] = sh
        self.bumper_cap = art.voltorb_cap(int(19 * S * 1.25))
        self.bumper_cap_f = art.voltorb_cap(int(19 * S * 1.25), True)
        self.particles = []
        self.popups = []
        self.t = 0.0
        self.shake_amt = 0.0
        self.flash_col = None
        self.flash_t = 0.0
        self.flash_dur = 0.3
        self.show = None          # (nom, t, durée, couleur)
        self.shot_flashes = []    # (shot, couleur, t)
        self.tint_cache = {}
        self.rot_cache = {}
        self.attract = False

    # ------------------------------------------------------------------
    # Effets déclenchés par le jeu
    # ------------------------------------------------------------------
    def shake(self, amt):
        self.shake_amt = min(14.0, self.shake_amt + amt * 8)

    def flash(self, col, dur=0.3):
        self.flash_col = col
        self.flash_t = dur
        self.flash_dur = dur

    def light_show(self, name, dur, color=(255, 255, 255)):
        self.show = [name, 0.0, dur, color]

    def shot_flash(self, shot, col):
        self.shot_flashes.append([shot, col, 0.0])

    def popup(self, x, y, txt, col=(255, 240, 120)):
        self.popups.append(Popup(x, y, txt, col))
        if len(self.popups) > 8:
            self.popups.pop(0)

    def burst(self, x, y, kind="spark", n=12, col=None):
        if x is None:
            return
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi)
            sp = random.uniform(150, 600)
            if kind == "spark":
                c = col or random.choice([(255, 240, 120), (255, 255, 255), (120, 200, 255)])
                self.particles.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp, random.uniform(0.15, 0.4),
                                               c, random.uniform(1.0, 2.2)))
            elif kind == "star":
                c = col or random.choice([(255, 230, 80), (255, 255, 255), (255, 120, 200), (120, 220, 255)])
                self.particles.append(Particle(x, y, math.cos(a) * sp * 1.5, math.sin(a) * sp * 1.5 - 200,
                                               random.uniform(0.6, 1.4), c, random.uniform(2.0, 3.5), "star", 900))
            elif kind == "fire":
                self.particles.append(Particle(x + random.uniform(-6, 6), y, random.uniform(-40, 40),
                                               random.uniform(-260, -120), random.uniform(0.3, 0.7),
                                               random.choice([(255, 200, 60), (255, 120, 30), (255, 60, 20)]),
                                               random.uniform(2, 4), "fire"))
        if len(self.particles) > 500:
            self.particles = self.particles[-500:]

    # ------------------------------------------------------------------
    def tinted(self, name, col, inten):
        q = max(1, min(8, int(inten * 8 + 0.5)))
        key = (name, col, q)
        img = self.tint_cache.get(key)
        if img is None:
            spr = self.static.lamp_sprites[name][0]
            img = spr.copy()
            img.fill(mul_col(col, q / 8), special_flags=pygame.BLEND_MULT)
            if len(self.tint_cache) > 4000:
                self.tint_cache.clear()
            self.tint_cache[key] = img
        return img

    def lamp_level(self, mode, t, phase=0.0):
        if mode == "on":
            return 1.0
        if mode == "blink":
            return 1.0 if (t * 2.4 + phase) % 1.0 < 0.55 else 0.15
        if mode == "fast":
            return 1.0 if (t * 6.5 + phase) % 1.0 < 0.5 else 0.1
        if mode == "pulse":
            return 0.35 + 0.65 * (0.5 + 0.5 * math.sin((t + phase) * 2 * math.pi * 1.2))
        return 1.0

    def show_level(self, ins):
        """Intensité additionnelle d'un spectacle lumineux pour un insert."""
        if not self.show:
            return 0.0, None
        name, t, dur, col = self.show
        x, y = ins.x, ins.y
        if name == "sweep":
            band = 1150 - (t / dur) * 1400
            return max(0.0, 1 - abs(y - band) / 120), col
        if name in ("mode_start", "capture", "mewtwo"):
            d = math.hypot(x - RING_C[0], y - RING_C[1])
            wave = (t * 700) % 800
            return max(0.0, 1 - abs(d - wave) / 90), col
        if name in ("jackpot", "multiball"):
            return (1.0 if (t * 8) % 1.0 < 0.5 else 0.0), col
        if name == "victory":
            a = math.atan2(y - RING_C[1], x - RING_C[0])
            hue = (a / (2 * math.pi) + t * 0.8) % 1.0
            c = pygame.Color(0)
            c.hsva = (hue * 360, 100, 100, 100)
            return 0.6 + 0.4 * math.sin(t * 10 + y * 0.02), (c.r, c.g, c.b)
        if name == "attract":
            band = (t * 500) % 1500 - 100
            return max(0.0, 1 - abs(y - band) / 160) * 0.9, col
        return 0.0, None

    # ------------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        self.shake_amt = max(0.0, self.shake_amt - dt * 30)
        if self.flash_t > 0:
            self.flash_t -= dt
        if self.show:
            self.show[1] += dt
            if self.show[1] > self.show[2]:
                self.show = None
        for f in self.shot_flashes:
            f[2] += dt
        self.shot_flashes = [f for f in self.shot_flashes if f[2] < 0.6]
        alive = []
        for p in self.particles:
            p.life -= dt
            if p.life > 0:
                p.vy += p.g * dt
                p.x += p.vx * dt
                p.y += p.vy * dt
                p.vx *= (1 - dt * 2.5)
                if p.kind != "star":
                    p.vy *= (1 - dt * 2.5)
                alive.append(p)
        self.particles = alive
        for pp in self.popups:
            pp.t += dt
            pp.y -= dt * 45
        self.popups = [pp for pp in self.popups if pp.t < 1.3]

    def add_impacts(self, events):
        """Étincelles sur les impacts physiques violents."""
        for (x, y, imp, mat) in events:
            if imp > 900 and mat in ("rubber", "post", "wall", "metal", "flipper"):
                self.burst(x, y, "spark", 4 if imp < 2000 else 8)

    # ------------------------------------------------------------------
    def draw(self, screen, dest, game, attract=False):
        s = self.surface
        tb = self.table
        st = self.static
        t = self.t
        s.blit(st.base, (0, 0))
        light = self.light
        light.fill((0, 0, 0))

        # --- éclairage général (GI) ---
        gi = game.gi_color if game.state == "playing" else (200, 200, 230)
        gi_k = 0.75 if not game.tilted else 0.1
        gim = st.gi_mask.copy()
        gim.fill(mul_col(gi, gi_k), special_flags=pygame.BLEND_MULT)
        light.blit(gim, (0, 0), special_flags=pygame.BLEND_ADD)

        # --- inserts ---
        lamps = game.lamps.states if game.state == "playing" else {}
        for ins in INSERTS:
            st_ = lamps.get(ins.name)
            inten = 0.0
            col = None
            if st_:
                cols, mode = st_
                phase = (ins.x + ins.y) * 0.0007
                lv = self.lamp_level(mode, t, phase)
                idx = int(t * 2.2) % len(cols) if len(cols) > 1 else 0
                col = cols[idx]
                inten = lv
            if attract or self.show:
                sl, scol = self.show_level(ins) if self.show else (0.0, None)
                if attract and not self.show:
                    self.show = None
                    band = (t * 420) % 1500 - 150
                    hue = ((ins.y / 1150) + t * 0.15) % 1.0
                    c = pygame.Color(0)
                    c.hsva = (hue * 360, 70, 100, 100)
                    sl = max(0.0, 1 - abs(ins.y - band) / 170) * 0.9 + 0.12 * (0.5 + 0.5 * math.sin(t * 3 + ins.x * 0.05))
                    scol = (c.r, c.g, c.b)
                if sl > inten:
                    inten, col = sl, scol
            if inten <= 0.02 or col is None:
                continue
            spr, ox, oy = st.lamp_sprites[ins.name]
            img = self.tinted(ins.name, col, inten)
            s.blit(img, (ox, oy), special_flags=pygame.BLEND_ADD)
            if ins.icon and ins.icon.startswith("leg:") and inten > 0.3:
                size = int(ins.w * S * 0.9)
                cimg = art.creature(ins.icon[4:], size)
                s.blit(cimg, (ins.x * S - size / 2, ins.y * S - size / 2))
            gr = int(max(ins.w, ins.h) * S * 0.5 / 4 * 2.2) + 2
            gl = glow(gr, mul_col(col, 0.55 * inten), falloff=1.8)
            light.blit(gl, (ins.x * S / 4 - gr, ins.y * S / 4 - gr), special_flags=pygame.BLEND_ADD)

        # --- flashs de tir ---
        from .layout import MOUTHS
        for shot, col, ft in self.shot_flashes:
            mx, my = MOUTHS.get(shot, (241, 445))
            k = 1.0 - ft / 0.6
            gr = int(26 + 20 * (1 - k))
            gl = glow(gr, mul_col(col, k), falloff=1.3)
            light.blit(gl, (mx * S / 4 - gr, (my - 30) * S / 4 - gr), special_flags=pygame.BLEND_ADD)

        # --- éléments dynamiques ---
        self._draw_targets(s, tb, game)
        self._draw_spinner(s, tb)
        self._draw_slings(s, tb, light)
        self._draw_bumpers(s, tb, light, game)
        self._draw_pokeball(s, tb, light, game)
        self._draw_plunger(s, tb)
        self._draw_kickback(s, tb, light)
        self._draw_gate(s, tb)

        # --- billes sur le plateau ---
        balls = [b for b in tb.world.balls if b.state in ("pf", "held")]
        for b in balls:
            self._draw_ball(s, b, light)

        # --- flippers (rotations mises en cache par demi-degré) ---
        for side, f in tb.flippers.items():
            img, sh = self.flipper_rot(side, f.angle)
            cx, cy = f.px * S, f.py * S
            s.blit(sh, (cx - sh.get_width() / 2 + 3, cy - sh.get_height() / 2 + 4))
            s.blit(img, (cx - img.get_width() / 2, cy - img.get_height() / 2))

        # --- couche supérieure : rampes, rails, tablier ---
        s.blit(st.top, (0, 0))
        for r in (tb.ramp_l, tb.ramp_r):
            if r.pulse > 0:
                pts = [(x * S / 4, y * S / 4) for x, y, h in r.path.pts[:9]]
                col = mul_col(r.color, r.pulse)
                if len(pts) > 1:
                    pygame.draw.lines(light, col, False, pts, 6)
        for b in tb.world.balls:
            if b.state == "ramp":
                self._draw_ball(s, b, light)

        # --- particules ---
        for p in self.particles:
            k = p.life / p.max
            col = mul_col(p.col, min(1.0, k * 1.5))
            x, y = p.x * S, p.y * S
            if p.kind == "fire":
                r = p.size * (0.5 + k)
                g = glow(int(r * 2) + 1, col, falloff=1.4)
                s.blit(g, (x - g.get_width() / 2, y - g.get_height() / 2), special_flags=pygame.BLEND_ADD)
            else:
                pygame.draw.circle(s, col, (x, y), max(1, p.size * (0.4 + 0.6 * k)))
                light.blit(glow(3, mul_col(col, 0.6)), (x / 4 - 3, y / 4 - 3), special_flags=pygame.BLEND_ADD)

        # --- bloom ---
        big = pygame.transform.smoothscale(light, (PF_PIX_W, PF_PIX_H))
        s.blit(big, (0, 0), special_flags=pygame.BLEND_ADD)

        # --- popups de score ---
        for pp in self.popups:
            a = 255 if pp.t < 0.9 else int(255 * (1.3 - pp.t) / 0.4)
            img = pp.img
            img.set_alpha(max(0, a))
            s.blit(img, (pp.x * S - img.get_width() / 2, pp.y * S - img.get_height() / 2))

        # --- flash global ---
        if self.flash_t > 0 and self.flash_col:
            k = self.flash_t / self.flash_dur
            ov = pygame.Surface((PF_PIX_W, PF_PIX_H))
            ov.fill(mul_col(self.flash_col, 0.35 * k))
            s.blit(ov, (0, 0), special_flags=pygame.BLEND_ADD)
        if game.tilted:
            ov = pygame.Surface((PF_PIX_W, PF_PIX_H))
            ov.fill((90, 90, 90))
            s.blit(ov, (0, 0), special_flags=pygame.BLEND_MULT)

        ox = oy = 0
        if self.shake_amt > 0.2:
            ox = random.uniform(-1, 1) * self.shake_amt
            oy = random.uniform(-1, 1) * self.shake_amt * 0.6
        screen.blit(s, (dest[0] + ox, dest[1] + oy))

    def flipper_rot(self, side, angle):
        key = (side, int(round(math.degrees(angle) * 2)))
        r = self.rot_cache.get(key)
        if r is None:
            a = -key[1] / 2.0
            r = (pygame.transform.rotozoom(self.flip_img[side], a, 1.0),
                 pygame.transform.rotozoom(self.flip_shadow[side], a, 1.0))
            self.rot_cache[key] = r
        return r

    # ------------------------------------------------------------------
    def _draw_ball(self, s, b, light):
        x, y = b.x * S, b.y * S
        h = b.h
        scale = 1.0 + h / 230.0
        img = self.ball_img
        if b.state == "held":
            img = pygame.transform.rotozoom(self.ball_img, 0, 0.85)
        elif scale > 1.01:
            img = pygame.transform.rotozoom(self.ball_img, 0, scale)
        # traînée lumineuse
        sp = b.speed
        if sp > 1800 and b.state == "pf" and len(b.trail) > 3:
            pts = list(b.trail)[-6:]
            for i, (tx, ty, th) in enumerate(pts[:-1]):
                k = (i + 1) / len(pts)
                pygame.draw.circle(light, (int(60 * k), int(70 * k), int(110 * k)), (tx * S / 4, ty * S / 4), 2)
        shx, shy = 2.5 + h * 0.22, 3.5 + h * 0.35
        sh = self.ball_shadow
        s.blit(sh, (x + shx * S - sh.get_width() / 2, y + shy * S - sh.get_height() / 2))
        s.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))

    def _draw_targets(self, s, tb, game):
        for i, t in enumerate(tb.grass.targets):
            (x1, y1), (x2, y2) = t.p1, t.p2
            hgt = 1.0 - t.anim
            if hgt < 0.05:
                continue
            r = pygame.Rect((x1 - 4) * S, (y1 - 4 - 6 * hgt) * S, (x2 - x1 + 8) * S, (8 + 6 * hgt) * S)
            base = (40, 170, 70) if not t.flash else (140, 255, 150)
            pygame.draw.rect(s, (10, 40, 15), r.move(2, 3), border_radius=3)
            pygame.draw.rect(s, base, r, border_radius=3)
            pygame.draw.rect(s, (170, 255, 170), r, 1, border_radius=3)
            # brins d'herbe
            for j in range(5):
                gx = r.x + 4 + j * (r.w - 8) / 4
                pygame.draw.line(s, (20, 90, 30), (gx, r.bottom - 2), (gx + 2, r.y + 2), 2)
        for t in tb.radar + tb.rocket:
            (x1, y1), (x2, y2) = t.p1, t.p2
            wob = math.sin(t.wobble * 30) * t.wobble * 1.5
            col = (60, 220, 100) if t.bank == "radar" else (230, 50, 60)
            if t.flash > 0:
                col = (255, 255, 255)
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy)
            nx, ny = -dy / L, dx / L
            if t.bank == "rocket":
                nx, ny = -nx, -ny
            p1 = (x1 + nx * wob, y1 + ny * wob)
            p2 = (x2 + nx * wob, y2 + ny * wob)
            thick_line(s, (20, 20, 25), P(p1[0] - nx * 2.5, p1[1] - ny * 2.5), P(p2[0] - nx * 2.5, p2[1] - ny * 2.5),
                       7 * S)
            thick_line(s, col, P(*p1), P(*p2), 5.2 * S)
            thick_line(s, (255, 255, 255), P(p1[0] + nx, p1[1] + ny), P(p2[0] + nx, p2[1] + ny), 1.2 * S)

    def _draw_spinner(self, s, tb):
        sp = tb.spinner
        (x1, y1), (x2, y2) = sp.p1, sp.p2
        a = math.radians(sp.angle)
        hgt = abs(math.cos(a)) * 9 + 1.5
        r = pygame.Rect(x1 * S + 2, (y1 - hgt / 2) * S, (x2 - x1) * S - 4, hgt * S)
        pygame.draw.rect(s, (120, 125, 140), r)
        pygame.draw.rect(s, (230, 235, 250) if math.cos(a) > 0 else (170, 170, 190), r.inflate(-4, -2))
        img = text("POKÉ", "black", 8, (200, 30, 40))
        if math.cos(a) > 0.5:
            s.blit(img, (r.centerx - img.get_width() / 2, r.centery - img.get_height() / 2))
        pygame.draw.line(s, (200, 200, 210), P(x1 - 2, y1), P(x2 + 2, y2), 2)

    def _draw_slings(self, s, tb, light):
        for nm in ("sling_l", "sling_r"):
            e = tb.by_name[nm]
            a, b, c = e.a, e.b, e.c
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            dx, dy = c[0] - a[0], c[1] - a[1]
            L = math.hypot(dx, dy)
            nx, ny = dy / L, -dx / L
            if nm == "sling_r":
                nx, ny = -nx, -ny
            bul = e.bulge * 5
            mid = (mx + nx * bul, my + ny * bul)
            for p, q in ((a, mid), (mid, c), (a, b), (b, c)):
                thick_line(s, (25, 25, 28), P(*p), P(*q), 7 * S)
                thick_line(s, (70, 70, 75), P(p[0] - 0.8, p[1] - 0.8), P(q[0] - 0.8, q[1] - 0.8), 2 * S)
            for p in (a, b, c):
                pygame.draw.circle(s, (210, 210, 225), P(*p), 3 * S)
            if e.flash > 0:
                k = e.flash / 0.18
                gl = glow(18, mul_col((255, 230, 90), k))
                light.blit(gl, (mx * S / 4 - 18, my * S / 4 - 18), special_flags=pygame.BLEND_ADD)

    def _draw_bumpers(self, s, tb, light, game):
        lamps = game.lamps.states if game.state == "playing" else {}
        for i, bp in enumerate(tb.bumpers):
            x, y = bp.x * S, bp.y * S
            r = bp.r * S
            fl = bp.flash > 0
            # jupe lumineuse
            col = (255, 230, 120)
            mode_l = lamps.get(f"bumper_{i}")
            if mode_l:
                col = mode_l[0][0]
            k = (bp.flash / 0.22) if fl else 0.25 + 0.1 * math.sin(self.t * 3 + i)
            pygame.draw.circle(s, mul_col(col, 0.3 + 0.7 * k), (x, y), r * 1.15)
            gl = glow(int(r / 4 * 3.2) + 2, mul_col(col, 0.9 * k + 0.15))
            light.blit(gl, (x / 4 - gl.get_width() / 2, y / 4 - gl.get_height() / 2), special_flags=pygame.BLEND_ADD)
            # anneau métallique
            rd = bp.ring * 2.5
            pygame.draw.circle(s, (60, 60, 70), (x + 2, y + 3), r)
            pygame.draw.circle(s, (190, 195, 210), (x, y + rd), r, max(2, int(r * 0.18)))
            cap = self.bumper_cap_f if fl else self.bumper_cap
            s.blit(cap, (x - cap.get_width() / 2, y - cap.get_height() / 2 - 2))

    def _draw_pokeball(self, s, tb, light, game):
        pb = tb.pokeball
        x, y = pb.x * S, pb.y * S
        r = pb.r * S
        lamps = game.lamps.states if game.state == "playing" else {}
        lit = "arrow_center" in lamps or pb.open > 0.05
        glow_btn = 0.5 + 0.5 * math.sin(self.t * 8) if lit else (pb.flash / 0.35 if pb.flash > 0 else 0.0)
        # socle lumineux
        base_col = (255, 255, 255)
        if lit:
            ac = lamps.get("arrow_center")
            if ac:
                base_col = ac[0][int(self.t * 2.2) % len(ac[0])]
            gl = glow(int(r / 4 * 2.6), mul_col(base_col, 0.6 + 0.3 * math.sin(self.t * 6)))
            light.blit(gl, (x / 4 - gl.get_width() / 2, y / 4 - gl.get_height() / 2), special_flags=pygame.BLEND_ADD)
        sh = soft_circle(r * 1.05, (0, 0, 0), 150, edge=6)
        s.blit(sh, (x + 4 - sh.get_width() / 2, y + 6 - sh.get_height() / 2))
        img = art.pokeball_sprite(int(r), round(glow_btn * 4) / 4, round(pb.open * 6) / 6)
        ang = pb.wobble_angle
        if abs(ang) > 0.3:
            img = pygame.transform.rotozoom(img, ang, 1.0)
        s.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        if pb.open > 0.05:
            beam = glow(int(r * 0.9), mul_col((255, 250, 210), pb.open), falloff=1.2)
            s.blit(beam, (x - beam.get_width() / 2, y - beam.get_height() / 2 - r * 0.2), special_flags=pygame.BLEND_ADD)

    def _draw_plunger(self, s, tb):
        pl = tb.plunger
        y = pl.y
        x1, x2 = pl.x1, pl.x2
        cx = (x1 + x2) / 2
        pygame.draw.rect(s, (60, 62, 70), pygame.Rect(cx * S - 4, y * S, 8, (1150 - y) * S))
        # ressort
        for j in range(8):
            yy = y + 4 + j * (40 - pl.pull * 0.6) / 8
            pygame.draw.line(s, (200, 200, 210), P(cx - 6, yy), P(cx + 6, yy + 2), 2)
        pygame.draw.rect(s, (230, 60, 60), pygame.Rect(x1 * S + 2, y * S - 3, (x2 - x1) * S - 4, 6), border_radius=3)

    def _draw_kickback(self, s, tb, light):
        kb = tb.kickback
        up = kb.anim * 10
        pygame.draw.rect(s, (170, 175, 190), pygame.Rect((kb.x - 7) * S, (kb.y + 6 - up) * S, 14 * S, 4 * S))
        if kb.lit:
            gl = glow(6, (40, 90, 255))
            light.blit(gl, (kb.x * S / 4 - 6, (kb.y + 8) * S / 4 - 6), special_flags=pygame.BLEND_ADD)

    def _draw_gate(self, s, tb):
        for g in (tb.by_name["shooter_gate"], tb.by_name["top_gate"]):
            (x1, y1), (x2, y2) = g.p1, g.p2
            dx, dy = x2 - x1, y2 - y1
            L = math.hypot(dx, dy) or 1
            sw = g.swing * 6
            nx, ny = -dy / L * sw, dx / L * sw
            pygame.draw.line(s, (90, 95, 110), P(x1, y1), P(x2, y2), 3)
            pygame.draw.line(s, (230, 235, 250), P(x1 + nx, y1 + ny), P(x2 + nx, y2 + ny), 2)
            pygame.draw.circle(s, (200, 205, 220), P(x1, y1), 3)
            pygame.draw.circle(s, (200, 205, 220), P(x2, y2), 3)
