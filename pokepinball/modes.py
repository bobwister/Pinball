"""Modes de jeu : Super Modes légendaires, multiballs, hurry-ups, assistants finaux."""
import random

from .data import SHOTS, LAMP, CHAPTERS, MEW, MEWTWO

ALL = list(SHOTS)
RAMPS_ORBITS = ["orbit_l", "ramp_l", "ramp_r", "orbit_r"]
RAINBOW = ["red", "orange", "yellow", "green", "cyan", "blue", "purple"]


class Mode:
    name = "mode"
    priority = 10
    is_multiball = False
    blocks_scoop_modes = False

    def __init__(self, game):
        self.game = game
        self.fx = game.fx
        self.t = 0.0
        self.active = False

    # cycle de vie -------------------------------------------------------
    def start(self):
        self.active = True

    def stop(self):
        self.active = False

    def update(self, dt):
        self.t += dt

    # interactions -------------------------------------------------------
    def on_shot(self, shot, kw):
        return False

    def on_event(self, ev, kw):
        pass

    def on_drain_to_single(self):
        pass

    def lamps(self, L):
        pass

    def needs_pokeball(self):
        return False

    def hud(self):
        return None

    def gi(self):
        return None

    # utilitaires --------------------------------------------------------
    def score(self, pts, x=None, y=None):
        return self.game.add_score(pts, x, y)


