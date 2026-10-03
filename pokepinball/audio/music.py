"""Compositeur procédural : musiques originales façon chiptune/épique (boucles sans couture)."""
import numpy as np

from .synth import (SR, osc, sine, noise, adsr, env_exp, lowpass, highpass, bandpass, reverb, normalize,
                    freq_curve, midi_hz, softclip)

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_midi(n):
    if n in ("r", "-", None):
        return None
    name = n[0].upper()
    acc = 0
    i = 1
    while i < len(n) and n[i] in "#b":
        acc += 1 if n[i] == "#" else -1
        i += 1
    octv = int(n[i:])
    return 12 * (octv + 1) + NOTE[name] + acc


def parse_melody(s):
    """'E5:1 G5:1 r:0.5 ...' → [(midi|None, beats)]."""
    out = []
    for tok in s.split():
        n, d = tok.split(":")
        out.append((note_midi(n), float(d)))
    return out


CHORD_TYPES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
               "dim": (0, 3, 6), "sus": (0, 5, 7), "5": (0, 7, 12)}


def chord_notes(sym, octave=3):
    root = sym[0]
    i = 1
    acc = 0
    while i < len(sym) and sym[i] in "#b":
        acc += 1 if sym[i] == "#" else -1
        i += 1
    q = sym[i:]
    base = 12 * (octave + 1) + NOTE[root] + acc
    return [base + iv for iv in CHORD_TYPES.get(q, CHORD_TYPES[""])]


# --------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------
def inst_lead(m, dur, vel=1.0, kind="square", duty=0.25):
    f = midi_hz(m)
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.12) * 4, 0, 1)
    x = osc(kind, f * vib, dur, duty) * 0.7 + osc(kind, f * vib * 1.003, dur, duty) * 0.3
    if kind == "saw":
        x = lowpass(x, 3800)
    return x * adsr(dur, 0.008, 0.08, 0.75, min(0.06, dur * 0.3)) * vel


def inst_bass(m, dur, vel=1.0):
    f = midi_hz(m)
    x = osc("tri", f, dur) * 0.8 + osc("square", f, dur, 0.5) * 0.25
    x = lowpass(x, 900)
    return x * adsr(dur, 0.004, 0.05, 0.85, min(0.03, dur * 0.3)) * vel


def inst_arp(m, dur, vel=1.0):
    return osc("square", midi_hz(m), dur, 0.125) * env_exp(dur, dur * 0.45) * vel


def inst_pad(notes, dur, vel=1.0):
    out = np.zeros(int(dur * SR))
    for m in notes:
        for det in (-0.07, 0.0, 0.07):
            out += osc("saw", midi_hz(m + det), dur) / (3 * len(notes))
    out = lowpass(out, 1800)
    return out * adsr(dur, min(0.3, dur * 0.3), 0.2, 0.8, min(0.3, dur * 0.3)) * vel


def inst_brass(m, dur, vel=1.0):
    f = midi_hz(m)
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = osc("saw", f, dur) * 0.6 + osc("saw", f * 1.004, dur) * 0.4
    cutoff = 900 + 2600 * np.clip(t / 0.08, 0, 1)
    x = lowpass(x, 3000)
    return x * adsr(dur, 0.03, 0.1, 0.8, min(0.1, dur * 0.3)) * vel


def drum_kick():
    d = 0.32
    from .synth import mix
    return mix(sine(freq_curve(150, 42, d), d) * env_exp(d, 0.09) * 1.1, bandpass(noise(0.01), 1000, 5000) * 0.2)


def drum_snare():
    d = 0.22
    return (bandpass(noise(d), 1200, 7000) * env_exp(d, 0.06) * 0.8 +
            sine(freq_curve(230, 160, d), d) * env_exp(d, 0.05) * 0.5)


def drum_hat(open_=False):
    d = 0.25 if open_ else 0.05
    return highpass(noise(d), 7000) * env_exp(d, 0.08 if open_ else 0.012) * 0.45


def drum_crash():
    d = 1.6
    return highpass(noise(d), 4000) * env_exp(d, 0.5) * 0.5


def drum_tom(f=110):
    d = 0.3
    return sine(freq_curve(f * 1.4, f, d), d) * env_exp(d, 0.12)


_DRUMS = None


