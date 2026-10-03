"""Simulation « joueur idéal » : mesure le temps pour terminer toutes les quêtes.

Le joueur ne perd jamais la bille et réussit un tir visé toutes les T secondes
(7 s par défaut = précision raisonnablement élevée). Usage :
    python tools/simulate_completion.py [graine] [secondes_par_tir]
"""
import os, sys, random, traceback
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pokepinball.table import Table
from pokepinball.game import Game, Lamps
from pokepinball import modes as M
from pokepinball.data import SHOTS
random.seed(int(sys.argv[1]) if len(sys.argv)>1 else 3)
T_SHOT = float(sys.argv[2]) if len(sys.argv)>2 else 7.0
T_MB = T_SHOT*0.5
log=[]
class FX:
    def lcd(self, name, **kw):
        if name in ("legendary_intro","gotcha","escaped","broke_free","multiball","chapter_complete","chapter_wizard",
                    "mewtwo_intro","mewtwo_phase","victory","wild_caught","team_rocket","rocket_defeated","extra_ball","mode_select"):
            extra = kw.get("leg").name if kw.get("leg") else kw.get("title", kw.get("chapter",""))
            log.append((g.game_time, name, extra))
    def __getattr__(self, n): return lambda *a, **k: None
tb=Table(); g=Game(tb, FX())
sim_balls=[1]
g.balls_in_play=lambda: sim_balls[0]
def add_balls(n, save=0.0):
    sim_balls[0]+=max(0,int(n)); g.ball_save(save)
g.add_balls=add_balls
g.start_game(); g.ev_launch({}); g.ball_launched=True
def adv(sec):
    n=int(sec/0.05)
    for i in range(n):
        g.update(0.05); tb.update(0.05)
        for ev,kw in tb.take_events(): g.handle(ev,kw)
        # multiball : fin après ~100 s
        mb=[m for m in g.modes if m.is_multiball] 
        if sim_balls[0]>1:
            mbt[0]+=0.05
            if mbt[0]>MB_LEN:
                sim_balls[0]=1; mbt[0]=0
        else: mbt[0]=0
MB_LEN=100.0
mbt=[0.0]
def fire(shot):
    if shot=="orbit_l":
        g.handle("orbit_left",{}); [g.handle("spinner",{}) for _ in range(8)]
    elif shot=="orbit_r": g.handle("orbit_right",{})
    elif shot=="ramp_l": g.handle("ramp_made",{"element":tb.ramp_l})
    elif shot=="ramp_r": g.handle("ramp_made",{"element":tb.ramp_r})
    elif shot=="bumper":
        g.handle("bumper_lane",{}); [g.handle("bumper",{"x":350,"y":200}) for _ in range(5)]
        g.handle("rollover",{"group":"top","index":random.randint(0,2)})
    elif shot=="scoop": g.handle("scoop",{})
    elif shot=="center":
        up=[t for t in tb.grass.targets if not t.down]
        if up:
            t=random.choice(up); t.set_down(True); g.handle("drop",{"index":t.index})
        else: g.handle("pokeball",{})
    elif shot.startswith("radar"):
        g.handle("standup",{"bank":"radar","index":int(shot[-1])})
    elif shot.startswith("rocket"):
        g.handle("standup",{"bank":"rocket","index":int(shot[-1])})
def choose():
    p=g.player; L=g.lamps.states
    lit=[s for s in SHOTS if "arrow_"+s in L]
    lm=g.legendary_mode()
    # priorité : flèches allumées par un mode
    if lit:
        # éviter le scoop si c'est juste "mode prêt" pendant un mode
        return random.choice(lit)
    if (p.mode_lit and p.available_legendaries()) or p.wizard_lit or p.mew_lit or p.mewtwo_lit or p.eb_lit:
        return "scoop"
    if p.chapter_clear and g.pokedex_needed() > 0:
        return "center"
    need=[i for i in range(3) if p.radar[i]<p.radar_need]
    if need and p.available_legendaries():
        return "radar"+str(need[0])
    return random.choice(SHOTS)
t_end=4*3600
shots=0
try:
    while g.game_time < t_end:
        if g.select is not None:
            adv(1.5); g.launch_button(); continue
        if g.scoop_busy():
            adv(0.5); continue
        s=choose()
        adv(T_MB if sim_balls[0]>1 else (T_SHOT if not s.startswith("radar") else T_SHOT*0.7))
        if g.select is not None or g.scoop_busy(): continue
        s=choose(); shots+=1
        fire(s)
        # tirs parasites (bumpers, slings...)
        if random.random()<0.3: g.handle("sling",{})
        if random.random()<0.15: g.handle("standup",{"bank":"rocket","index":random.randint(0,2)})
        if random.random()<0.1: g.handle("rollover",{"group":"lane","index":random.randint(0,3)})
        if g.player.mewtwo_done: break
except Exception:
    traceback.print_exc()
p=g.player
for t,n,x in log:
    print(f"{int(t//60):3d}:{int(t%60):02d}  {n:18s} {x}")
print(f"TOTAL {g.game_time / 60:.1f} min · tirs réussis {shots} · score {p.score:,} · "
      f"Mewtwo vaincu : {'oui' if p.mewtwo_done else 'non'} · Pokédex {len(p.pokedex)}")