# ==========================================================================
# Super Modes légendaires
# ==========================================================================
class LegendaryMode(Mode):
    name = "legendary"
    priority = 50
    BASE_TIME = 75.0
    CAPTURE_TIME = 30.0
    HIT_TIME_BONUS = 4.0

    def __init__(self, game, leg):
        super().__init__(game)
        self.leg = leg
        self.player = game.player
        self.hp = self.player.leg_hp.get(leg.key, float(leg.hp))
        self.timer = self.BASE_TIME
        self.phase = "intro"
        self.intro_t = 3.6
        self.shakes = 0
        self.need_shakes = 3
        self.capture_timer = 0.0
        self.lit = set()
        self.colors = {}
        self.extra = ""
        self.damage_dealt = 0
        self.mode_points = 0
        self.last_hit_t = -10.0
        self.hits = 0

    @property
    def lamp(self):
        return self.leg.lamp

    # ------------------------------------------------------------------
    def start(self):
        super().start()
        g = self.game
        self.need_shakes = 2 if self.player.super_ball else 3
        g.fx.music("battle_" + str(self.leg.chapter) if self.leg.chapter <= 4 else "battle_1")
        g.fx.lcd("legendary_intro", leg=self.leg)
        g.fx.callout("leg_" + self.leg.key)
        g.fx.sound("roar_" + self.leg.key)
        g.fx.light_show("mode_start", 2.5, color=LAMP[self.lamp])
        g.table.grass.reset()
        self.setup()

    def begin_battle(self):
        self.phase = "battle"
        self.game.ball_save(8.0)

    def setup(self):
        self.lit = set(ALL)

    def stop(self):
        super().stop()
        if self.leg.key not in self.player.captured:
            self.player.leg_hp[self.leg.key] = max(1.0, self.hp)
        tb = self.game.table
        tb.pokeball.open_target = 0.0

    # ------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        g = self.game
        if self.phase == "intro":
            self.intro_t -= dt
            if self.intro_t <= 0:
                self.begin_battle()
            return
        if g.scoop_busy() or g.paused_timers():
            return
        if self.phase == "battle":
            self.timer -= dt
            self.battle_update(dt)
            if self.timer <= 0:
                self.fail()
        elif self.phase == "capture":
            self.capture_timer -= dt
            g.table.grass.drop_all()
            g.table.pokeball.open_target = 1.0
            if self.capture_timer <= 0:
                self.broke_free()

    def battle_update(self, dt):
        pass

    # ------------------------------------------------------------------
    def damage(self, amount, shot=None, kind="hit"):
        if self.phase != "battle":
            return
        amount = max(1.0, amount) * self.player.damage_mult()
        self.hp -= amount
        self.hits += 1
        self.damage_dealt += amount
        pts = int(amount * 30_000) // 10 * 10
        self.mode_points += pts
        x, y = self.game.shot_pos(shot)
        self.score(pts, x, y)
        self.timer = min(99.0, self.timer + self.HIT_TIME_BONUS)
        self.last_hit_t = self.t
        self.fx.sound("hit_" + self.leg.type)
        self.fx.lcd("leg_hit", leg=self.leg, dmg=int(round(amount)), hp=max(0.0, self.hp) / self.leg.hp,
                    attack=self.leg.attack, kind=kind)
        self.fx.flash(LAMP[self.lamp], 0.25)
        if shot:
            self.fx.shot_flash(shot, LAMP[self.lamp])
        if self.hp <= 0:
            self.hp = 0
            self.start_capture()

    def start_capture(self):
        self.phase = "capture"
        self.shakes = 0
        self.capture_timer = self.CAPTURE_TIME
        g = self.game
        g.table.grass.drop_all()
        g.table.pokeball.open_target = 1.0
        self.fx.lcd("capture_phase", leg=self.leg)
        self.fx.callout("throw_ball")
        self.fx.sound("weakened")
        self.fx.music("capture")
        self.fx.light_show("capture", 2.0, color=LAMP["red"])
        g.ball_save(6.0)

    def capture_hit(self):
        self.shakes += 1
        self.capture_timer = max(self.capture_timer, 12.0)
        self.fx.sound("shake")
        self.score(500_000)
        if self.shakes >= self.need_shakes:
            self.success()
        else:
            self.fx.lcd("shake", leg=self.leg, n=self.shakes, need=self.need_shakes)
            self.fx.callout("shake_" + str(self.shakes))

    def success(self):
        g = self.game
        self.phase = "done"
        value = self.leg.capture_value + int(self.timer * 50_000)
        self.score(value)
        p = self.player
        p.captured.append(self.leg.key)
        p.leg_hp.pop(self.leg.key, None)
        p.super_ball = False
        p.stats["legendaries"] += 1
        self.hp = 0
        self.fx.lcd("gotcha", leg=self.leg, value=value + self.mode_points)
        self.fx.sound("gotcha")
        self.fx.callout("gotcha")
        self.fx.light_show("victory", 3.0, color=LAMP[self.lamp])
        self.fx.music_stinger("capture_jingle")
        g.table.pokeball.open_target = 0.0
        g.end_legendary(self, success=True)

    def broke_free(self):
        self.phase = "battle"
        self.hp = self.leg.hp * 0.3
        self.timer = max(self.timer, 20.0) + 15.0
        self.shakes = 0
        self.game.table.pokeball.open_target = 0.0
        self.game.table.grass.reset()
        self.fx.lcd("broke_free", leg=self.leg)
        self.fx.sound("break_free")
        self.fx.callout("broke_free")
        self.fx.music("battle_" + str(min(4, self.leg.chapter)))
        self.setup()

    def fail(self):
        self.phase = "done"
        self.fx.lcd("escaped", leg=self.leg)
        self.fx.sound("escaped")
        self.fx.callout("escaped")
        self.game.end_legendary(self, success=False)

    def end_by_drain(self):
        self.phase = "done"

    # ------------------------------------------------------------------
    def on_shot(self, shot, kw):
        if self.phase == "capture":
            if shot == "center" and kw.get("via") == "pokeball":
                self.capture_hit()
                return True
            return False
        if self.phase != "battle":
            return False
        return self.battle_shot(shot, kw)

    def battle_shot(self, shot, kw):
        if shot in self.lit:
            self.damage(8, shot)
            return True
        return False

    def needs_pokeball(self):
        return self.phase == "capture"

    # ------------------------------------------------------------------
    def lamps(self, L):
        col = LAMP[self.lamp]
        if self.phase == "capture":
            L.arrow("center", [LAMP["red"], LAMP["white"]], "fast")
            L.set("center_capture", LAMP["white"], "fast")
            for s in ALL:
                if s != "center":
                    L.arrow(s, None)
            return
        if self.phase != "battle":
            return
        for s in ALL:
            if s in self.lit:
                L.arrow(s, self.colors.get(s, col), "blink")

    def gi(self):
        return LAMP[self.lamp]

    def hud(self):
        lines = list(self.leg.rules_text)
        if self.phase == "capture":
            lines = ["LANCEZ LA POKÉBALL !", f"Secousses {self.shakes}/{self.need_shakes}",
                     "Frappez la Pokéball centrale"]
        return {
            "kind": "legendary", "leg": self.leg, "phase": self.phase,
            "hp": max(0.0, self.hp) / self.leg.hp, "timer": self.capture_timer if self.phase == "capture" else self.timer,
            "lines": lines, "extra": self.extra, "shakes": self.shakes, "need": self.need_shakes,
            "points": self.mode_points,
        }


