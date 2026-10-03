"""Géométrie du plateau « POKÉMON — Légendes » (unités : mm).

Disposition inspirée des Stern modernes :
    orbite G (spinner) | scoop « Centre Pokémon » | rampe G (Lugia) |
    Hautes Herbes (3 drop targets) + Pokéball centrale |
    rampe D (Ho-Oh) | couloir des bumpers | orbite D
    + 3 couloirs supérieurs, 3 bumpers Voltorbe, 2 banques de cibles fixes,
    slingshots, inlanes/outlanes, kickback Ronflex, couloir de lancement.
"""
import math

from .config import PF_W, PF_H
from .physics import World, Segment, Circle, Flipper, RampPath
from . import elements as el

CX = 241.0          # axe central de la zone de jeu (hors couloir de lancement)


def arc(cx, cy, r, a0, a1, n=None):
    """Points d'un arc (degrés, sens horaire écran)."""
    if n is None:
        n = max(4, int(abs(a1 - a0) / 4))
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


def mirror(pts):
    return [(2 * CX - x, y) for x, y in pts]


class Table:
    def __init__(self):
        self.world = World()
        self.world.listener = self
        self.elements = []
        self.by_name = {}
        self.walls = []          # (points, style, rad) pour le rendu
        self.posts = []          # (x, y, r, style)
        self.events = []
        self.flippers = {}
        self._build()
        self.world.build_grid()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def emit(self, ev, **kw):
        self.events.append((ev, kw))

    def add(self, e):
        self.elements.append(e)
        self.by_name[e.name] = e
        return e

    def wall(self, pts, style="wall", rad=3.0, rest=0.45, fric=0.06, closed=False, render=True):
        w = self.world
        tag = {"rubber": "rubber", "metal": "metal"}.get(style, "wall")
        seq = list(pts) + ([pts[0]] if closed else [])
        for (x1, y1), (x2, y2) in zip(seq[:-1], seq[1:]):
            w.add(Segment(x1, y1, x2, y2, rad=rad, tag=tag, rest=rest, fric=fric))
        if render:
            self.walls.append((seq, style, rad))

    def post(self, x, y, r=6.0, style="rubber", rest=0.75):
        self.world.add(Circle(x, y, r, tag="rubber" if style == "rubber" else "metal", rest=rest, fric=0.15))
        self.posts.append((x, y, r, style))

    def _build(self):
        W = self.world

        # ---------------- contour extérieur ----------------
        outer = [(0, PF_H), (0, 800), (40, 690)]
        self.wall(outer, "metal", rad=2)
        # banque gauche (cibles RADAR) sur la paroi biseautée
        self.wall([(40, 690), (0, 560)], "wall", rad=2)
        top = [(0, 560), (0, 200)] + arc(200, 200, 200, 180, 270, 30)[1:] + \
              [(320, 0)] + arc(320, 200, 200, 270, 360, 30)[1:] + [(PF_W, PF_H)]
        self.outer_top = top
        self.wall(top, "metal", rad=2)
        # mur du couloir de lancement
        self.wall([(485, PF_H), (485, 330)], "metal", rad=3)
        # paroi biseautée droite (cibles TEAM ROCKET)
        self.wall([(482, 800), (442, 690)], "metal", rad=2)
        self.wall([(442, 690), (482, 560)], "wall", rad=2)

        # ---------------- îlot central (rampes, scoop, nid de la Pokéball) ----------
        self.island = (
            [(47, 440), (47, 200)] + arc(200, 200, 153, 180, 255, 20)[1:] +
            [(300, 75), (300, 382), (366, 410), (366, 440), (361, 470), (356, 440), (356, 405.8),
             (300, 382), (300, 440), (296, 470), (292, 440), (292, 330), (278, 290), (204, 290),
             (190, 330), (190, 440), (181, 470), (176, 440), (176, 390), (120, 390), (120, 440),
             (113, 470), (108, 440), (108, 420)] + arc(84, 420, 24, 0, -180, 14)[1:] +
            [(60, 440), (52, 470)])
        self.wall(self.island, "wall", rad=3, closed=True)
        for x in (52, 113, 181, 296, 361):
            self.post(x, 470, 5.0)

        # mur intérieur de l'orbite droite
        # la paroi intérieure s'incurve vers la droite : la bille rejoint en douceur
        # l'arc extérieur (boucle d'orbite fluide) ; sommet incliné pour ne rien bloquer
        self.right_block = [(437, 470), (437, 330), (472, 200), (472, 186), (437, 96)]
        self.wall(self.right_block, "wall", rad=3)
        self.post(437, 470, 5.0)
        # guides des couloirs supérieurs
        for x in (349, 395):
            self.wall([(x, 75), (x, 125)], "metal", rad=3)

        # ---------------- inlanes / outlanes / slingshots ----------------
        sep_l = ([(40, 812), (52, 812)] + arc(132, 903.8, 80, 180, 120, 12) +
                 [(158, 1011.2), (136, 1018), (132, 1045), (132, PF_H), (40, PF_H)])
        self.wall(sep_l, "metal", rad=2, closed=True)
        self.wall(mirror(sep_l), "metal", rad=2, closed=True)
        self.post(46, 812, 7)
        self.post(2 * CX - 46, 812, 7)
        self.sep_l = sep_l

        sl = [(96, 840), (96, 925), (149, 955.6)]
        self.add(el.Slingshot(self, "sling_l", sl[0], sl[1], sl[2]))
        sr = mirror(sl)
        self.add(el.Slingshot(self, "sling_r", sr[0], sr[1], sr[2]))
        self.posts.extend([(x, y, 6, "rubber") for x, y in sl + sr])

        # ---------------- flippers ----------------
        fl = Flipper(149, 1032, 30, -25, "L", name="flipper_l")
        fr = Flipper(2 * CX - 149, 1032, 150, 205, "R", name="flipper_r")
        W.flippers.extend([fl, fr])
        self.flippers = {"L": fl, "R": fr}

        # ---------------- bumpers Voltorbe ----------------
        self.bumpers = [
            self.add(el.PopBumper(self, "bumper_a", 330, 175)),
            self.add(el.PopBumper(self, "bumper_b", 410, 170)),
            self.add(el.PopBumper(self, "bumper_c", 370, 245)),
        ]

        # ---------------- couloirs supérieurs ----------------
        self.top_lanes = [self.add(el.Rollover(self, f"toplane_{i}", x, 100, group="top", index=i))
                          for i, x in enumerate((326, 372, 417.5))]

        # ---------------- inlanes / outlanes ----------------
        self.lanes = [
            self.add(el.Rollover(self, "outlane_l", 20, 905, group="lane", index=0)),
            self.add(el.Rollover(self, "inlane_l", 73, 880, group="lane", index=1)),
            self.add(el.Rollover(self, "inlane_r", 2 * CX - 73, 880, group="lane", index=2)),
            self.add(el.Rollover(self, "outlane_r", 2 * CX - 20, 905, group="lane", index=3)),
        ]
        self.kickback = self.add(el.Kickback(self, "kickback", 20, 1055))

        # ---------------- Hautes Herbes : 3 drop targets ----------------
        drops = []
        xs = [193.0, 225.0, 257.0, 289.0]
        for i in range(3):
            drops.append(self.add(el.DropTarget(self, f"drop_{i}", xs[i] + 4, 425, xs[i + 1] - 4, 425,
                                                index=i, bank="grass")))
        self.grass = el.DropBank("grass", drops)

        # ---------------- Pokéball centrale ----------------
        self.pokeball = self.add(el.PokeballToy(self, "pokeball", CX, 340, 40))

        # ---------------- banques de cibles fixes ----------------
        def bank(p_top, p_bot, name, bank_name, flip):
            (x0, y0), (x1, y1) = p_top, p_bot
            L = math.hypot(x1 - x0, y1 - y0)
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            nx, ny = (uy, -ux) if not flip else (-uy, ux)
            out = []
            for i, t in enumerate((0.25, 0.5, 0.75)):
                cx, cy = x0 + ux * L * t + nx * 4, y0 + uy * L * t + ny * 4
                out.append(self.add(el.Standup(self, f"{name}_{i}", cx - ux * 12, cy - uy * 12,
                                               cx + ux * 12, cy + uy * 12, index=i, bank=bank_name)))
            return out
        self.radar = bank((0, 560), (40, 690), "radar", "radar", False)
        self.rocket = bank((482, 560), (442, 690), "rocket", "rocket", True)

        # ---------------- scoop « Centre Pokémon » ----------------
        # éjection quasi verticale : la bille retombe dans l'inlane gauche (flipper gauche)
        self.scoop = self.add(el.Scoop(self, "scoop", 84, 424, eject_dir=91.6, eject_speed=1150))

        # ---------------- spinner + orbites ----------------
        self.spinner = self.add(el.Spinner(self, "spinner", (0, 432), (44, 432)))
        a_in, a_out = math.radians(225), math.radians(225)
        self.add(el.LineSwitch(self, "orbit_l_sw",
                               (200 + 200 * math.cos(a_out), 200 + 200 * math.sin(a_out)),
                               (200 + 153 * math.cos(a_in), 200 + 153 * math.sin(a_in)),
                               "orbit_left", want_dir=-1))
        self.add(el.LineSwitch(self, "orbit_r_sw", (440, 360), (482, 360), "orbit_right", want_dir=-1))
        self.add(el.LineSwitch(self, "shooter_sw", (488, 345), (520, 345), "launch", want_dir=-1))
        self.add(el.LineSwitch(self, "bumper_lane_sw", (369, 430), (434, 430), "bumper_lane", want_dir=-1))

        # porte anti-retour en haut du couloir de lancement
        self.add(el.OneWayGate(self, "shooter_gate", (520, 298), (485, 330)))
        # porte en haut à gauche : l'orbite gauche passe (sens horaire) ; les billes venant
        # de la droite (lancement, orbite droite) retombent dans les couloirs du haut
        a = math.radians(255)
        self.add(el.OneWayGate(self, "top_gate", (200 + 153 * math.cos(a), 200 + 153 * math.sin(a)),
                               (200 + 200 * math.cos(a), 200 + 200 * math.sin(a))))

        # ---------------- rampes ----------------
        lpts = [(148, 440, 0), (148, 400, 10), (148, 330, 35), (145, 270, 55), (132, 218, 67),
                (108, 184, 74), (78, 172, 77), (50, 184, 75), (30, 214, 71), (24, 260, 67),
                (24, 400, 60), (24, 560, 50), (24, 700, 40), (27, 762, 30), (40, 800, 20),
                (62, 826, 9), (73, 846, 0)]
        lpath = RampPath("ramp_l", lpts, sensors=[])
        lpath.sensors = [(lpath.cum[6], "made")]
        self.ramp_l = self.add(el.Ramp(self, "ramp_l", (173, 438), (123, 438), lpath, color=(90, 170, 255)))

        rpts = [(328, 440, 0), (328, 400, 10), (331, 330, 35), (345, 272, 52), (368, 224, 64),
                (400, 190, 72), (432, 170, 77), (456, 178, 75), (466, 205, 71), (466, 260, 67),
                (466, 400, 60), (466, 560, 50), (466, 700, 40), (463, 762, 30), (450, 800, 20),
                (420, 826, 9), (2 * CX - 73, 846, 0)]
        rpath = RampPath("ramp_r", rpts, sensors=[])
        rpath.sensors = [(rpath.cum[6], "made")]
        self.ramp_r = self.add(el.Ramp(self, "ramp_r", (353, 438), (303, 438), rpath, color=(255, 140, 70)))

        # ---------------- tirette ----------------
        self.plunger = self.add(el.Plunger(self, "plunger", 489, 519, 1105))
        self.shooter_rest = (504.0, 1105 - 13.6)

    # ------------------------------------------------------------------
    # Rappels du moteur physique
    # ------------------------------------------------------------------
    def on_hit(self, owner, ball, coll, nx, ny, imp):
        owner.on_hit(ball, coll, nx, ny, imp)

    def on_sensor(self, owner, ball, coll, direction):
        if owner is not None:
            owner.on_sensor(ball, coll, direction)

    def on_ramp(self, path, ball, name):
        if path.owner is not None:
            path.owner.on_ramp_event(ball, name)

    def on_flipper_hit(self, flipper, ball, imp):
        if imp > 200:
            self.world.impact_events.append((ball.x, ball.y, imp, "flipper"))

    # ------------------------------------------------------------------
    def update(self, dt):
        for e in self.elements:
            e.update(dt)

    def step(self, dt):
        self.world.step(dt)
        self.update(dt)
        self.ball_search(dt)

    def ball_search(self, dt):
        """Comme sur un vrai Stern : une bille immobile hors zone de repos est délogée."""
        import random
        for b in self.world.balls:
            if b.state != "pf":
                b.still_t = 0.0
                continue
            ax, ay = b.anchor
            if abs(b.x - ax) > 2.5 or abs(b.y - ay) > 2.5:
                b.anchor = (b.x, b.y)
                b.still_t = 0.0
                continue
            b.still_t += dt
            in_shooter = b.x > 486 and b.y > 900
            cradled = b.y > 950 and any(f.pressed for f in self.flippers.values())
            if b.still_t > 3.0 and not in_shooter and not cradled:
                b.still_t = 0.0
                b.vx += random.uniform(-350, 350)
                b.vy += random.uniform(-450, -150)
                self.emit("ball_search", ball=b, x=b.x, y=b.y)

    def take_events(self):
        ev = self.events
        self.events = []
        return ev

    def new_ball_in_shooter(self):
        x, y = self.shooter_rest
        return self.world.add_ball(x, y)
