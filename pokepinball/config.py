"""Constantes globales : écran, dimensions du plateau, physique."""
import math
import os

# --------------------------------------------------------------------------
# Écran (résolution logique, mise à l'échelle automatique par SDL)
# --------------------------------------------------------------------------
SCREEN_W = 1920
SCREEN_H = 1080
FPS = 60

# --------------------------------------------------------------------------
# Plateau (unités : millimètres). Format "widebody" Stern : 20.5" x 45".
# Repère : x vers la droite, y vers le joueur (bas de l'écran).
# --------------------------------------------------------------------------
PF_W = 520.0
PF_H = 1150.0
PF_SCALE = SCREEN_H / PF_H          # pixels par mm (~0.939)
PF_PIX_W = int(round(PF_W * PF_SCALE))
PF_PIX_H = SCREEN_H
PF_SCREEN_X = 452                    # position du plateau à l'écran
PF_SCREEN_Y = 0

# --------------------------------------------------------------------------
# Physique réaliste d'une bille de flipper
# --------------------------------------------------------------------------
TILT_DEG = 6.5                       # inclinaison standard recommandée par Stern
G = 9810.0                           # mm/s²
# Bille pleine qui roule sans glisser : a = 5/7 · g · sin(θ)  (~793 mm/s²)
G_ROLL = 5.0 / 7.0 * G * math.sin(math.radians(TILT_DEG))
SIN_TILT = math.sin(math.radians(TILT_DEG))
BALL_R = 13.5                        # bille acier 1-1/16" (27 mm), 80 g
ROLL_DECEL = 22.0                    # résistance au roulement (mm/s²)
LINEAR_DRAG = 0.012                  # traînée (1/s)
MAX_SPEED = 7500.0                   # sécurité numérique
SUBSTEP_MAX_MOVE = 3.0               # déplacement max (mm) par sous-pas
MIN_SUBSTEPS = 4
MAX_SUBSTEPS = 48

# Flippers (3" Stern) — course ~ 30-35 ms
FLIPPER_LEN = 74.0
FLIPPER_R1 = 12.0
FLIPPER_R2 = 6.6
FLIPPER_ACCEL = 1500.0               # rad/s²
FLIPPER_MAX_W = 40.0                 # rad/s
FLIPPER_RETURN_ACCEL = 700.0
FLIPPER_RETURN_MAX_W = 24.0

# --------------------------------------------------------------------------
# Chemins
# --------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT_DIR, ".cache")
SAVE_FILE = os.path.join(ROOT_DIR, "highscores.json")


def pf_to_screen(x, y):
    """Convertit des mm du plateau en pixels écran."""
    return (PF_SCREEN_X + x * PF_SCALE, PF_SCREEN_Y + y * PF_SCALE)


def mm(v):
    """Longueur en mm → pixels."""
    return v * PF_SCALE