# ---------------------------------------------------------------- Kanto
class ArticunoMode(LegendaryMode):
    def setup(self):
        self.lit = set(ALL)

    def battle_shot(self, shot, kw):
        if shot not in self.lit:
            return False
        combo = self.t - self.last_hit_t < 4.0
        self.lit.discard(shot)
        self.damage(16 if combo else 8, shot, "combo" if combo else "hit")
        if not self.lit and self.phase == "battle":
            self.lit = set(ALL)
            self.fx.lcd("message", title="BLIZZARD !", sub="Toutes les cibles se rallument", color=LAMP["ice"])
        self.extra = "COMBO = DÉGÂTS x2"
        return True


class ZapdosMode(LegendaryMode):
    def setup(self):
        self.lit = set(RAMPS_ORBITS)
        self.charge = 0.0

    def charge_up(self, v):
        if self.phase != "battle":
            return
        before = self.charge
        self.charge = min(100.0, self.charge + v)
        if before < 100 <= self.charge:
            self.fx.sound("charge_full")
            self.fx.lcd("message", title="CHARGE MAX !", sub="Déchargez sur une flèche jaune", color=LAMP["yellow"])

    def on_event(self, ev, kw):
        if ev == "bumper":
            self.charge_up(3.0)
        elif ev == "spinner":
            self.charge_up(1.5)
        elif ev == "rollover" and kw.get("group") == "top":
            self.charge_up(6.0)

    def battle_shot(self, shot, kw):
        if shot in self.lit:
            dmg = 6 + self.charge * 0.16
            self.charge = 0.0
            self.fx.sound("thunder")
            self.fx.shake(0.4)
            self.damage(dmg, shot, "thunder")
            return True
        return False

    def battle_update(self, dt):
        self.extra = f"CHARGE {int(self.charge)}%"

    def lamps(self, L):
        super().lamps(L)
        if self.phase == "battle":
            L.set("spinner", LAMP["yellow"], "fast")
            for b in range(3):
                L.set(f"bumper_{b}", LAMP["yellow"], "blink")


class MoltresMode(LegendaryMode):
    FLAME_TIME = 13.0

    def setup(self):
        self.current = None
        self.next_flame()

    def next_flame(self):
        choices = [s for s in ALL if s != self.current]
        self.current = random.choice(choices)
        self.flame_t = self.FLAME_TIME
        self.lit = {self.current}

    def battle_update(self, dt):
        self.flame_t -= dt
        if self.flame_t <= 0:
            self.fx.sound("fizzle")
            self.next_flame()
        self.extra = f"FLAMME {max(0, self.flame_t):.0f}s"

    def battle_shot(self, shot, kw):
        if shot == self.current:
            dmg = 9 + 7 * max(0.0, self.flame_t) / self.FLAME_TIME
            self.fx.sound("fireball")
            self.damage(dmg, shot, "fire")
            self.next_flame()
            return True
        return False

    def lamps(self, L):
        if self.phase == "battle" and self.current:
            speed = "fast" if self.flame_t < 4 else "blink"
            L.arrow(self.current, [LAMP["orange"], LAMP["red"], LAMP["yellow"]], speed)
        else:
            super().lamps(L)


# ---------------------------------------------------------------- Johto
class RaikouMode(LegendaryMode):
    def setup(self):
        self.lit = set(RAMPS_ORBITS + ["bumper"])
        self.chain = 0
        self.chain_t = 0.0

    def battle_update(self, dt):
        if self.chain_t > 0:
            self.chain_t -= dt
            if self.chain_t <= 0:
                self.chain = 0
        self.extra = f"CHAÎNE x{self.chain}" if self.chain else "ENCHAÎNEZ !"

    def battle_shot(self, shot, kw):
        if shot in self.lit:
            self.chain = min(5, self.chain + 1)
            self.chain_t = 5.0
            self.fx.sound("zap")
            self.damage(4.5 * self.chain, shot, "combo" if self.chain > 1 else "hit")
            return True
        return False


