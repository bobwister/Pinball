"""Écran LCD façon Stern : affichage du score, HUD des modes et animations vidéo."""
import math
import random

import pygame

from ..data import LEG_BY_KEY, LEGENDARIES, CHAPTERS, MEWTWO, TYPE_COLORS
from .assets import text, glow, gradient_surface, mul_col, lerp_col, blit_center
from . import art
from .fxlib import (ease_out_back, ease_out, ease_in, fmt, Sparks, rays, radial_bg, big_text, slam,
                    shine, hp_bar, stripes_wipe, textbox)

W, H = 904, 508


def leg_of(kw):
    leg = kw.get("leg")
    if isinstance(leg, str):
        leg = LEG_BY_KEY.get(leg, MEWTWO)
    return leg


# ==========================================================================
# Scènes superposées
# ==========================================================================
class Scene:
    duration = 2.0
    priority = 5
    full = True

    def __init__(self, lcd, **kw):
        self.lcd = lcd
        self.kw = kw
        self.t = 0.0
        self.sp = Sparks()
        self.init()

    def init(self):
        pass

    def update(self, dt):
        self.t += dt
        self.sp.update(dt)

    @property
    def done(self):
        return self.t >= self.duration

    def draw(self, s, game):
        pass

    # aides
    def fade(self):
        if self.t > self.duration - 0.25:
            return max(0.0, (self.duration - self.t) / 0.25)
        return 1.0


class MessageScene(Scene):
    duration = 2.2
    priority = 4

    def draw(self, s, game):
        col = self.kw.get("color", (255, 255, 255))
        radial_bg(s, mul_col(col, 0.55), (8, 8, 18))
        rays(s, W / 2, H / 2, mul_col(col, 0.6), self.t * 0.4, n=14, alpha=35)
        title = big_text(self.kw.get("title", ""), 64 if len(self.kw.get("title", "")) < 18 else 48,
                         (255, 255, 255), outline=mul_col(col, 0.35), ow=5)
        slam(s, title, W / 2, H / 2 - 30, self.t)
        sub = self.kw.get("sub")
        if sub and self.t > 0.25:
            im = text(sub, "semi", 30, lerp_col(col, (255, 255, 255), 0.6), outline=(0, 0, 0), outline_w=2)
            im.set_alpha(int(255 * min(1, (self.t - 0.25) * 4)))
            blit_center(s, im, W / 2, H / 2 + 50)
        shine(s, (0, H / 2 - 80, W, 110), self.t, 0.9)


class JackpotScene(Scene):
    duration = 2.4
    priority = 7

    def init(self):
        self.sp.burst(W / 2, H / 2, 90, speed=(200, 800), life=(0.6, 1.6), size=(2, 6))

    def draw(self, s, game):
        radial_bg(s, (150, 100, 10), (20, 8, 0))
        rays(s, W / 2, H / 2, (255, 200, 60), self.t * 1.2, n=18, alpha=50)
        self.sp.draw(s)
        title = big_text(self.kw.get("title", "JACKPOT"), 92, (255, 230, 80), outline=(120, 50, 0), ow=6,
                         grad=((255, 250, 180), (255, 170, 20)))
        slam(s, title, W / 2, H / 2 - 50, self.t)
        v = self.kw.get("value", 0)
        shown = int(v * min(1.0, self.t / 0.9))
        im = big_text(fmt(shown), 58, (255, 255, 255), outline=(60, 30, 0), ow=4)
        blit_center(s, im, W / 2, H / 2 + 60)
        shine(s, (0, H / 2 - 120, W, 140), self.t, 1.4)


class SuperJackpotScene(JackpotScene):
    duration = 3.2
    priority = 8

    def init(self):
        self.sp.burst(W / 2, H / 2, 160, cols=[(255, 230, 80), (255, 255, 255), (255, 90, 200), (90, 200, 255)],
                      speed=(250, 950), life=(0.8, 2.0), size=(2, 7))

    def draw(self, s, game):
        hue = (self.t * 0.5) % 1.0
        c = pygame.Color(0)
        c.hsva = (hue * 360, 80, 70, 100)
        radial_bg(s, (c.r, c.g, c.b), (10, 0, 20))
        rays(s, W / 2, H / 2, (255, 255, 255), -self.t * 1.5, n=22, alpha=40)
        self.sp.draw(s)
        t1 = big_text("SUPER", 70, (255, 255, 255), outline=(80, 0, 80), ow=5)
        t2 = big_text("JACKPOT", 104, (255, 230, 80), outline=(120, 40, 0), ow=7,
                      grad=((255, 255, 200), (255, 160, 20)))
        slam(s, t1, W / 2, H / 2 - 120, self.t)
        slam(s, t2, W / 2, H / 2 - 20, self.t - 0.15)
        v = self.kw.get("value", 0)
        im = big_text(fmt(int(v * min(1.0, self.t / 1.2))), 60, (255, 255, 255), ow=4)
        blit_center(s, im, W / 2, H / 2 + 95)


class MultiballScene(Scene):
    duration = 3.0
    priority = 8

    def draw(self, s, game):
        radial_bg(s, (20, 120, 60), (0, 10, 5))
        rays(s, W / 2, H / 2, (120, 255, 160), self.t * 0.9, n=16, alpha=40)
        n = self.kw.get("balls", 3)
        for i in range(n):
            a = self.t * 3 + i * 2 * math.pi / n
            x = W / 2 + math.cos(a) * 300 * ease_out(self.t / 0.6)
            y = H / 2 + 40 + math.sin(a) * 90
            art.draw_pokeball(s, x, y, 34, angle=self.t * 300 + i * 40)
        im = big_text("MULTIBALL", 96, (255, 255, 255), outline=(0, 90, 30), ow=6,
                      grad=((255, 255, 255), (150, 255, 170)))
        slam(s, im, W / 2, H / 2 - 110, self.t)
        sub = big_text(self.kw.get("title", ""), 40, (255, 240, 120), ow=3)
        if self.t > 0.3:
            blit_center(s, sub, W / 2, H / 2 + 170)


class BallSavedScene(Scene):
    duration = 1.8
    priority = 6

    def draw(self, s, game):
        radial_bg(s, (20, 60, 150), (0, 0, 20))
        r = 90 + 20 * math.sin(self.t * 10)
        g = glow(int(r * 1.6), (60, 140, 255))
        s.blit(g, (W / 2 - g.get_width() / 2, H / 2 - 30 - g.get_height() / 2), special_flags=pygame.BLEND_ADD)
        art.draw_pokeball(s, W / 2, H / 2 - 30, 70, angle=math.sin(self.t * 12) * 10)
        im = big_text("BALLE SAUVÉE !", 64, (255, 255, 255), outline=(20, 50, 140), ow=5)
        slam(s, im, W / 2, H / 2 + 120, self.t)


class ExtraBallScene(Scene):
    duration = 2.8
    priority = 8

    def init(self):
        self.sp.burst(W / 2, H / 2, 80, cols=[(255, 160, 40), (255, 255, 255)])

    def draw(self, s, game):
        radial_bg(s, (160, 70, 0), (15, 5, 0))
        rays(s, W / 2, H / 2, (255, 180, 80), self.t, n=16, alpha=45)
        self.sp.draw(s)
        t1 = self.kw.get("title", "BALLE SUPPLÉMENTAIRE !")
        im = big_text(t1, 62 if len(t1) < 20 else 50, (255, 255, 255), outline=(120, 50, 0), ow=5)
        slam(s, im, W / 2, H / 2 - 20, self.t)
        sub = self.kw.get("sub")
        if sub:
            blit_center(s, text(sub, "semi", 30, (255, 230, 180), outline=(0, 0, 0), outline_w=2), W / 2, H / 2 + 60)


class SkillShotScene(Scene):
    duration = 2.4
    priority = 7

    def init(self):
        self.sp.burst(W / 2, H / 2, 70, cols=[(255, 255, 120), (120, 220, 255)])

    def draw(self, s, game):
        sup = self.kw.get("super")
        radial_bg(s, (30, 90, 160) if sup else (140, 120, 10), (5, 5, 15))
        rays(s, W / 2, H / 2, (255, 255, 200), self.t * 1.5, n=20, alpha=40)
        self.sp.draw(s)
        im = big_text("SUPER SKILL SHOT" if sup else "SKILL SHOT", 76 if not sup else 64, (255, 255, 255),
                      outline=(40, 40, 0) if not sup else (10, 40, 90), ow=6)
        slam(s, im, W / 2, H / 2 - 40, self.t)
        v = big_text(fmt(self.kw.get("value", 0)), 56, (255, 240, 120), ow=4)
        if self.t > 0.3:
            blit_center(s, v, W / 2, H / 2 + 60)


