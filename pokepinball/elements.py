"""Éléments de jeu du plateau (bumpers, slingshots, cibles, rampes, scoop...).

Chaque élément possède des collisionneurs/capteurs physiques et émet des
événements de jeu vers les règles via `table.emit(nom, **données)`.
"""
import math
import random

from .physics import Segment, Circle, LineSensor, CircleSensor


class Element:
    kind = "element"

    def __init__(self, table, name):
        self.table = table
        self.name = name
        self.flash = 0.0          # animation de flash (s)
        self.cooldown = 0.0

    def on_hit(self, ball, coll, nx, ny, imp):
        pass

    def on_sensor(self, ball, coll, direction):
        pass

    def update(self, dt):
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        if self.cooldown > 0:
            self.cooldown = max(0.0, self.cooldown - dt)

    def emit(self, ev, **kw):
        self.table.emit(ev, element=self, **kw)


# --------------------------------------------------------------------------
class PopBumper(Element):
    kind = "bumper"

    def __init__(self, table, name, x, y, r=24.0, kick=1350.0):
        super().__init__(table, name)
        self.x, self.y, self.r = x, y, r
        self.kick = kick
        self.coll = table.world.add(Circle(x, y, r, owner=self, tag="bumper", rest=0.4, fric=0.05))
        self.ring = 0.0           # descente de l'anneau (animation)

    def on_hit(self, ball, coll, nx, ny, imp):
        if self.cooldown > 0:
            return
        vn = ball.vx * nx + ball.vy * ny
        tx, ty = -ny, nx
        vt = ball.vx * tx + ball.vy * ty
        out = max(vn, 0.0) * 0.3 + self.kick * random.uniform(0.92, 1.08)
        ball.vx = tx * vt * 0.8 + nx * out
        ball.vy = ty * vt * 0.8 + ny * out
        self.cooldown = 0.06
        self.flash = 0.22
        self.ring = 1.0
        self.emit("bumper", ball=ball, x=self.x + nx * self.r, y=self.y + ny * self.r)

    def update(self, dt):
        super().update(dt)
        self.ring = max(0.0, self.ring - dt * 9)


# --------------------------------------------------------------------------
class Slingshot(Element):
    kind = "sling"

    def __init__(self, table, name, a, b, c, kick=1250.0):
        """a=haut, b=bas-extérieur, c=bas-intérieur ; a→c est la face active."""
        super().__init__(table, name)
        self.a, self.b, self.c = a, b, c
        self.kick = kick
        w = table.world
        self.face = w.add(Segment(a[0], a[1], c[0], c[1], rad=4, owner=self, tag="sling", rest=0.7, fric=0.15))
        w.add(Segment(a[0], a[1], b[0], b[1], rad=4, tag="rubber", rest=0.6, fric=0.15))
        w.add(Segment(b[0], b[1], c[0], c[1], rad=4, tag="rubber", rest=0.6, fric=0.15))
        self.bulge = 0.0

    def on_hit(self, ball, coll, nx, ny, imp):
        if imp < 140 or self.cooldown > 0:
            if imp > 250:
                self.table.world.impact_events.append((ball.x - nx * ball.r, ball.y - ny * ball.r, imp, "rubber"))
            return
        # n doit pointer hors du triangle (vers le plateau)
        ball.vx += nx * self.kick
        ball.vy += ny * self.kick
        self.cooldown = 0.12
        self.flash = 0.18
        self.bulge = 1.0
        self.emit("sling", ball=ball, x=ball.x - nx * ball.r, y=ball.y - ny * ball.r)

    def update(self, dt):
        super().update(dt)
        self.bulge = max(0.0, self.bulge - dt * 8)


# --------------------------------------------------------------------------
class DropTarget(Element):
    kind = "drop"

    def __init__(self, table, name, x1, y1, x2, y2, index=0, bank=None):
        super().__init__(table, name)
        self.p1, self.p2 = (x1, y1), (x2, y2)
        self.index = index
        self.bank = bank
        self.coll = table.world.add(Segment(x1, y1, x2, y2, rad=4, owner=self, tag="drop", rest=0.25, fric=0.1))
        self.down = False
        self.anim = 0.0           # 0 = levée, 1 = baissée
        self.pending_reset = False

    def on_hit(self, ball, coll, nx, ny, imp):
        if self.down or imp < 70:
            return
        self.set_down(True)
        self.flash = 0.3
        self.emit("drop", ball=ball, index=self.index, bank=self.bank)

    def set_down(self, down):
        self.down = down
        self.coll.enabled = not down
        if not down:
            self.pending_reset = False

    def reset(self):
        # ne remonte pas une cible si une bille est posée dessus
        for b in self.table.world.balls:
            if b.state != "pf":
                continue
            cx = (self.p1[0] + self.p2[0]) / 2
            cy = (self.p1[1] + self.p2[1]) / 2
            if abs(b.x - cx) < 40 and abs(b.y - cy) < 22:
                self.pending_reset = True
                return
        self.set_down(False)

    def update(self, dt):
        super().update(dt)
        target = 1.0 if self.down else 0.0
        self.anim += (target - self.anim) * min(1.0, dt * 25)
        if self.pending_reset:
            self.reset()