class EnteiMode(LegendaryMode):
    def setup(self):
        self.stage = "grass"
        self.lit = {"ramp_l", "ramp_r", "center"}
        self.game.table.grass.reset()

    def battle_shot(self, shot, kw):
        if shot == "center":
            if kw.get("via") == "drop" and self.stage == "grass":
                self.damage(4, shot)
                if self.game.table.grass.all_down():
                    self.stage = "pokeball"
                    self.fx.lcd("message", title="ARÈNE DÉGAGÉE !", sub="Frappez la Pokéball", color=LAMP["red"])
                return True
            if kw.get("via") == "pokeball" and self.stage == "pokeball":
                self.fx.sound("eruption")
                self.fx.shake(0.6)
                self.damage(18, shot, "fire")
                self.stage = "grass"
                self.game.table.grass.reset()
                return True
            return False
        if shot in ("ramp_l", "ramp_r"):
            self.damage(5, shot)
            return True
        return False

    def needs_pokeball(self):
        return super().needs_pokeball() or (self.phase == "battle" and self.stage == "pokeball")

    def battle_update(self, dt):
        self.extra = "HERBES" if self.stage == "grass" else "POKÉBALL !"

    def lamps(self, L):
        super().lamps(L)
        if self.phase == "battle":
            if self.stage == "pokeball":
                L.arrow("center", [LAMP["red"], LAMP["orange"]], "fast")
            for i in range(3):
                L.set(f"grass_{i}", LAMP["red"], "blink")


class SuicuneMode(LegendaryMode):
    def setup(self):
        self.idx = 0
        self.dir = 1
        self.interval = 2.4
        self.move_t = self.interval
        self.lit = {ALL[self.idx]}

    def battle_update(self, dt):
        self.move_t -= dt
        if self.move_t <= 0:
            self.move_t = self.interval
            self.idx += self.dir
            if self.idx >= len(ALL) - 1 or self.idx <= 0:
                self.dir = -self.dir
                self.idx = max(0, min(len(ALL) - 1, self.idx))
            self.lit = {ALL[self.idx]}
        self.extra = f"VITESSE {self.interval:.1f}s"

    def battle_shot(self, shot, kw):
        if shot in self.lit:
            self.fx.sound("splash")
            self.damage(12, shot, "water")
            self.interval = min(4.5, self.interval + 0.3)
            return True
        self.damage(2, shot, "splash")
        return True


# ---------------------------------------------------------------- Gardiens
class LugiaMode(LegendaryMode):
    def setup(self):
        self.next = "ramp_l"
        self.lit = {self.next}
        self.last_ramp_t = -10

    def battle_shot(self, shot, kw):
        if shot == self.next:
            combo = self.t - self.last_ramp_t < 6.0
            self.last_ramp_t = self.t
            self.fx.sound("aeroblast")
            self.damage(15 if combo else 10, shot, "combo" if combo else "hit")
            self.next = "ramp_r" if shot == "ramp_l" else "ramp_l"
            self.lit = {self.next}
            return True
        return False


class HoohMode(LegendaryMode):
    def setup(self):
        self.reset_rainbow()

    def reset_rainbow(self):
        self.lit = set(ALL)
        self.colors = {s: LAMP[c] for s, c in zip(ALL, RAINBOW)}
        self.sacred = False

    def begin_battle(self):
        super().begin_battle()
        self.game.add_balls(1, save=15.0)
        self.fx.lcd("multiball", title="FEU SACRÉ", balls=2)

    def battle_shot(self, shot, kw):
        if self.sacred:
            if shot == "center" and kw.get("via") == "pokeball":
                self.fx.sound("sacred_fire")
                self.damage(20, shot, "fire")
                self.reset_rainbow()
                return True
            return False
        if shot in self.lit:
            self.lit.discard(shot)
            self.damage(7, shot)
            if not self.lit:
                self.sacred = True
                self.lit = {"center"}
                self.colors = {"center": LAMP["gold"]}
                self.fx.lcd("message", title="FEU SACRÉ PRÊT !", sub="Frappez la Pokéball", color=LAMP["gold"])
            return True
        return False

    def needs_pokeball(self):
        return super().needs_pokeball() or (self.phase == "battle" and self.sacred)


# ---------------------------------------------------------------- Hoenn
class GroudonMode(LegendaryMode):
    QUAKE_EVERY = 18.0

    def setup(self):
        self.lit = {"center", "scoop"}
        self.quake_t = self.QUAKE_EVERY
        self.grass_down_t = 0.0

    def battle_update(self, dt):
        self.quake_t -= dt
        if self.quake_t <= 0:
            self.quake_t = self.QUAKE_EVERY
            self.fx.sound("earthquake")
            self.fx.shake(1.2)
            self.fx.lcd("message", title="SÉISME !", sub="Le plateau tremble", color=LAMP["brown"])
            self.game.quake()
        tb = self.game.table
        if tb.grass.all_down():
            self.grass_down_t += dt
            if self.grass_down_t > 4.0:
                tb.grass.reset()
                self.grass_down_t = 0.0
        self.extra = f"SÉISME DANS {max(0, self.quake_t):.0f}s"

    def battle_shot(self, shot, kw):
        if shot == "center":
            if kw.get("via") == "drop":
                self.damage(6, shot)
            else:
                self.fx.sound("rock_smash")
                self.damage(14, shot, "rock")
            return True
        if shot == "scoop":
            self.damage(8, shot)
            return True
        return False


