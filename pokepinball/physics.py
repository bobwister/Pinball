"""Moteur physique 2D d'une bille de flipper sur plan incliné.

- Bille pleine roulant sans glisser : accélération 5/7·g·sin(6.5°).
- Sous-pas adaptatifs (déplacement max ~3 mm par sous-pas) : aucun effet tunnel.
- Flippers = capsules effilées en rotation (SDF exacte), vitesse du point de
  contact prise en compte dans l'impulsion (ω × r) + frottement de Coulomb.
- Rampes = trajectoires 3D paramétriques : conservation de l'énergie
  (la bille peut échouer et redescendre si le tir est trop faible).
"""
import math
from collections import deque

from .config import (G_ROLL, G, SIN_TILT, BALL_R, ROLL_DECEL, LINEAR_DRAG, MAX_SPEED,
                     SUBSTEP_MAX_MOVE, MIN_SUBSTEPS, MAX_SUBSTEPS, PF_H,
                     FLIPPER_LEN, FLIPPER_R1, FLIPPER_R2, FLIPPER_ACCEL, FLIPPER_MAX_W,
                     FLIPPER_RETURN_ACCEL, FLIPPER_RETURN_MAX_W)

GRID_CELL = 40.0


# ==========================================================================
# Bille
# ==========================================================================
class Ball:
    _next_id = 0

    def __init__(self, x, y):
        Ball._next_id += 1
        self.id = Ball._next_id
        self.x = x
        self.y = y
        self.px = x
        self.py = y
        self.vx = 0.0
        self.vy = 0.0
        self.r = BALL_R
        self.state = "pf"          # pf | ramp | held | gone
        self.ramp = None
        self.s = 0.0               # abscisse curviligne sur la rampe
        self.sv = 0.0              # vitesse sur la rampe
        self.h = 0.0               # hauteur au-dessus du plateau (rendu)
        self.inside = set()        # capteurs circulaires occupés
        self.roll = 0.0            # angle de roulement (rendu)
        self.trail = deque(maxlen=14)
        self.age = 0.0
        self.still_t = 0.0         # temps immobile (recherche de bille)
        self.anchor = (x, y)
        self.last_flip_time = -10.0
        self.ramp_sensor_idx = 0

    @property
    def speed(self):
        if self.state == "ramp":
            return abs(self.sv)
        return math.hypot(self.vx, self.vy)


# ==========================================================================
# Collisionneurs statiques
# ==========================================================================
class Collider:
    __slots__ = ("owner", "tag", "rest", "fric", "solid", "enabled", "one_way",
                 "bbox", "kind", "layer_mask")

    def __init__(self, owner=None, tag="", rest=0.5, fric=0.08, solid=True):
        self.owner = owner
        self.tag = tag
        self.rest = rest
        self.fric = fric
        self.solid = solid
        self.enabled = True
        self.one_way = False
        self.kind = ""


class Segment(Collider):
    __slots__ = ("x1", "y1", "x2", "y2", "rad", "dx", "dy", "len2", "nx", "ny", "length")

    def __init__(self, x1, y1, x2, y2, rad=0.0, **kw):
        super().__init__(**kw)
        self.kind = "seg"
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)
        self.rad = rad
        self.dx = self.x2 - self.x1
        self.dy = self.y2 - self.y1
        self.len2 = self.dx * self.dx + self.dy * self.dy or 1e-9
        self.length = math.sqrt(self.len2)
        # normale "gauche" (pour les portillons à sens unique)
        self.nx = -self.dy / self.length
        self.ny = self.dx / self.length
        pad = rad + BALL_R + 2
        self.bbox = (min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad)


class Circle(Collider):
    __slots__ = ("x", "y", "rad")

    def __init__(self, x, y, rad, **kw):
        super().__init__(**kw)
        self.kind = "circ"
        self.x, self.y, self.rad = float(x), float(y), float(rad)
        pad = rad + BALL_R + 2
        self.bbox = (x - pad, y - pad, x + pad, y + pad)