def drums():
    global _DRUMS
    if _DRUMS is None:
        _DRUMS = {"k": drum_kick(), "s": drum_snare(), "h": drum_hat(), "o": drum_hat(True), "c": drum_crash(),
                  "t": drum_tom(100), "T": drum_tom(150)}
    return _DRUMS


DRUM_PATTERNS = {
    # 16 pas par mesure
    "rock": "k-h-s-h-k-kks-h-",
    "drive": "k-hhs-hhk-hhs-hh",
    "march": "k-s-k-s-k-s-kss-",
    "epic": "k--hs--hk-khs-hh",
    "half": "k---h---s---h---",
    "four": "k-h-k-h-k-h-k-ho",
    "tick": "h---h---h---h---",
    "none": "----------------",
    "battle": "k-hks-hkk-hks-hs",
}


# --------------------------------------------------------------------------
class Track:
    def __init__(self, bpm, chords, melody=None, bars=None, drum="rock", bass="eighth", arp=True, pad=False,
                 lead="square", lead_vol=0.55, transpose=0, fill_every=4, brass=False, harmony=True,
                 bass_oct=2, arp_oct=4, swing=0.0, crash_every=8, drum_vol=0.8):
        self.bpm = bpm
        self.chords = chords
        self.melody = parse_melody(melody) if melody else []
        self.bars = bars or len(chords)
        self.drum = drum
        self.bass = bass
        self.arp = arp
        self.pad = pad
        self.lead = lead
        self.lead_vol = lead_vol
        self.transpose = transpose
        self.fill_every = fill_every
        self.brass = brass
        self.harmony = harmony
        self.bass_oct = bass_oct
        self.arp_oct = arp_oct
        self.crash_every = crash_every
        self.drum_vol = drum_vol

    def render(self, loop=True):
        beat = 60.0 / self.bpm
        bar = beat * 4
        L = int(self.bars * bar * SR)
        tail = int(2.0 * SR)
        lead = np.zeros(L + tail)
        harm = np.zeros(L + tail)
        bass = np.zeros(L + tail)
        arpL = np.zeros(L + tail)
        arpR = np.zeros(L + tail)
        padb = np.zeros(L + tail)
        drm = np.zeros(L + tail)
        tr = self.transpose

        def put(buf, x, start):
            s = int(start * SR)
            e = min(len(buf), s + len(x))
            if s < len(buf):
                buf[s:e] += x[:e - s]

        # mélodie
        pos = 0.0
        for m, d in self.melody:
            if m is not None:
                dur = d * beat
                if self.brass:
                    put(lead, inst_brass(m + tr, dur * 0.95, self.lead_vol), pos * beat)
                else:
                    put(lead, inst_lead(m + tr, dur * 0.92, self.lead_vol, self.lead), pos * beat)
                if self.harmony:
                    put(harm, inst_lead(m + tr - 12, dur * 0.9, 0.22, "tri"), pos * beat)
            pos += d
            if pos >= self.bars * 4:
                break
        # accords : basse, arpèges, nappes
        for b in range(self.bars):
            sym = self.chords[b % len(self.chords)]
            cn = [n + tr for n in chord_notes(sym, 3)]
            root = cn[0] - 12 * (3 - self.bass_oct)
            t0 = b * bar
            if self.bass == "eighth":
                for k in range(8):
                    mm = root + (12 if k % 4 == 3 else 0)
                    put(bass, inst_bass(mm, beat * 0.45, 0.6), t0 + k * beat / 2)
            elif self.bass == "gallop":
                for k in range(4):
                    put(bass, inst_bass(root, beat * 0.22, 0.6), t0 + k * beat)
                    put(bass, inst_bass(root, beat * 0.22, 0.5), t0 + k * beat + beat * 0.5)
                    put(bass, inst_bass(root + 7, beat * 0.22, 0.5), t0 + k * beat + beat * 0.75)
            elif self.bass == "sixteenth":
                for k in range(16):
                    put(bass, inst_bass(root + (12 if k % 8 == 7 else 0), beat * 0.22, 0.55), t0 + k * beat / 4)
            elif self.bass == "long":
                put(bass, inst_bass(root, bar * 0.95, 0.6), t0)
            elif self.bass == "walk":
                seq = [root, root + 7, root + 12, root + 7]
                for k in range(4):
                    put(bass, inst_bass(seq[k], beat * 0.9, 0.6), t0 + k * beat)
            if self.arp:
                ar = [n + 12 * (self.arp_oct - 3) for n in cn]
                pat = ar + [ar[1] + 12 if len(ar) > 1 else ar[0] + 12]
                for k in range(16):
                    m = pat[k % len(pat)]
                    buf = arpL if k % 2 == 0 else arpR
                    put(buf, inst_arp(m, beat * 0.24, 0.16), t0 + k * beat / 4)
            if self.pad:
                put(padb, inst_pad([n + 12 for n in cn], bar * 1.02, 0.5), t0)
            # batterie
            pat = DRUM_PATTERNS.get(self.drum, DRUM_PATTERNS["rock"])
            if self.fill_every and (b + 1) % self.fill_every == 0 and self.drum not in ("none", "tick", "half"):
                pat = pat[:12] + "TtTs"
            D = drums()
            for k, ch in enumerate(pat):
                if ch in D:
                    put(drm, D[ch] * self.drum_vol, t0 + k * beat / 4)
            if self.crash_every and b % self.crash_every == 0 and self.drum not in ("none", "tick"):
                put(drm, D["c"] * 0.6 * self.drum_vol, t0)
        # mixage
        lead = reverb(lead, 1.1, 0.22)[:L + tail]
        from .synth import delay
        echo = delay(lead, beat * 0.75, 0.3, 0.25, 3)[:L + tail]
        padb = reverb(padb, 1.8, 0.4)[:L + tail]
        left = lead * 0.9 + echo * 0.25 + harm * 0.8 + bass + arpL * 1.0 + arpR * 0.35 + padb * 0.9 + drm * 0.9
        right = lead * 0.9 + np.roll(echo, int(0.011 * SR)) * 0.25 + harm * 0.8 + bass + arpL * 0.35 + arpR * 1.0 \
            + np.roll(padb, int(0.013 * SR)) * 0.9 + drm * 0.9
        out = np.stack([left, right], axis=1)
        if loop:
            out[:tail] += out[L:L + tail]
            out = out[:L]
        out = softclip(out * 0.9, 1.2)
        return normalize(out, 0.85)