class KyogreMode(LegendaryMode):
    def setup(self):
        self.lit = {"orbit_l", "orbit_r", "bumper"}
        self.tide = 0.0

    def on_event(self, ev, kw):
        if ev == "spinner" and self.phase == "battle":
            self.hp -= 0.6
            self.tide = min(100, self.tide + 1)
            if self.hp <= 0:
                self.hp = 0.1

    def battle_shot(self, shot, kw):
        if shot in ("orbit_l", "orbit_r"):
            self.fx.sound("wave")
            self.damage(12, shot, "water")
            return True
        if shot == "bumper":
            self.damage(6, shot)
            return True
        return False

    def battle_update(self, dt):
        self.extra = f"MARÉE {int(self.tide)}%"

    def lamps(self, L):
        super().lamps(L)
        if self.phase == "battle":
            L.set("spinner", LAMP["blue"], "fast")


class RayquazaMode(LegendaryMode):
    def setup(self):
        self.seq = 0
        self.lit = {ALL[self.seq]}

    def begin_battle(self):
        super().begin_battle()
        self.game.add_balls(1, save=15.0)
        self.fx.lcd("multiball", title="DRACO-ASCENSION", balls=2)

    def battle_shot(self, shot, kw):
        if shot == ALL[self.seq]:
            self.fx.sound("dragon")
            self.damage(13, shot, "dragon")
            self.seq = (self.seq + 1) % len(ALL)
            self.lit = {ALL[self.seq]}
            return True
        self.damage(2, shot)
        return True

    def lamps(self, L):
        super().lamps(L)
        if self.phase == "battle":
            for i, s in enumerate(ALL):
                if i > self.seq:
                    L.arrow(s, (20, 90, 40), "on")


LEG_MODES = {
    "articuno": ArticunoMode, "zapdos": ZapdosMode, "moltres": MoltresMode,
    "raikou": RaikouMode, "entei": EnteiMode, "suicune": SuicuneMode,
    "lugia": LugiaMode, "hooh": HoohMode,
    "groudon": GroudonMode, "kyogre": KyogreMode, "rayquaza": RayquazaMode,
}


# ==========================================================================
# Mew (mode caché)
# ==========================================================================
class MewMode(LegendaryMode):
    BASE_TIME = 90.0
    HIT_TIME_BONUS = 5.0

    def __init__(self, game):
        super().__init__(game, MEW)
        self.catches = 0
        self.need = 6

    def setup(self):
        self.current = random.choice(ALL)
        self.lit = {self.current}
        self.tp = 3.0

    def battle_update(self, dt):
        self.tp -= dt
        if self.tp <= 0:
            self.tp = 3.0
            self.current = random.choice([s for s in ALL if s != self.current])
            self.lit = {self.current}
            self.fx.sound("teleport")
        self.extra = f"MEW {self.catches}/{self.need}"

    def battle_shot(self, shot, kw):
        if shot == self.current:
            self.catches += 1
            self.fx.sound("mew_giggle")
            self.damage(self.leg.hp / self.need + 0.01, shot, "psychic")
            self.current = random.choice([s for s in ALL if s != self.current])
            self.lit = {self.current}
            self.tp = 3.0
            return True
        return False

    def lamps(self, L):
        if self.phase == "battle":
            L.arrow(self.current, [LAMP["pink"], LAMP["white"]], "fast")
        else:
            super().lamps(L)