class LineSensor(Collider):
    """Détecte le franchissement d'une ligne (sens donné par la normale gauche)."""
    __slots__ = ("x1", "y1", "x2", "y2", "nx", "ny")

    def __init__(self, x1, y1, x2, y2, **kw):
        kw.setdefault("solid", False)
        super().__init__(**kw)
        self.kind = "line"
        self.x1, self.y1, self.x2, self.y2 = float(x1), float(y1), float(x2), float(y2)
        L = math.hypot(x2 - x1, y2 - y1) or 1e-9
        self.nx = -(y2 - y1) / L
        self.ny = (x2 - x1) / L
        pad = BALL_R + 4
        self.bbox = (min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad)


class CircleSensor(Collider):
    __slots__ = ("x", "y", "rad")

    def __init__(self, x, y, rad, **kw):
        kw.setdefault("solid", False)
        super().__init__(**kw)
        self.kind = "csens"
        self.x, self.y, self.rad = float(x), float(y), float(rad)
        pad = rad + 4
        self.bbox = (x - pad, y - pad, x + pad, y + pad)


# ==========================================================================
# Flipper
# ==========================================================================
class Flipper:
    def __init__(self, px, py, rest_deg, up_deg, side, length=FLIPPER_LEN,
                 r1=FLIPPER_R1, r2=FLIPPER_R2, name="", power=1.0):
        self.px, self.py = float(px), float(py)
        self.rest = math.radians(rest_deg)
        self.up = math.radians(up_deg)
        self.dir = 1.0 if self.up > self.rest else -1.0   # sens de levée
        self.angle = self.rest
        self.w = 0.0
        self.length = length
        self.r1, self.r2 = r1, r2
        self.side = side
        self.name = name
        self.pressed = False
        self.enabled = True
        self.power = power
        b = (r1 - r2) / length
        self._b = b
        self._a = math.sqrt(1.0 - b * b)
        self.owner = None
        self.at_eos = False

    @property
    def tip(self):
        return (self.px + math.cos(self.angle) * self.length,
                self.py + math.sin(self.angle) * self.length)

    def update(self, h):
        d = self.dir
        if self.pressed and self.enabled:
            self.w += d * FLIPPER_ACCEL * self.power * h
            wmax = FLIPPER_MAX_W * self.power
            if self.w * d > wmax:
                self.w = d * wmax
            self.angle += self.w * h
            if (self.angle - self.up) * d >= 0:
                self.angle = self.up
                self.w = 0.0
                self.at_eos = True
        else:
            self.at_eos = False
            self.w -= d * FLIPPER_RETURN_ACCEL * h
            if -self.w * d > FLIPPER_RETURN_MAX_W:
                self.w = -d * FLIPPER_RETURN_MAX_W
            self.angle += self.w * h
            if (self.angle - self.rest) * d <= 0:
                self.angle = self.rest
                self.w = 0.0

    def moving(self):
        return abs(self.w) > 1e-6

    def sdf(self, x, y):
        """Distance signée bille→flipper : (dist, nx, ny)."""
        c = math.cos(self.angle)
        s = math.sin(self.angle)
        rx = x - self.px
        ry = y - self.py
        ly = rx * c + ry * s           # le long de l'axe
        lx = -rx * s + ry * c          # latéral (perp = (-s, c))
        sign = 1.0 if lx >= 0 else -1.0
        ax = abs(lx)
        a, b, hgt = self._a, self._b, self.length
        k = -b * ax + a * ly
        if k < 0.0:
            d = math.hypot(ax, ly)
            if d < 1e-9:
                return -self.r1, 0.0, -1.0
            nlx, nly = ax / d, ly / d
            dist = d - self.r1
        elif k > a * hgt:
            d = math.hypot(ax, ly - hgt)
            if d < 1e-9:
                return -self.r2, 0.0, -1.0
            nlx, nly = ax / d, (ly - hgt) / d
            dist = d - self.r2
        else:
            nlx, nly = a, b
            dist = ax * a + ly * b - self.r1
        nlx *= sign
        # local -> monde : x_local sur perp, y_local sur u
        nx = nlx * (-s) + nly * c
        ny = nlx * c + nly * s
        return dist, nx, ny


