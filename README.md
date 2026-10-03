# POKÉMON PINBALL — Légendes

Flipper vidéo en Python/pygame inspiré des machines **Stern** modernes (John Wick, Pirates des Caraïbes,
Godzilla…) sur le thème Pokémon : capturez les **11 Pokémon légendaires**, puis **Mew**, avant d'affronter
**Mewtwo** dans le combat final.

Tout est généré par le code : plateau, illustrations des légendaires (courbes de Bézier), animations LCD,
bruitages, musiques originales (synthèse numpy) et voix d'annonceur (synthèse vocale Windows). Aucun fichier
graphique ou sonore externe.

## Lancer le jeu

```bash
pip install -r requirements.txt
python main.py                 # fenêtre (1920x1080 mise à l'échelle)
python main.py --fullscreen    # plein écran
python main.py --novoice       # sans annonceur   ·   --nosound : sans audio   ·   --debug : touches de test
```

Python 3.10+ requis. Au premier lancement, la synthèse des sons, des musiques et des voix prend quelques
secondes (écran de chargement), puis tout est mis en cache dans `.cache/`.

## Commandes

| Action | Touches |
|---|---|
| Flipper gauche / droit | `Maj gauche` / `Maj droite` (ou `←` / `→`) |
| Tirette (maintenir puis relâcher) | `Entrée` ou `↓` — la force dépend de la durée de tirage |
| Démarrer / ajouter un joueur (jusqu'à 4) | `Entrée` (écran titre) · `1` |
| Secouer la table (attention au TILT) | `Espace` (vers le haut) · `Ctrl gauche` / `Ctrl droit` |
| Choix du légendaire au Centre Pokémon | flippers pour choisir, `Entrée` pour valider |
| Pause · Musique on/off · Plein écran · FPS | `P` · `M` · `F11` · `F3` |
| Abandonner la partie / quitter | `Échap` (deux fois en partie) |

Avant de lancer la bille, les flippers déplacent le couloir lumineux du **skill shot**. Pendant la partie,
ils font tourner les lettres des couloirs (*lane change*).

## Le plateau

```
            ┌──────── arc supérieur ────────┐
  orbite G  │  rampe LUGIA   POKÉBALL    3 couloirs + 3 bumpers Voltorbe
 (spinner)  │  scoop CENTRE  (derrière     rampe HO-OH   orbite D
            │  POKÉMON       les herbes)                  couloir de lancement
   cibles POKÉ RADAR     anneau des légendaires      cibles TEAM ROCKET
            slingshots · inlanes / outlanes (kickback RONFLEX) · 2 flippers
```

7 tirs majeurs, chacun avec sa flèche RGB qui change de couleur selon la mission en cours :
**orbite gauche** (spinner), **Centre Pokémon** (scoop), **rampe Lugia**, **centre** (3 cibles tombantes
« Hautes Herbes » devant la **Pokéball géante**), **rampe Ho-Oh**, **couloir des bumpers**, **orbite droite**.
Les rampes renvoient la bille dans l'inlane du même côté : rampe gauche → flipper gauche → rampe droite…
de quoi enchaîner les combos. Le scoop éjecte la bille dans l'inlane gauche.

## Règles (feuille de règles)

**Progression principale — 4 chapitres**

1. **POKÉ RADAR** : les 3 cibles vertes à gauche allument un *Légendaire* (1 coup par cible au début,
   puis 2, puis 3 au fil de l'aventure). Le premier légendaire est allumé d'office.
2. **CENTRE POKÉMON** (scoop) : choisissez votre adversaire parmi les légendaires du chapitre (flippers).
3. **Combat** : chaque légendaire a ses propres règles ; chaque tir réussi lui retire des PV (barre de vie
   style Pokémon sur le LCD) et ajoute du temps au chrono.
4. **Capture** : quand il est K.O., la Pokéball s'ouvre — frappez-la **3 fois** (3 secousses) avant la fin
   du compte à rebours… sinon il se libère avec 30 % de ses PV. *GOTCHA !*
5. Chapitre terminé + **Pokédex** suffisant (2 / 5 / 8 / 12 Pokémon sauvages) → **multiball de chapitre**
   au Centre Pokémon, puis chapitre suivant.

| Chapitre | Légendaires | Mécanique de combat | Multiball |
|---|---|---|---|
| 1 · Kanto | **Artikodin** | toutes les flèches cyan ; chaque tir gèle sa cible, combos x2 | Trio des Oiseaux |
| | **Électhor** | chargez avec bumpers/spinner/couloirs, déchargez sur rampes/orbites | |
| | **Sulfura** | un tir enflammé à la fois, à toucher avant qu'il ne s'éteigne | |
| 2 · Johto | **Raikou** | chaînes de combos : dégâts multipliés | Trio des Bêtes |
| | **Entei** | abattre les Hautes Herbes puis frapper la Pokéball | |
| | **Suicune** | une cible bleue qui se déplace (va-et-vient) | |
| 3 · Gardiens | **Lugia** | rampes uniquement, en alternance gauche/droite | Gardiens Célestes |
| | **Ho-Oh** | multiball 2 billes, les 7 couleurs de l'arc-en-ciel puis la Pokéball | |
| 4 · Hoenn | **Groudon** | tirs au centre + séismes qui secouent le plateau | Choc des Titans (4 billes) |
| | **Kyogre** | orbites et spinner (la marée monte) | |
| | **Rayquaza** | multiball 2 billes, tirs dans l'ordre de gauche à droite | |

**Final** : **Mew** se téléporte d'une flèche à l'autre (6 touches puis capture), puis **MEWTWO** :
phase 1 *Barrière Psy* (7 boucliers, 2 coups chacun), phase 2 *Multiball Psyko* (4 billes, jackpots = dégâts,
super jackpot à la Pokéball), phase 3 *Master Ball* (brisez sa garde psychique puis frappez la Pokéball, 3 fois).
Victoire → « Maître Pokémon », balle supplémentaire, et une nouvelle aventure recommence (score conservé).

**Fonctions annexes (typiquement Stern)**

- **Hautes Herbes** : abattez les 3 cibles → un Pokémon sauvage apparaît → frappez la Pokéball pour le capturer
  (Pokédex + verrou). 3 captures → **Multiball Safari** (jackpots sur rampes/orbites, super jackpot à la Pokéball).
- **Team Rocket** : 3 cibles rouges à droite → *hurry-up* : une flèche rouge à toucher avant que la valeur ne
  fonde (« La Team Rocket s'envole vers d'autres cieux ! »). Les 2e et 6e victoires allument une Extra Ball.
- **Skill shot** (couloir clignotant du haut, choisi avec les flippers avant le lancement) et **Super skill
  shot** (maintenir flipper gauche au lancement puis réussir la rampe Lugia).
- **Couloirs du haut** → bonus x (jusqu'à 6x) · **Couloirs P-O-K-É** → Mystère + **kickback Ronflex**.
- **Mystère** au Centre Pokémon : Bonbon Rare, Potion (ball save), Super Ball (capture en 2 secousses),
  Multi Exp. (score x2), Hyper Ball, Pépite…
- **Combos** (tirs majeurs enchaînés en moins de 4 s), **Extra Ball** (Pokédex 5 et 15, chapitre 2, Team Rocket),
  **Ball save** au lancement et en multiball, **TILT** après 2 avertissements, bonus de fin de bille, records.

## Physique

- Plateau 20,5" x 45" (520 x 1150 mm) incliné à **6,5°** (inclinaison recommandée par Stern).
- Bille d'acier de 27 mm qui **roule** : accélération 5/7·g·sin(6,5°) ≈ 0,79 m/s², résistance au roulement.
- **Sous-pas adaptatifs** (≤ 3 mm de déplacement par pas) : pas d'effet tunnel, même à 7 m/s.
- **Flippers** 3" modélisés comme des capsules effilées en rotation (distance signée exacte) : la vitesse du
  point de contact (ω × r) entre dans l'impulsion, frottement de Coulomb, élasticité du caoutchouc décroissante
  avec la vitesse (amortis, *cradles*, *live catches* possibles), course de ~35 ms.
- Physique réaliste des tirs : tirer tôt envoie la bille du même côté (*backhand*), tirer tard la croise.
- **Rampes** : trajectoires 3D à énergie conservée — un tir trop faible échoue et redescend.
- Bumpers, slingshots, kickback, scoop, portes anti-retour, spinner, cibles tombantes, *ball search*.
- Les touches sont **horodatées** et appliquées à l'instant exact dans la simulation (précision ~3 ms au lieu
  de la granularité de 16 ms d'une image).

## Durée de jeu

La difficulté est calibrée avec `tools/simulate_completion.py` : un « joueur idéal » qui ne perd jamais la
bille et réussit un tir visé toutes les 7 secondes termine toutes les quêtes (11 légendaires, 4 multiballs de
chapitre, Pokédex, Mew, Mewtwo) en **61 à 65 minutes** (8 graines testées). À 9 s par tir, ~87 minutes.
`tools/shot_map.py` mesure les fenêtres de timing de chaque tir depuis les flippers.

## Structure du code

```
main.py                     point d'entrée
pokepinball/
  config.py                 écran, dimensions, constantes physiques
  physics.py                moteur 2D (bille, segments, cercles, flippers, rampes, capteurs)
  elements.py · table.py    éléments de jeu et géométrie du plateau
  data.py                   légendaires, Pokémon sauvages, chapitres, couleurs de types
  game.py · modes.py        règles Stern : billes, scoring, modes, multiballs, Mewtwo
  app.py                    boucle principale, entrées horodatées, effets
  render/                   plateau (statique + dynamique, bloom), LCD, panneaux, art procédural
  audio/                    synthèse des bruitages, compositeur de musiques, voix
tools/                      simulations de calibrage
```

*Jeu de fan non officiel, sans but commercial. Pokémon et les noms des Pokémon sont des marques de Nintendo,
Game Freak et The Pokémon Company. Stern est une marque de Stern Pinball, Inc.*
