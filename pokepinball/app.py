"""Application : fenêtre, boucle principale, entrées horodatées, orchestration."""
import sys
import time

import pygame

from .config import SCREEN_W, SCREEN_H, FPS, PF_SCREEN_X, PF_SCREEN_Y, PF_PIX_W
from .data import LAMP


class FX:
    """Façade d'effets utilisée par les règles du jeu."""

    def __init__(self, app):
        self.app = app

    def sound(self, name, vol=1.0):
        self.app.audio.play(name, vol)

    def callout(self, key):
        self.app.audio.callout(key)

    def music(self, name):
        self.app.audio.music(name)

    def music_stinger(self, name):
        self.app.audio.stinger(name)

    def lcd(self, name, **kw):
        self.app.lcd.push(name, **kw)
        flash = {"jackpot": LAMP["gold"], "super_jackpot": LAMP["white"], "multiball": LAMP["green"],
                 "gotcha": LAMP["white"], "extra_ball": LAMP["orange"], "victory": LAMP["purple"],
                 "legendary_intro": None}.get(name, 0)
        if name == "legendary_intro":
            leg = kw.get("leg")
            flash = getattr(leg, "color", None)
        if flash:
            self.app.panels.flash(flash, 0.6)

    def flash(self, col, dur=0.3):
        self.app.renderer.flash(col, dur)
        self.app.panels.flash(col, dur)

    def shake(self, amt):
        self.app.renderer.shake(amt)

    def light_show(self, name, dur, color=(255, 255, 255)):
        self.app.renderer.light_show(name, dur, color)

    def particles(self, x, y, kind="spark", n=10):
        self.app.renderer.burst(x, y, kind, n)

    def popup(self, x, y, txt):
        self.app.renderer.popup(x, y, txt)

    def shot_flash(self, shot, col):
        self.app.renderer.shot_flash(shot, col)


KEYS_L = (pygame.K_LSHIFT, pygame.K_LEFT)
KEYS_R = (pygame.K_RSHIFT, pygame.K_RIGHT)
KEYS_PLUNGER = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_DOWN)
KEYS_START = (pygame.K_1, pygame.K_KP1, pygame.K_AMPERSAND, pygame.K_s)