# ==========================================================================
# Multiballs
# ==========================================================================
class MultiballMode(Mode):
    priority = 40
    is_multiball = True
    blocks_scoop_modes = True
    title = "MULTIBALL"
    balls = 3
    jackpot_base = 1_000_000
    super_base = 5_000_000
    shots = RAMPS_ORBITS
    color_names = ["green"]
    music = "multiball"

    def __init__(self, game):
        super().__init__(game)
        self.jackpots = 0
        self.level = 1
        self.lit = set()
        self.super_lit = False
        self.total = 0

    def start(self):
        super().start()
        self.lit = set(self.shots)
        self.fx.lcd("multiball", title=self.title, balls=self.balls)
        self.fx.callout("multiball")
        self.fx.sound("multiball_start")
        self.fx.music(self.music)
        self.fx.light_show("multiball", 3.0, color=LAMP[self.color_names[0]])
        self.game.add_balls(self.balls - self.game.balls_in_play(), save=20.0)

    def jackpot_value(self):
        return self.jackpot_base * self.level + 250_000 * self.jackpots

    def on_shot(self, shot, kw):
        if self.super_lit and shot == "center" and kw.get("via") == "pokeball":
            v = self.super_base * self.level
            self.total += self.score(v)
            self.fx.lcd("super_jackpot", value=v)
            self.fx.callout("super_jackpot")
            self.fx.sound("super_jackpot")
            self.fx.light_show("jackpot", 2.5, color=LAMP["gold"])
            self.fx.shake(0.6)
            self.super_lit = False
            self.level += 1
            self.lit = set(self.shots)
            self.game.table.grass.reset()
            return True
        if shot in self.lit:
            v = self.jackpot_value()
            self.jackpots += 1
            self.lit.discard(shot)
            x, y = self.game.shot_pos(shot)
            self.total += self.score(v, x, y)
            self.fx.lcd("jackpot", value=v, title="JACKPOT" if self.level == 1 else f"JACKPOT x{self.level}")
            self.fx.callout("jackpot")
            self.fx.sound("jackpot")
            self.fx.shot_flash(shot, LAMP["gold"])
            self.fx.light_show("jackpot", 1.2, color=LAMP[self.color_names[0]])
            if not self.lit:
                self.super_lit = True
                self.fx.lcd("message", title="SUPER JACKPOT ALLUMÉ", sub="Frappez la Pokéball !", color=LAMP["gold"])
                self.fx.callout("super_jackpot_lit")
            return True
        return False

    def needs_pokeball(self):
        return self.super_lit

    def on_drain_to_single(self):
        self.fx.lcd("message", title=f"{self.title}", sub=f"TOTAL {self.total:,}".replace(",", " "),
                    color=LAMP["gold"])
        self.game.end_multiball(self)

    def lamps(self, L):
        cols = [LAMP[c] for c in self.color_names]
        for i, s in enumerate(self.shots):
            if s in self.lit:
                L.arrow(s, cols[i % len(cols)] if len(cols) > 1 else cols, "blink")
        if self.super_lit:
            L.arrow("center", [LAMP["gold"], LAMP["white"]], "fast")
            L.set("center_super", LAMP["gold"], "fast")

    def gi(self):
        return LAMP[self.color_names[0]]

    def hud(self):
        return {"kind": "multiball", "title": self.title, "jackpots": self.jackpots,
                "value": self.jackpot_value(), "super": self.super_lit, "total": self.total,
                "lines": ["JACKPOTS : flèches clignotantes",
                          "SUPER JACKPOT : Pokéball" if self.super_lit else f"{len(self.lit)} jackpots restants"]}


class SafariMultiball(MultiballMode):
    title = "MULTIBALL SAFARI"
    balls = 3
    color_names = ["green"]
    music = "multiball"


class ChapterWizard(MultiballMode):
    priority = 45

    def __init__(self, game, chapter):
        super().__init__(game)
        ch = CHAPTERS[chapter]
        self.chapter = chapter
        self.title = ch["wizard"]
        self.balls = ch["balls"]
        self.color_names = ch["colors"]
        self.jackpot_base = 2_000_000 * chapter
        self.super_base = 10_000_000 * chapter
        self.shots = list(ALL if chapter >= 3 else RAMPS_ORBITS + ["bumper", "scoop"])
        self.shots = [s for s in self.shots if s != "center"]
        self.music = "wizard"

    def start(self):
        super().start()
        self.fx.lcd("chapter_wizard", chapter=self.chapter)

    def on_drain_to_single(self):
        super().on_drain_to_single()
        self.game.chapter_wizard_done(self.chapter)