class DropBank:
    def __init__(self, name, targets):
        self.name = name
        self.targets = targets

    def all_down(self):
        return all(t.down for t in self.targets)

    def count_down(self):
        return sum(1 for t in self.targets if t.down)

    def reset(self):
        for t in self.targets:
            t.reset()

    def drop_all(self):
        for t in self.targets:
            t.set_down(True)


# --------------------------------------------------------------------------
class Standup(Element):
    kind = "standup"

    def __init__(self, table, name, x1, y1, x2, y2, index=0, bank=None):
        super().__init__(table, name)
        self.p1, self.p2 = (x1, y1), (x2, y2)
        self.index = index
        self.bank = bank
        self.coll = table.world.add(Segment(x1, y1, x2, y2, rad=3, owner=self, tag="standup", rest=0.35, fric=0.1))
        self.wobble = 0.0

    def on_hit(self, ball, coll, nx, ny, imp):
        if imp < 90 or self.cooldown > 0:
            return
        self.cooldown = 0.12
        self.flash = 0.25
        self.wobble = 1.0
        self.emit("standup", ball=ball, index=self.index, bank=self.bank)

    def update(self, dt):
        super().update(dt)
        self.wobble = max(0.0, self.wobble - dt * 6)


# --------------------------------------------------------------------------
class Rollover(Element):
    kind = "rollover"

    def __init__(self, table, name, x, y, r=11.0, group=None, index=0):
        super().__init__(table, name)
        self.x, self.y = x, y
        self.group = group
        self.index = index
        table.world.add(CircleSensor(x, y, r, owner=self))

    def on_sensor(self, ball, coll, direction):
        if direction > 0:
            self.flash = 0.3
            self.emit("rollover", ball=ball, group=self.group, index=self.index)


# --------------------------------------------------------------------------
class LineSwitch(Element):
    """Interrupteur de franchissement (entrée/sortie d'orbite...)."""
    kind = "switch"

    def __init__(self, table, name, p1, p2, event, want_dir=1):
        super().__init__(table, name)
        self.p1, self.p2 = p1, p2
        self.event = event
        self.want_dir = want_dir
        table.world.add(LineSensor(p1[0], p1[1], p2[0], p2[1], owner=self))

    def on_sensor(self, ball, coll, direction):
        if self.want_dir == 0 or direction == self.want_dir:
            if self.cooldown <= 0:
                self.cooldown = 0.15
                self.flash = 0.3
                self.emit(self.event, ball=ball, speed=ball.speed)


# --------------------------------------------------------------------------
class Spinner(Element):
    kind = "spinner"

    def __init__(self, table, name, p1, p2):
        super().__init__(table, name)
        self.p1, self.p2 = p1, p2
        table.world.add(LineSensor(p1[0], p1[1], p2[0], p2[1], owner=self))
        self.angle = 0.0
        self.w = 0.0              # tours/s
        self.count_acc = 0.0

    def on_sensor(self, ball, coll, direction):
        sp = ball.speed
        self.w = max(self.w, sp / 95.0)      # ~ tours par seconde
        self.emit("spinner_enter", ball=ball, speed=sp)

    def update(self, dt):
        super().update(dt)
        if self.w > 0.05:
            turns = self.w * dt
            self.angle = (self.angle + turns * 360.0) % 360.0
            self.count_acc += turns
            while self.count_acc >= 1.0:
                self.count_acc -= 1.0
                self.flash = 0.12
                self.emit("spinner")
            # frottement de l'axe
            self.w = max(0.0, self.w - (3.5 + self.w * 0.9) * dt)
        else:
            self.w = 0.0
            # retombe à la verticale
            self.angle *= max(0.0, 1.0 - dt * 6)