# ==========================================================================
# Rampe : trajectoire paramétrique 3D
# ==========================================================================
class RampPath:
    def __init__(self, name, points, owner=None, friction=150.0, entry_min=250.0,
                 sensors=None, exit_speed_scale=0.9, max_exit_speed=2600.0):
        """points : liste de (x, y, h) — h = hauteur au-dessus du plateau (mm)."""
        self.name = name
        self.owner = owner
        self.pts = [(float(x), float(y), float(h)) for x, y, h in points]
        self.friction = friction
        self.entry_min = entry_min
        self.exit_speed_scale = exit_speed_scale
        self.max_exit_speed = max_exit_speed
        self.cum = [0.0]
        self.seg = []
        for i in range(len(self.pts) - 1):
            x1, y1, h1 = self.pts[i]
            x2, y2, h2 = self.pts[i + 1]
            L = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (h2 - h1) ** 2) or 1e-6
            z1 = (PF_H - y1) * SIN_TILT + h1
            z2 = (PF_H - y2) * SIN_TILT + h2
            self.seg.append((L, (z2 - z1) / L))
            self.cum.append(self.cum[-1] + L)
        self.length = self.cum[-1]
        self.sensors = sorted(sensors or [], key=lambda t: t[0])   # [(s, name)]
        self.balls = []

    def locate(self, s):
        s = max(0.0, min(self.length, s))
        lo, hi = 0, len(self.cum) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.cum[mid] <= s:
                lo = mid
            else:
                hi = mid
        i = min(lo, len(self.seg) - 1)
        L = self.seg[i][0]
        t = (s - self.cum[i]) / L
        x1, y1, h1 = self.pts[i]
        x2, y2, h2 = self.pts[i + 1]
        return i, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, h1 + (h2 - h1) * t

    def dir2d(self, i):
        x1, y1, _ = self.pts[i]
        x2, y2, _ = self.pts[i + 1]
        L = math.hypot(x2 - x1, y2 - y1) or 1e-6
        return (x2 - x1) / L, (y2 - y1) / L