class ComboScene(Scene):
    duration = 1.3
    priority = 3
    full = False

    def draw(self, s, game):
        n = self.kw.get("n", 2)
        k = ease_out_back(min(1, self.t / 0.3))
        a = self.fade()
        box = pygame.Surface((330, 120), pygame.SRCALPHA)
        pygame.draw.rect(box, (255, 255, 255, int(220 * a)), box.get_rect(), border_radius=16)
        pygame.draw.rect(box, (40, 40, 60, int(255 * a)), box.get_rect().inflate(-8, -8), border_radius=14)
        im = text(f"COMBO x{n}", "black", 46, (255, 230, 80), outline=(0, 0, 0), outline_w=3)
        blit_center(box, im, 165, 45)
        v = text(fmt(self.kw.get("value", 0)), "digital", 28, (255, 255, 255))
        blit_center(box, v, 165, 92)
        box = pygame.transform.rotozoom(box, 0, max(0.05, k))
        box.set_alpha(int(255 * a))
        s.blit(box, (W - box.get_width() - 20, H - box.get_height() - 70))


class RadarScene(Scene):
    duration = 1.4
    priority = 3
    full = False

    def draw(self, s, game):
        radar = self.kw.get("radar", [0, 0, 0])
        need = self.kw.get("need", 1)
        a = self.fade()
        box = pygame.Surface((380, 120), pygame.SRCALPHA)
        pygame.draw.rect(box, (10, 40, 20, int(230 * a)), box.get_rect(), border_radius=14)
        pygame.draw.rect(box, (90, 255, 140, int(255 * a)), box.get_rect(), 3, border_radius=14)
        blit_center(box, text("POKÉ RADAR", "black", 32, (150, 255, 170)), 190, 32)
        for i in range(3):
            frac = radar[i] / max(1, need)
            x = 110 + i * 80
            pygame.draw.circle(box, (30, 60, 40), (x, 82), 22)
            if frac > 0:
                pygame.draw.circle(box, lerp_col((40, 120, 60), (120, 255, 150), frac), (x, 82), int(8 + 14 * frac))
            pygame.draw.circle(box, (150, 255, 170), (x, 82), 22, 3)
        s.blit(box, (W / 2 - 190, H - 190))


class ModeLitScene(Scene):
    duration = 2.4
    priority = 6

    def draw(self, s, game):
        radial_bg(s, (90, 90, 160), (5, 5, 20))
        rays(s, W / 2, H / 2, (200, 200, 255), self.t * 0.8, n=12, alpha=40)
        p = game.player
        keys = p.available_legendaries() if p else []
        for i, k in enumerate(keys):
            x = W / 2 + (i - (len(keys) - 1) / 2) * 220
            sil = art.creature_silhouette(k, 170, (20, 20, 40))
            au = art.creature_aura(k, 170, LEG_BY_KEY[k].color, 10)
            s.blit(au, (x - au.get_width() / 2, 190 - au.get_height() / 2), special_flags=pygame.BLEND_ADD)
            s.blit(sil, (x - 85, 105))
            q = text("?", "black", 70, (255, 255, 255), outline=(0, 0, 0), outline_w=3)
            blit_center(s, q, x, 190)
        im = big_text("LÉGENDAIRE PRÊT !", 60, (255, 255, 255), outline=(30, 30, 100), ow=5)
        slam(s, im, W / 2, 365, self.t)
        blit_center(s, text("Tirez le CENTRE POKÉMON", "semi", 30, (220, 220, 255), outline=(0, 0, 0), outline_w=2),
                    W / 2, 430)


class BonusXScene(Scene):
    duration = 1.8
    priority = 4

    def draw(self, s, game):
        radial_bg(s, (130, 110, 20), (10, 8, 0))
        im = big_text(f"BONUS {self.kw.get('n', 2)}X", 90, (255, 240, 120), outline=(90, 60, 0), ow=6)
        slam(s, im, W / 2, H / 2, self.t)
        for i, ic in enumerate(("Feu", "Eau", "Électrik")):
            ti = art.type_icon(ic, 60, TYPE_COLORS[ic])
            blit_center(s, ti, W / 2 + (i - 1) * 90, H / 2 + 110)


class WildAppearsScene(Scene):
    duration = 3.2
    priority = 6

    def draw(self, s, game):
        num, name, ptype = self.kw.get("poke", (25, "PIKACHU", "Électrik"))
        col = TYPE_COLORS.get(ptype, (200, 200, 200))
        t = self.t
        # décor de combat façon jeu
        s.blit(gradient_surface(W, H, (200, 230, 255), (120, 200, 120)), (0, 0))
        pygame.draw.ellipse(s, (110, 180, 90), pygame.Rect(W * 0.55, H * 0.42, 330, 70))
        pygame.draw.ellipse(s, (90, 160, 80), pygame.Rect(W * 0.55, H * 0.42, 330, 70), 4)
        x = W * 0.55 + 165 + (1 - ease_out(min(1, t / 0.8))) * 500
        # silhouette mystère qui se colore
        r = 70
        pygame.draw.ellipse(s, (0, 0, 0, 60), pygame.Rect(x - 70, H * 0.42 + 20, 140, 30))
        body_col = lerp_col((20, 20, 30), col, min(1.0, max(0.0, (t - 0.9) * 2)))
        pygame.draw.circle(s, body_col, (int(x), int(H * 0.30)), r)
        ti = art.type_icon(ptype, 80, lerp_col((60, 60, 70), (255, 255, 255), min(1, max(0, (t - 0.9) * 2))))
        blit_center(s, ti, x, H * 0.30)
        nm = text(f"N°{num:03d}", "digital", 24, (40, 40, 60))
        s.blit(nm, (60, 50))
        textbox(s, (40, H - 150, W - 80, 120), f"Un {name} sauvage apparaît !\nFrappez la POKÉBALL !",
                max(0, t - 0.6), cps=45)
        if t < 0.5:
            stripes_wipe(s, 1 - t / 0.5)


class WildCaughtScene(Scene):
    duration = 3.4
    priority = 7

    def init(self):
        self.burst_done = False

    def draw(self, s, game):
        num, name, ptype = self.kw.get("poke", (25, "PIKACHU", "Électrik"))
        radial_bg(s, (60, 140, 80), (5, 15, 10))
        t = self.t
        ang = 0
        if 0.4 < t < 2.0:
            ph = (t - 0.4) / 0.5
            ang = math.sin(ph * math.pi * 2) * 25 if int(ph) % 1 == 0 else 0
            ang = math.sin(ph * math.pi) * 22 if (ph % 1) < 0.5 else 0
        if t > 2.0 and not self.burst_done:
            self.burst_done = True
            self.sp.burst(W / 2, H / 2 - 40, 60, cols=[(255, 255, 140), (255, 255, 255)], g=0)
        self.sp.draw(s)
        art.draw_pokeball(s, W / 2, H / 2 - 40, 80, angle=ang)
        if t > 2.0:
            im = big_text("GOTCHA !", 80, (255, 255, 255), outline=(20, 80, 30), ow=6)
            slam(s, im, W / 2, 90, t - 2.0)
            blit_center(s, text(f"{name} est attrapé !", "black", 36, (255, 240, 140), outline=(0, 0, 0),
                                outline_w=3), W / 2, H - 120)
            locks, need = self.kw.get("locks", 0), self.kw.get("need", 3)
            blit_center(s, text(f"SAFARI {locks}/{need}   ·   POKÉDEX {self.kw.get('count', 0)}", "digital", 28,
                                (200, 255, 210)), W / 2, H - 70)
        else:
            blit_center(s, text("...", "black", 60, (255, 255, 255)), W / 2, H - 110)


