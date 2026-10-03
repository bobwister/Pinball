"""Gestionnaire audio : génération (cache disque), bruitages, musiques, voix d'annonceur."""
import os
import subprocess
import threading
import time

import numpy as np
import pygame

from ..config import CACHE_DIR
from . import synth
from .synth import SR, to_int16

VERSION = "v3"

CALLOUTS = {
    "start": "Que l'aventure commence !",
    "leg_articuno": "Artikodin, l'oiseau légendaire des glaces !",
    "leg_zapdos": "Électhor, l'oiseau légendaire de la foudre !",
    "leg_moltres": "Sulfura, l'oiseau légendaire des flammes !",
    "leg_raikou": "Raikou, la bête du tonnerre !",
    "leg_entei": "Entei, la bête des volcans !",
    "leg_suicune": "Suicune, la bête des aurores !",
    "leg_lugia": "Lugia, le gardien des mers !",
    "leg_hooh": "Ho-Oh, le gardien de l'arc-en-ciel !",
    "leg_groudon": "Groudon, le maître des continents !",
    "leg_kyogre": "Kyogre, le maître des océans !",
    "leg_rayquaza": "Rayquaza, le maître du ciel !",
    "leg_mew": "Mew ! Le Pokémon mirage !",
    "throw_ball": "Il est affaibli ! Lancez la Pokéball !",
    "shake_1": "Un...",
    "shake_2": "Deux...",
    "gotcha": "Gotcha ! Capture réussie !",
    "broke_free": "Oh non ! Il s'est libéré !",
    "escaped": "Il s'est enfui...",
    "chapter_complete": "Chapitre terminé ! Multiball de chapitre prêt !",
    "multiball": "Multiball !",
    "jackpot": "Jackpot !",
    "super_jackpot": "Super jackpot !",
    "super_jackpot_lit": "Super jackpot allumé !",
    "ball_saved": "Balle sauvée !",
    "extra_ball": "Balle supplémentaire !",
    "eb_lit": "Balle supplémentaire allumée !",
    "shoot_again": "Rejouez !",
    "skill_shot": "Skill shot !",
    "super_skill": "Super skill shot !",
    "combo": "Combo !",
    "wild": "Un Pokémon sauvage apparaît !",
    "caught": "Pokémon capturé !",
    "legendary_ready": "Légendaire prêt !",
    "choose": "Choisissez votre adversaire !",
    "team_rocket": "Attention ! La Team Rocket !",
    "rocket_blast": "La Team Rocket s'envole vers d'autres cieux !",
    "snorlax": "Ronflex !",
    "danger": "Attention !",
    "tilt": "Tilt !",
    "mewtwo": "Mewtwo vous défie ! Le combat final commence !",
    "master_ball": "Lancez la Master Ball !",
    "victory": "Félicitations ! Vous êtes un maître Pokémon !",
    "game_over": "Partie terminée.",
}

MUSIC_NAMES = ["main", "attract", "battle_1", "battle_2", "battle_3", "battle_4", "capture", "multiball",
               "wizard", "mewtwo", "select", "bonus", "game_over"]


