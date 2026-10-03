"""Disposition des inserts lumineux du plateau (mm)."""
import math

from ..data import SHOTS, LAMP, LEG_BY_KEY

FLIP_MID = (241.0, 1035.0)
MOUTHS = {
    "orbit_l": (22, 440), "scoop": (84, 445), "ramp_l": (148, 445), "center": (241, 445),
    "ramp_r": (328, 445), "bumper": (402, 445), "orbit_r": (461, 440),
}
LABELS = {
    "orbit_l": "ORBITE", "scoop": "CENTRE", "ramp_l": "LUGIA", "center": "CAPTURE",
    "ramp_r": "HO-OH", "bumper": "VOLTORBE", "orbit_r": "ORBITE",
}
RING_C = (241.0, 692.0)
RING_R = 80.0


class Insert:
    def __init__(self, name, shape, x, y, w, h=None, angle=0.0, base=(255, 255, 255), label=None,
                 icon=None, label_size=8.0):
        self.name = name
        self.shape = shape          # arrow | circle | rect | star | tri
        self.x, self.y = x, y
        self.w = w
        self.h = h if h is not None else w
        self.angle = angle          # degrés (0 = pointe vers le haut)
        self.base = base
        self.label = label
        self.icon = icon
        self.label_size = label_size


def shot_dir(shot):
    mx, my = MOUTHS[shot]
    dx, dy = mx - FLIP_MID[0], my - FLIP_MID[1]
    L = math.hypot(dx, dy)
    return dx / L, dy / L


def along(shot, d):
    mx, my = MOUTHS[shot]
    ux, uy = shot_dir(shot)
    return mx - ux * d, my - uy * d


def build_inserts():
    ins = []
    for s in SHOTS:
        ux, uy = shot_dir(s)
        ang = math.degrees(math.atan2(ux, -uy))
        x, y = along(s, 64 if s != "center" else 60)
        ins.append(Insert("arrow_" + s, "arrow", x, y, 24, 34, ang, (235, 235, 245), LABELS[s]))
        cx, cy = along(s, 97 if s != "center" else 91)
        ins.append(Insert("shot_combo_" + s, "circle", cx, cy, 9, base=(230, 230, 255)))
    # Centre Pokémon : 3 inserts empilés
    for i, (nm, col, lab) in enumerate((("scoop_mode", (255, 255, 255), "LÉGENDAIRE"),
                                        ("scoop_eb", LAMP["orange"], "EXTRA BALL"),
                                        ("scoop_mystery", LAMP["purple"], "MYSTÈRE"))):
        x, y = along("scoop", 122 + i * 22)
        ins.append(Insert(nm, "rect", x + 18, y, 46, 13, 0, col, lab, label_size=6.2))
    # Capture + verrous
    ins.append(Insert("center_capture", "rect", 241, 540, 58, 14, 0, (120, 255, 150), "CAPTURE", label_size=7))
    for i in range(3):
        ins.append(Insert(f"lock_{i}", "circle", 221 + 20 * i, 566, 12, base=(255, 70, 70), icon="pokeball"))
    for i, x in enumerate((209, 241, 273)):
        ins.append(Insert(f"grass_{i}", "circle", x, 455, 9, base=(90, 220, 110)))
    # Anneau des légendaires
    order = ["articuno", "zapdos", "moltres", "raikou", "entei", "suicune", "lugia", "hooh",
             "groudon", "kyogre", "rayquaza"]
    for i, key in enumerate(order):
        a = math.radians(-60 + i * 30)
        x, y = RING_C[0] + math.cos(a) * RING_R, RING_C[1] + math.sin(a) * RING_R
        leg = LEG_BY_KEY[key]
        ins.append(Insert("leg_" + key, "circle", x, y, 25, base=LAMP[leg.lamp], icon="leg:" + key))
    ins.append(Insert("leg_mew", "circle", RING_C[0], RING_C[1] - RING_R, 25, base=LAMP["pink"], icon="leg:mew"))
    ins.append(Insert("leg_mewtwo", "circle", RING_C[0], RING_C[1], 42, base=LAMP["purple"], icon="leg:mewtwo"))
    # Radar / Team Rocket
    for i, (x, y) in enumerate(((47, 598), (56, 628), (65, 658))):
        ins.append(Insert(f"radar_{i}", "circle", x, y, 13, base=(80, 255, 120), icon="radar"))
    for i, (x, y) in enumerate(((435, 598), (426, 628), (417, 658))):
        ins.append(Insert(f"rocket_{i}", "circle", x, y, 13, base=(255, 60, 60), icon="R"))
    # Bonus X
    for i, n in enumerate(range(2, 7)):
        ins.append(Insert(f"bx_{n}", "circle", 191 + 25 * i, 868, 17, base=(255, 220, 60), label=f"{n}x",
                          label_size=7.5))
    ins.append(Insert("shoot_again", "circle", 241, 1040, 22, base=(255, 150, 40), label="REJOUEZ", label_size=5.2))
    ins.append(Insert("kickback", "rect", 20, 990, 20, 46, 0, (80, 140, 255), "RONFLEX", label_size=5.0))
    for i, (x, y, l) in enumerate(((20, 940, "P"), (73, 928, "O"), (409, 928, "K"), (462, 940, "É"))):
        ins.append(Insert(f"lane_{i}", "circle", x, y, 15, base=(80, 230, 255), label=l, label_size=8))
    for i, (x, ic) in enumerate(((326, "Feu"), (372, "Eau"), (417.5, "Électrik"))):
        ins.append(Insert(f"toplane_{i}", "circle", x, 88, 16, base=(255, 230, 120), icon="type:" + ic))
    ins.append(Insert("spinner", "circle", 22, 398, 10, base=(255, 230, 80)))
    return ins


INSERTS = build_inserts()
INSERT_BY_NAME = {i.name: i for i in INSERTS}