class ModeSelectScene(Scene):
    duration = 999
    priority = 9

    @property
    def done(self):
        return self.lcd.game_ref.select is None

    def draw(self, s, game):
        sel = game.select
        if sel is None:
            return
        opts = sel["options"]
        idx = sel["idx"]
        leg = LEG_BY_KEY[opts[idx]]
        radial_bg(s, mul_col(leg.color, 0.6), (6, 6, 16))
        rays(s, W / 2, H / 2 - 20, mul_col(leg.color, 0.8), self.t * 0.5, n=14, alpha=35)
        head = text("CHOISISSEZ VOTRE LÉGENDAIRE", "black", 34, (255, 255, 255), outline=(0, 0, 0), outline_w=3)
        blit_center(s, head, W / 2, 34)
        for i, k in enumerate(opts):
            L = LEG_BY_KEY[k]
            off = i - idx
            x = W / 2 + off * 270
            sc = 1.0 if off == 0 else 0.62
            size = int(220 * sc)
            if off == 0:
                au = art.creature_aura(k, size, L.color, 14)
                s.blit(au, (x - au.get_width() / 2, 200 - au.get_height() / 2), special_flags=pygame.BLEND_ADD)
                bob = math.sin(self.t * 3) * 6
                s.blit(art.creature(k, size), (x - size / 2, 200 - size / 2 + bob))
            else:
                img = art.creature(k, size).copy()
                img.set_alpha(110)
                s.blit(img, (x - size / 2, 200 - size / 2))
        pygame.draw.polygon(s, (255, 255, 255), [(60, 200), (90, 175), (90, 225)])
        pygame.draw.polygon(s, (255, 255, 255), [(W - 60, 200), (W - 90, 175), (W - 90, 225)])
        name = big_text(leg.name, 56, (255, 255, 255), outline=mul_col(leg.color, 0.4), ow=5)
        blit_center(s, name, W / 2, 345)
        blit_center(s, text(f"{leg.mode_title}  ·  {leg.type}", "semi", 26, lerp_col(leg.color, (255, 255, 255), 0.5),
                            outline=(0, 0, 0), outline_w=2), W / 2, 392)
        for j, ln in enumerate(leg.rules_text[:2]):
            blit_center(s, text(ln, "semi", 22, (230, 230, 240)), W / 2, 428 + j * 26)
        hp = game.player.leg_hp.get(leg.key)
        if hp:
            blit_center(s, text(f"PV restants {int(hp / leg.hp * 100)}%", "digital", 22, (255, 200, 120)), W - 120, 470)
        tt = text(f"{max(0, int(sel['t'])) + 1}", "black", 40, (255, 230, 80), outline=(0, 0, 0), outline_w=3)
        s.blit(tt, (24, H - 64))
        hint = text("◄ ► flippers   ·   ENTRÉE : valider", "semi", 20, (200, 200, 220))
        s.blit(hint, (W - hint.get_width() - 20, 74))


class LegendaryIntroScene(Scene):
    duration = 3.6
    priority = 9

    def init(self):
        leg = leg_of(self.kw)
        self.leg = leg
        self.flashes = [0.15, 0.32, 0.55]

    def draw(self, s, game):
        leg = self.leg
        t = self.t
        s.fill((0, 0, 0))
        k = ease_out(min(1, (t - 0.5) / 1.0))
        radial_bg(s, mul_col(leg.color, 0.75 * k), (0, 0, 0))
        rays(s, W / 2, H / 2, leg.color, t * 0.7, n=18, alpha=int(50 * k))
        # éclairs d'introduction
        if any(abs(t - f) < 0.04 for f in self.flashes):
            s.fill((255, 255, 255))
        size = int(360 * (0.6 + 0.4 * ease_out_back(min(1, max(0, (t - 0.55) / 0.7)))))
        if t > 0.5:
            au = art.creature_aura(leg.key, size, leg.color, 18)
            s.blit(au, (W * 0.32 - au.get_width() / 2, H / 2 - au.get_height() / 2), special_flags=pygame.BLEND_ADD)
            img = art.creature(leg.key, size)
            s.blit(img, (W * 0.32 - size / 2, H / 2 - size / 2 + math.sin(t * 2.5) * 6))
        elif t > 0.1:
            sil = art.creature_silhouette(leg.key, 300, (0, 0, 0))
            s.fill(mul_col(leg.color, 0.4))
            s.blit(sil, (W * 0.32 - 150, H / 2 - 150))
        if t > 1.0:
            nm = big_text(leg.name, 70 if len(leg.name) < 9 else 58, (255, 255, 255),
                          outline=mul_col(leg.color, 0.35), ow=6)
            slam(s, nm, W * 0.70, H / 2 - 60, t - 1.0)
        if t > 1.4:
            ti = art.type_icon(leg.type, 44, leg.color)
            sub = text(leg.mode_title.upper(), "black", 26, lerp_col(leg.color, (255, 255, 255), 0.55),
                       outline=(0, 0, 0), outline_w=2)
            blit_center(s, sub, W * 0.70, H / 2 + 10)
            s.blit(ti, (W * 0.70 - 22, H / 2 + 40))
        if t > 1.9:
            msg = "Le combat légendaire commence !" if leg.key != "mew" else "Mew joue avec vous..."
            im = text(msg, "semi", 24, (230, 230, 240), outline=(0, 0, 0), outline_w=2)
            blit_center(s, im, W * 0.70, H / 2 + 120)
        shine(s, (0, 0, W, H), t, 0.8, leg.color)


class LegHitScene(Scene):
    duration = 1.1
    priority = 2
    full = False

    def draw(self, s, game):
        leg = leg_of(self.kw)
        dmg = self.kw.get("dmg", 0)
        k = 1 - self.t / self.duration
        im = text(f"-{dmg}", "black", 74, (255, 255, 255), outline=mul_col(leg.color, 0.45), outline_w=5)
        y = 170 - self.t * 70
        im.set_alpha(int(255 * min(1, k * 2)))
        s.blit(im, (W * 0.22 - im.get_width() / 2 + 120, y))
        att = text(self.kw.get("attack", "") + (" !" if self.kw.get("kind") != "combo" else " — COMBO !"), "black",
                   30, lerp_col(leg.color, (255, 255, 255), 0.4), outline=(0, 0, 0), outline_w=3)
        att.set_alpha(int(255 * min(1, k * 2)))
        s.blit(att, (W / 2 - att.get_width() / 2, 84))
        if self.t < 0.12:
            ov = pygame.Surface((W, H))
            ov.fill(mul_col(leg.color, 0.6))
            s.blit(ov, (0, 0), special_flags=pygame.BLEND_ADD)


class CapturePhaseScene(Scene):
    duration = 2.6
    priority = 8

    def draw(self, s, game):
        leg = leg_of(self.kw)
        radial_bg(s, (150, 20, 30), (10, 0, 0))
        rays(s, W / 2, H / 2, (255, 120, 120), self.t, n=16, alpha=40)
        size = 230
        img = art.creature(leg.key, size)
        s.blit(img, (W * 0.72 - size / 2, H / 2 - size / 2 - 20))
        # Pokéball lancée en arc
        t = min(1.0, self.t / 1.0)
        x = W * 0.12 + (W * 0.5) * t
        y = H * 0.8 - math.sin(t * math.pi) * 260
        art.draw_pokeball(s, x, y, 40, angle=self.t * 700)
        im = big_text("LANCEZ LA POKÉBALL !", 58, (255, 255, 255), outline=(120, 0, 0), ow=5)
        slam(s, im, W / 2, 60, self.t)
        blit_center(s, text(f"{leg.name} est affaibli !", "black", 30, (255, 220, 120), outline=(0, 0, 0),
                            outline_w=3), W / 2, H - 50)


class ShakeScene(Scene):
    duration = 1.4
    priority = 7

    def draw(self, s, game):
        n, need = self.kw.get("n", 1), self.kw.get("need", 3)
        radial_bg(s, (60, 10, 20), (5, 0, 5))
        ang = math.sin(self.t * 14) * 28 * max(0, 1 - self.t / 0.9)
        art.draw_pokeball(s, W / 2, H / 2 - 20, 110, angle=ang)
        for i in range(need):
            col = (255, 230, 80) if i < n else (70, 70, 80)
            pygame.draw.circle(s, col, (int(W / 2 + (i - (need - 1) / 2) * 60), H - 70), 18)
        blit_center(s, big_text(f"SECOUSSE {n} !", 48, (255, 255, 255), ow=4), W / 2, 50)