class Audio:
    def __init__(self, enabled=True, voice=True):
        self.enabled = enabled and pygame.mixer.get_init() is not None
        self.voice_enabled = voice
        self.sounds = {}
        self.music_snd = {}
        self.voices = {}
        self.pending = []          # (type, name, array) produits par le thread
        self.lock = threading.Lock()
        self.progress = 0.0
        self.total = 1
        self.done_count = 0
        self.ready = False
        self.cur_music = None
        self.music_vol = 0.42
        self.sfx_vol = 0.85
        self.voice_vol = 1.0
        self.music_muted = False
        self.duck = 0.0
        self.last_play = {}
        self.want_music = None
        if not self.enabled:
            return
        pygame.mixer.set_num_channels(48)
        pygame.mixer.set_reserved(6)
        self.ch_music = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
        self.ch_music_idx = 0
        self.ch_sting = pygame.mixer.Channel(2)
        self.ch_voice = pygame.mixer.Channel(3)
        self.ch_roll = pygame.mixer.Channel(4)
        self.ch_wire = pygame.mixer.Channel(5)
        for d in ("sfx", "music", "voice"):
            os.makedirs(os.path.join(CACHE_DIR, d), exist_ok=True)

    # ------------------------------------------------------------------
    # Génération en arrière-plan
    # ------------------------------------------------------------------
    def start_loading(self):
        if not self.enabled:
            self.ready = True
            return
        from . import music
        self.jobs = ([("sfx", k) for k in synth.SFX] + [("sfx", "loop_roll"), ("sfx", "loop_wire")] +
                     [("jingle", k) for k in music.JINGLES] + [("music", k) for k in MUSIC_NAMES])
        self.total = len(self.jobs) + (len(CALLOUTS) if self.voice_enabled else 0)
        threading.Thread(target=self._worker, daemon=True).start()
        if self.voice_enabled:
            threading.Thread(target=self._voice_worker, daemon=True).start()

    def _cache_path(self, kind, name):
        import zlib
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in name.encode("ascii", "replace").decode())
        if not name.isascii():
            safe += "_" + format(zlib.crc32(name.encode("utf-8")), "x")
        return os.path.join(CACHE_DIR, "music" if kind in ("music", "jingle") else kind, f"{safe}_{VERSION}.npy")

    def _worker(self):
        from . import music
        # la musique principale d'abord pour l'écran d'attraction
        order = sorted(self.jobs, key=lambda j: 0 if j == ("music", "attract") else (1 if j[0] == "sfx" else 2))
        for kind, name in order:
            path = self._cache_path(kind, name)
            arr = None
            try:
                if os.path.exists(path):
                    arr = np.load(path)
                else:
                    if kind == "sfx":
                        if name == "loop_roll":
                            x = synth.loop_roll()
                        elif name == "loop_wire":
                            x = synth.loop_wire()
                        else:
                            x = synth.SFX[name]()
                        arr = to_int16(x)
                    elif kind == "jingle":
                        arr = to_int16(music.JINGLES[name]())
                    else:
                        arr = to_int16(music.render_music(name))
                    np.save(path, arr)
            except Exception as e:  # un son manquant ne doit jamais bloquer le jeu
                print("audio:", kind, name, e)
            if arr is not None:
                with self.lock:
                    self.pending.append((kind, name, arr))
            with self.lock:
                self.done_count += 1

    def _voice_worker(self):
        vdir = os.path.join(CACHE_DIR, "voice")
        missing = [k for k in CALLOUTS if not os.path.exists(os.path.join(vdir, f"{k}_{VERSION}.npy"))]
        if missing and os.name == "nt":
            self._sapi_generate(missing, vdir)
        for k in CALLOUTS:
            npy = os.path.join(vdir, f"{k}_{VERSION}.npy")
            arr = None
            try:
                if os.path.exists(npy):
                    arr = np.load(npy)
                else:
                    wav = os.path.join(vdir, f"{k}.wav")
                    if os.path.exists(wav):
                        arr = self._process_voice(wav)
                        np.save(npy, arr)
            except Exception as e:
                print("voix:", k, e)
            if arr is not None:
                with self.lock:
                    self.pending.append(("voice", k, arr))
            with self.lock:
                self.done_count += 1

    def _sapi_generate(self, keys, vdir):
        lines = ["Add-Type -AssemblyName System.Speech",
                 "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
                 "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -eq 'fr-FR' } | "
                 "Select-Object -First 1",
                 "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }",
                 "$s.Rate = 1", "$s.Volume = 100"]
        for k in keys:
            txt = CALLOUTS[k].replace("'", "''")
            path = os.path.join(vdir, f"{k}.wav").replace("'", "''")
            lines.append(f"$s.SetOutputToWaveFile('{path}'); $s.Speak('{txt}')")
        lines.append("$s.SetOutputToNull()")
        script = os.path.join(vdir, "gen.ps1")
        with open(script, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(lines))
        try:
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                           timeout=180, capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as e:
            print("SAPI indisponible :", e)

    def _process_voice(self, wav):
        from scipy.io import wavfile
        from scipy.signal import resample_poly
        sr, x = wavfile.read(wav)
        x = x.astype(np.float64)
        if x.ndim > 1:
            x = x.mean(axis=1)
        x /= (np.max(np.abs(x)) + 1e-9)
        if sr != SR:
            from math import gcd
            g = gcd(sr, SR)
            x = resample_poly(x, SR // g, sr // g)
        # voix d'annonceur : coupe-bas, présence, compression, réverbération
        x = synth.highpass(x, 140)
        x = x + synth.bandpass(x, 2000, 5000) * 0.6
        x = synth.softclip(x * 1.6, 1.8)
        x = synth.reverb(x, 0.9, 0.18)
        x = synth.normalize(x, 0.95)
        st = np.stack([x, np.roll(x, int(0.008 * SR)) * 0.92], axis=1)
        return to_int16(st)

    def poll(self):
        """Convertit les tableaux prêts en objets Sound (thread principal)."""
        if not self.enabled:
            return
        with self.lock:
            items = self.pending[:6]
            self.pending = self.pending[6:]
            self.progress = self.done_count / max(1, self.total)
        for kind, name, arr in items:
            try:
                snd = pygame.sndarray.make_sound(arr)
            except Exception as e:
                print("son:", name, e)
                continue
            if kind == "sfx":
                self.sounds[name] = snd
                if name == "loop_roll":
                    self.ch_roll.play(snd, loops=-1)
                    self.ch_roll.set_volume(0.0)
                elif name == "loop_wire":
                    self.ch_wire.play(snd, loops=-1)
                    self.ch_wire.set_volume(0.0)
            elif kind == "jingle":
                self.sounds["jingle_" + name] = snd
            elif kind == "music":
                self.music_snd[name] = snd
                if self.want_music == name and self.cur_music != name:
                    self.music(name)
            elif kind == "voice":
                self.voices[name] = snd
        if self.done_count >= self.total and not self.pending:
            self.ready = True

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def play(self, name, vol=1.0, pan=0.0, cooldown=0.025):
        if not self.enabled:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = time.perf_counter()
        if now - self.last_play.get(name, 0) < cooldown:
            return
        self.last_play[name] = now
        ch = pygame.mixer.find_channel(True)
        if ch is None:
            return
        ch.play(snd)
        v = vol * self.sfx_vol
        pan = max(-1.0, min(1.0, pan))
        ch.set_volume(v * min(1.0, 1 - pan), v * min(1.0, 1 + pan))

    def music(self, name, fade=700):
        if not self.enabled:
            return
        self.want_music = name
        if name == self.cur_music:
            return
        old = self.ch_music[self.ch_music_idx]
        old.fadeout(fade)
        self.cur_music = None
        if name is None:
            return
        snd = self.music_snd.get(name)
        if snd is None:
            return
        self.ch_music_idx ^= 1
        ch = self.ch_music[self.ch_music_idx]
        ch.play(snd, loops=-1 if name != "game_over" else 0, fade_ms=fade)
        ch.set_volume(0 if self.music_muted else self.music_vol)
        self.cur_music = name

    def stinger(self, name):
        if not self.enabled:
            return
        snd = self.sounds.get("jingle_" + name)
        if snd is None:
            return
        self.ch_sting.play(snd)
        self.ch_sting.set_volume(0.9)
        self.duck = max(self.duck, snd.get_length())

    def callout(self, key):
        if not self.enabled or not self.voice_enabled:
            return
        snd = self.voices.get(key)
        if snd is None:
            return
        self.ch_voice.play(snd)
        self.ch_voice.set_volume(self.voice_vol)
        self.duck = max(self.duck, snd.get_length() * 0.8)

    def toggle_music(self):
        self.music_muted = not self.music_muted

    def update(self, dt, world):
        if not self.enabled:
            return
        self.poll()
        self.duck = max(0.0, self.duck - dt)
        target = 0.0 if self.music_muted else self.music_vol * (0.45 if self.duck > 0 else 1.0)
        ch = self.ch_music[self.ch_music_idx]
        cur = ch.get_volume()
        ch.set_volume(cur + (target - cur) * min(1.0, dt * 8))
        # roulement de la bille
        pf_sp = 0.0
        wire = 0.0
        for b in world.balls:
            if b.state == "pf":
                pf_sp = max(pf_sp, b.speed)
            elif b.state == "ramp":
                wire = max(wire, abs(b.sv))
        rv = min(1.0, pf_sp / 3500.0) ** 0.8 * 0.55
        self.ch_roll.set_volume(rv * self.sfx_vol)
        self.ch_wire.set_volume(min(1.0, wire / 2500.0) * 0.5 * self.sfx_vol)

    def impacts(self, events, pf_w=482.0):
        for x, y, imp, mat in events:
            v = min(1.0, imp / 3000.0)
            if v < 0.08:
                continue
            pan = (x / pf_w) * 2 - 1
            if mat in ("rubber", "post", "sling"):
                self.play("hit_rubber", v, pan, 0.03)
            elif mat in ("metal", "plunger"):
                self.play("hit_metal", v * 0.8, pan, 0.03)
            elif mat == "ball":
                self.play("ball_click", v, pan, 0.03)
            elif mat == "flipper":
                self.play("hit_rubber", v * 0.7, pan, 0.03)
            else:
                self.play("hit_wall", v * 0.8, pan, 0.03)