# --------------------------------------------------------------------------
class OneWayGate(Element):
    kind = "gate"

    def __init__(self, table, name, p1, p2):
        """Bloque les billes venant du côté de la normale gauche de p1→p2."""
        super().__init__(table, name)
        self.p1, self.p2 = p1, p2
        seg = table.world.add(Segment(p1[0], p1[1], p2[0], p2[1], rad=1.5, tag="metal", rest=0.3, fric=0.05))
        seg.one_way = True
        table.world.add(LineSensor(p1[0], p1[1], p2[0], p2[1], owner=self))
        self.swing = 0.0

    def on_sensor(self, ball, coll, direction):
        self.swing = 1.0
        self.emit("gate", ball=ball, direction=direction)

    def update(self, dt):
        super().update(dt)
        self.swing = max(0.0, self.swing - dt * 3)


# --------------------------------------------------------------------------
class Scoop(Element):
    """Trou de capture : retient la bille puis l'éjecte (VUK/kickout)."""
    kind = "scoop"

    def __init__(self, table, name, x, y, eject_dir, eject_speed=1900.0, r=11.0):
        super().__init__(table, name)
        self.x, self.y = x, y
        self.eject_dir = eject_dir
        self.eject_speed = eject_speed
        self.sensor = table.world.add(CircleSensor(x, y, r, owner=self))
        self.held = []            # billes retenues
        self.hold_time = 0.0
        self.auto_eject = 0.8     # par défaut, éjection après 0.8 s
        self.kick_anim = 0.0
        self.locked = False       # les règles peuvent bloquer l'éjection

    def on_sensor(self, ball, coll, direction):
        if direction <= 0 or ball.state != "pf":
            return
        ball.state = "held"
        ball.vx = ball.vy = 0.0
        ball.x, ball.y = self.x, self.y
        self.held.append(ball)
        self.hold_time = self.auto_eject
        self.flash = 0.5
        self.emit("scoop", ball=ball, speed=0)

    def hold(self, seconds):
        self.hold_time = max(self.hold_time, seconds)

    def release_now(self):
        self.hold_time = 0.0

    def update(self, dt):
        super().update(dt)
        self.kick_anim = max(0.0, self.kick_anim - dt * 5)
        if self.held and not self.locked:
            self.hold_time -= dt
            if self.hold_time <= 0:
                b = self.held.pop(0)
                ang = math.radians(self.eject_dir + random.uniform(-0.8, 0.8))
                sp = self.eject_speed * random.uniform(0.96, 1.04)
                b.state = "pf"
                b.x, b.y = self.x + math.cos(ang) * 4, self.y + math.sin(ang) * 4
                b.px, b.py = b.x, b.y
                b.vx = math.cos(ang) * sp
                b.vy = math.sin(ang) * sp
                b.inside = {self.sensor}
                self.kick_anim = 1.0
                self.hold_time = 0.6
                self.emit("scoop_eject", ball=b)


# --------------------------------------------------------------------------
class Kickback(Element):
    kind = "kickback"

    def __init__(self, table, name, x, y, speed=3900.0):
        super().__init__(table, name)
        self.x, self.y = x, y
        self.speed = speed
        self.lit = False
        table.world.add(CircleSensor(x, y, 14, owner=self))
        self.anim = 0.0

    def on_sensor(self, ball, coll, direction):
        if direction <= 0:
            return
        if self.lit and ball.vy > 0:
            ball.vx = random.uniform(-40, 40)
            ball.vy = -self.speed * random.uniform(0.97, 1.03)
            self.anim = 1.0
            self.flash = 0.6
            self.emit("kickback", ball=ball)

    def update(self, dt):
        super().update(dt)
        self.anim = max(0.0, self.anim - dt * 4)


# --------------------------------------------------------------------------
class PokeballToy(Element):
    """Grande Pokéball centrale : jouet à frapper (bash toy) avec animations."""
    kind = "pokeball"

    def __init__(self, table, name, x, y, r=40.0):
        super().__init__(table, name)
        self.x, self.y, self.r = x, y, r
        self.coll = table.world.add(Circle(x, y, r, owner=self, tag="pokeball", rest=0.42, fric=0.08))
        self.shake = 0.0           # amplitude de tremblement
        self.shake_t = 0.0
        self.open = 0.0            # ouverture du capot (0..1)
        self.open_target = 0.0
        self.glow = 0.0
        self.button_color = (255, 255, 255)
        self.spin = 0.0

    def on_hit(self, ball, coll, nx, ny, imp):
        if imp < 120 or self.cooldown > 0:
            return
        self.cooldown = 0.25
        self.flash = 0.35
        self.shake = min(1.0, 0.4 + imp / 4000.0)
        self.emit("pokeball", ball=ball, impact=imp)

    def update(self, dt):
        super().update(dt)
        self.shake_t += dt
        self.shake = max(0.0, self.shake - dt * 1.6)
        self.open += (self.open_target - self.open) * min(1.0, dt * 6)
        self.glow = max(0.0, self.glow - dt)

    @property
    def wobble_angle(self):
        return math.sin(self.shake_t * 28.0) * 14.0 * self.shake