# ==========================================================================
# Monde
# ==========================================================================
class World:
    def __init__(self):
        self.statics = []
        self.grid = {}
        self.flippers = []
        self.balls = []
        self.ramps = []
        self.events = []          # (nom, données) consommés par les règles
        self.time = 0.0
        self.impact_events = []   # (x, y, force, matériau) pour son/particules
        self.listener = None      # objet avec on_hit / on_sensor / on_ramp

    # ---------------------------------------------------------------
    def add(self, c):
        self.statics.append(c)
        return c

    def build_grid(self):
        self.grid = {}
        for c in self.statics:
            x0, y0, x1, y1 = c.bbox
            for gx in range(int(x0 // GRID_CELL), int(x1 // GRID_CELL) + 1):
                for gy in range(int(y0 // GRID_CELL), int(y1 // GRID_CELL) + 1):
                    self.grid.setdefault((gx, gy), []).append(c)

    def add_ball(self, x, y, vx=0.0, vy=0.0):
        b = Ball(x, y)
        b.vx, b.vy = vx, vy
        self.balls.append(b)
        return b

    # ---------------------------------------------------------------
    def step(self, dt):
        vmax = 0.0
        for b in self.balls:
            if b.state == "pf":
                sp = abs(b.vx) + abs(b.vy)
                if sp > vmax:
                    vmax = sp
            elif b.state == "ramp":
                sp = abs(b.sv)
                if sp > vmax:
                    vmax = sp
        wmax = 0.0
        for f in self.flippers:
            if f.pressed or f.moving():
                wmax = max(wmax, FLIPPER_MAX_W * f.power * f.length)
        move = max(vmax, wmax) * dt
        n = int(math.ceil(move / SUBSTEP_MAX_MOVE))
        n = max(MIN_SUBSTEPS, min(MAX_SUBSTEPS, n))
        h = dt / n
        for _ in range(n):
            self._substep(h)
        for b in self.balls:
            if b.state in ("pf", "ramp"):
                b.age += dt
                b.trail.append((b.x, b.y, b.h))
                b.roll += b.speed * dt / b.r

    # ---------------------------------------------------------------
    def _substep(self, h):
        self.time += h
        for f in self.flippers:
            f.update(h)
        balls = self.balls
        for b in balls:
            st = b.state
            if st == "pf":
                self._move_pf(b, h)
            elif st == "ramp":
                self._move_ramp(b, h)
        # collisions bille-bille
        nb = len(balls)
        if nb > 1:
            for i in range(nb):
                a = balls[i]
                if a.state != "pf":
                    continue
                for j in range(i + 1, nb):
                    c = balls[j]
                    if c.state != "pf":
                        continue
                    dx = c.x - a.x
                    dy = c.y - a.y
                    rr = a.r + c.r
                    d2 = dx * dx + dy * dy
                    if d2 < rr * rr and d2 > 1e-9:
                        d = math.sqrt(d2)
                        nx, ny = dx / d, dy / d
                        pen = (rr - d) * 0.5
                        a.x -= nx * pen
                        a.y -= ny * pen
                        c.x += nx * pen
                        c.y += ny * pen
                        vn = (c.vx - a.vx) * nx + (c.vy - a.vy) * ny
                        if vn < 0:
                            j_ = -(1.0 + 0.92) * vn * 0.5
                            a.vx -= j_ * nx
                            a.vy -= j_ * ny
                            c.vx += j_ * nx
                            c.vy += j_ * ny
                            if -vn > 150:
                                self.impact_events.append((a.x + nx * a.r, a.y + ny * a.r, -vn, "ball"))

    # ---------------------------------------------------------------
    def _move_pf(self, b, h):
        b.px, b.py = b.x, b.y
        b.vy += G_ROLL * h
        sp = math.hypot(b.vx, b.vy)
        if sp > 1e-6:
            dec = ROLL_DECEL * h + LINEAR_DRAG * sp * h
            if dec >= sp:
                b.vx = b.vy = 0.0
            else:
                k = (sp - dec) / sp
                if sp > MAX_SPEED:
                    k *= MAX_SPEED / sp
                b.vx *= k
                b.vy *= k
        b.x += b.vx * h
        b.y += b.vy * h

        cell = self.grid.get((int(b.x // GRID_CELL), int(b.y // GRID_CELL)))
        if cell:
            for _pass in range(2):
                hit_any = False
                for c in cell:
                    if not c.enabled:
                        continue
                    k = c.kind
                    if k == "seg":
                        if self._collide_seg(b, c):
                            hit_any = True
                    elif k == "circ":
                        if self._collide_circ(b, c):
                            hit_any = True
                    elif _pass == 0:
                        if k == "line":
                            self._check_line(b, c)
                        elif k == "csens":
                            self._check_csens(b, c)
                    if b.state != "pf":
                        return
                if not hit_any:
                    break
        for f in self.flippers:
            self._collide_flipper(b, f)
        if b.y > PF_H + 40 and b.state == "pf":
            b.state = "gone"
            self.events.append(("drain", b))

    # ---------------------------------------------------------------
    def _resolve(self, b, nx, ny, pen, rest, fric, vcx=0.0, vcy=0.0):
        b.x += nx * pen
        b.y += ny * pen
        rvx = b.vx - vcx
        rvy = b.vy - vcy
        vn = rvx * nx + rvy * ny
        if vn >= 0.0:
            return 0.0
        e = rest if vn < -60.0 else 0.0
        jn = -(1.0 + e) * vn
        tx, ty = -ny, nx
        vt = rvx * tx + rvy * ty
        f = fric * jn
        if vt > 0:
            dvt = -min(vt, f)
        else:
            dvt = min(-vt, f)
        rvx += jn * nx + dvt * tx
        rvy += jn * ny + dvt * ty
        b.vx = rvx + vcx
        b.vy = rvy + vcy
        return -vn

    def _collide_seg(self, b, c):
        ex = b.x - c.x1
        ey = b.y - c.y1
        t = (ex * c.dx + ey * c.dy) / c.len2
        if t < 0.0:
            t = 0.0
        elif t > 1.0:
            t = 1.0
        qx = c.x1 + c.dx * t
        qy = c.y1 + c.dy * t
        dx = b.x - qx
        dy = b.y - qy
        rr = b.r + c.rad
        d2 = dx * dx + dy * dy
        if d2 >= rr * rr:
            return False
        if c.one_way:
            # ne bloque que si la bille arrive par le côté de la normale
            side = (b.px - c.x1) * c.nx + (b.py - c.y1) * c.ny
            if side < 0 or (b.vx * c.nx + b.vy * c.ny) > 0:
                return False
        d = math.sqrt(d2)
        if d < 1e-9:
            nx, ny = c.nx, c.ny
        else:
            nx, ny = dx / d, dy / d
        imp = self._resolve(b, nx, ny, rr - d, c.rest, c.fric)
        if c.owner is not None and self.listener is not None:
            self.listener.on_hit(c.owner, b, c, nx, ny, imp)
        elif imp > 250:
            self.impact_events.append((qx, qy, imp, c.tag or "wall"))
        return True

    def _collide_circ(self, b, c):
        dx = b.x - c.x
        dy = b.y - c.y
        rr = b.r + c.rad
        d2 = dx * dx + dy * dy
        if d2 >= rr * rr:
            return False
        d = math.sqrt(d2)
        if d < 1e-9:
            nx, ny = 0.0, -1.0
        else:
            nx, ny = dx / d, dy / d
        imp = self._resolve(b, nx, ny, rr - d, c.rest, c.fric)
        if c.owner is not None and self.listener is not None:
            self.listener.on_hit(c.owner, b, c, nx, ny, imp)
        elif imp > 250:
            self.impact_events.append((c.x + nx * c.rad, c.y + ny * c.rad, imp, c.tag or "post"))
        return True

    def _check_line(self, b, c):
        # franchissement entre (px,py) et (x,y)
        s0 = (b.px - c.x1) * c.nx + (b.py - c.y1) * c.ny
        s1 = (b.x - c.x1) * c.nx + (b.y - c.y1) * c.ny
        if (s0 > 0) == (s1 > 0):
            return
        # intersection à l'intérieur du segment ?
        t = s0 / (s0 - s1) if s0 != s1 else 0.0
        ix = b.px + (b.x - b.px) * t
        iy = b.py + (b.y - b.py) * t
        dx = c.x2 - c.x1
        dy = c.y2 - c.y1
        u = ((ix - c.x1) * dx + (iy - c.y1) * dy) / (dx * dx + dy * dy)
        if u < -0.02 or u > 1.02:
            return
        direction = 1 if s1 > s0 else -1     # +1 : passage dans le sens de la normale
        if self.listener is not None:
            self.listener.on_sensor(c.owner, b, c, direction)

    def _check_csens(self, b, c):
        dx = b.x - c.x
        dy = b.y - c.y
        inside = dx * dx + dy * dy < c.rad * c.rad
        was = c in b.inside
        if inside and not was:
            b.inside.add(c)
            if self.listener is not None:
                self.listener.on_sensor(c.owner, b, c, 1)
        elif was and not inside:
            b.inside.discard(c)
            if self.listener is not None:
                self.listener.on_sensor(c.owner, b, c, -1)

    def _collide_flipper(self, b, f):
        dxp = b.x - f.px
        dyp = b.y - f.py
        reach = f.length + f.r1 + b.r + 2
        if dxp * dxp + dyp * dyp > reach * reach:
            return
        dist, nx, ny = f.sdf(b.x, b.y)
        pen = b.r - dist
        if pen <= 0:
            return
        # point de contact (sur la surface du flipper)
        cx = b.x - nx * (b.r - pen * 0.5)
        cy = b.y - ny * (b.r - pen * 0.5)
        w = f.w
        vcx = -w * (cy - f.py)
        vcy = w * (cx - f.px)
        rvn = (b.vx - vcx) * nx + (b.vy - vcy) * ny
        # caoutchouc : l'élasticité baisse avec la vitesse d'impact
        rest = 0.62 - 0.00009 * (-rvn if rvn < 0 else 0)
        if rest < 0.28:
            rest = 0.28
        imp = self._resolve(b, nx, ny, pen, rest, 0.14, vcx, vcy)
        if imp > 0:
            if f.moving():
                b.last_flip_time = self.time
            if self.listener is not None:
                self.listener.on_flipper_hit(f, b, imp)

    # ---------------------------------------------------------------
    def put_on_ramp(self, b, ramp, speed):
        b.state = "ramp"
        b.ramp = ramp
        b.s = 0.0
        b.sv = speed
        b.ramp_sensor_idx = 0
        b.inside.clear()
        ramp.balls.append(b)

    def _move_ramp(self, b, h):
        r = b.ramp
        i, x, y, hh = r.locate(b.s)
        L, slope = r.seg[i]
        # roulement : a = -5/7 g dz/ds ; frottement constant
        a = -5.0 / 7.0 * G * slope
        if b.sv > 0:
            a -= r.friction
        elif b.sv < 0:
            a += r.friction
        b.sv += a * h
        b.sv -= b.sv * 0.04 * h
        b.s += b.sv * h
        # capteurs le long de la rampe
        sens = r.sensors
        while b.ramp_sensor_idx < len(sens) and b.s >= sens[b.ramp_sensor_idx][0]:
            name = sens[b.ramp_sensor_idx][1]
            b.ramp_sensor_idx += 1
            if self.listener is not None:
                self.listener.on_ramp(r, b, name)
        if b.s >= r.length:
            i = len(r.seg) - 1
            dx, dy = r.dir2d(i)
            x, y, hh = r.pts[-1]
            sp = min(abs(b.sv) * r.exit_speed_scale, r.max_exit_speed)
            self._leave_ramp(b, r, x, y, dx * sp, dy * sp)
            if self.listener is not None:
                self.listener.on_ramp(r, b, "exit")
            return
        if b.s <= 0.0 and b.sv < 0:
            dx, dy = r.dir2d(0)
            x, y, hh = r.pts[0]
            sp = abs(b.sv)
            self._leave_ramp(b, r, x - dx * 3, y - dy * 3, -dx * sp, -dy * sp)
            if self.listener is not None:
                self.listener.on_ramp(r, b, "fail")
            return
        i, x, y, hh = r.locate(b.s)
        b.px, b.py = b.x, b.y
        b.x, b.y, b.h = x, y, hh
        # vitesse 2D apparente (pour le rendu/son)
        dx, dy = r.dir2d(i)
        b.vx, b.vy = dx * b.sv, dy * b.sv

    def _leave_ramp(self, b, r, x, y, vx, vy):
        if b in r.balls:
            r.balls.remove(b)
        b.state = "pf"
        b.ramp = None
        b.x, b.y = x, y
        b.px, b.py = x, y
        b.vx, b.vy = vx, vy
        b.h = 0.0

    # ---------------------------------------------------------------
    def remove_gone(self):
        self.balls = [b for b in self.balls if b.state != "gone"]

    def nudge(self, ix, iy):
        for b in self.balls:
            if b.state == "pf":
                b.vx += ix
                b.vy += iy
