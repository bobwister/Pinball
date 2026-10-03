"""Cartographie des tirs : bille descendant d'une inlane, flip à instant variable.

Affiche, pour chaque flipper, quel tir est atteint selon le retard du flip
(en ms après l'arrivée de la bille sur le flipper) et la largeur de chaque fenêtre.
    python tools/shot_map.py [vitesse_inlane_mm_s]
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pokepinball.table import Table  # noqa: E402

DT = 1 / 500
MAJOR = {"ramp_made": "RAMPE", "orbit_left": "ORB-G", "orbit_right": "ORB-D", "scoop": "SCOOP",
         "pokeball": "POKÉBALL", "drop": "HERBES", "bumper_lane": "BUMPERS", "standup": "CIBLE",
         "spinner_enter": "SPINNER"}


def setup(side, vin):
    t = Table()
    x = 73 if side == "L" else 409
    b = t.world.add_ball(x, 860)
    b.vy = vin
    return t, b


def arrival(side, vin):
    t, b = setup(side, vin)
    f = t.flippers[side]
    tt = 0.0
    while tt < 3:
        tt += DT
        t.step(DT)
        dx, dy = b.x - f.px, b.y - f.py
        s = dx * math.cos(f.angle) + dy * math.sin(f.angle)
        if s >= 0 and abs(-dx * math.sin(f.angle) + dy * math.cos(f.angle)) < 40:
            return tt
    return None


def run(side, flip_t, vin):
    random.seed(3)
    t, b = setup(side, vin)
    f = t.flippers[side]
    tt = 0.0
    while tt < 3.0:
        tt += DT
        f.pressed = flip_t <= tt < flip_t + 0.3
        t.step(DT)
        for ev, kw in t.take_events():
            if ev in MAJOR and tt >= flip_t:
                e = kw.get("element")
                n = MAJOR[ev]
                if ev == "standup":
                    n = e.name.split("_")[0].upper()
                if ev == "ramp_made":
                    n += " " + ("G" if e.name.endswith("l") else "D")
                return n
        if b.state == "gone":
            return "perdue"
    return "-"


def main():
    vin = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    for side in ("L", "R"):
        t0 = arrival(side, vin)
        seq = [(k * 2, run(side, t0 + k * 0.002, vin)) for k in range(-5, 80)]
        runs = []
        for ms, r in seq:
            if runs and runs[-1][0] == r:
                runs[-1][2] = ms
            else:
                runs.append([r, ms, ms])
        print(f"--- flipper {'gauche' if side == 'L' else 'droit'} (bille à {vin:.0f} mm/s)")
        print("  ".join(f"{r}@{a}ms[{b - a + 2}ms]" for r, a, b in runs))


if __name__ == "__main__":
    main()