# --------------------------------------------------------------------------
# Partitions (compositions originales)
# --------------------------------------------------------------------------
MAIN_MEL = ("E5:1 G5:1 C6:1.5 B5:0.5 A5:1 G5:1 D5:2 E5:1 A5:1 C6:1 B5:0.5 A5:0.5 G5:1.5 F5:0.5 E5:1 C5:1 "
            "E5:1 G5:1 C6:1.5 D6:0.5 E6:1 D6:1 B5:2 C6:1 A5:1 F5:1 A5:1 G5:3 r:1 "
            "C6:0.5 B5:0.5 A5:1 E5:1 A5:1 F5:1 A5:1 C6:2 G5:0.5 A5:0.5 G5:1 E5:1 C5:1 D5:1 G5:1 B5:2 "
            "A5:1 C6:1 F6:1.5 E6:0.5 D6:1 B5:1 G5:1 D6:1 C6:1.5 B5:0.5 C6:1 G5:1 C6:3 r:1")
MAIN_CH = ["C", "G", "Am", "F", "C", "G", "F", "G", "Am", "F", "C", "G", "F", "G", "C", "C"]

BATTLE_MEL = ("A4:0.5 C5:0.5 E5:0.5 A5:0.5 G5:0.5 E5:0.5 C5:0.5 E5:0.5 F5:1 E5:0.5 F5:0.5 A5:1 C6:1 "
              "B5:1 A5:0.5 G5:0.5 D5:1 G5:1 E5:2 A5:1 r:1 "
              "A5:0.5 B5:0.5 C6:1 B5:0.5 A5:0.5 E5:1 F5:0.5 G5:0.5 A5:1 C6:1 A5:1 "
              "G#5:1 B5:1 E6:1 D6:0.5 B5:0.5 G#5:2 E5:2 "
              "D5:0.5 F5:0.5 A5:1 D6:1 C6:1 C6:0.5 B5:0.5 A5:1 E5:1 A5:1 F5:1 A5:1 D6:1.5 C6:0.5 "
              "B5:1 G#5:1 E5:1 B5:1 C6:1 A5:1 F5:1 C6:1 D6:1 B5:1 G5:1 D6:1 E6:1.5 D6:0.5 C6:1 B5:1 A5:3 r:1")