class App:
    def __init__(self, fullscreen=False, sound=True, voice=True, debug=False):
        self.debug = debug
        if sound:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        if sound:
            try:
                pygame.mixer.init(44100, -16, 2, 512)
            except pygame.error:
                sound = False
        flags = pygame.SCALED
        if fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags, vsync=1)
        except pygame.error:
            self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        pygame.display.set_caption("POKÉMON PINBALL — Légendes")
        self._set_icon()
        self.clock = pygame.time.Clock()
        from .audio.audio import Audio
        self.audio = Audio(enabled=sound, voice=voice)
        self.audio.start_loading()
        self.loading_screen("Construction du plateau...", 0.05)
        from .table import Table
        from .game import Game
        from .render.playfield import PlayfieldRenderer
        from .render.lcd import LCD
        from .render.panels import Panels
        self.table = Table()
        self.fx = FX(self)
        self.game = Game(self.table, self.fx)
        self.loading_screen("Impression des plastiques...", 0.15)
        self.renderer = PlayfieldRenderer(self.table)
        self.loading_screen("Allumage de l'écran LCD...", 0.3)
        self.lcd = LCD()
        self.panels = Panels()
        self.background = self._build_background()
        self.input_q = []
        self.sim_time = time.perf_counter()
        self.paused = False
        self.running = True
        self.esc_t = 0.0
        self.fps_show = debug
        self.keys_down = set()
        self.wait_audio()
        self.audio.music("attract")

    # ------------------------------------------------------------------
    def _set_icon(self):
        try:
            from .render import art
            ic = pygame.Surface((64, 64), pygame.SRCALPHA)
            art.draw_pokeball(ic, 32, 32, 28)
            pygame.display.set_icon(ic)
        except Exception:
            pass

    def loading_screen(self, msg, frac):
        from .render.assets import text, blit_center
        s = self.screen
        s.fill((6, 6, 16))
        try:
            from .render import art
            lg = art.logo(700)
            s.blit(lg, (SCREEN_W / 2 - lg.get_width() / 2, 260))
            art.draw_pokeball(s, SCREEN_W / 2, 640, 50, angle=time.time() * 200 % 360)
        except Exception:
            pass
        r = pygame.Rect(SCREEN_W / 2 - 400, 740, 800, 22)
        pygame.draw.rect(s, (40, 44, 70), r, border_radius=11)
        pygame.draw.rect(s, (255, 210, 60), pygame.Rect(r.x, r.y, int(r.w * max(0.0, min(1.0, frac))), r.h),
                         border_radius=11)
        blit_center(s, text(msg, "semi", 26, (200, 205, 235)), SCREEN_W / 2, 800)
        pygame.display.flip()
        pygame.event.pump()

    def wait_audio(self):
        """Attend les bruitages (premier lancement : synthèse + voix ~20-60 s)."""
        if not self.audio.enabled:
            return
        from .audio.synth import SFX
        need = len(SFX) + 2
        t0 = time.time()
        while self.audio.done_count < need and time.time() - t0 < 90:
            self.audio.poll()
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    return
            frac = 0.3 + 0.7 * self.audio.done_count / max(1, self.audio.total)
            self.loading_screen("Synthèse des sons et de la musique (premier lancement)...", frac)
            time.sleep(0.03)

    def _build_background(self):
        from .render.assets import gradient_surface
        bg = gradient_surface(SCREEN_W, SCREEN_H, (16, 16, 26), (6, 6, 12)).convert()
        # rails latéraux chromés autour du plateau
        x0, x1 = PF_SCREEN_X - 8, PF_SCREEN_X + PF_PIX_W + 2
        for x in (x0, x1):
            pygame.draw.rect(bg, (70, 74, 92), pygame.Rect(x, 0, 6, SCREEN_H))
            pygame.draw.line(bg, (190, 195, 215), (x + 1, 0), (x + 1, SCREEN_H), 1)
        return bg

    # ------------------------------------------------------------------
    # Entrées horodatées (précision sub-image pour le timing des flippers)
    # ------------------------------------------------------------------
    def poll_input(self):
        now = time.perf_counter()
        for e in pygame.event.get():
            self.input_q.append((now, e))

    def apply_event(self, e):
        g = self.game
        if e.type == pygame.QUIT:
            self.running = False
            return
        if e.type not in (pygame.KEYDOWN, pygame.KEYUP):
            return
        down = e.type == pygame.KEYDOWN
        k = e.key
        if down:
            self.keys_down.add(k)
        else:
            self.keys_down.discard(k)
        if k in KEYS_L or k in KEYS_R:
            side = "L" if k in KEYS_L else "R"
            other = KEYS_L if side == "L" else KEYS_R
            pressed = any(kk in self.keys_down for kk in other)
            if g.hs_entry is not None and down:
                g.hs_input(side)
                return
            if g.state == "playing" and not self.paused:
                f = self.table.flippers[side]
                was = f.pressed
                g.flipper(side, pressed)
                if f.pressed != was:
                    pan = -0.5 if side == "L" else 0.5
                    self.audio.play("flipper_up" if f.pressed else "flipper_down", 1.0 if f.pressed else 0.6, pan,
                                    cooldown=0.0)
            return
        if not down:
            if k in KEYS_PLUNGER and g.state == "playing":
                self.table.plunger.set_pulling(False)
            return
        # touches pressées
        if k == pygame.K_ESCAPE:
            if g.state == "playing" and time.time() - self.esc_t > 2.0:
                self.esc_t = time.time()
                self.lcd.push("message", title="ÉCHAP", sub="Appuyez encore pour abandonner", color=(200, 60, 60))
                return
            if g.state == "playing":
                g.state = "attract"
                self.lcd.clear()
                for b in self.table.world.balls:
                    b.state = "gone"
                self.table.world.remove_gone()
                self.audio.music("attract")
                return
            self.running = False
        elif k == pygame.K_F11:
            pygame.display.toggle_fullscreen()
        elif k == pygame.K_p:
            self.paused = not self.paused
        elif k == pygame.K_m:
            self.audio.toggle_music()
        elif k == pygame.K_F3:
            self.fps_show = not self.fps_show
        elif g.hs_entry is not None:
            if k in KEYS_PLUNGER or k in KEYS_START:
                g.hs_input("ok")
        elif k in KEYS_START:
            g.start_button()
        elif k in KEYS_PLUNGER:
            if g.state in ("attract", "game_over"):
                g.start_button()
                self.lcd.clear()
            elif g.select is not None:
                g.launch_button()
            elif g.state == "playing":
                self.table.plunger.set_pulling(True)
        elif k == pygame.K_SPACE:
            g.nudge(0, -1)
        elif k == pygame.K_LCTRL:
            g.nudge(1, 0)
        elif k == pygame.K_RCTRL:
            g.nudge(-1, 0)
        elif self.debug:
            self.debug_key(k)

    def debug_key(self, k):
        g = self.game
        p = g.player
        if p is None:
            return
        if k == pygame.K_F5:
            g.add_balls(1)
        elif k == pygame.K_F6:
            p.mode_lit = True
        elif k == pygame.K_F7:
            lm = g.legendary_mode()
            if lm:
                lm.damage(30, "center")
        elif k == pygame.K_F8:
            for key in p.available_legendaries():
                p.captured.append(key)
            p.wizard_lit = True
        elif k == pygame.K_F9:
            p.chapter = 5
            p.mew_done = True
            p.mewtwo_lit = True

    # ------------------------------------------------------------------
    def step_sim(self, dt):
        g = self.game
        tb = self.table
        if g.state == "playing" and not self.paused:
            tb.step(dt)
        else:
            tb.update(dt)
        for ev, kw in tb.take_events():
            g.handle(ev, kw)
        w = tb.world
        if w.events:
            evs = w.events
            w.events = []
            for ev, ball in evs:
                g.handle(ev, {"ball": ball})
        if w.impact_events:
            imps = w.impact_events
            w.impact_events = []
            self.audio.impacts(imps)
            self.renderer.add_impacts(imps)

    def run(self):
        last = time.perf_counter()
        self.sim_time = last
        while self.running:
            self.poll_input()
            now = time.perf_counter()
            frame_dt = min(0.05, now - last)
            last = now
            # physique jusqu'à "maintenant", en appliquant chaque entrée à son instant
            start = now - frame_dt
            if self.sim_time < start:
                self.sim_time = start
            q = sorted(self.input_q, key=lambda it: it[0])
            self.input_q = []
            for t_e, e in q:
                t_e = max(self.sim_time, min(now, t_e))
                if t_e > self.sim_time:
                    self.step_sim(t_e - self.sim_time)
                    self.sim_time = t_e
                self.apply_event(e)
            if now > self.sim_time:
                self.step_sim(now - self.sim_time)
                self.sim_time = now
            if not self.paused:
                self.game.update(frame_dt)
            self.renderer.update(frame_dt)
            self.lcd.update(frame_dt, self.game)
            self.panels.update(frame_dt)
            self.audio.update(frame_dt, self.table.world)
            self.draw()
            self.poll_input()
            pygame.display.flip()
            self.clock.tick(FPS * 2)
        pygame.quit()

    def draw(self):
        s = self.screen
        g = self.game
        s.blit(self.background, (0, 0))
        attract = g.state in ("attract", "game_over")
        self.renderer.draw(s, (PF_SCREEN_X, PF_SCREEN_Y), g, attract=attract)
        self.poll_input()
        lcd_surf = self.lcd.draw(g)
        self.poll_input()
        self.panels.draw(s, g, lcd_surf)
        if self.paused:
            from .render.assets import text, blit_center
            ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 150))
            s.blit(ov, (0, 0))
            blit_center(s, text("PAUSE", "black", 120, (255, 255, 255), outline=(0, 0, 0), outline_w=6),
                        SCREEN_W / 2, SCREEN_H / 2)
        if self.fps_show:
            from .render.assets import text
            s.blit(text(f"{self.clock.get_fps():.0f} fps", "mono", 18, (0, 255, 0)), (8, SCREEN_H - 26))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    app = App(fullscreen="--fullscreen" in argv, sound="--nosound" not in argv, voice="--novoice" not in argv,
              debug="--debug" in argv)
    app.run()