# --------------------------------------------------------------------------
class Ramp(Element):
    kind = "ramp"

    def __init__(self, table, name, entry_p1, entry_p2, path, made_s=None, color=(120, 200, 255)):
        super().__init__(table, name)
        self.path = path
        path.owner = self
        self.color = color
        self.entry = (entry_p1, entry_p2)
        table.world.add(LineSensor(entry_p1[0], entry_p1[1], entry_p2[0], entry_p2[1], owner=self))
        table.world.ramps.append(path)
        self.pulse = 0.0

    def on_sensor(self, ball, coll, direction):
        # la normale gauche de p1→p2 pointe vers le haut de la rampe
        if ball.state != "pf":
            return
        vn = ball.vx * coll.nx + ball.vy * coll.ny
        if direction > 0 and vn > self.path.entry_min:
            self.table.world.put_on_ramp(ball, self.path, vn * 0.97)
            self.emit("ramp_enter", ball=ball, speed=vn)

    def on_ramp_event(self, ball, ev):
        if ev == "made":
            self.flash = 0.6
            self.pulse = 1.0
            self.emit("ramp_made", ball=ball)
        elif ev == "fail":
            self.emit("ramp_fail", ball=ball)
        elif ev == "exit":
            self.emit("ramp_exit", ball=ball)
        else:
            self.emit("ramp_" + ev, ball=ball)

    def update(self, dt):
        super().update(dt)
        self.pulse = max(0.0, self.pulse - dt * 1.5)


# --------------------------------------------------------------------------
class Plunger(Element):
    kind = "plunger"

    def __init__(self, table, name, x1, x2, y, max_pull=42.0):
        super().__init__(table, name)
        self.x1, self.x2, self.y0 = x1, x2, y
        self.max_pull = max_pull
        self.pull = 0.0
        self.pulling = False
        self.release_anim = 0.0
        self.coll = table.world.add(Segment(x1, y, x2, y, rad=2, tag="plunger", rest=0.2, fric=0.2))
        # boîte englobante élargie : le segment se déplace avec la tirette
        bx0, by0, bx1, by1 = self.coll.bbox
        self.coll.bbox = (bx0, by0, bx1, by1 + max_pull)
        self.auto_fire_pending = False

    @property
    def y(self):
        return self.y0 + self.pull

    def set_pulling(self, on):
        if on and not self.pulling:
            self.pulling = True
        elif not on and self.pulling:
            self.pulling = False
            self.fire(self.pull / self.max_pull)

    def ball_on_plunger(self):
        for b in self.table.world.balls:
            if b.state == "pf" and self.x1 - 4 <= b.x <= self.x2 + 4 and                     self.y0 - b.r - 18 <= b.y <= self.y0 + self.max_pull and abs(b.vy) < 400:
                return b
        return None

    def fire(self, strength, auto=False):
        b = self.ball_on_plunger()
        self.release_anim = 1.0
        if b is not None and strength > 0.03:
            # la tige revient en position et pousse la bille : course 0-42 mm → 1250-2900 mm/s
            # (≈1400 : retombe dans les couloirs du haut ; plein tirage : tour complet par l'orbite)
            v = 1250.0 + 1650.0 * strength
            if not auto:
                v *= random.uniform(0.99, 1.01)
            b.y = min(b.y, self.y0 - b.r - 2.5)
            b.py = b.y
            b.vy = -v
            b.vx = 0.0
            self.emit("plunger_fire", ball=b, strength=strength, auto=auto)
        self.pull = 0.0
        self.coll.y1 = self.coll.y2 = self.y0
        self._refresh()

    def _refresh(self):
        c = self.coll
        c.y1 = c.y2 = self.y

    def update(self, dt):
        super().update(dt)
        if self.pulling:
            self.pull = min(self.max_pull, self.pull + dt * self.max_pull / 1.1)
        self._refresh()
        self.release_anim = max(0.0, self.release_anim - dt * 6)
