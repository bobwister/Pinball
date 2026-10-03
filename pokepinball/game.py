"""Moteur de règles façon Stern : joueurs, billes, scoring, fonctionnalités, modes."""
import json
import random

from .config import SAVE_FILE
from .data import SHOTS, LAMP, LEGENDARIES, LEG_BY_KEY, CHAPTERS, WILD, MYSTERY_AWARDS
from . import modes as M

BALLS_PER_GAME = 3
BALL_SAVE_TIME = 12.0
COMBO_WINDOW = 4.0
# Pokémon sauvages requis pour débloquer le multiball de fin de chapitre
POKEDEX_GATE = {1: 2, 2: 5, 3: 8, 4: 12}
SKILL_WINDOW = 7.0

SHOT_POS = {
    "orbit_l": (22, 470), "scoop": (84, 450), "ramp_l": (148, 450), "center": (241, 400),
    "ramp_r": (328, 450), "bumper": (402, 450), "orbit_r": (460, 470),
}


def fmt(n):
    return f"{int(n):,}".replace(",", " ")


class Lamps:
    """États des lampes calculés à chaque image : nom → (couleurs, mode)."""

    def __init__(self):
        self.states = {}

    def set(self, name, color, mode="on"):
        if color is None:
            self.states.pop(name, None)
            return
        if isinstance(color, tuple):
            color = [color]
        self.states[name] = (color, mode)

    def arrow(self, shot, color, mode="on"):
        self.set("arrow_" + shot, color, mode)

    def get(self, name):
        return self.states.get(name)


class NullFX:
    def __getattr__(self, name):
        return lambda *a, **k: None


class Player:
    def __init__(self, idx):
        self.idx = idx
        self.score = 0
        self.ball = 1
        self.extra_balls = 0
        self.bonus_x = 1
        self.captured = []
        self.leg_hp = {}
        self.chapter = 1
        self.wizard_lit = False
        self.chapter_clear = False
        self.wizards_done = set()
        self.mew_lit = False
        self.mew_done = False
        self.mewtwo_lit = False
        self.mewtwo_done = 0
        self.mewtwo_progress = {}
        self.radar = [0, 0, 0]
        self.radar_need = 1
        self.mode_lit = True
        self.modes_played = 0
        self.rocket = [False, False, False]
        self.rocket_defeats = 0
        self.top_lanes = [False, False, False]
        self.lanes = [False, False, False, False]
        self.kickback = True
        self.mystery_lit = False
        self.eb_lit = False
        self.pokedex = []
        self.locks = 0
        self.locks_needed = 3
        self.capture_lit = False
        self.wild_current = None
        self.bumper_hits = 0
        self.bumper_level = 1
        self.super_ball = False
        self.multi_exp_t = 0.0
        self.loops = 0
        self.stats = {k: 0 for k in ("ramps", "orbits", "combos", "bumpers", "spins", "jackpots",
                                      "legendaries", "drops", "standups", "captures")}

    def damage_mult(self):
        return 1.0

    def chapter_keys(self):
        return CHAPTERS.get(self.chapter, {}).get("keys", [])

    def available_legendaries(self):
        return [k for k in self.chapter_keys() if k not in self.captured]