BATTLE_CH = ["Am", "F", "G", "Am", "Am", "F", "E", "E", "Dm", "Am", "Dm", "E", "F", "G", "Am", "Am"]

MB_MEL = ("C6:0.5 A5:0.5 F5:0.5 A5:0.5 C6:1 D6:1 B5:0.5 G5:0.5 D5:0.5 G5:0.5 B5:1 D6:1 "
          "E6:0.5 D6:0.5 B5:0.5 G5:0.5 E5:1 G5:1 A5:2 C6:1 E6:1 "
          "F6:1 E6:0.5 D6:0.5 A5:1 D6:1 G5:1 B5:1 D6:1 F6:1 E6:2 C6:1 G5:1 C6:3 r:1")
MB_CH = ["F", "G", "Em", "Am", "Dm", "G", "C", "C"]

WIZ_MEL = ("Eb5:1.5 Bb4:0.5 Eb5:1 G5:1 F5:1.5 D5:0.5 Bb4:2 C5:1 Eb5:1 G5:1 C6:1 Ab5:3 r:1 "
           "G5:1.5 F5:0.5 Eb5:1 Bb5:1 Bb5:1.5 C6:0.5 D6:2 C6:1 Ab5:1 F5:1 Ab5:1 G5:3 r:1")
WIZ_CH = ["Eb", "Bb", "Cm", "Ab", "Eb", "Bb", "Ab", "Bb"]

MEWTWO_MEL = ("C5:1 Db5:0.5 C5:0.5 G4:1 C5:1 Eb5:1 Db5:1 C5:2 F5:1 Eb5:0.5 Db5:0.5 C5:1 G5:1 Gb5:2 G5:2 "
              "Ab5:1 G5:0.5 F5:0.5 Eb5:1 C5:1 Bb4:1 C5:1 Db5:2 C5:1 Eb5:1 G5:1 C6:1 B5:3 r:1")
MEWTWO_CH = ["Cm", "Db", "Cm", "G", "Ab", "Bb", "Cm", "G"]

CAPTURE_MEL = ("E5:0.5 E5:0.5 F5:0.5 E5:0.5 G5:1 F5:1 E5:0.5 E5:0.5 F5:0.5 G5:0.5 A5:1 B5:1 " * 3 +
               "G5:0.5 A5:0.5 B5:0.5 C6:0.5 D6:1 C6:1 B5:0.5 C6:0.5 D6:0.5 E6:0.5 F#6:1 D#6:1")
CAPTURE_CH = ["Em", "F", "Em", "F", "Em", "F", "G", "B"]

SELECT_MEL = "E5:2 r:2 B4:2 r:2 C5:2 r:2 D5:1 E5:1 B4:2"
SELECT_CH = ["Am", "Am", "F", "E"]

BONUS_MEL = "C6:0.5 E6:0.5 G6:0.5 E6:0.5 " * 2 + "C6:0.5 F6:0.5 A6:0.5 F6:0.5 " * 2 + "B5:0.5 D6:0.5 G6:0.5 D6:0.5 G6:2 E6:2 C6:2"
BONUS_CH = ["C", "C", "F", "G"]

GAMEOVER_MEL = "G5:1 E5:1 C5:1 G4:1 A4:1.5 B4:0.5 C5:4"