class GotchaScene(Scene):
    duration = 4.8
    priority = 9

    def init(self):
        self.leg = leg_of(self.kw)
        self.burst = False

    def draw(self, s, game):
        leg = self.leg
        t = self.t
        radial_bg(s, mul_col(leg.color, 0.4), (4, 4, 10))
        cx, cy = W / 2, H / 2 - 10
        if t < 0.9:
            # aspiration rouge vers la Pokéball
            k = t / 0.9
            size = int(260 * (1 - k * 0.9))
            img = art.creature(leg.key, max(8, size))
            red = img.copy()
            red.fill((255, 60, 60, 255), special_flags=pygame.BLEND_RGBA_MULT)
            s.blit(red if k > 0.3 else img, (cx - size / 2, cy - 60 - size / 2 * (1 - k)))
            for i in range(6):
                pygame.draw.line(s, (255, 80, 80), (cx, cy + 40), (cx + random.uniform(-160, 160) * (1 - k),
                                                                     cy - 120 * (1 - k)), 3)
            art.draw_pokeball(s, cx, cy + 40, 60, open_=1 - k)
        else:
            ph = t - 0.9
            ang = 0
            if ph < 2.4:
                shake_i = int(ph / 0.8)
                local = (ph % 0.8) / 0.8
                ang = math.sin(local * math.pi * 2) * 25 if local < 0.5 else 0
            art.draw_pokeball(s, cx, cy + 40, 70, angle=ang, glow_btn=1.0 if ph < 2.4 and (ph % 0.8) > 0.6 else 0)
            if ph >= 2.4:
                if not self.burst:
                    self.burst = True
                    self.sp.burst(cx, cy + 40, 100, cols=[(255, 255, 160), (255, 255, 255), leg.color], g=0,
                                  speed=(150, 600))
                self.sp.draw(s)
                im = big_text("GOTCHA !", 96, (255, 255, 255), outline=mul_col(leg.color, 0.35), ow=7,
                              grad=((255, 255, 255), lerp_col(leg.color, (255, 255, 255), 0.4)))
                slam(s, im, W / 2, 80, ph - 2.4)
                blit_center(s, text(f"{leg.name} a été capturé !", "black", 36, (255, 240, 150), outline=(0, 0, 0),
                                    outline_w=3), W / 2, H - 115)
                blit_center(s, big_text(fmt(self.kw.get("value", 0)), 48, (255, 255, 255), ow=4), W / 2, H - 58)
            else:
                for i in range(3):
                    col = (255, 230, 80) if ph > (i + 1) * 0.8 - 0.05 else (60, 60, 70)
                    pygame.draw.circle(s, col, (int(W / 2 + (i - 1) * 50), H - 60), 14)


class BrokeFreeScene(Scene):
    duration = 2.2
    priority = 8

    def draw(self, s, game):
        leg = leg_of(self.kw)
        radial_bg(s, (120, 40, 10), (5, 0, 0))
        k = ease_out_back(min(1, self.t / 0.4))
        size = int(220 * k)
        if size > 5:
            s.blit(art.creature(leg.key, size), (W / 2 - size / 2, H / 2 - size / 2 - 20))
        art.draw_pokeball(s, W / 2 - 200, H / 2 + 80, 40, open_=1.0, angle=-30)
        im = big_text("OH NON !", 72, (255, 255, 255), outline=(100, 20, 0), ow=6)
        slam(s, im, W / 2, 60, self.t)
        blit_center(s, text(f"{leg.name} s'est libéré !", "black", 34, (255, 200, 140), outline=(0, 0, 0),
                            outline_w=3), W / 2, H - 50)


class EscapedScene(Scene):
    duration = 2.6
    priority = 8

    def draw(self, s, game):
        leg = leg_of(self.kw)
        s.fill((10, 10, 20))
        x = W / 2 + ease_in(self.t / 2.0) * 700
        img = art.creature(leg.key, 220)
        img.set_alpha(int(255 * max(0, 1 - self.t / 2.2)))
        s.blit(img, (x - 110, H / 2 - 130))
        blit_center(s, big_text(f"{leg.name} S'EST ENFUI...", 50, (200, 200, 220), ow=4), W / 2, H - 90)
        blit_center(s, text("Complétez le RADAR pour retenter", "semi", 24, (170, 170, 200)), W / 2, H - 40)


class ChapterScene(Scene):
    duration = 3.6
    priority = 8

    def draw(self, s, game):
        ch = self.kw.get("chapter", 1)
        info = CHAPTERS.get(ch, CHAPTERS[1])
        complete = self.kw.get("complete", False)
        radial_bg(s, (60, 40, 120), (4, 2, 12))
        rays(s, W / 2, H / 2, (200, 170, 255), self.t * 0.6, n=20, alpha=35)
        keys = info["keys"]
        for i, k in enumerate(keys):
            x = W / 2 + (i - (len(keys) - 1) / 2) * 250
            L = LEG_BY_KEY[k]
            d = max(0.0, self.t - 0.3 * i)
            size = int(170 * ease_out_back(min(1, d / 0.6)))
            if size > 4:
                au = art.creature_aura(k, 170, L.color, 10)
                s.blit(au, (x - au.get_width() / 2, 230 - au.get_height() / 2), special_flags=pygame.BLEND_ADD)
                s.blit(art.creature(k, size), (x - size / 2, 230 - size / 2))
        title = f"CHAPITRE {ch} TERMINÉ !" if complete else f"CHAPITRE {ch} : {info['title']}"
        im = big_text(title, 54, (255, 255, 255), outline=(40, 20, 90), ow=5)
        slam(s, im, W / 2, 60, self.t)
        sub = (f"{info['wizard']} prêt au Centre Pokémon !" if complete else info["sub"])
        blit_center(s, text(sub, "black", 30, (255, 230, 140), outline=(0, 0, 0), outline_w=3), W / 2, H - 70)


class ChapterWizardScene(Scene):
    duration = 3.0
    priority = 9

    def draw(self, s, game):
        ch = self.kw.get("chapter", 1)
        info = CHAPTERS.get(ch, CHAPTERS[1])
        hue = (self.t * 0.3) % 1
        c = pygame.Color(0)
        c.hsva = (hue * 360, 70, 60, 100)
        radial_bg(s, (c.r, c.g, c.b), (5, 0, 10))
        rays(s, W / 2, H / 2, (255, 255, 255), self.t, n=24, alpha=35)
        keys = info["keys"]
        for i, k in enumerate(keys):
            a = self.t * 1.5 + i * 2 * math.pi / len(keys)
            x = W / 2 + math.cos(a) * 280
            y = H / 2 + 20 + math.sin(a) * 60
            s.blit(art.creature(k, 150), (x - 75, y - 75))
        im = big_text(info["wizard"], 66, (255, 255, 255), outline=(60, 0, 80), ow=6)
        slam(s, im, W / 2, 70, self.t)
        blit_center(s, text(f"{info['wizard_place']}  ·  MULTIBALL {info['balls']} BILLES", "black", 28,
                            (255, 230, 140), outline=(0, 0, 0), outline_w=3), W / 2, H - 45)


class MysteryScene(Scene):
    duration = 2.8
    priority = 6

    def draw(self, s, game):
        from ..data import MYSTERY_AWARDS
        radial_bg(s, (90, 30, 140), (6, 0, 12))
        if self.t < 1.3:
            i = int(self.t * 16) % len(MYSTERY_AWARDS)
            name = MYSTERY_AWARDS[i][0]
            blit_center(s, big_text(name, 60, (200, 180, 255), ow=4), W / 2, H / 2)
            blit_center(s, text("? MYSTÈRE ?", "black", 34, (255, 255, 255)), W / 2, 60)
        else:
            if not self.sp.p and self.t < 1.4:
                self.sp.burst(W / 2, H / 2, 60, cols=[(220, 180, 255), (255, 255, 255)], g=0)
            self.sp.draw(s)
            im = big_text(self.kw.get("award", ""), 70, (255, 255, 255), outline=(70, 20, 110), ow=6)
            slam(s, im, W / 2, H / 2 - 20, self.t - 1.3)
            blit_center(s, text(self.kw.get("desc", ""), "semi", 30, (230, 210, 255), outline=(0, 0, 0), outline_w=2),
                        W / 2, H / 2 + 70)


