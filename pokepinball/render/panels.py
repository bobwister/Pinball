"""Panneaux du « meuble » : fronton (translite), cadre du LCD, tableau des missions."""
import math
import random

import pygame

from ..data import LEG_BY_KEY, CHAPTERS
from .assets import text, glow, gradient_surface, mul_col, blit_center
from . import art

TRANSLITE = pygame.Rect(962, 8, 946, 470)
LCD_BEZEL = pygame.Rect(966, 486, 938, 540)
LCD_POS = (983, 502)
BOARD = pygame.Rect(10, 8, 428, 1064)


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


class Panels:
    def __init__(self):
        self.t = 0.0
        self.translite = self._build_translite()
        self.bezel = self._build_bezel()
        self.board_bg = self._build_board_bg()
        self.flash_col = None
        self.flash_t = 0.0
        self.bulbs = self._bulb_positions()

    # ------------------------------------------------------------------
    def _build_translite(self):
        w, h = TRANSLITE.size
        s = pygame.Surface((w, h))
        s.blit(gradient_surface(w, h, (18, 10, 52), (40, 14, 70)), (0, 0))
        rnd = random.Random(5)
        for _ in range(260):
            b = rnd.randint(80, 255)
            pygame.draw.circle(s, (b, b, 255), (rnd.randint(0, w), rnd.randint(0, h)), rnd.choice((1, 1, 2)))
        for x, y, r, c in ((w / 2, h * 0.62, 330, (130, 50, 200)), (120, 300, 200, (40, 90, 200)),
                           (w - 120, 300, 200, (200, 70, 40))):
            g = glow(r, c, falloff=1.5)
            s.blit(g, (x - r, y - r), special_flags=pygame.BLEND_ADD)
        # légendaires autour de Mewtwo
        left = ["articuno", "zapdos", "moltres", "raikou", "entei", "suicune"]
        right = ["lugia", "hooh", "groudon", "kyogre", "rayquaza", "mew"]
        pos_l = [(20, 120), (110, 40), (200, 140), (10, 280), (120, 230), (230, 300)]
        for k, (x, y) in zip(left, pos_l):
            s.blit(art.creature(k, 150), (x, y))
        for k, (x, y) in zip(right, pos_l):
            s.blit(art.creature(k, 150, True), (w - x - 150, y))
        au = art.creature_aura("mewtwo", 330, (190, 90, 255), 22)
        s.blit(au, (w / 2 - au.get_width() / 2, 150 - 44), special_flags=pygame.BLEND_ADD)
        s.blit(art.creature("mewtwo", 330), (w / 2 - 165, 150))
        lg = art.logo(560)
        s.blit(lg, (w / 2 - lg.get_width() / 2, 6))
        rib = text("ATTRAPEZ LES LÉGENDES", "black", 30, (255, 255, 255), outline=(60, 0, 90), outline_w=4)
        blit_center(s, rib, w / 2, h - 28)
        return s

    def _build_bezel(self):
        w, h = LCD_BEZEL.size
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (14, 14, 20), s.get_rect(), border_radius=18)
        pygame.draw.rect(s, (120, 125, 150), s.get_rect(), 4, border_radius=18)
        pygame.draw.rect(s, (40, 42, 56), s.get_rect().inflate(-14, -14), 3, border_radius=14)
        return s

    def _build_board_bg(self):
        w, h = BOARD.size
        s = pygame.Surface((w, h))
        s.blit(gradient_surface(w, h, (14, 16, 38), (8, 8, 20)), (0, 0))
        pygame.draw.rect(s, (90, 100, 160), s.get_rect(), 3, border_radius=12)
        hd = text("MISSIONS LÉGENDAIRES", "black", 28, (255, 225, 90), outline=(30, 30, 80), outline_w=3)
        blit_center(s, hd, w / 2, 30)
        return s

    def _bulb_positions(self):
        r = TRANSLITE
        pts = []
        n = 40
        for i in range(n):
            pts.append((r.x + 10 + i * (r.w - 20) / (n - 1), r.y + 6))
            pts.append((r.x + 10 + i * (r.w - 20) / (n - 1), r.bottom - 6))
        for i in range(1, 16):
            pts.append((r.x + 6, r.y + 6 + i * (r.h - 12) / 16))
            pts.append((r.right - 6, r.y + 6 + i * (r.h - 12) / 16))
        return pts

    # ------------------------------------------------------------------
    def flash(self, col, dur=0.3):
        self.flash_col = col
        self.flash_t = dur

    def update(self, dt):
        self.t += dt
        self.flash_t = max(0.0, self.flash_t - dt)

    def draw(self, screen, game, lcd_surf):
        t = self.t
        # fronton
        screen.blit(self.translite, TRANSLITE.topleft)
        gi = game.gi_color if game.state == "playing" else (200, 180, 255)
        for i, (x, y) in enumerate(self.bulbs):
            on = (int(t * 8) + i) % 6 < 3 if game.state != "playing" else ((int(t * 3) + i) % 4 != 0)
            c = gi if on else mul_col(gi, 0.25)
            pygame.draw.circle(screen, c, (int(x), int(y)), 3)
        for fx in (TRANSLITE.x + 60, TRANSLITE.right - 60):
            k = 0.35 + 0.25 * math.sin(t * 2 + fx)
            col = gi
            if self.flash_t > 0 and self.flash_col:
                k = 1.0
                col = self.flash_col
            g = glow(90, mul_col(col, k), falloff=1.6)
            screen.blit(g, (fx - 90, TRANSLITE.y + 20 - 90), special_flags=pygame.BLEND_ADD)
        pygame.draw.rect(screen, (150, 155, 185), TRANSLITE, 3, border_radius=10)
        # LCD
        screen.blit(self.bezel, LCD_BEZEL.topleft)
        screen.blit(lcd_surf, LCD_POS)
        # boutons sous le LCD
        y = LCD_BEZEL.bottom + 8
        legend = "SHIFT G/D : flippers   ·   ENTRÉE/↓ : tirette   ·   ESPACE/CTRL : secouer   ·   1 : joueur +   ·   F11 · ÉCHAP"
        im = text(legend, "semi", 17, (150, 155, 190))
        screen.blit(im, (LCD_BEZEL.centerx - im.get_width() / 2, y + 12))
        # tableau des missions
        self.draw_board(screen, game)

    # ------------------------------------------------------------------
    def board_key(self, game):
        p = game.player if game.players else None
        if p is None:
            return None
        lm = game.legendary_mode()
        return (p.idx, tuple(p.captured), p.chapter, tuple(sorted(p.wizards_done)), p.wizard_lit, p.chapter_clear,
                p.mew_lit, p.mew_done, p.mewtwo_lit, p.mewtwo_done, len(p.pokedex), p.locks, p.locks_needed,
                p.rocket_defeats, p.bonus_x, int(game.game_time), lm.leg.key if lm else None)

    def draw_board(self, screen, game):
        """Le tableau est mis en cache ; seules les auras animées sont redessinées."""
        key = self.board_key(game)
        if key != getattr(self, "_board_key", "x") or not hasattr(self, "_board_surf"):
            self._board_key = key
            surf = pygame.Surface(BOARD.size)
            self._anim = []
            self._draw_board(surf, game, (-BOARD.x, -BOARD.y))
            self._board_surf = surf
        screen.blit(self._board_surf, BOARD.topleft)
        t = self.t
        for (img, x, y) in self._anim:
            a = img.copy()
            k_ = int(150 + 100 * math.sin(t * 6))
            a.fill((k_, k_, k_), special_flags=pygame.BLEND_MULT)
            screen.blit(a, (x, y), special_flags=pygame.BLEND_ADD)

    def _draw_board(self, screen, game, off):
        b = BOARD.move(off)
        screen.blit(self.board_bg, b.topleft)
        p = game.player if game.players else None
        captured = set(p.captured) if p else set()
        cur_mode = game.legendary_mode() if p else None
        y = b.y + 62
        t = self.t
        for ch in (1, 2, 3, 4):
            info = CHAPTERS[ch]
            active = p is not None and p.chapter == ch
            done = p is not None and ch in p.wizards_done
            card = pygame.Rect(b.x + 12, y, b.w - 24, 170)
            col = (110, 140, 255) if active else ((80, 200, 120) if done else (60, 64, 96))
            pygame.draw.rect(screen, (18, 20, 46), card, border_radius=12)
            pygame.draw.rect(screen, col, card, 3 if active else 2, border_radius=12)
            if active:
                g = glow(40, mul_col(col, 0.5))
                screen.blit(g, (card.right - 70, card.y - 30), special_flags=pygame.BLEND_ADD)
            screen.blit(text(f"CHAPITRE {ch} · {info['title']}", "black", 19, (255, 255, 255)), (card.x + 12, card.y + 8))
            screen.blit(text(info["sub"], "semi", 16, (180, 190, 230)), (card.x + 12, card.y + 32))
            keys = info["keys"]
            for i, k in enumerate(keys):
                x = card.x + 20 + i * 128
                size = 92
                leg = LEG_BY_KEY[k]
                if k in captured:
                    screen.blit(art.creature(k, size), (x, card.y + 52))
                    pygame.draw.circle(screen, (60, 220, 100), (x + size - 8, card.y + 62), 11)
                    pygame.draw.lines(screen, (255, 255, 255), False,
                                      [(x + size - 14, card.y + 62), (x + size - 9, card.y + 67), (x + size - 2, card.y + 56)], 3)
                elif cur_mode is not None and cur_mode.leg.key == k:
                    au = art.creature_aura(k, size, leg.color, 8)
                    self._anim.append((au, x - 16 - off[0], card.y + 52 - 16 - off[1]))
                    screen.blit(art.creature(k, size), (x, card.y + 52))
                elif active:
                    screen.blit(art.creature_silhouette(k, size, mul_col(leg.color, 0.45)), (x, card.y + 52))
                else:
                    screen.blit(art.creature_silhouette(k, size, (40, 42, 66)), (x, card.y + 52))
                nm = text(leg.name, "semi", 14, (220, 220, 240) if (k in captured or active) else (100, 100, 130))
                screen.blit(nm, (x + size / 2 - nm.get_width() / 2, card.y + 146))
            st = "✓" if done else ("PRÊT !" if p and active and p.wizard_lit else "")
            if st:
                im = text(f"{info['wizard']} {st}", "black", 14, (255, 220, 90))
                screen.blit(im, (card.right - im.get_width() - 10, card.y + 12 + 22))
            y += 180
        # final
        card = pygame.Rect(b.x + 12, y, b.w - 24, 120)
        pygame.draw.rect(screen, (30, 14, 46), card, border_radius=12)
        pygame.draw.rect(screen, (170, 90, 255), card, 2, border_radius=12)
        screen.blit(text("FINAL · GROTTE AZURÉE", "black", 19, (230, 200, 255)), (card.x + 12, card.y + 8))
        for i, k in enumerate(("mew", "mewtwo")):
            x = card.x + 24 + i * 190
            got = p is not None and ((k == "mew" and p.mew_done) or (k == "mewtwo" and p.mewtwo_done))
            lit = p is not None and ((k == "mew" and p.mew_lit) or (k == "mewtwo" and p.mewtwo_lit))
            if got or lit:
                screen.blit(art.creature(k, 84), (x, card.y + 32))
            else:
                screen.blit(art.creature_silhouette(k, 84, (50, 36, 70)), (x, card.y + 32))
            screen.blit(text(k.upper(), "black", 16, (220, 200, 255)), (x + 88, card.y + 66))
        y += 132
        # statistiques
        box = pygame.Rect(b.x + 12, y, b.w - 24, b.bottom - y - 10)
        pygame.draw.rect(screen, (16, 18, 40), box, border_radius=12)
        pygame.draw.rect(screen, (70, 80, 130), box, 2, border_radius=12)
        if p is None:
            lines = [("APPUYEZ SUR ENTRÉE", (255, 230, 100)), ("pour commencer une partie", (200, 200, 230)),
                     ("Jusqu'à 4 joueurs : touche 1", (170, 175, 210))]
        else:
            lines = [(f"POKÉDEX : {len(p.pokedex)} capturés", (150, 255, 170)),
                     (f"SAFARI : {p.locks}/{p.locks_needed}  ·  BONUS x{p.bonus_x}", (200, 220, 255)),
                     (f"TEAM ROCKET vaincue : {p.rocket_defeats}", (255, 150, 150)),
                     (f"Temps de jeu : {int(game.game_time // 60)} min {int(game.game_time % 60):02d}", (180, 180, 210))]
            if p.pokedex:
                lines.append(("Derniers : " + ", ".join(p.pokedex[-3:]), (170, 175, 210)))
        for i, (ln, c) in enumerate(lines):
            screen.blit(text(ln, "semi", 18, c), (box.x + 14, box.y + 10 + i * 24))
