"""Données du thème : types, légendaires, Pokémon sauvages, chapitres."""

TYPE_COLORS = {
    "Normal": (168, 168, 120), "Feu": (240, 128, 48), "Eau": (104, 144, 240),
    "Plante": (120, 200, 80), "Électrik": (248, 208, 48), "Glace": (152, 216, 216),
    "Combat": (192, 48, 40), "Poison": (160, 64, 160), "Sol": (224, 192, 104),
    "Vol": (168, 144, 240), "Psy": (248, 88, 136), "Insecte": (168, 184, 32),
    "Roche": (184, 160, 56), "Spectre": (112, 88, 152), "Dragon": (112, 56, 248),
    "Ténèbres": (112, 88, 72), "Acier": (184, 184, 208), "Fée": (238, 153, 172),
}

# Couleurs "insert" (saturées pour les lampes RGB du plateau)
LAMP = {
    "white": (255, 255, 255), "red": (255, 40, 40), "orange": (255, 140, 20),
    "yellow": (255, 230, 40), "green": (40, 255, 90), "cyan": (40, 230, 255),
    "blue": (50, 110, 255), "purple": (190, 60, 255), "pink": (255, 90, 200),
    "gold": (255, 200, 60), "ice": (160, 240, 255), "brown": (200, 120, 60),
}

SHOTS = ["orbit_l", "scoop", "ramp_l", "center", "ramp_r", "bumper", "orbit_r"]
SHOT_LABELS = {
    "orbit_l": "ORBITE", "scoop": "CENTRE POKÉMON", "ramp_l": "RAMPE LUGIA",
    "center": "POKÉBALL", "ramp_r": "RAMPE HO-OH", "bumper": "VOLTORBES", "orbit_r": "ORBITE",
}


class Legendary:
    def __init__(self, key, name, ptype, color, chapter, attack, mode_title, rules_text,
                 capture_value, num, lamp, hp=100, sub=None):
        self.key = key
        self.name = name
        self.type = ptype
        self.sub = sub
        self.color = color
        self.chapter = chapter
        self.attack = attack
        self.mode_title = mode_title
        self.rules_text = rules_text
        self.capture_value = capture_value
        self.num = num
        self.lamp = lamp
        self.hp = hp


LEGENDARIES = [
    Legendary("articuno", "ARTIKODIN", "Glace", (120, 210, 255), 1, "LASER GLACE",
              "Blizzard aux Îles Écume", ["Tirez les flèches CYAN", "Chaque tir gèle sa cible",
                                          "Combos = dégâts x2"], 5_000_000, 144, "ice", sub="Vol"),
    Legendary("zapdos", "ÉLECTHOR", "Électrik", (255, 220, 40), 1, "FATAL-FOUDRE",
              "Orage à la Centrale", ["Chargez avec BUMPERS et SPINNER", "Déchargez sur les flèches JAUNES",
                                      "Plus de charge = plus de dégâts"], 5_000_000, 145, "yellow", sub="Vol"),
    Legendary("moltres", "SULFURA", "Feu", (255, 120, 30), 1, "DÉFLAGRATION",
              "Brasier de la Route Victoire", ["Un tir enflammé à la fois", "Touchez-le avant qu'il s'éteigne",
                                               "Vite = plus de dégâts"], 5_000_000, 146, "orange", sub="Vol"),
    Legendary("raikou", "RAIKOU", "Électrik", (250, 200, 60), 2, "VITESSE EXTRÊME",
              "Course éclair", ["Enchaînez les COMBOS", "Chaque combo multiplie les dégâts",
                                "Orbites et rampes allumées"], 8_000_000, 243, "yellow"),
    Legendary("entei", "ENTEI", "Feu", (230, 70, 40), 2, "ÉRUPTION",
              "Volcan de la Tour Cendrée", ["Abattez les HAUTES HERBES", "Puis frappez la POKÉBALL",
                                            "Rampes : dégâts légers"], 8_000_000, 244, "red"),
    Legendary("suicune", "SUICUNE", "Eau", (80, 170, 255), 2, "AURORE",
              "Le vent du Nord", ["Une cible BLEUE se déplace", "Visez-la avec précision",
                                  "Chaque tir la ralentit"], 8_000_000, 245, "blue"),
    Legendary("lugia", "LUGIA", "Psy", (190, 210, 255), 3, "AÉROBLAST",
              "Tempête des Îles Tourbillon", ["RAMPES seulement", "Alternez gauche / droite",
                                              "Combo de rampes = x2"], 12_000_000, 249, "ice", sub="Vol"),
    Legendary("hooh", "HO-OH", "Feu", (255, 170, 40), 3, "FEU SACRÉ",
              "Arc-en-ciel de la Tour Carillon", ["MULTIBALL 2 billes", "Toutes les couleurs de l'arc-en-ciel",
                                                  "Puis la POKÉBALL"], 12_000_000, 250, "gold", sub="Vol"),
    Legendary("groudon", "GROUDON", "Sol", (220, 70, 50), 4, "SÉISME",
              "Le Magma Ancestral", ["Frappez le CENTRE", "Herbes et Pokéball",
                                     "Attention aux secousses !"], 15_000_000, 383, "red"),
    Legendary("kyogre", "KYOGRE", "Eau", (60, 110, 255), 4, "ONDE ORIGINELLE",
              "Le Raz-de-marée", ["ORBITES et SPINNER", "Faites monter la marée",
                                  "Orbites = gros dégâts"], 15_000_000, 382, "blue"),
    Legendary("rayquaza", "RAYQUAZA", "Dragon", (60, 220, 120), 4, "DRACO-ASCENSION",
              "Le Pilier Céleste", ["MULTIBALL 2 billes", "Tirez de GAUCHE à DROITE",
                                    "Ordre parfait = dégâts max"], 15_000_000, 384, "green", sub="Vol"),
]
# difficulté progressive : plus de PV dans les chapitres avancés
for _l in LEGENDARIES:
    _l.hp = {1: 135, 2: 150, 3: 170, 4: 185}[_l.chapter]