class Game:
    def __init__(self, table, fx=None):
        self.table = table
        self.fx = fx or NullFX()
        self.state = "attract"
        self.players = []
        self.pidx = 0
        self.modes = []
        self.time = 0.0
        self.ball_save_t = 0.0
        self.ball_save_pending = 0.0
        self.pending_launch = 0
        self.launch_delay = 0.0
        self.tilt_meter = 0.0
        self.tilt_warnings = 0
        self.tilted = False
        self.last_shot = None
        self.last_shot_t = -10.0
        self.combo = 0
        self.skill_lane = 1
        self.skill_t = 0.0
        self.skill_armed = False
        self.super_skill_t = 0.0
        self.ball_launched = False
        self.select = None
        self.bonus_t = 0.0
        self.grass_down_t = 0.0
        self.scoop_action_t = 0.0
        self.game_time = 0.0
        self.high_scores = self.load_scores()
        self.hs_entry = None
        self.match_t = 0.0
        self.last_score_flash = 0
        self.lamps = Lamps()
        self.gi_color = (255, 236, 200)

    # ------------------------------------------------------------------
    # Sauvegarde des records
    # ------------------------------------------------------------------
    def load_scores(self):
        default = [("ASH", 250_000_000), ("PIK", 180_000_000), ("OAK", 120_000_000),
                   ("MTY", 80_000_000), ("RED", 50_000_000), ("BLU", 25_000_000)]
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            return [(e[0], int(e[1])) for e in d.get("scores", [])][:6] or default
        except Exception:
            return default

    def save_scores(self):
        try:
            with open(SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump({"scores": self.high_scores}, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    # ------------------------------------------------------------------
    @property
    def player(self):
        return self.players[self.pidx] if self.players else None

    def active(self, cls):
        for m in self.modes:
            if isinstance(m, cls):
                return m
        return None

    def legendary_mode(self):
        return self.active(M.LegendaryMode)

    def multiball_active(self):
        return any(m.is_multiball for m in self.modes) or self.balls_in_play() > 1

    def balls_in_play(self):
        return sum(1 for b in self.table.world.balls if b.state != "gone") + self.pending_launch

    def scoop_busy(self):
        return self.select is not None or self.scoop_action_t > 0

    def paused_timers(self):
        return self.bonus_t > 0

    def shot_pos(self, shot):
        return SHOT_POS.get(shot, (241, 500))

    # ------------------------------------------------------------------
    # Démarrage / joueurs
    # ------------------------------------------------------------------
    def start_button(self):
        if self.state in ("attract", "game_over"):
            self.start_game()
        elif self.state == "playing" and self.player.ball == 1 and len(self.players) < 4 \
                and all(p.ball == 1 for p in self.players):
            self.players.append(Player(len(self.players)))
            self.fx.sound("add_player")
            self.fx.lcd("message", title=f"JOUEUR {len(self.players)}", sub="a rejoint la partie",
                        color=LAMP["yellow"])

    def start_game(self):
        self.players = [Player(0)]
        self.pidx = 0
        self.modes = []
        self.state = "playing"
        self.game_time = 0.0
        for b in list(self.table.world.balls):
            b.state = "gone"
        self.table.world.remove_gone()
        self.table.grass.reset()
        self.fx.sound("start")
        self.fx.callout("start")
        self.start_ball()

    def start_ball(self):
        p = self.player
        self.tilted = False
        self.tilt_warnings = 0
        self.tilt_meter = 0.0
        self.ball_save_t = 0.0
        self.ball_save_pending = BALL_SAVE_TIME
        self.ball_launched = False
        self.skill_lane = random.randint(0, 2)
        self.skill_t = 0.0
        self.combo = 0
        self.last_shot = None
        p.top_lanes = [False, False, False]
        for f in self.table.flippers.values():
            f.enabled = True
        self.table.kickback.lit = p.kickback
        self.table.grass.reset()
        self.table.pokeball.open_target = 0.0
        self.table.new_ball_in_shooter()
        self.fx.music("main")
        self.fx.lcd("player_up", player=p.idx + 1, ball=p.ball)
        if p.mewtwo_lit and not p.mewtwo_progress:
            pass

    # ------------------------------------------------------------------
    # Entrées
    # ------------------------------------------------------------------
    def flipper(self, side, down):
        if self.state != "playing":
            return
        if self.select is not None and down:
            self.mode_select_move(-1 if side == "L" else 1)
        if not self.tilted:
            self.table.flippers[side].pressed = down
        if down:
            # changement de couloir (lane change)
            p = self.player
            if side == "L":
                p.top_lanes = p.top_lanes[1:] + p.top_lanes[:1]
                p.lanes = p.lanes[1:] + p.lanes[:1]
            else:
                p.top_lanes = p.top_lanes[-1:] + p.top_lanes[:-1]
                p.lanes = p.lanes[-1:] + p.lanes[:-1]
            if not self.ball_launched:
                self.skill_lane = (self.skill_lane + (-1 if side == "L" else 1)) % 3
                self.fx.sound("lane_change")

    def launch_button(self):
        if self.select is not None:
            self.mode_select_confirm()

    def nudge(self, dx, dy):
        if self.state != "playing" or self.tilted:
            return
        self.table.world.nudge(dx * 280, dy * 260 - 60)
        self.fx.shake(0.5)
        self.fx.sound("nudge")
        self.tilt_meter += 1.0
        if self.tilt_meter > 1.7:
            self.tilt_meter = 0.0
            self.tilt_warnings += 1
            if self.tilt_warnings >= 3:
                self.tilt()
            else:
                self.fx.lcd("tilt_warning", n=self.tilt_warnings)
                self.fx.sound("tilt_warning")
                self.fx.callout("danger")

    def tilt(self):
        self.tilted = True
        for f in self.table.flippers.values():
            f.pressed = False
            f.enabled = False
        self.table.kickback.lit = False
        self.ball_save_t = 0.0
        self.pending_launch = 0
        self.fx.lcd("tilt")
        self.fx.sound("tilt")
        self.fx.callout("tilt")
        self.fx.music(None)
        for m in list(self.modes):
            self.abort_mode(m)
        if self.select is not None:
            self.select = None
        self.table.scoop.locked = False

    # ------------------------------------------------------------------
    # Score
    # ------------------------------------------------------------------
    def add_score(self, pts, x=None, y=None):
        if self.state != "playing" or self.tilted:
            return 0
        p = self.player
        mult = 2 if p.multi_exp_t > 0 else 1
        pts = int(pts) * mult
        p.score += pts
        if x is not None and pts >= 100_000:
            self.fx.popup(x, y, fmt(pts))
        return pts

    def ball_save(self, seconds):
        self.ball_save_t = max(self.ball_save_t, seconds)

    def add_balls(self, n, save=0.0):
        n = max(0, int(n))
        self.pending_launch += n
        if save:
            self.ball_save(save)

    def light_extra_ball(self):
        p = self.player
        if not p.eb_lit:
            p.eb_lit = True
            self.fx.lcd("extra_ball_lit")
            self.fx.callout("eb_lit")
            self.fx.sound("eb_lit")

    # ------------------------------------------------------------------
    # Modes
    # ------------------------------------------------------------------
    def start_mode(self, mode):
        self.modes.append(mode)
        self.modes.sort(key=lambda m: m.priority)
        mode.start()
        return mode

    def stop_mode(self, mode, silent=False):
        if mode in self.modes:
            self.modes.remove(mode)
            mode.stop()

    def end_legendary(self, mode, success):
        p = self.player
        self.stop_mode(mode)
        p.modes_played += 1
        p.radar = [0, 0, 0]
        p.radar_need = 1 if p.modes_played < 3 else (2 if p.modes_played < 7 else 3)
        self.table.pokeball.open_target = 0.0
        self.table.grass.reset()
        if mode.leg.key == "mew" and not success:
            p.mew_lit = True
        if success:
            if mode.leg.key == "mew":
                p.mew_done = True
                p.mew_lit = False
                p.mewtwo_lit = True
                self.fx.lcd("message", title="MEWTWO VOUS ATTEND", sub="Centre Pokémon : combat final !",
                            color=LAMP["purple"])
            elif not p.available_legendaries():
                p.chapter_clear = True
                self.check_wizard(announce_missing=True)
            if p.chapter == 2 and not p.available_legendaries():
                self.light_extra_ball()
        self.fx.music("main" if not self.multiball_active() else "multiball")

    def pokedex_needed(self):
        p = self.player
        return max(0, POKEDEX_GATE.get(p.chapter, 0) - len(p.pokedex))

    def check_wizard(self, announce_missing=False):
        p = self.player
        if not p.chapter_clear or p.wizard_lit or p.chapter not in POKEDEX_GATE:
            return
        need = self.pokedex_needed()
        if need <= 0:
            p.wizard_lit = True
            self.fx.lcd("chapter_complete", chapter=p.chapter)
            self.fx.callout("chapter_complete")
        elif announce_missing:
            self.fx.lcd("message", title=f"CHAPITRE {p.chapter} TERMINÉ !",
                        sub=f"Capturez encore {need} Pokémon sauvage(s) pour le multiball",
                        color=LAMP["green"])

    def chapter_wizard_done(self, chapter):
        p = self.player
        p.wizards_done.add(chapter)
        p.wizard_lit = False
        p.chapter_clear = False
        if chapter >= 4:
            p.chapter = 5
            p.mew_lit = True
            self.fx.lcd("message", title="UN MIRAGE ROSE...", sub="Mew est apparu ! Centre Pokémon",
                        color=LAMP["pink"])
        else:
            p.chapter = chapter + 1
            p.mode_lit = True
            self.fx.lcd("chapter_intro", chapter=p.chapter)

    def end_multiball(self, mode):
        self.stop_mode(mode)
        self.fx.music("main")

    def mewtwo_won(self, mode):
        p = self.player
        self.stop_mode(mode)
        p.mewtwo_done += 1
        p.mewtwo_lit = False
        p.mewtwo_progress = {}
        p.captured.append("mewtwo")
        # nouvelle aventure : la progression repart, le score reste
        p.loops += 1
        p.captured = []
        p.leg_hp = {}
        p.chapter = 1
        p.wizard_lit = False
        p.chapter_clear = False
        p.wizards_done = set()
        p.mew_done = False
        p.mode_lit = True
        p.extra_balls += 1
        self.fx.lcd("message", title="NOUVELLE AVENTURE", sub=f"Boucle {p.loops + 1} — Balle supplémentaire !",
                    color=LAMP["gold"])

    def quake(self):
        for b in self.table.world.balls:
            if b.state == "pf":
                b.vx += random.uniform(-220, 220)
                b.vy += random.uniform(-260, 60)

    # ------------------------------------------------------------------
    # Sélection de mode au Centre Pokémon
    # ------------------------------------------------------------------
    def begin_mode_select(self):
        p = self.player
        opts = p.available_legendaries()
        if not opts:
            return False
        self.select = {"options": opts, "idx": 0, "t": 10.0}
        sc = self.table.scoop
        sc.locked = True
        self.fx.lcd("mode_select", select=self.select, player=p)
        self.fx.sound("select_open")
        self.fx.callout("choose")
        self.fx.music("select")
        return True

    def mode_select_move(self, d):
        s = self.select
        s["idx"] = (s["idx"] + d) % len(s["options"])
        s["t"] = max(s["t"], 4.0)
        self.fx.sound("select_tick")

    def mode_select_confirm(self):
        s = self.select
        if s is None:
            return
        key = s["options"][s["idx"]]
        self.select = None
        p = self.player
        p.mode_lit = False
        leg = LEG_BY_KEY[key]
        mode = M.LEG_MODES[key](self, leg)
        self.start_mode(mode)
        sc = self.table.scoop
        sc.locked = False
        sc.hold(mode.intro_t)
        self.scoop_action_t = mode.intro_t
        self.fx.sound("select_confirm")

    # ------------------------------------------------------------------
    # Boucle de mise à jour
    # ------------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        if self.state == "playing":
            self.game_time += dt
            self.update_playing(dt)
        elif self.state == "bonus":
            self.bonus_t -= dt
            if self.bonus_t <= 0:
                self.next_ball()
        elif self.state == "game_over":
            self.match_t -= dt
            if self.match_t <= 0 and self.hs_entry is None:
                self.state = "attract"
                self.fx.music("attract")
        self.lamps = self.compute_lamps()

    def update_playing(self, dt):
        p = self.player
        tb = self.table
        if self.ball_save_t > 0:
            self.ball_save_t = max(0.0, self.ball_save_t - dt)
        self.tilt_meter = max(0.0, self.tilt_meter - dt * 0.4)
        if self.skill_t > 0:
            self.skill_t -= dt
        if self.super_skill_t > 0:
            self.super_skill_t -= dt
        if p.multi_exp_t > 0:
            p.multi_exp_t -= dt
        if self.scoop_action_t > 0:
            self.scoop_action_t -= dt

        # sélection de mode
        if self.select is not None:
            self.select["t"] -= dt
            if self.select["t"] <= 0:
                self.mode_select_confirm()

        # éjection automatique (multiball / ball save)
        self.update_autolaunch(dt)

        # herbes hautes : remise en place automatique
        need_pb = p.capture_lit or any(m.needs_pokeball() for m in self.modes)
        if tb.grass.all_down() and not need_pb:
            self.grass_down_t += dt
            if self.grass_down_t > 2.5:
                tb.grass.reset()
                self.grass_down_t = 0.0
        else:
            self.grass_down_t = 0.0
        if need_pb and not tb.grass.all_down():
            if p.capture_lit or any(m.needs_pokeball() and not isinstance(m, M.EnteiMode) for m in self.modes):
                tb.grass.drop_all()
        tb.pokeball.open_target = 1.0 if any(
            (getattr(m, "phase", "") == "capture") or (isinstance(m, M.MewtwoMode) and m.stage == 3)
            for m in self.modes) else 0.0

        for m in list(self.modes):
            if m.active:
                m.update(dt)

        # multiball terminé ?
        if self.balls_in_play() <= 1:
            for m in list(self.modes):
                if m.is_multiball:
                    m.on_drain_to_single()

    def update_autolaunch(self, dt):
        tb = self.table
        if self.launch_delay > 0:
            self.launch_delay -= dt
            if self.launch_delay <= 0:
                tb.plunger.fire(0.86, auto=True)
            return
        shooter_ball = tb.plunger.ball_on_plunger()
        if shooter_ball is not None:
            if self.pending_launch > 0 or (self.ball_launched and self.balls_in_play() > 1):
                self.launch_delay = 0.6
            return
        if self.pending_launch > 0 and not self.tilted:
            # place une nouvelle bille dans le couloir si libre
            lane_free = all(not (b.x > 486 and b.y > 900) for b in tb.world.balls if b.state == "pf")
            if lane_free:
                tb.new_ball_in_shooter()
                self.pending_launch -= 1
                self.launch_delay = 0.7

    # ------------------------------------------------------------------
    # Fin de bille
    # ------------------------------------------------------------------
    def on_drain(self, ball):
        if self.state != "playing":
            return
        tb = self.table
        tb.world.remove_gone()
        if self.tilted:
            if self.balls_in_play() == 0:
                self.end_ball()
            return
        if self.ball_save_t > 0 and self.ball_launched:
            self.pending_launch += 1
            self.fx.lcd("ball_saved")
            self.fx.callout("ball_saved")
            self.fx.sound("ball_saved")
            return
        n = self.balls_in_play()
        self.fx.sound("drain")
        if n >= 1:
            if n == 1:
                for m in list(self.modes):
                    if m.is_multiball:
                        m.on_drain_to_single()
            return
        self.end_ball()

    def abort_mode(self, m):
        """Mode interrompu (bille perdue, tilt) : la progression est conservée et rallumée."""
        p = self.player
        if isinstance(m, M.LegendaryMode):
            m.end_by_drain()
            p.leg_hp[m.leg.key] = max(1.0, m.hp)
            if m.leg.key == "mew":
                p.mew_lit = True
            else:
                p.mode_lit = True
        elif isinstance(m, M.ChapterWizard):
            self.chapter_wizard_done(m.chapter)
        elif isinstance(m, M.MewtwoMode) and m.phase != "won":
            p.mewtwo_lit = True
        self.stop_mode(m, silent=True)

    def end_ball(self):
        p = self.player
        for m in list(self.modes):
            self.abort_mode(m)
        if self.select is not None:
            self.select = None
        self.table.scoop.locked = False
        self.table.pokeball.open_target = 0.0
        for f in self.table.flippers.values():
            f.pressed = False
        if self.tilted:
            self.bonus_t = 2.0
            self.state = "bonus"
            self.fx.lcd("message", title="TILT", sub="Pas de bonus", color=LAMP["red"])
            return
        s = p.stats
        lines = [
            ("POKÉDEX", len(p.pokedex), 250_000),
            ("LÉGENDAIRES", len(p.captured), 2_000_000),
            ("RAMPES", s["ramps"], 25_000),
            ("ORBITES", s["orbits"], 25_000),
            ("COMBOS", s["combos"], 50_000),
            ("VOLTORBES", s["bumpers"], 2_000),
        ]
        total = sum(n * v for _, n, v in lines) * p.bonus_x
        p.score += total
        self.fx.lcd("bonus", lines=lines, mult=p.bonus_x, total=total)
        self.fx.music("bonus")
        self.bonus_t = 5.5
        self.state = "bonus"
        p.bonus_x = 1
        for k in s:
            if k in ("ramps", "orbits", "combos", "bumpers"):
                s[k] = 0

    def next_ball(self):
        p = self.player
        if p.extra_balls > 0 and not self.tilted:
            p.extra_balls -= 1
            self.state = "playing"
            self.fx.lcd("shoot_again")
            self.fx.callout("shoot_again")
            self.start_ball()
            return
        p.ball += 1
        n = len(self.players)
        for k in range(1, n + 1):
            cand = (self.pidx + k) % n
            if self.players[cand].ball <= BALLS_PER_GAME:
                self.pidx = cand
                self.state = "playing"
                self.start_ball()
                return
        self.game_over()

    def game_over(self):
        self.state = "game_over"
        self.match_t = 7.0
        self.fx.music("game_over")
        self.fx.callout("game_over")
        self.fx.lcd("game_over", players=[pl.score for pl in self.players],
                    match=random.randint(0, 9) * 10)
        # records
        entries = []
        for pl in self.players:
            if len(self.high_scores) < 6 or pl.score > self.high_scores[-1][1]:
                entries.append(pl)
        if entries:
            self.hs_entry = {"queue": entries, "letters": [0, 0, 0], "pos": 0}
        for b in self.table.world.balls:
            b.state = "gone"
        self.table.world.remove_gone()

    # saisie des initiales ------------------------------------------------
    ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "

    def hs_input(self, action):
        h = self.hs_entry
        if h is None:
            return
        if action == "L":
            h["letters"][h["pos"]] = (h["letters"][h["pos"]] - 1) % len(self.ALPHA)
            self.fx.sound("select_tick")
        elif action == "R":
            h["letters"][h["pos"]] = (h["letters"][h["pos"]] + 1) % len(self.ALPHA)
            self.fx.sound("select_tick")
        elif action == "ok":
            h["pos"] += 1
            self.fx.sound("select_confirm")
            if h["pos"] >= 3:
                pl = h["queue"].pop(0)
                name = "".join(self.ALPHA[i] for i in h["letters"]).strip() or "???"
                self.high_scores.append((name, pl.score))
                self.high_scores.sort(key=lambda e: -e[1])
                self.high_scores = self.high_scores[:6]
                self.save_scores()
                if h["queue"]:
                    self.hs_entry = {"queue": h["queue"], "letters": [0, 0, 0], "pos": 0}
                else:
                    self.hs_entry = None
                    self.state = "attract"
                    self.fx.music("attract")

    # ------------------------------------------------------------------
    # Événements du plateau
    # ------------------------------------------------------------------
    def handle(self, ev, kw):
        if self.state != "playing":
            return
        p = self.player
        if ev == "drain":
            self.on_drain(kw.get("ball"))
            return
        if self.tilted:
            return
        for m in list(self.modes):
            m.on_event(ev, kw)
        h = getattr(self, "ev_" + ev, None)
        if h:
            h(kw)

    # --- interrupteurs ---------------------------------------------------
    def ev_launch(self, kw):
        if not self.ball_launched:
            self.ball_launched = True
            self.skill_t = SKILL_WINDOW
            self.ball_save_t = max(self.ball_save_t, self.ball_save_pending)
            self.ball_save_pending = 0.0
            if self.skill_armed:
                self.super_skill_t = 9.0
                self.fx.lcd("message", title="SUPER SKILL SHOT", sub="Visez la RAMPE LUGIA !", color=LAMP["cyan"])

    def ev_plunger_fire(self, kw):
        if not kw.get("auto"):
            self.fx.sound("plunger")
            self.skill_armed = self.table.flippers["L"].pressed and not self.ball_launched
        else:
            self.fx.sound("autolaunch")

    def ev_bumper(self, kw):
        p = self.player
        p.bumper_hits += 1
        p.stats["bumpers"] += 1
        self.add_score(5_000 * p.bumper_level)
        self.fx.sound("bumper")
        self.fx.particles(kw.get("x"), kw.get("y"), "spark", 10)
        if p.bumper_hits % 30 == 0:
            p.bumper_level = min(9, p.bumper_level + 1)
            self.add_score(500_000)
            self.fx.lcd("message", title="VOLTORBE ÉVOLUE !", sub=f"Bumpers niveau {p.bumper_level}",
                        color=LAMP["red"])
            self.fx.sound("evolve")

    def ev_sling(self, kw):
        self.add_score(1_010)
        self.fx.sound("sling")

    def ev_spinner(self, kw):
        p = self.player
        p.stats["spins"] += 1
        self.add_score(2_500 + 250 * p.bumper_level)
        self.fx.sound("spinner")

    def ev_spinner_enter(self, kw):
        pass

    def ev_rollover(self, kw):
        p = self.player
        grp, i = kw.get("group"), kw.get("index")
        self.fx.sound("rollover")
        self.add_score(5_000)
        if grp == "top":
            if self.skill_t > 0 and self.ball_launched:
                self.skill_t = 0.0
                if i == self.skill_lane:
                    v = 1_000_000 + 500_000 * (p.ball - 1)
                    self.add_score(v)
                    self.fx.lcd("skill_shot", value=v)
                    self.fx.callout("skill_shot")
                    self.fx.sound("skill_shot")
                    self.fx.light_show("jackpot", 1.0, color=LAMP["yellow"])
            p.top_lanes[i] = True
            if all(p.top_lanes):
                p.top_lanes = [False, False, False]
                if p.bonus_x < 6:
                    p.bonus_x += 1
                self.add_score(100_000)
                self.fx.lcd("bonus_x", n=p.bonus_x)
                self.fx.sound("lanes_complete")
                self.fx.light_show("sweep", 0.8, color=LAMP["yellow"])
        elif grp == "lane":
            if i in (0, 3):
                self.fx.sound("outlane")
            p.lanes[i] = True
            if all(p.lanes):
                p.lanes = [False] * 4
                self.add_score(250_000)
                p.mystery_lit = True
                if not p.kickback:
                    p.kickback = True
                    self.table.kickback.lit = True
                    self.fx.lcd("message", title="RONFLEX SE RÉVEILLE", sub="Kickback allumé + Mystère",
                                color=LAMP["blue"])
                else:
                    self.fx.lcd("message", title="P O K É", sub="Mystère allumé au Centre Pokémon",
                                color=LAMP["purple"])
                self.fx.sound("lanes_complete")

    def ev_kickback(self, kw):
        p = self.player
        p.kickback = False
        self.table.kickback.lit = False
        self.fx.sound("kickback")
        self.fx.lcd("message", title="RONFLEX !", sub="Bille renvoyée", color=LAMP["blue"])
        self.fx.callout("snorlax")
        self.ball_save(2.0)

    def ev_standup(self, kw):
        p = self.player
        bank, i = kw.get("bank"), kw.get("index")
        p.stats["standups"] += 1
        self.add_score(25_000)
        self.fx.sound("standup")
        if bank == "radar":
            lm = self.legendary_mode()
            if lm and lm.phase == "battle":
                lm.timer = min(99, lm.timer + 3)
            if p.mode_lit or not p.available_legendaries():
                return
            p.radar[i] = min(p.radar_need, p.radar[i] + 1)
            if all(r >= p.radar_need for r in p.radar):
                p.radar = [0, 0, 0]
                p.mode_lit = True
                self.fx.lcd("mode_lit")
                self.fx.callout("legendary_ready")
                self.fx.sound("mode_lit")
            else:
                self.fx.lcd("radar", radar=list(p.radar), need=p.radar_need)
        elif bank == "rocket":
            if self.active(M.TeamRocketMode):
                return
            p.rocket[i] = True
            if all(p.rocket):
                p.rocket = [False, False, False]
                self.start_mode(M.TeamRocketMode(self))

    def ev_drop(self, kw):
        p = self.player
        p.stats["drops"] += 1
        self.add_score(15_000)
        self.fx.sound("drop")
        self.on_shot("center", {"via": "drop", "index": kw.get("index")})
        if self.table.grass.all_down():
            self.grass_complete()

    def grass_complete(self):
        p = self.player
        allowed = (not self.legendary_mode() and not self.multiball_active() and not self.active(M.MewtwoMode))
        self.add_score(100_000)
        if allowed and not p.capture_lit:
            pool = [w for w in WILD if w[1] not in p.pokedex] or WILD
            p.wild_current = random.choice(pool)
            p.capture_lit = True
            self.fx.lcd("wild_appears", poke=p.wild_current)
            self.fx.callout("wild")
            self.fx.sound("wild_appears")
            self.fx.music_stinger("wild")

    def ev_pokeball(self, kw):
        self.fx.sound("pokeball_hit")
        if self.on_shot("center", {"via": "pokeball"}):
            return
        p = self.player
        if p.capture_lit and p.wild_current:
            self.capture_wild()
        else:
            self.add_score(25_000)

    def capture_wild(self):
        p = self.player
        poke = p.wild_current
        p.capture_lit = False
        p.wild_current = None
        p.pokedex.append(poke[1])
        p.stats["captures"] += 1
        v = 750_000 + 100_000 * len(p.pokedex)
        self.add_score(v)
        p.locks += 1
        self.fx.lcd("wild_caught", poke=poke, value=v, locks=p.locks, need=p.locks_needed,
                    count=len(p.pokedex))
        self.fx.sound("gotcha_small")
        self.fx.callout("caught")
        self.table.grass.reset()
        if len(p.pokedex) in (5, 15):
            self.light_extra_ball()
        self.check_wizard()
        if p.locks >= p.locks_needed and not self.multiball_active() and not self.legendary_mode():
            p.locks = 0
            p.locks_needed = min(6, p.locks_needed + 1)
            self.start_mode(M.SafariMultiball(self))

    def ev_ramp_enter(self, kw):
        self.fx.sound("ramp_enter")

    def ev_ramp_fail(self, kw):
        self.fx.sound("ramp_fail")

    def ev_ramp_exit(self, kw):
        self.fx.sound("ramp_exit")

    def ev_ramp_made(self, kw):
        e = kw["element"]
        shot = "ramp_l" if e.name == "ramp_l" else "ramp_r"
        self.player.stats["ramps"] += 1
        self.add_score(50_000)
        self.fx.sound("ramp_made")
        if shot == "ramp_l" and self.super_skill_t > 0:
            self.super_skill_t = 0
            v = 3_000_000
            self.add_score(v)
            self.fx.lcd("skill_shot", value=v, super=True)
            self.fx.callout("super_skill")
            self.player.radar = [self.player.radar_need] * 3
        self.on_shot(shot, kw)

    def ev_orbit_left(self, kw):
        self.player.stats["orbits"] += 1
        self.add_score(40_000)
        self.fx.sound("orbit")
        self.on_shot("orbit_l", kw)

    def ev_orbit_right(self, kw):
        self.player.stats["orbits"] += 1
        self.add_score(40_000)
        self.fx.sound("orbit")
        self.on_shot("orbit_r", kw)

    def ev_bumper_lane(self, kw):
        self.add_score(20_000)
        self.on_shot("bumper", kw)

    def ev_scoop(self, kw):
        self.fx.sound("scoop_in")
        self.add_score(30_000)
        consumed = self.on_shot("scoop", kw)
        self.scoop_award(consumed)

    def ev_scoop_eject(self, kw):
        self.fx.sound("scoop_kick")

    def ev_gate(self, kw):
        pass

    # --- tirs majeurs ------------------------------------------------------
    def on_shot(self, shot, kw):
        if kw.get("via") != "drop":
            if shot == self.last_shot and self.time - self.last_shot_t < COMBO_WINDOW:
                pass
            elif self.time - self.last_shot_t < COMBO_WINDOW:
                self.combo += 1
                p = self.player
                p.stats["combos"] += 1
                v = 250_000 * self.combo
                x, y = self.shot_pos(shot)
                self.add_score(v, x, y)
                self.fx.lcd("combo", n=self.combo + 1, value=v)
                self.fx.sound("combo")
                if self.combo + 1 in (3, 5):
                    self.fx.callout("combo")
            else:
                self.combo = 0
            self.last_shot = shot
            self.last_shot_t = self.time
        for m in sorted(self.modes, key=lambda m: -m.priority):
            if m.active and m.on_shot(shot, kw):
                return True
        return False

    # --- Centre Pokémon ------------------------------------------------------
    def scoop_award(self, consumed):
        p = self.player
        sc = self.table.scoop
        mb = self.multiball_active()
        busy = any(m.blocks_scoop_modes for m in self.modes) or self.legendary_mode() is not None
        if consumed:
            sc.hold(1.0)
            return
        if not mb and not busy:
            if p.mewtwo_lit:
                p.mewtwo_lit = False
                mode = self.start_mode(M.MewtwoMode(self))
                sc.hold(5.0)
                self.scoop_action_t = 5.0
                return
            if p.mew_lit:
                p.mew_lit = False
                mode = self.start_mode(M.MewMode(self))
                sc.hold(mode.intro_t)
                self.scoop_action_t = mode.intro_t
                return
            if p.wizard_lit:
                p.wizard_lit = False
                self.start_mode(M.ChapterWizard(self, p.chapter))
                sc.hold(3.0)
                self.scoop_action_t = 3.0
                return
        if p.eb_lit:
            p.eb_lit = False
            p.extra_balls += 1
            self.fx.lcd("extra_ball")
            self.fx.callout("extra_ball")
            self.fx.sound("extra_ball")
            self.fx.light_show("jackpot", 2.0, color=LAMP["orange"])
            sc.hold(2.5)
            return
        if p.mode_lit and not mb and not busy and p.available_legendaries():
            self.begin_mode_select()
            return
        if p.mystery_lit:
            p.mystery_lit = False
            self.mystery()
            sc.hold(2.6)
            return
        sc.hold(0.9)

    def mystery(self):
        p = self.player
        name, desc = random.choice(MYSTERY_AWARDS)
        if name == "BONBON RARE":
            p.bonus_x = min(6, p.bonus_x + 1)
        elif name == "POTION":
            self.ball_save(15.0)
        elif name == "SUPER BALL":
            p.super_ball = True
        elif name == "PÉPITE":
            v = random.choice([1_000_000, 2_000_000, 3_000_000])
            self.add_score(v)
            desc = fmt(v) + " points"
        elif name == "POKÉ RADAR":
            p.radar = [p.radar_need] * 3
            if not p.mode_lit and p.available_legendaries():
                p.mode_lit = True
        elif name == "RONFLEX":
            p.kickback = True
            self.table.kickback.lit = True
        elif name == "MULTI EXP.":
            p.multi_exp_t = 30.0
        elif name == "HYPER BALL":
            if not self.legendary_mode() and not self.multiball_active():
                self.table.grass.drop_all()
                self.grass_complete()
        self.fx.lcd("mystery", award=name, desc=desc)
        self.fx.sound("mystery")

    # ------------------------------------------------------------------
    # Lampes
    # ------------------------------------------------------------------
    def compute_lamps(self):
        L = Lamps()
        if self.state != "playing" or not self.players:
            return L
        p = self.player
        # couloirs
        for i, on in enumerate(p.top_lanes):
            if not self.ball_launched or self.skill_t > 0:
                if i == self.skill_lane:
                    L.set(f"toplane_{i}", LAMP["yellow"], "fast")
                    continue
            if on:
                L.set(f"toplane_{i}", LAMP["white"])
        for i, on in enumerate(p.lanes):
            if on:
                L.set(f"lane_{i}", LAMP["cyan"])
        if p.kickback:
            L.set("kickback", LAMP["blue"], "on")
        if self.ball_save_t > 0 or (not self.ball_launched and self.ball_save_pending > 0):
            L.set("shoot_again", LAMP["orange"], "fast" if self.ball_save_t < 3 else "blink")
        elif p.extra_balls > 0:
            L.set("shoot_again", LAMP["orange"])
        for n in range(2, 7):
            if p.bonus_x >= n:
                L.set(f"bx_{n}", LAMP["yellow"])
        for i in range(3):
            r = p.radar[i]
            if p.mode_lit:
                L.set(f"radar_{i}", LAMP["green"], "blink")
            elif r >= p.radar_need:
                L.set(f"radar_{i}", LAMP["green"])
            elif r > 0:
                L.set(f"radar_{i}", LAMP["green"], "pulse")
            if p.rocket[i]:
                L.set(f"rocket_{i}", LAMP["red"])
        for i in range(3):
            if i < p.locks:
                L.set(f"lock_{i}", LAMP["green"])
            elif i == p.locks and p.capture_lit:
                L.set(f"lock_{i}", LAMP["green"], "blink")
        if p.capture_lit:
            L.arrow("center", LAMP["green"], "blink")
            L.set("center_capture", LAMP["green"], "blink")
        for i, t in enumerate(self.table.grass.targets):
            if not t.down:
                L.set(f"grass_{i}", LAMP["green"])
        # légendaires (anneau central)
        lm = self.legendary_mode()
        for leg in LEGENDARIES:
            if leg.key in p.captured:
                L.set("leg_" + leg.key, LAMP[leg.lamp])
            elif lm and lm.leg.key == leg.key:
                L.set("leg_" + leg.key, LAMP[leg.lamp], "fast")
            elif leg.key in p.available_legendaries():
                L.set("leg_" + leg.key, LAMP[leg.lamp], "pulse")
        if p.mew_done:
            L.set("leg_mew", LAMP["pink"])
        elif p.mew_lit or (lm and lm.leg.key == "mew"):
            L.set("leg_mew", LAMP["pink"], "fast")
        if self.active(M.MewtwoMode):
            L.set("leg_mewtwo", LAMP["purple"], "fast")
        elif p.mewtwo_lit:
            L.set("leg_mewtwo", LAMP["purple"], "blink")
        # Centre Pokémon
        busy = self.multiball_active() or lm is not None or self.active(M.MewtwoMode)
        if not busy and (p.mewtwo_lit or p.mew_lit or p.wizard_lit):
            col = LAMP["purple"] if p.mewtwo_lit else (LAMP["pink"] if p.mew_lit else LAMP["gold"])
            L.set("scoop_mode", col, "fast")
            L.arrow("scoop", [col, LAMP["white"]], "fast")
        elif p.mode_lit and not busy and p.available_legendaries():
            L.set("scoop_mode", LAMP["white"], "blink")
            cols = [LAMP[LEG_BY_KEY[k].lamp] for k in p.available_legendaries()]
            L.arrow("scoop", cols, "blink")
        if p.eb_lit:
            L.set("scoop_eb", LAMP["orange"], "blink")
            if not L.get("arrow_scoop"):
                L.arrow("scoop", LAMP["orange"], "blink")
        if p.mystery_lit:
            L.set("scoop_mystery", LAMP["purple"], "blink")
        # combos : flèches blanches pendant la fenêtre
        if self.time - self.last_shot_t < COMBO_WINDOW and self.last_shot:
            for s in SHOTS:
                if s != self.last_shot and s != "center":
                    L.set("shot_combo_" + s, LAMP["white"], "fast")
        if self.super_skill_t > 0:
            L.arrow("ramp_l", LAMP["cyan"], "fast")
        # modes (priorité croissante : les plus importants écrasent)
        for m in sorted(self.modes, key=lambda m: m.priority):
            m.lamps(L)
        # éclairage général
        gi = None
        for m in sorted(self.modes, key=lambda m: m.priority):
            g = m.gi()
            if g:
                gi = g
        self.gi_color = gi or (255, 236, 205)
        return L

    def hud(self):
        best = None
        for m in sorted(self.modes, key=lambda m: m.priority):
            h = m.hud()
            if h:
                best = h
        if best:
            return best
        p = self.player
        if p is None:
            return None
        if p.mewtwo_lit:
            lines = ["MEWTWO VOUS ATTEND", "Tirez le Centre Pokémon", "Combat final !"]
        elif p.mew_lit:
            lines = ["MEW EST APPARU", "Tirez le Centre Pokémon", ""]
        elif p.wizard_lit:
            lines = [CHAPTERS[p.chapter]["wizard"], "Prêt au Centre Pokémon", "Multiball de chapitre"]
        elif p.mode_lit and p.available_legendaries():
            lines = ["LÉGENDAIRE PRÊT", "Tirez le CENTRE POKÉMON", "(scoop à gauche)"]
        elif p.chapter_clear and not p.wizard_lit and self.pokedex_needed() > 0:
            lines = [f"POKÉDEX : encore {self.pokedex_needed()}", "Abattez les HAUTES HERBES",
                     "puis capturez à la POKÉBALL"]
        elif p.capture_lit and p.wild_current:
            lines = [f"{p.wild_current[1]} SAUVAGE !", "Frappez la POKÉBALL", "pour le capturer"]
        else:
            need = p.radar_need * 3 - sum(p.radar)
            lines = [f"RADAR : {need} cible(s)", "Cibles vertes à gauche", "→ allume un Légendaire"]
        return {"kind": "base", "lines": lines}