TRACKS = {
    "main": lambda: Track(140, MAIN_CH, MAIN_MEL, drum="rock", bass="eighth", arp=True),
    "attract": lambda: Track(116, MAIN_CH, MAIN_MEL, drum="half", bass="walk", arp=True, pad=True, lead="tri",
                             lead_vol=0.6),
    "battle_1": lambda: Track(168, BATTLE_CH, BATTLE_MEL, drum="drive", bass="gallop", arp=True),
    "battle_2": lambda: Track(172, BATTLE_CH, BATTLE_MEL, drum="battle", bass="sixteenth", arp=True, lead="saw",
                              transpose=5),
    "battle_3": lambda: Track(150, BATTLE_CH, BATTLE_MEL, drum="epic", bass="eighth", arp=False, pad=True,
                              brass=True, transpose=7, lead_vol=0.6),
    "battle_4": lambda: Track(160, BATTLE_CH, BATTLE_MEL, drum="battle", bass="gallop", arp=True, pad=True,
                              lead="saw", transpose=3),
    "capture": lambda: Track(176, CAPTURE_CH, CAPTURE_MEL, drum="four", bass="sixteenth", arp=True),
    "multiball": lambda: Track(152, MB_CH * 2, MB_MEL + " " + MB_MEL, drum="drive", bass="eighth", arp=True),
    "wizard": lambda: Track(140, WIZ_CH * 2, WIZ_MEL + " " + WIZ_MEL, drum="epic", bass="gallop", arp=True,
                            pad=True, brass=True),
    "mewtwo": lambda: Track(138, MEWTWO_CH * 2, MEWTWO_MEL + " " + MEWTWO_MEL, drum="battle", bass="sixteenth",
                            arp=False, pad=True, lead="saw", lead_vol=0.5),
    "select": lambda: Track(96, SELECT_CH, SELECT_MEL, drum="tick", bass="long", arp=True, pad=True, lead="tri",
                            harmony=False),
    "bonus": lambda: Track(124, BONUS_CH, BONUS_MEL, drum="four", bass="walk", arp=False, lead="square",
                           lead_vol=0.4),
    "game_over": lambda: Track(90, ["C", "Am", "F"], GAMEOVER_MEL, drum="none", bass="long", arp=False,
                               pad=True, lead="tri"),
}


def render_music(name):
    tr = TRACKS[name]()
    return tr.render(loop=(name != "game_over"))


# --------------------------------------------------------------------------
# Jingles
# --------------------------------------------------------------------------
def jingle(mel, chords_at, bpm=132, end_chord=None, brass=True, dur_extra=1.6):
    beat = 60.0 / bpm
    m = parse_melody(mel)
    total = sum(d for _, d in m) * beat + dur_extra
    n = int(total * SR)
    lead = np.zeros(n)
    pad = np.zeros(n)
    pos = 0.0
    for mm, d in m:
        if mm is not None:
            x = inst_brass(mm, d * beat * 0.95, 0.6) if brass else inst_lead(mm, d * beat * 0.95, 0.6)
            s = int(pos * beat * SR)
            lead[s:s + len(x)] += x[:n - s]
            x2 = inst_lead(mm - 12, d * beat * 0.9, 0.25, "tri")
            lead[s:s + len(x2)] += x2[:n - s]
        pos += d
    for at, sym, dur in chords_at:
        x = inst_pad([v + 12 for v in chord_notes(sym, 3)], dur * beat, 0.7)
        s = int(at * beat * SR)
        pad[s:s + len(x)] += x[:n - s]
    D = drums()
    dr = np.zeros(n)
    for k in range(int(pos)):
        x = D["s"] * 0.5 if k % 2 else D["k"] * 0.7
        s = int(k * beat * SR)
        dr[s:s + len(x)] += x[:n - s]
    s = int(pos * beat * SR)
    c = D["c"]
    dr[s:s + len(c)] += c[:n - s] * 0.8
    k = D["k"]
    dr[s:s + len(k)] += k[:n - s]
    mixd = reverb(lead + pad * 0.8 + dr * 0.7, 1.4, 0.3)
    st = np.stack([mixd, np.roll(mixd, int(0.012 * SR))], axis=1)
    return normalize(st, 0.9)


JINGLES = {
    "capture_jingle": lambda: jingle("G4:0.5 C5:0.5 E5:0.5 G5:0.5 E5:0.5 G5:0.5 C6:3",
                                     [(0, "C", 2), (2, "G", 1), (3, "C", 4)]),
    "victory": lambda: jingle("C5:0.5 E5:0.5 G5:0.5 C6:1.5 B5:0.5 A5:0.5 G5:0.5 A5:0.5 B5:0.5 C6:0.5 D6:0.5 "
                              "E6:1 D6:0.5 E6:0.5 G6:4", [(0, "C", 2.5), (2.5, "F", 2), (4.5, "G", 2.5),
                                                         (7, "C", 5)], bpm=120, dur_extra=2.5),
    "wild": lambda: jingle("E5:0.25 E5:0.25 F5:0.25 G5:0.25 B5:1.5", [(0, "Em", 2.5)], bpm=150, brass=False,
                           dur_extra=0.8),
}