LEG_BY_KEY = {l.key: l for l in LEGENDARIES}

MEW = Legendary("mew", "MEW", "Psy", (255, 150, 210), 5, "MÉTRONOME", "Le mirage de Mew",
                ["Mew se téléporte !", "Touchez la cible ROSE", "6 fois pour l'attraper"],
                25_000_000, 151, "pink")
MEWTWO = Legendary("mewtwo", "MEWTWO", "Psy", (180, 90, 255), 6, "FRAPPE PSY", "La Grotte Azurée",
                   ["Brisez la BARRIÈRE", "Multiball PSYKO", "Lancez la MASTER BALL"],
                   100_000_000, 150, "purple")

CHAPTERS = {
    1: {"title": "KANTO", "sub": "Les Oiseaux Légendaires", "keys": ["articuno", "zapdos", "moltres"],
        "wizard": "TRIO DES OISEAUX", "wizard_place": "Îles Écume", "balls": 3,
        "colors": ["ice", "yellow", "orange"]},
    2: {"title": "JOHTO", "sub": "Les Bêtes Légendaires", "keys": ["raikou", "entei", "suicune"],
        "wizard": "TRIO DES BÊTES", "wizard_place": "Tour Cendrée", "balls": 3,
        "colors": ["yellow", "red", "blue"]},
    3: {"title": "JOHTO", "sub": "Les Gardiens des Tours", "keys": ["lugia", "hooh"],
        "wizard": "GARDIENS CÉLESTES", "wizard_place": "Tour Carillon", "balls": 3,
        "colors": ["ice", "gold"]},
    4: {"title": "HOENN", "sub": "Les Super-Anciens", "keys": ["groudon", "kyogre", "rayquaza"],
        "wizard": "CHOC DES TITANS", "wizard_place": "Pilier Céleste", "balls": 4,
        "colors": ["red", "blue", "green"]},
}

# (n°, nom, type)
WILD = [
    (1, "BULBIZARRE", "Plante"), (4, "SALAMÈCHE", "Feu"), (7, "CARAPUCE", "Eau"),
    (10, "CHENIPAN", "Insecte"), (16, "ROUCOOL", "Vol"), (19, "RATTATA", "Normal"),
    (25, "PIKACHU", "Électrik"), (27, "SABELETTE", "Sol"), (35, "MÉLOFÉE", "Fée"),
    (37, "GOUPIX", "Feu"), (39, "RONDOUDOU", "Fée"), (41, "NOSFERAPTI", "Poison"),
    (43, "MYSTHERBE", "Plante"), (50, "TAUPIQUEUR", "Sol"), (52, "MIAOUSS", "Normal"),
    (54, "PSYKOKWAK", "Eau"), (58, "CANINOS", "Feu"), (60, "PTITARD", "Eau"),
    (63, "ABRA", "Psy"), (66, "MACHOC", "Combat"), (72, "TENTACOOL", "Eau"),
    (74, "RACAILLOU", "Roche"), (77, "PONYTA", "Feu"), (79, "RAMOLOSS", "Eau"),
    (81, "MAGNÉTI", "Électrik"), (92, "FANTOMINUS", "Spectre"), (95, "ONIX", "Roche"),
    (100, "VOLTORBE", "Électrik"), (104, "OSSELAIT", "Sol"), (108, "EXCELANGUE", "Normal"),
    (113, "LEVEINARD", "Normal"), (115, "KANGOUREX", "Normal"), (120, "STARI", "Eau"),
    (122, "M. MIME", "Psy"), (123, "INSÉCATEUR", "Insecte"), (125, "ÉLEKTEK", "Électrik"),
    (126, "MAGMAR", "Feu"), (127, "SCARABRUTE", "Insecte"), (129, "MAGICARPE", "Eau"),
    (131, "LOKHLASS", "Eau"), (133, "ÉVOLI", "Normal"), (137, "PORYGON", "Normal"),
    (138, "AMONITA", "Roche"), (142, "PTÉRA", "Roche"), (143, "RONFLEX", "Normal"),
    (147, "MINIDRACO", "Dragon"), (149, "DRACOLOSSE", "Dragon"), (152, "GERMIGNON", "Plante"),
    (155, "HÉRICENDRE", "Feu"), (158, "KAIMINUS", "Eau"), (172, "PICHU", "Électrik"),
    (175, "TOGEPI", "Fée"), (179, "WATTOUAT", "Électrik"), (196, "MENTALI", "Psy"),
    (197, "NOCTALI", "Ténèbres"), (212, "CIZAYOX", "Acier"), (248, "TYRANOCIF", "Roche"),
    (252, "ARCKO", "Plante"), (255, "POUSSIFEU", "Feu"), (258, "GOBOU", "Eau"),
    (282, "GARDEVOIR", "Psy"), (302, "TÉNÉFIX", "Spectre"), (359, "ABSOL", "Ténèbres"),
    (373, "DRATTAK", "Dragon"), (448, "LUCARIO", "Combat"),
]

MYSTERY_AWARDS = [
    ("BONBON RARE", "Bonus x +1"),
    ("POTION", "Ball Save 15 s"),
    ("SUPER BALL", "Capture facilitée"),
    ("PÉPITE", "Points"),
    ("POKÉ RADAR", "Radar complété"),
    ("PÉPITE", "Points"),
    ("RONFLEX", "Kickback allumé"),
    ("MULTI EXP.", "Score x2 30 s"),
    ("HYPER BALL", "Capture Pokémon allumée"),
]