# ==========================================================================
# Hurry-up Team Rocket
# ==========================================================================
class TeamRocketMode(Mode):
    name = "rocket"
    priority = 60
    DURATION = 25.0

    def start(self):
        super().start()
        self.shot = random.choice(["ramp_l", "ramp_r", "orbit_l", "orbit_r", "scoop"])
        self.time = self.DURATION
        self.value = 3_000_000
        self.fx.lcd("team_rocket", shot=self.shot)
        self.fx.callout("team_rocket")
        self.fx.sound("rocket_alarm")

    def update(self, dt):
        super().update(dt)
        if self.game.scoop_busy():
            return
        self.time -= dt
        self.value = max(500_000, int(3_000_000 - (self.DURATION - self.time) * 100_000) // 1000 * 1000)
        if self.time <= 0:
            self.fx.lcd("message", title="LA TEAM ROCKET S'ENFUIT", sub="Trop tard...", color=LAMP["red"])
            self.game.stop_mode(self)

    def on_shot(self, shot, kw):
        if shot == self.shot:
            v = self.value
            x, y = self.game.shot_pos(shot)
            self.score(v, x, y)
            p = self.game.player
            p.rocket_defeats += 1
            self.fx.lcd("rocket_defeated", value=v)
            self.fx.callout("rocket_blast")
            self.fx.sound("rocket_blast")
            self.fx.light_show("jackpot", 1.5, color=LAMP["red"])
            if p.rocket_defeats in (2, 6):
                self.game.light_extra_ball()
            self.game.stop_mode(self)
            return False   # le tir compte aussi pour les autres modes
        return False

    def lamps(self, L):
        L.arrow(self.shot, [LAMP["red"], LAMP["white"]], "fast")
        for i in range(3):
            L.set(f"rocket_{i}", LAMP["red"], "fast")

    def hud(self):
        return None     # affiché en bandeau par le LCD


# ==========================================================================
# Combat final : MEWTWO
# ==========================================================================
class MewtwoMode(Mode):
    name = "mewtwo"
    priority = 80
    MAX_HP = 260.0
    is_multiball = False
    blocks_scoop_modes = True

    def __init__(self, game):
        super().__init__(game)
        self.leg = MEWTWO
        self.phase = "intro"
        self.intro_t = 5.0
        p = game.player
        saved = p.mewtwo_progress
        self.stage = saved.get("stage", 1)
        self.shields = dict(saved.get("shields", {s: 2 for s in ALL}))
        self.hp = saved.get("hp", self.MAX_HP)
        self.jackpots = 0
        self.super_lit = False
        self.shakes = 0
        self.total = 0
        self.lit = set(ALL) - {"center"}
        self.guard = None

    @property
    def lamp(self):
        return "purple"

    def start(self):
        super().start()
        self.fx.lcd("mewtwo_intro")
        self.fx.callout("mewtwo")
        self.fx.music("mewtwo")
        self.fx.sound("roar_mewtwo")
        self.fx.light_show("mewtwo", 4.0, color=LAMP["purple"])
        self.game.table.grass.reset()

    def update(self, dt):
        super().update(dt)
        if self.phase == "intro":
            self.intro_t -= dt
            if self.intro_t <= 0:
                self.phase = "fight"
                self.enter_stage(self.stage, announce=True)
            return
        if self.stage == 3:
            self.game.table.grass.drop_all()
            self.game.table.pokeball.open_target = 1.0

    def enter_stage(self, stage, announce=True):
        self.stage = stage
        g = self.game
        if stage == 1:
            g.ball_save(20.0)
            if announce:
                self.fx.lcd("mewtwo_phase", n=1, title="BARRIÈRE PSY", sub="Brisez les 7 boucliers")
        elif stage == 2:
            self.fx.lcd("mewtwo_phase", n=2, title="MULTIBALL PSYKO", sub="Jackpots = dégâts")
            self.fx.callout("multiball")
            g.add_balls(4 - g.balls_in_play(), save=25.0)
            self.lit = set(ALL) - {"center"}
        elif stage == 3:
            self.fx.lcd("mewtwo_phase", n=3, title="MASTER BALL", sub="Brisez sa garde, puis frappez la Pokéball !")
            self.fx.callout("master_ball")
            self.shakes = 0
            self.new_guard()
            g.table.grass.drop_all()
            g.table.pokeball.open_target = 1.0
            g.ball_save(10.0)
        self.save()

    def new_guard(self):
        """Mewtwo dévie la Master Ball : il faut d'abord briser sa garde psychique."""
        self.guard = random.choice([x for x in ALL if x != "center"])

    def save(self):
        self.game.player.mewtwo_progress = {"stage": self.stage, "shields": dict(self.shields), "hp": self.hp}

    def on_shot(self, shot, kw):
        if self.phase != "fight":
            return False
        x, y = self.game.shot_pos(shot)
        if self.stage == 1:
            if shot in self.shields:
                self.shields[shot] -= 1
                self.total += self.score(2_000_000, x, y)
                self.fx.shot_flash(shot, LAMP["purple"])
                if self.shields[shot] <= 0:
                    del self.shields[shot]
                    self.fx.sound("shield_break")
                    self.fx.lcd("shield_break", left=len(self.shields))
                else:
                    self.fx.sound("hit_Psy")
                    self.fx.lcd("message", title="BOUCLIER FISSURÉ", sub="Encore un tir !", color=LAMP["purple"])
                if not self.shields:
                    self.enter_stage(2)
                self.save()
                return True
            return False
        if self.stage == 2:
            if self.super_lit and shot == "center" and kw.get("via") == "pokeball":
                self.super_lit = False
                self.hp -= 22
                self.total += self.score(15_000_000)
                self.fx.lcd("super_jackpot", value=15_000_000)
                self.fx.callout("super_jackpot")
                self.fx.sound("super_jackpot")
                self.fx.shake(0.8)
                self.lit = set(ALL) - {"center"}
                self.game.table.grass.reset()
                self.check_hp()
                return True
            if shot in self.lit:
                self.lit.discard(shot)
                self.jackpots += 1
                self.hp -= 9
                v = 3_000_000 + 500_000 * self.jackpots
                self.total += self.score(v, x, y)
                self.fx.lcd("jackpot", value=v, title="JACKPOT PSY")
                self.fx.callout("jackpot")
                self.fx.sound("jackpot")
                self.fx.shot_flash(shot, LAMP["purple"])
                if self.jackpots % 4 == 0:
                    self.super_lit = True
                    self.fx.lcd("message", title="SUPER JACKPOT ALLUMÉ", sub="Pokéball !", color=LAMP["gold"])
                if not self.lit:
                    self.lit = set(ALL) - {"center"}
                self.check_hp()
                return True
            return False
        if self.stage == 3:
            if self.guard and shot == self.guard:
                self.guard = None
                self.total += self.score(4_000_000, x, y)
                self.fx.sound("shield_break")
                self.fx.lcd("message", title="GARDE BRISÉE !", sub="Vite : la Pokéball !", color=LAMP["purple"])
                return True
            if shot == "center" and kw.get("via") == "pokeball" and not self.guard:
                self.shakes += 1
                self.new_guard()
                self.fx.sound("shake")
                self.score(5_000_000)
                if self.shakes >= 3:
                    self.victory()
                else:
                    self.fx.lcd("shake", leg=self.leg, n=self.shakes, need=3)
                    self.fx.callout("shake_" + str(self.shakes))
                return True
        return False

    def check_hp(self):
        self.save()
        if self.hp <= 0:
            self.hp = 0
            self.enter_stage(3)

    def victory(self):
        self.phase = "won"
        v = MEWTWO.capture_value
        self.score(v)
        self.fx.lcd("victory", value=v + self.total)
        self.fx.callout("victory")
        self.fx.sound("gotcha")
        self.fx.music_stinger("victory")
        self.fx.light_show("victory", 8.0, color=LAMP["purple"])
        self.game.table.pokeball.open_target = 0.0
        self.game.mewtwo_won(self)

    def needs_pokeball(self):
        return self.phase == "fight" and (self.stage == 3 or (self.stage == 2 and self.super_lit))

    def lamps(self, L):
        if self.phase != "fight":
            return
        P = LAMP["purple"]
        if self.stage == 1:
            for s, hp in self.shields.items():
                L.arrow(s, [P, LAMP["pink"]] if hp > 1 else [LAMP["white"], P], "blink" if hp > 1 else "fast")
        elif self.stage == 2:
            for s in self.lit:
                L.arrow(s, P, "fast")
            if self.super_lit:
                L.arrow("center", [LAMP["gold"], LAMP["white"]], "fast")
        elif self.stage == 3:
            if self.guard:
                L.arrow(self.guard, [P, LAMP["white"]], "fast")
            else:
                L.arrow("center", [P, LAMP["white"], LAMP["gold"]], "fast")
                L.set("center_capture", LAMP["white"], "fast")

    def gi(self):
        return LAMP["purple"]

    def on_drain_to_single(self):
        pass

    def hud(self):
        lines = {1: ["BARRIÈRE PSY", f"{len(self.shields)} boucliers restants", "Tirez les flèches violettes"],
                 2: ["MULTIBALL PSYKO", "Jackpots = dégâts", "Super Jackpot : Pokéball"],
                 3: ["MASTER BALL !", f"Secousses {self.shakes}/3",
                     "Brisez la garde (flèche)" if self.guard else "Frappez la Pokéball !"]}.get(self.stage, [])
        return {"kind": "mewtwo", "leg": MEWTWO, "stage": self.stage, "hp": max(0, self.hp) / self.MAX_HP,
                "lines": lines, "phase": self.phase, "shields": len(self.shields), "total": self.total,
                "timer": None, "shakes": self.shakes, "need": 3}