class TeamRocketScene(Scene):
    duration = 2.8
    priority = 7

    def draw(self, s, game):
        on = int(self.t * 6) % 2 == 0
        s.fill((120, 0, 0) if on else (30, 0, 0))
        r = text("R", "black", 260, (255, 255, 255) if on else (200, 40, 40), outline=(0, 0, 0), outline_w=6)
        blit_center(s, r, W / 2, H / 2 - 30)
        im = big_text("TEAM ROCKET !", 68, (255, 255, 255), outline=(80, 0, 0), ow=6)
        slam(s, im, W / 2, 60, self.t)
        from ..data import SHOT_LABELS
        shot = SHOT_LABELS.get(self.kw.get("shot"), "")
        blit_center(s, text(f"Ils volent des Pokémon ! Tirez : {shot}", "black", 28, (255, 220, 220),
                            outline=(0, 0, 0), outline_w=3), W / 2, H - 50)


class RocketDefeatedScene(Scene):
    duration = 2.8
    priority = 7

    def draw(self, s, game):
        s.blit(gradient_surface(W, H, (40, 60, 140), (140, 180, 255)), (0, 0))
        t = self.t
        x = W / 2 + t * 260
        y = H / 2 + 60 - t * 220
        sz = max(4, int(90 - t * 30))
        pygame.draw.circle(s, (255, 255, 255), (int(x), int(y)), sz // 3)
        if t > 2.0:
            g = glow(int(40 + 20 * math.sin(t * 30)), (255, 255, 200))
            s.blit(g, (x - g.get_width() / 2, y - g.get_height() / 2), special_flags=pygame.BLEND_ADD)
        im = text("LA TEAM ROCKET S'ENVOLE", "black", 44, (255, 255, 255), outline=(20, 30, 90), outline_w=4)
        blit_center(s, im, W / 2, 60)
        blit_center(s, text("VERS D'AUTRES CIEUX !", "black", 44, (255, 230, 120), outline=(20, 30, 90),
                            outline_w=4), W / 2, 115)
        blit_center(s, big_text(fmt(self.kw.get("value", 0)), 50, (255, 255, 255), ow=4), W / 2, H - 60)


class TiltScene(Scene):
    duration = 2.0
    priority = 10

    def draw(self, s, game):
        warn = self.kw.get("warn")
        on = int(self.t * 5) % 2 == 0
        s.fill((140, 0, 0) if on else (20, 0, 0))
        if warn:
            im = big_text("ATTENTION !", 90, (255, 255, 255), ow=6)
            blit_center(s, im, W / 2, H / 2 - 20)
            blit_center(s, text(f"Avertissement {self.kw.get('n', 1)}/2", "black", 34, (255, 200, 200)), W / 2,
                        H / 2 + 70)
        else:
            blit_center(s, big_text("TILT", 170, (255, 255, 255), ow=8), W / 2, H / 2)


class BonusScene(Scene):
    duration = 5.5
    priority = 9

    def draw(self, s, game):
        radial_bg(s, (30, 40, 110), (2, 2, 12))
        blit_center(s, big_text("BONUS", 56, (255, 230, 100), ow=4), W / 2, 44)
        lines = self.kw.get("lines", [])
        for i, (name, n, v) in enumerate(lines):
            d = self.t - 0.4 - i * 0.45
            if d < 0:
                break
            y = 100 + i * 46
            a = min(1, d * 4)
            l1 = text(name, "black", 30, (220, 230, 255))
            l2 = text(f"{n} x {fmt(v)}", "digital", 30, (255, 255, 255))
            l1.set_alpha(int(255 * a))
            l2.set_alpha(int(255 * a))
            s.blit(l1, (140, y))
            s.blit(l2, (W - 140 - l2.get_width(), y))
        d = self.t - 0.4 - len(lines) * 0.45
        if d > 0:
            m = text(f"MULTIPLICATEUR x{self.kw.get('mult', 1)}", "black", 32, (255, 200, 80), outline=(0, 0, 0),
                     outline_w=2)
            blit_center(s, m, W / 2, 400)
        if d > 0.5:
            tot = big_text(fmt(self.kw.get("total", 0) * min(1, (d - 0.5) * 1.5)), 50, (255, 255, 255), ow=4)
            blit_center(s, tot, W / 2, 460)


class PlayerUpScene(Scene):
    duration = 2.0
    priority = 5

    def draw(self, s, game):
        radial_bg(s, (40, 60, 140), (2, 4, 14))
        rays(s, W / 2, H / 2, (150, 180, 255), self.t * 0.5, n=12, alpha=30)
        im = big_text(f"JOUEUR {self.kw.get('player', 1)}", 80, (255, 255, 255), outline=(20, 30, 90), ow=6)
        slam(s, im, W / 2, H / 2 - 50, self.t)
        b = text(f"BALLE {self.kw.get('ball', 1)}", "black", 44, (255, 220, 90), outline=(0, 0, 0), outline_w=3)
        blit_center(s, b, W / 2, H / 2 + 50)
        blit_center(s, text("Tirez la tirette : visez le couloir qui clignote !", "semi", 24, (210, 210, 240)),
                    W / 2, H - 50)


class MewtwoIntroScene(Scene):
    duration = 5.0
    priority = 10

    def draw(self, s, game):
        t = self.t
        s.fill((0, 0, 0))
        k = ease_out(min(1, t / 2.0))
        radial_bg(s, (int(90 * k), int(20 * k), int(140 * k)), (0, 0, 0))
        for i in range(6):
            r = ((t * 220 + i * 90) % 540)
            pygame.draw.circle(s, (int(160 * (1 - r / 540)), 60, int(255 * (1 - r / 540))), (W // 2, H // 2), int(r), 3)
        if t > 1.0:
            size = int(380 * ease_out_back(min(1, (t - 1.0) / 1.2)))
            if size > 4:
                au = art.creature_aura("mewtwo", size, (190, 90, 255), 20)
                s.blit(au, (W / 2 - au.get_width() / 2, H / 2 - au.get_height() / 2 + 10),
                       special_flags=pygame.BLEND_ADD)
                s.blit(art.creature("mewtwo", size), (W / 2 - size / 2, H / 2 - size / 2 + 10))
        if t > 2.2:
            im = big_text("MEWTWO", 100, (255, 255, 255), outline=(70, 0, 110), ow=7,
                          grad=((255, 255, 255), (210, 160, 255)))
            slam(s, im, W / 2, 70, t - 2.2)
        if t > 3.0:
            blit_center(s, text("« Je suis né pour être le plus fort. »", "semi", 28, (220, 190, 255),
                                outline=(0, 0, 0), outline_w=2), W / 2, H - 50)


class MewtwoPhaseScene(Scene):
    duration = 2.8
    priority = 9

    def draw(self, s, game):
        radial_bg(s, (90, 30, 140), (5, 0, 12))
        rays(s, W / 2, H / 2, (200, 140, 255), -self.t * 0.8, n=16, alpha=40)
        n = self.kw.get("n", 1)
        blit_center(s, text(f"PHASE {n}/3", "black", 36, (230, 200, 255), outline=(0, 0, 0), outline_w=3), W / 2, 60)
        im = big_text(self.kw.get("title", ""), 72, (255, 255, 255), outline=(70, 0, 110), ow=6)
        slam(s, im, W / 2, H / 2 - 10, self.t)
        blit_center(s, text(self.kw.get("sub", ""), "black", 30, (255, 220, 140), outline=(0, 0, 0), outline_w=3),
                    W / 2, H - 70)


class ShieldBreakScene(Scene):
    duration = 1.2
    priority = 4
    full = False

    def init(self):
        self.shards = [(random.uniform(0, 2 * math.pi), random.uniform(200, 600)) for _ in range(20)]

    def draw(self, s, game):
        t = self.t
        for a, sp in self.shards:
            x = W / 2 + math.cos(a) * sp * t
            y = H / 2 + math.sin(a) * sp * t + 300 * t * t
            pygame.draw.polygon(s, (220, 180, 255), [(x, y), (x + 12, y + 5), (x + 4, y + 16)])
        im = text(f"BOUCLIER BRISÉ !  ({self.kw.get('left', 0)} restants)", "black", 36, (255, 255, 255),
                  outline=(80, 0, 120), outline_w=4)
        im.set_alpha(int(255 * self.fade()))
        blit_center(s, im, W / 2, 30)


class VictoryScene(Scene):
    duration = 9.0
    priority = 10

    def update(self, dt):
        super().update(dt)
        if random.random() < dt * 5:
            self.sp.burst(random.uniform(100, W - 100), random.uniform(60, H / 2), 70,
                          cols=[(255, 90, 90), (255, 230, 80), (120, 220, 255), (200, 120, 255), (255, 255, 255)],
                          speed=(80, 380), life=(0.8, 1.8), g=120)

    def draw(self, s, game):
        t = self.t
        hue = (t * 0.2) % 1
        c = pygame.Color(0)
        c.hsva = (hue * 360, 60, 45, 100)
        radial_bg(s, (c.r, c.g, c.b), (0, 0, 0))
        rays(s, W / 2, H / 2, (255, 255, 255), t * 0.4, n=24, alpha=25)
        self.sp.draw(s)
        art.draw_pokeball(s, W / 2, H / 2 + 20, 90, angle=math.sin(t * 2) * 6, top=(120, 40, 170))
        im = big_text("MEWTWO CAPTURÉ !", 74, (255, 255, 255), outline=(70, 0, 110), ow=6)
        slam(s, im, W / 2, 70, t)
        if t > 1.5:
            blit_center(s, big_text("MAÎTRE POKÉMON", 60, (255, 230, 90), outline=(90, 50, 0), ow=5,
                                    grad=((255, 255, 200), (255, 170, 30))), W / 2, H - 120)
        if t > 2.5:
            blit_center(s, big_text(fmt(self.kw.get("value", 0)), 44, (255, 255, 255), ow=4), W / 2, H - 50)


class GameOverScene(Scene):
    duration = 7.0
    priority = 10

    def draw(self, s, game):
        radial_bg(s, (60, 20, 40), (4, 2, 6))
        im = big_text("GAME OVER", 100, (255, 255, 255), outline=(90, 10, 30), ow=7)
        slam(s, im, W / 2, 110, self.t)
        scores = self.kw.get("players", [])
        for i, sc in enumerate(scores):
            blit_center(s, text(f"J{i + 1}   {fmt(sc)}", "digital", 40, (255, 230, 150)), W / 2, 230 + i * 48)
        if self.t > 2.5:
            m = self.kw.get("match", 0)
            spin = int(self.t * 20) % 10 * 10 if self.t < 4.0 else m
            blit_center(s, text(f"MATCH  {spin:02d}", "black", 40, (200, 200, 255), outline=(0, 0, 0), outline_w=3),
                        W / 2, H - 50)


SCENES = {
    "message": MessageScene, "jackpot": JackpotScene, "super_jackpot": SuperJackpotScene,
    "multiball": MultiballScene, "ball_saved": BallSavedScene, "extra_ball": ExtraBallScene,
    "extra_ball_lit": (ExtraBallScene, {"title": "EXTRA BALL ALLUMÉE", "sub": "Tirez le Centre Pokémon"}),
    "shoot_again": (ExtraBallScene, {"title": "REJOUEZ !", "sub": "Même joueur, nouvelle bille"}),
    "skill_shot": SkillShotScene, "combo": ComboScene, "radar": RadarScene, "mode_lit": ModeLitScene,
    "bonus_x": BonusXScene, "wild_appears": WildAppearsScene, "wild_caught": WildCaughtScene,
    "mode_select": ModeSelectScene, "legendary_intro": LegendaryIntroScene, "leg_hit": LegHitScene,
    "capture_phase": CapturePhaseScene, "shake": ShakeScene, "gotcha": GotchaScene,
    "broke_free": BrokeFreeScene, "escaped": EscapedScene,
    "chapter_complete": (ChapterScene, {"complete": True}), "chapter_intro": ChapterScene,
    "chapter_wizard": ChapterWizardScene, "mystery": MysteryScene, "team_rocket": TeamRocketScene,
    "rocket_defeated": RocketDefeatedScene, "tilt_warning": (TiltScene, {"warn": True}), "tilt": TiltScene,
    "bonus": BonusScene, "player_up": PlayerUpScene, "mewtwo_intro": MewtwoIntroScene,
    "mewtwo_phase": MewtwoPhaseScene, "shield_break": ShieldBreakScene, "victory": VictoryScene,
    "game_over": GameOverScene,
}


# ==========================================================================
# Écran LCD
# ==========================================================================
class LCD:
    def __init__(self):
        self.surf = pygame.Surface((W, H)).convert()
        self.overlay = None
        self.queue = []
        self.minor = []          # petites incrustations (combo, radar, dégâts)
        self.t = 0.0
        self.bg = Sparks()
        self.game_ref = None
        self.attract_page = 0
        self.attract_t = 0.0
        self.scanlines = self._scanlines()
        self.hp_disp = 1.0

    def _scanlines(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        for y in range(0, H, 3):
            pygame.draw.line(s, (0, 0, 0, 28), (0, y), (W, y))
        return s

    def push(self, name, **kw):
        entry = SCENES.get(name)
        if entry is None:
            return
        if isinstance(entry, tuple):
            cls, extra = entry
            kw = dict(extra, **kw)
        else:
            cls = entry
        sc = cls(self, **kw)
        if not sc.full:
            self.minor = [m for m in self.minor if type(m) is not type(sc)]
            self.minor.append(sc)
            return
        cur = self.overlay
        if cur is None or sc.priority >= cur.priority:
            if cur is not None and cur.priority >= 6 and not cur.done and cur.t < cur.duration * 0.5 \
                    and sc.priority < 9:
                self.queue.insert(0, sc) if sc.priority > cur.priority else self.queue.append(sc)
                if sc.priority > cur.priority:
                    self.queue.pop(0)
                    self.overlay = sc
                    self.queue.insert(0, cur)
                return
            self.overlay = sc
        else:
            self.queue.append(sc)
            self.queue.sort(key=lambda q: -q.priority)
            self.queue = self.queue[:4]

    def clear(self):
        self.overlay = None
        self.queue = []
        self.minor = []

    def update(self, dt, game):
        self.game_ref = game
        self.t += dt
        self.bg.update(dt)
        if self.overlay:
            self.overlay.update(dt)
            if self.overlay.done:
                self.overlay = self.queue.pop(0) if self.queue else None
        for m in self.minor:
            m.update(dt)
        self.minor = [m for m in self.minor if not m.done]
        if game.state == "attract":
            self.attract_t += dt
            if self.attract_t > 7.0:
                self.attract_t = 0.0
                self.attract_page = (self.attract_page + 1) % 5
        if game.select is not None and not isinstance(self.overlay, ModeSelectScene):
            if not isinstance(self.overlay, LegendaryIntroScene):
                self.push("mode_select")

    # ------------------------------------------------------------------
    def draw(self, game):
        s = self.surf
        if self.overlay is not None:
            self.overlay.draw(s, game)
        elif game.state == "attract" or (game.state == "game_over" and game.hs_entry is None):
            self.draw_attract(s, game)
        elif game.hs_entry is not None:
            self.draw_hs_entry(s, game)
        else:
            self.draw_base(s, game)
        for m in self.minor:
            m.draw(s, game)
        s.blit(self.scanlines, (0, 0))
        return s

    # ------------------------------------------------------------------
    def draw_base(self, s, game):
        p = game.player
        hud = game.hud() if p else None
        kind = hud["kind"] if hud else "base"
        col = game.gi_color if kind != "base" else (60, 80, 160)
        s.fill((4, 5, 14))
        g = glow(520, mul_col(col, 0.38), falloff=1.4)
        s.blit(g, (W / 2 - 520, H / 2 - 520), special_flags=pygame.BLEND_ADD)
        # particules d'ambiance selon le type
        if random.random() < 0.5:
            leg = hud.get("leg") if hud else None
            tp = leg.type if leg else None
            if tp == "Glace":
                self.bg.rain(W, 1, [(220, 240, 255)], vy=(40, 120))
            elif tp == "Feu":
                self.bg.p.append([random.uniform(0, W), H + 5, random.uniform(-20, 20), random.uniform(-160, -60),
                                  2.5, 0.0, random.choice([(255, 150, 40), (255, 80, 20)]), 3, 0])
            elif tp == "Eau":
                self.bg.p.append([random.uniform(0, W), H + 5, 0, random.uniform(-90, -40), 5, 0.0,
                                  (120, 180, 255), 4, 0])
            elif tp == "Électrik":
                if random.random() < 0.2:
                    self.bg.burst(random.uniform(0, W), random.uniform(0, H), 6, cols=[(255, 240, 120)], g=0,
                                  speed=(60, 200), life=(0.2, 0.4))
            else:
                self.bg.rain(W, 1, [mul_col(col, 0.8)], vy=(20, 60))
        self.bg.draw(s)
        # score
        self.draw_scores(s, game)
        if kind == "legendary":
            self.draw_leg_hud(s, game, hud)
        elif kind == "mewtwo":
            self.draw_mewtwo_hud(s, game, hud)
        elif kind == "multiball":
            self.draw_mb_hud(s, game, hud)
        else:
            self.draw_idle_hud(s, game, hud)
        from ..modes import TeamRocketMode
        rocket = game.active(TeamRocketMode)
        if rocket:
            on = int(self.t * 4) % 2 == 0
            pygame.draw.rect(s, (160, 0, 0) if on else (90, 0, 0), pygame.Rect(0, H - 78, W, 40))
            im = text(f"TEAM ROCKET  {fmt(rocket.value)}  ·  {max(0, int(rocket.time))}s", "black", 26,
                      (255, 255, 255))
            blit_center(s, im, W / 2, H - 58)
        self.draw_status_bar(s, game)

    def draw_scores(self, s, game):
        p = game.player
        n = len(game.players)
        big = text(fmt(p.score), "digital", 74 if p.score < 10 ** 10 else 60, (255, 255, 255),
                   outline=(20, 30, 70), outline_w=4)
        blit_center(s, big, W / 2, 46)
        for pl in game.players:
            if pl is p:
                continue
            im = text(f"J{pl.idx + 1}  {fmt(pl.score)}", "digital", 22, (170, 180, 220))
            x = 14 if pl.idx % 2 == 0 else W - im.get_width() - 14
            y = 8 if pl.idx < 2 else 34
            s.blit(im, (x, y))

    def draw_status_bar(self, s, game):
        p = game.player
        info = f"JOUEUR {p.idx + 1}   ·   BALLE {min(p.ball, 3)}/3"
        if p.extra_balls:
            info += f"   ·   EXTRA BALL x{p.extra_balls}"
        im = text(info, "semi", 20, (170, 180, 220))
        s.blit(im, (14, H - 28))
        right = f"POKÉDEX {len(p.pokedex)}   ·   LÉGENDAIRES {len([k for k in p.captured if k in LEG_BY_KEY])}/11"
        if p.multi_exp_t > 0:
            right = f"MULTI EXP x2 {int(p.multi_exp_t)}s   ·   " + right
        im2 = text(right, "semi", 20, (170, 180, 220))
        s.blit(im2, (W - im2.get_width() - 14, H - 28))
        if game.ball_save_t > 0:
            on = int(self.t * 4) % 2 == 0
            if on:
                bs = text("BALL SAVE", "black", 20, (255, 170, 60))
                blit_center(s, bs, W / 2, H - 18)

    def draw_leg_hud(self, s, game, hud):
        leg = hud["leg"]
        phase = hud["phase"]
        x0, y0 = 40, 108
        bob = math.sin(self.t * 2.4) * 6
        size = 250
        au = art.creature_aura(leg.key, size, leg.color, 14)
        pulse = 0.6 + 0.4 * math.sin(self.t * 3)
        au2 = au.copy()
        kk = int(255 * pulse)
        au2.fill((kk, kk, kk), special_flags=pygame.BLEND_MULT)
        s.blit(au2, (x0 + 10 - 28, y0 + bob - 28), special_flags=pygame.BLEND_ADD)
        img = art.creature(leg.key, size)
        if phase == "capture":
            img = img.copy()
            img.fill((255, 140, 140, 255), special_flags=pygame.BLEND_RGBA_MULT)
        s.blit(img, (x0 + 10, y0 + bob))
        # boîte de nom façon combat Pokémon
        bx, by, bw, bh = 330, 108, 540, 108
        pygame.draw.rect(s, (245, 245, 235), pygame.Rect(bx, by, bw, bh), border_radius=14)
        pygame.draw.rect(s, (40, 50, 70), pygame.Rect(bx, by, bw, bh), 4, border_radius=14)
        nm = text(leg.name, "black", 34, (40, 40, 50))
        s.blit(nm, (bx + 18, by + 10))
        lv = text(f"N.{50 + leg.chapter * 10}", "black", 26, (40, 40, 50))
        s.blit(lv, (bx + bw - lv.get_width() - 18, by + 14))
        ti = art.type_icon(leg.type, 30, leg.color)
        s.blit(ti, (bx + 26 + nm.get_width(), by + 14))
        target = hud["hp"]
        self.hp_disp += (target - self.hp_disp) * 0.12
        if abs(self.hp_disp - target) > 0.5:
            self.hp_disp = target
        hp_bar(s, bx + 70, by + 64, bw - 100, 22, self.hp_disp)
        # minuteur
        tm = hud.get("timer")
        if tm is not None:
            tx, ty = 800, 290
            frac = max(0.0, min(1.0, tm / 99.0))
            pygame.draw.circle(s, (20, 20, 30), (tx, ty), 56)
            pygame.draw.arc(s, (255, 90, 90) if tm < 10 else (255, 220, 90),
                            pygame.Rect(tx - 52, ty - 52, 104, 104), math.pi / 2, math.pi / 2 + 2 * math.pi * frac, 8)
            im = text(f"{max(0, int(tm))}", "black", 52, (255, 255, 255))
            blit_center(s, im, tx, ty)
        if phase == "capture":
            n, need = hud.get("shakes", 0), hud.get("need", 3)
            for i in range(need):
                cx = 400 + i * 70
                art.draw_pokeball(s, cx, 290, 24, shading=False,
                                  top=(230, 40, 50) if i < n else (90, 90, 100),
                                  bottom=(240, 240, 240) if i < n else (120, 120, 130))
        # consignes
        for j, ln in enumerate(hud.get("lines", [])[:3]):
            col = (255, 255, 255) if j == 0 else (200, 205, 230)
            im = text(ln, "black" if j == 0 else "semi", 28 if j == 0 else 24, col, outline=(0, 0, 0), outline_w=2)
            s.blit(im, (330, 340 + j * 34))
        ex = hud.get("extra")
        if ex and phase == "battle":
            pill = text(ex, "black", 24, (20, 20, 30))
            r = pygame.Rect(330, 240, pill.get_width() + 30, 40)
            pygame.draw.rect(s, leg.color, r, border_radius=20)
            s.blit(pill, (r.x + 15, r.y + 6))
        pts = hud.get("points", 0)
        if pts:
            im = text(f"MODE  {fmt(pts)}", "digital", 22, (200, 200, 230))
            s.blit(im, (800 - im.get_width() / 2, 352))

    def draw_mewtwo_hud(self, s, game, hud):
        stage = hud["stage"]
        bob = math.sin(self.t * 2) * 6
        size = 260
        au = art.creature_aura("mewtwo", size, (180, 80, 255), 16)
        s.blit(au, (60 - 32, 110 + bob - 32), special_flags=pygame.BLEND_ADD)
        s.blit(art.creature("mewtwo", size), (60, 110 + bob))
        bx, by, bw = 360, 110, 500
        pygame.draw.rect(s, (30, 10, 50), pygame.Rect(bx, by, bw, 100), border_radius=14)
        pygame.draw.rect(s, (190, 120, 255), pygame.Rect(bx, by, bw, 100), 4, border_radius=14)
        s.blit(text("MEWTWO", "black", 36, (255, 255, 255)), (bx + 18, by + 8))
        s.blit(text(f"PHASE {stage}/3", "black", 24, (220, 180, 255)), (bx + bw - 150, by + 14))
        if stage == 1:
            n = hud.get("shields", 7)
            for i in range(7):
                c = (190, 120, 255) if i < n else (60, 40, 80)
                pygame.draw.polygon(s, c, [(bx + 40 + i * 62, by + 60), (bx + 70 + i * 62, by + 52),
                                           (bx + 90 + i * 62, by + 70), (bx + 60 + i * 62, by + 88)])
        else:
            hp_bar(s, bx + 60, by + 62, bw - 90, 22, hud["hp"])
        if stage == 3:
            n = hud.get("shakes", 0)
            for i in range(3):
                art.draw_pokeball(s, 470 + i * 80, 280, 28, shading=False, top=(120, 40, 170) if i < n else (70, 60, 80))
        for j, ln in enumerate(hud.get("lines", [])[:3]):
            im = text(ln, "black" if j == 0 else "semi", 30 if j == 0 else 24, (255, 255, 255) if j == 0 else (210, 200, 240),
                      outline=(0, 0, 0), outline_w=2)
            s.blit(im, (360, 330 + j * 36))

    def draw_mb_hud(self, s, game, hud):
        t = self.t
        for i in range(3):
            a = t * 1.5 + i * 2.1
            art.draw_pokeball(s, 150 + math.cos(a) * 80, 260 + math.sin(a) * 50, 34, angle=t * 200 + i * 50)
        im = big_text(hud.get("title", "MULTIBALL"), 48, (255, 255, 255), ow=4)
        s.blit(im, (320, 120))
        v = text(f"JACKPOT  {fmt(hud.get('value', 0))}", "black", 36, (255, 230, 90), outline=(0, 0, 0), outline_w=3)
        s.blit(v, (330, 200))
        s.blit(text(f"Jackpots : {hud.get('jackpots', 0)}   ·   Total {fmt(hud.get('total', 0))}", "semi", 26,
                    (220, 230, 255)), (330, 255))
        for j, ln in enumerate(hud.get("lines", [])):
            s.blit(text(ln, "semi", 26, (230, 255, 230) if not hud.get("super") else (255, 230, 120)), (330, 310 + j * 34))

    def draw_idle_hud(self, s, game, hud):
        p = game.player
        lines = hud.get("lines", []) if hud else []
        # carte objectif
        r = pygame.Rect(150, 130, W - 300, 200)
        lay = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(lay, (20, 30, 70, 200), lay.get_rect(), border_radius=18)
        pygame.draw.rect(lay, (110, 140, 255, 255), lay.get_rect(), 3, border_radius=18)
        s.blit(lay, r.topleft)
        for j, ln in enumerate(lines[:3]):
            im = text(ln, "black" if j == 0 else "semi", 38 if j == 0 else 28,
                      (255, 230, 100) if j == 0 else (220, 225, 255), outline=(0, 0, 0), outline_w=2)
            blit_center(s, im, W / 2, r.y + 50 + j * 50)
        # progression des chapitres
        ch = min(p.chapter, 4)
        info = CHAPTERS.get(ch)
        if info:
            keys = info["keys"]
            for i, k in enumerate(keys):
                x = W / 2 + (i - (len(keys) - 1) / 2) * 120
                if k in p.captured:
                    s.blit(art.creature(k, 90), (x - 45, 352))
                else:
                    s.blit(art.creature_silhouette(k, 90, (40, 50, 90)), (x - 45, 352))
            im = text(f"CHAPITRE {ch} · {info['sub']}", "semi", 22, (170, 180, 230))
            blit_center(s, im, W / 2, 455)

    # ------------------------------------------------------------------
    def draw_attract(self, s, game):
        t = self.attract_t
        page = self.attract_page
        s.fill((3, 3, 12))
        if page == 0:
            hue = (self.t * 0.05) % 1
            c = pygame.Color(0)
            c.hsva = (hue * 360, 60, 40, 100)
            radial_bg(s, (c.r, c.g, c.b), (2, 2, 10))
            rays(s, W / 2, H / 2, (255, 255, 255), self.t * 0.2, n=20, alpha=18)
            keys = [l.key for l in LEGENDARIES] + ["mew", "mewtwo"]
            for i, k in enumerate(keys):
                x = (i * 150 - self.t * 90) % (len(keys) * 150) - 150
                s.blit(art.creature(k, 120), (x, H - 170))
            lg = art.logo(620)
            s.blit(lg, (W / 2 - lg.get_width() / 2, 30))
            if int(self.t * 2) % 2 == 0:
                blit_center(s, text("APPUYEZ SUR ENTRÉE POUR JOUER", "black", 34, (255, 255, 255), outline=(0, 0, 0),
                                    outline_w=3), W / 2, 285)
        elif page == 1:
            radial_bg(s, (60, 40, 10), (2, 2, 6))
            blit_center(s, big_text("MEILLEURS DRESSEURS", 46, (255, 220, 80), ow=4), W / 2, 50)
            for i, (name, sc) in enumerate(game.high_scores[:6]):
                lab = "GRAND CHAMPION" if i == 0 else f"#{i}"
                col = (255, 230, 120) if i == 0 else (220, 225, 255)
                s.blit(text(lab, "black", 28, col), (110, 112 + i * 60))
                s.blit(text(name, "black", 34, (255, 255, 255)), (380, 108 + i * 60))
                im = text(fmt(sc), "digital", 34, col)
                s.blit(im, (W - 110 - im.get_width(), 108 + i * 60))
        elif page == 2:
            radial_bg(s, (20, 50, 100), (2, 2, 8))
            blit_center(s, big_text("COMMENT JOUER", 46, (255, 255, 255), ow=4), W / 2, 44)
            rules = ["POKÉ RADAR (cibles vertes) → allume un LÉGENDAIRE",
                     "CENTRE POKÉMON (scoop) → choisissez votre combat",
                     "Touchez les flèches de couleur pour l'affaiblir",
                     "Puis frappez la POKÉBALL 3 fois : GOTCHA !",
                     "HAUTES HERBES → Pokémon sauvage → capture",
                     "3 captures → MULTIBALL SAFARI",
                     "Cibles TEAM ROCKET → Hurry-up",
                     "11 légendaires + Mew → combat final : MEWTWO"]
            for i, ln in enumerate(rules):
                s.blit(text(ln, "semi", 25, (225, 230, 255)), (70, 100 + i * 47))
        elif page == 3:
            leg = LEGENDARIES[int(self.t / 7) % len(LEGENDARIES)]
            radial_bg(s, mul_col(leg.color, 0.5), (2, 2, 8))
            au = art.creature_aura(leg.key, 330, leg.color, 16)
            s.blit(au, (60 - 32, 90 - 32), special_flags=pygame.BLEND_ADD)
            s.blit(art.creature(leg.key, 330), (60, 90 + math.sin(self.t * 2) * 8))
            s.blit(big_text(leg.name, 60, (255, 255, 255), outline=mul_col(leg.color, 0.4), ow=5), (430, 130))
            s.blit(text(f"N°{leg.num:03d} · Type {leg.type}", "black", 28, lerp_col(leg.color, (255, 255, 255), 0.5)),
                   (440, 215))
            s.blit(text(leg.mode_title, "semi", 28, (220, 220, 240)), (440, 260))
            for j, ln in enumerate(leg.rules_text):
                s.blit(text("• " + ln, "semi", 24, (200, 205, 230)), (440, 310 + j * 34))
        else:
            radial_bg(s, (90, 30, 140), (3, 0, 8))
            au = art.creature_aura("mewtwo", 360, (190, 90, 255), 20)
            s.blit(au, (W / 2 - au.get_width() / 2, 80 - 36 + 180 - au.get_height() / 2 + 36),
                   special_flags=pygame.BLEND_ADD)
            s.blit(art.creature("mewtwo", 360), (W / 2 - 180, 80))
            blit_center(s, big_text("L'ULTIME DÉFI", 54, (255, 255, 255), outline=(70, 0, 110), ow=5), W / 2, 50)
            blit_center(s, text("Capturez les 11 légendaires pour affronter MEWTWO", "black", 28, (230, 200, 255),
                                outline=(0, 0, 0), outline_w=2), W / 2, H - 50)

    def draw_hs_entry(self, s, game):
        h = game.hs_entry
        radial_bg(s, (110, 80, 10), (4, 2, 0))
        blit_center(s, big_text("NOUVEAU RECORD !", 56, (255, 230, 90), ow=5), W / 2, 60)
        pl = h["queue"][0]
        blit_center(s, text(f"JOUEUR {pl.idx + 1}  ·  {fmt(pl.score)}", "digital", 36, (255, 255, 255)), W / 2, 140)
        for i in range(3):
            ch = game.ALPHA[h["letters"][i]]
            x = W / 2 + (i - 1) * 110
            r = pygame.Rect(x - 45, 200, 90, 120)
            pygame.draw.rect(s, (40, 30, 10), r, border_radius=12)
            pygame.draw.rect(s, (255, 220, 80) if i == h["pos"] else (120, 100, 50), r, 4, border_radius=12)
            blit_center(s, text(ch if ch != " " else "_", "black", 80, (255, 255, 255)), x, 260)
        blit_center(s, text("Flippers : lettre   ·   ENTRÉE : valider", "semi", 26, (230, 220, 200)), W / 2, 380)
