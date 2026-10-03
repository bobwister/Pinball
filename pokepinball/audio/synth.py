"""Synthèse sonore procédurale (numpy/scipy) : bruitages du flipper."""
import math

import numpy as np
from scipy import signal

SR = 44100
rng = np.random.default_rng(1234)


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------
def tt(dur):
    return np.arange(int(dur * SR)) / SR


def sine(f, dur, phase=0.0):
    t = tt(dur)
    if callable(f):
        f = f(t)
    if not np.isscalar(f):
        f = np.asarray(f)[:len(t)]
        ph = 2 * np.pi * np.cumsum(f) / SR
        return np.sin(ph + phase)
    return np.sin(2 * np.pi * f * t + phase)


def freq_curve(f0, f1, dur, kind="exp"):
    t = tt(dur)
    x = t / max(dur, 1e-6)
    if kind == "exp":
        return f0 * (f1 / f0) ** x
    return f0 + (f1 - f0) * x


def osc(kind, f, dur, duty=0.5):
    """f : fréquence fixe ou tableau de fréquences instantanées."""
    n = int(dur * SR)
    if np.isscalar(f):
        ph = (np.arange(n) * f / SR) % 1.0
    else:
        ph = np.cumsum(f[:n]) / SR % 1.0
    if kind == "sine":
        return np.sin(2 * np.pi * ph)
    if kind == "square":
        return np.where(ph < duty, 1.0, -1.0)
    if kind == "saw":
        return 2.0 * ph - 1.0
    if kind == "tri":
        return 4.0 * np.abs(ph - 0.5) - 1.0
    raise ValueError(kind)


def noise(dur):
    return rng.uniform(-1, 1, int(dur * SR))


def env_exp(dur, decay, attack=0.002):
    t = tt(dur)
    e = np.exp(-t / max(decay, 1e-5))
    a = np.clip(t / max(attack, 1e-5), 0, 1)
    return e * a


def adsr(dur, a=0.01, d=0.1, s=0.7, r=0.1):
    n = int(dur * SR)
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    e[:na] = np.linspace(0, 1, na, endpoint=False) if na else e[:na]
    nd2 = min(nd, max(0, n - na))
    if nd2:
        e[na:na + nd2] = np.linspace(1, s, nd2, endpoint=False)
    if nr and n > nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def lowpass(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "low")
    return signal.lfilter(b, a, x)


def highpass(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "high")
    return signal.lfilter(b, a, x)


def bandpass(x, f1, f2, order=2):
    b, a = signal.butter(order, [max(1e-4, f1 / (SR / 2)), min(0.99, f2 / (SR / 2))], "band")
    return signal.lfilter(b, a, x)


def pad_to(x, n):
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])


def mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n)
    for p in parts:
        out[:len(p)] += p
    return out


def delay(x, sec, fb=0.35, mix_=0.35, n=4):
    d = int(sec * SR)
    out = np.concatenate([x, np.zeros(d * n)])
    tap = x.copy()
    for i in range(1, n + 1):
        tap = tap * fb
        out[d * i:d * i + len(x)] += tap * mix_ / fb
    return out


_ir_cache = {}


def reverb(x, size=1.2, wet=0.25, damp=4000):
    key = (size, damp)
    ir = _ir_cache.get(key)
    if ir is None:
        n = int(size * SR)
        t = np.arange(n) / SR
        ir = rng.normal(0, 1, n) * np.exp(-t * 6.0 / size)
        ir = lowpass(ir, damp)
        ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
        _ir_cache[key] = ir
    wetsig = signal.fftconvolve(x, ir)[:len(x) + len(ir) // 2]
    out = np.zeros(len(wetsig))
    out[:len(x)] += x * (1 - wet * 0.5)
    out += wetsig * wet
    return out


def normalize(x, peak=0.9):
    m = np.max(np.abs(x)) + 1e-9
    return x * (peak / m)


def softclip(x, drive=1.5):
    return np.tanh(x * drive) / np.tanh(drive)


def stereo(x, pan=0.0, width=0.0):
    l = x * math.cos((pan + 1) * math.pi / 4)
    r = x * math.sin((pan + 1) * math.pi / 4)
    if width > 0:
        d = int(0.012 * SR * width)
        r = np.concatenate([np.zeros(d), r])[:len(x)]
    return np.stack([l, r], axis=1)


def to_int16(x, vol=1.0):
    if x.ndim == 1:
        x = stereo(x)
    return np.ascontiguousarray(np.clip(x * vol * 32767, -32767, 32767).astype(np.int16))


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


# --------------------------------------------------------------------------
# Bruitages
# --------------------------------------------------------------------------
def sfx_flipper_up():
    d = 0.11
    thump = sine(freq_curve(160, 55, d), d) * env_exp(d, 0.025) * 0.9
    clack = bandpass(noise(d), 1500, 6000) * env_exp(d, 0.008) * 0.8
    click = highpass(noise(0.01), 4000) * 0.6
    return normalize(mix(thump, clack, click), 0.85)


def sfx_flipper_down():
    d = 0.08
    return normalize(bandpass(noise(d), 800, 4000) * env_exp(d, 0.01) + sine(90, d) * env_exp(d, 0.02) * 0.4, 0.45)


def sfx_bumper():
    d = 0.35
    thump = sine(freq_curve(220, 70, d), d) * env_exp(d, 0.05)
    snap = bandpass(noise(d), 2000, 7000) * env_exp(d, 0.012)
    zap = osc("square", freq_curve(1800, 300, 0.12), 0.12, 0.3) * env_exp(0.12, 0.04) * 0.25
    ring = sine(1320, d) * env_exp(d, 0.09) * 0.12
    return normalize(reverb(mix(thump, snap * 0.9, zap, ring), 0.4, 0.12), 0.95)


def sfx_sling():
    d = 0.18
    thump = sine(freq_curve(180, 60, d), d) * env_exp(d, 0.03)
    snap = bandpass(noise(d), 1200, 5000) * env_exp(d, 0.01)
    return normalize(mix(thump, snap * 0.9), 0.85)


def sfx_spinner():
    d = 0.035
    c = bandpass(noise(d), 3000, 9000) * env_exp(d, 0.004) + sine(2600, d) * env_exp(d, 0.006) * 0.4
    return normalize(c, 0.45)


def sfx_rollover():
    d = 0.12
    blip = osc("square", 1046, d, 0.25) * env_exp(d, 0.03) * 0.4 + osc("square", 1568, d, 0.25) * \
        pad_to(np.zeros(int(0.04 * SR)), int(d * SR)) * 0
    b2 = np.concatenate([np.zeros(int(0.045 * SR)), osc("square", 1568, 0.08, 0.25) * env_exp(0.08, 0.03) * 0.4])
    click = bandpass(noise(0.02), 2000, 6000) * env_exp(0.02, 0.004) * 0.5
    return normalize(mix(blip, b2, click), 0.5)


def sfx_standup():
    d = 0.12
    return normalize(mix(bandpass(noise(d), 1000, 5000) * env_exp(d, 0.01), sine(420, d) * env_exp(d, 0.03) * 0.6), 0.7)


def sfx_drop():
    d = 0.25
    clack = bandpass(noise(d), 900, 4000) * env_exp(d, 0.012)
    thud = sine(freq_curve(140, 50, d), d) * env_exp(d, 0.06) * 0.8
    rustle = bandpass(noise(d), 3000, 8000) * env_exp(d, 0.08) * 0.25
    return normalize(mix(clack, thud, rustle), 0.85)


def sfx_pokeball_hit():
    d = 0.4
    thud = sine(freq_curve(200, 80, d), d) * env_exp(d, 0.05)
    plastic = bandpass(noise(d), 1500, 5000) * env_exp(d, 0.015) * 0.8
    ping = sine(1760, d) * env_exp(d, 0.12) * 0.25 + sine(2637, d) * env_exp(d, 0.08) * 0.15
    return normalize(reverb(mix(thud, plastic, ping), 0.6, 0.15), 0.9)


def sfx_scoop_in():
    d = 0.3
    return normalize(mix(sine(freq_curve(120, 45, d), d) * env_exp(d, 0.08),
                         bandpass(noise(d), 300, 1500) * env_exp(d, 0.04) * 0.6), 0.85)


def sfx_kick():
    d = 0.25
    return normalize(mix(sine(freq_curve(110, 40, d), d) * env_exp(d, 0.05) * 1.2,
                         bandpass(noise(d), 500, 3000) * env_exp(d, 0.02)), 0.95)


def sfx_ramp_enter():
    d = 0.5
    f = freq_curve(400, 1400, d)
    wh = bandpass(noise(d), 600, 2500) * adsr(d, 0.05, 0.2, 0.5, 0.2) * 0.6
    tone = osc("square", f, d, 0.25) * adsr(d, 0.01, 0.1, 0.3, 0.2) * 0.12
    return normalize(mix(wh, tone), 0.5)


def sfx_ramp_made():
    notes = [72, 76, 79, 84, 88]
    out = np.zeros(int(0.7 * SR))
    for i, m in enumerate(notes):
        st = int(i * 0.06 * SR)
        n = osc("square", midi_hz(m), 0.25, 0.25) * env_exp(0.25, 0.08) * 0.35
        n += sine(midi_hz(m) * 2, 0.25) * env_exp(0.25, 0.06) * 0.2
        out[st:st + len(n)] += n
    return normalize(reverb(out, 0.8, 0.25), 0.7)


def sfx_ramp_fail():
    d = 0.4
    return normalize(osc("square", freq_curve(500, 150, d), d, 0.3) * adsr(d, 0.01, 0.1, 0.4, 0.2) * 0.3, 0.4)


def sfx_orbit():
    d = 0.55
    wh = bandpass(noise(d), 400, 3000) * np.sin(np.linspace(0, np.pi, int(d * SR))) * 0.6
    sw = osc("saw", freq_curve(200, 900, d), d) * np.sin(np.linspace(0, np.pi, int(d * SR))) * 0.15
    return normalize(lowpass(mix(wh, sw), 4000), 0.55)


def sfx_plunger():
    d = 0.3
    return normalize(mix(sine(freq_curve(90, 40, d), d) * env_exp(d, 0.06), bandpass(noise(d), 800, 5000) *
                         env_exp(d, 0.015) * 0.9, sine(1200, d) * env_exp(d, 0.05) * 0.15), 0.9)


def sfx_drain():
    notes = [67, 63, 60, 55]
    out = np.zeros(int(1.2 * SR))
    for i, m in enumerate(notes):
        st = int(i * 0.16 * SR)
        n = osc("tri", midi_hz(m), 0.4, 0.5) * adsr(0.4, 0.01, 0.1, 0.6, 0.15) * 0.5
        out[st:st + len(n)] += n
    return normalize(reverb(out, 1.0, 0.3), 0.6)


def arpeggio(notes, step=0.07, dur=0.3, kind="square", duty=0.25, decay=0.1, vol=0.4, verb=0.3):
    total = step * len(notes) + dur + 0.1
    out = np.zeros(int(total * SR))
    for i, m in enumerate(notes):
        if m is None:
            continue
        st = int(i * step * SR)
        n = osc(kind, midi_hz(m), dur, duty) * env_exp(dur, decay) * vol
        n += sine(midi_hz(m), dur) * env_exp(dur, decay * 1.5) * vol * 0.5
        out[st:st + len(n)] += n
    return normalize(reverb(out, 1.0, verb), 0.8)


def chord_hit(notes, dur=1.2, vol=0.5, kind="saw", verb=0.35, lp=5000):
    out = np.zeros(int(dur * SR))
    for m in notes:
        for det in (-0.08, 0.0, 0.08):
            f = midi_hz(m + det)
            out += osc(kind, f, dur) * adsr(dur, 0.005, 0.25, 0.4, 0.4) * vol / len(notes)
    out = lowpass(out, lp)
    boom = sine(freq_curve(120, 40, 0.6), 0.6) * env_exp(0.6, 0.15) * 0.8
    return normalize(reverb(mix(out, boom), 1.4, verb), 0.9)


def sfx_jackpot():
    a = arpeggio([60, 64, 67, 72, 76, 79, 84], step=0.05, dur=0.35, vol=0.4)
    c = chord_hit([60, 64, 67, 72], 1.4)
    return normalize(mix(a, np.concatenate([np.zeros(int(0.32 * SR)), c])), 0.95)


def sfx_super_jackpot():
    a = arpeggio([60, 64, 67, 72, 76, 79, 84, 88, 91, 96], step=0.045, dur=0.4, vol=0.4)
    c = chord_hit([60, 64, 67, 72, 76], 2.2)
    sw = bandpass(noise(1.5), 2000, 9000) * np.linspace(0, 1, int(1.5 * SR)) ** 2 * 0.2
    return normalize(mix(sw, np.concatenate([np.zeros(int(0.45 * SR)), a]),
                         np.concatenate([np.zeros(int(0.9 * SR)), c])), 0.95)


def sfx_multiball_start():
    r = noise(1.2)
    siren = osc("square", 600 + 300 * np.sin(2 * np.pi * 4 * tt(1.2)), 1.2, 0.5) * 0.15
    c = chord_hit([57, 61, 64, 69], 1.6)
    return normalize(mix(siren * adsr(1.2, 0.05, 0.2, 0.8, 0.3), np.concatenate([np.zeros(int(1.0 * SR)), c])), 0.9)


def sfx_extra_ball():
    return arpeggio([67, 72, 76, 79, 84, None, 79, 84, 88, 91], step=0.09, dur=0.4, vol=0.4, verb=0.35)


def sfx_skill_shot():
    return arpeggio([72, 79, 84, 91, 96], step=0.06, dur=0.4, kind="square", duty=0.125, vol=0.45)


def sfx_combo():
    return arpeggio([76, 83, 88], step=0.05, dur=0.2, vol=0.35, verb=0.2)


def sfx_lanes_complete():
    return arpeggio([72, 74, 76, 79, 81, 84], step=0.05, dur=0.2, vol=0.35, verb=0.2)


def sfx_mystery():
    out = arpeggio([60 + (i * 5) % 24 for i in range(18)], step=0.06, dur=0.12, vol=0.3, verb=0.2)
    return mix(out, np.concatenate([np.zeros(int(1.2 * SR)), arpeggio([72, 76, 79, 84], 0.06, 0.4)]))


def sfx_select_tick():
    d = 0.06
    return normalize(osc("square", 1318, d, 0.25) * env_exp(d, 0.02), 0.35)


def sfx_select_confirm():
    return arpeggio([67, 74, 79], step=0.05, dur=0.25, vol=0.4, verb=0.2)


def sfx_select_open():
    d = 0.8
    return normalize(lowpass(osc("saw", freq_curve(100, 800, d), d), 2500) * adsr(d, 0.02, 0.2, 0.6, 0.3) * 0.4, 0.6)


def sfx_wild_appears():
    out = np.zeros(int(1.0 * SR))
    for i in range(12):
        st = int(i * 0.05 * SR)
        n = osc("square", midi_hz(84 - (i % 4) * 3), 0.06, 0.5) * 0.25
        out[st:st + len(n)] += n
    return normalize(reverb(out, 0.6, 0.2), 0.6)


def sfx_shake():
    d = 0.35
    wob = osc("tri", freq_curve(300, 200, d), d) * (0.5 + 0.5 * np.sin(2 * np.pi * 14 * tt(d))) * adsr(d, 0.01, 0.1, 0.6, 0.1)
    click = np.concatenate([np.zeros(int(0.28 * SR)), bandpass(noise(0.05), 2000, 7000) * env_exp(0.05, 0.006)])
    return normalize(mix(wob * 0.4, click), 0.6)


def sfx_gotcha():
    click = bandpass(noise(0.05), 2000, 8000) * env_exp(0.05, 0.005)
    fan = arpeggio([72, 76, 79, 84, 79, 84, 88], step=0.11, dur=0.45, kind="square", duty=0.25, vol=0.35,
                   verb=0.35)
    spark = bandpass(noise(1.0), 5000, 12000) * env_exp(1.0, 0.3) * 0.25
    return normalize(mix(click, np.concatenate([np.zeros(int(0.15 * SR)), spark]),
                         np.concatenate([np.zeros(int(0.3 * SR)), fan])), 0.9)


def sfx_gotcha_small():
    return arpeggio([79, 84, 88, 91], step=0.07, dur=0.3, vol=0.35, verb=0.25)


def sfx_weakened():
    d = 0.8
    return normalize(osc("square", freq_curve(900, 200, d), d, 0.4) * adsr(d, 0.01, 0.2, 0.5, 0.3) * 0.3, 0.5)


def sfx_break_free():
    d = 0.5
    pop = mix(bandpass(noise(d), 500, 4000) * env_exp(d, 0.04), sine(freq_curve(300, 900, d), d) * env_exp(d, 0.1) * 0.5)
    return normalize(reverb(pop, 0.6, 0.2), 0.8)


def sfx_escaped():
    return arpeggio([72, 67, 63, 60, 55], step=0.12, dur=0.4, kind="tri", vol=0.5, verb=0.4)


def sfx_tilt_warning():
    d = 0.6
    return normalize(osc("square", 140, d, 0.5) * adsr(d, 0.005, 0.05, 0.9, 0.05) * 0.4, 0.6)


def sfx_tilt():
    d = 1.6
    return normalize(lowpass(osc("saw", freq_curve(160, 40, d), d), 900) * adsr(d, 0.01, 0.3, 0.8, 0.4), 0.8)


def sfx_start():
    return arpeggio([60, 64, 67, 72, None, 67, 72, 76, 79], step=0.1, dur=0.4, vol=0.4, verb=0.35)


def sfx_nudge():
    d = 0.15
    return normalize(sine(freq_curve(80, 40, d), d) * env_exp(d, 0.05) + bandpass(noise(d), 200, 900) *
                     env_exp(d, 0.03) * 0.5, 0.7)


def sfx_ball_saved():
    return arpeggio([72, 76, 79, 76, 84], step=0.08, dur=0.3, kind="tri", vol=0.5, verb=0.3)


def sfx_eb_lit():
    return arpeggio([79, 84, 79, 84, 91], step=0.07, dur=0.25, vol=0.35, verb=0.25)


def sfx_mode_lit():
    return arpeggio([64, 68, 71, 76, 80, 83], step=0.07, dur=0.35, kind="saw", vol=0.3, verb=0.4)


def sfx_evolve():
    return arpeggio([60 + i for i in range(0, 25, 2)], step=0.035, dur=0.2, vol=0.3, verb=0.3)


def sfx_rocket_alarm():
    d = 1.4
    f = 700 + 300 * np.sign(np.sin(2 * np.pi * 3 * tt(d)))
    return normalize(osc("square", f, d, 0.5) * adsr(d, 0.01, 0.1, 0.8, 0.2) * 0.3, 0.55)


def sfx_rocket_blast():
    d = 1.6
    whoosh = bandpass(noise(d), 1000, 6000) * np.linspace(1, 0, int(d * SR)) ** 2
    rise = osc("sine", freq_curve(300, 2400, d), d) * adsr(d, 0.01, 0.2, 0.4, 0.5) * 0.4
    ping = np.concatenate([np.zeros(int(1.3 * SR)), sine(3520, 0.4) * env_exp(0.4, 0.1) * 0.6])
    return normalize(mix(whoosh * 0.5, rise, ping), 0.85)


def sfx_outlane():
    d = 0.5
    return normalize(osc("tri", freq_curve(500, 120, d), d) * adsr(d, 0.01, 0.1, 0.6, 0.2) * 0.4, 0.5)


def sfx_lane_change():
    d = 0.04
    return normalize(osc("square", 2093, d, 0.25) * env_exp(d, 0.01), 0.2)


def sfx_add_player():
    return arpeggio([72, 79], step=0.08, dur=0.25, vol=0.4, verb=0.2)


def sfx_hit_generic():
    d = 0.3
    return normalize(mix(sine(freq_curve(300, 80, d), d) * env_exp(d, 0.06), bandpass(noise(d), 800, 5000) *
                         env_exp(d, 0.03)), 0.8)


# --- attaques par type ---------------------------------------------------
def sfx_ice():
    d = 0.7
    shimmer = mix(*[sine(f, d) * env_exp(d, 0.25) * 0.15 for f in (2093, 2637, 3136, 4186)])
    crack = bandpass(noise(d), 3000, 10000) * env_exp(d, 0.03)
    return normalize(reverb(mix(shimmer, crack * 0.7, sine(freq_curve(400, 120, 0.2), 0.2) * env_exp(0.2, 0.05)),
                            1.0, 0.35), 0.85)


def sfx_thunder():
    d = 1.4
    crack = highpass(noise(0.15), 1500) * env_exp(0.15, 0.03)
    rumble = lowpass(noise(d), 300) * env_exp(d, 0.5) * 3
    zap = osc("square", 80 + 40 * rng.random(int(0.3 * SR)), 0.3, 0.5) * env_exp(0.3, 0.1) * 0.2
    return normalize(reverb(mix(crack, rumble, zap), 1.2, 0.3), 0.95)


def sfx_zap():
    d = 0.35
    f = 400 + 900 * rng.random(int(d * SR))
    return normalize(mix(osc("square", lowpass(f, 300), d, 0.4) * env_exp(d, 0.1) * 0.5,
                         highpass(noise(d), 3000) * env_exp(d, 0.05) * 0.4), 0.8)


def sfx_fire():
    d = 0.9
    roar = bandpass(noise(d), 200, 2500) * adsr(d, 0.05, 0.2, 0.6, 0.4)
    crackle = highpass(noise(d), 4000) * (rng.random(int(d * SR)) > 0.995) * 3
    boom = sine(freq_curve(120, 40, 0.5), 0.5) * env_exp(0.5, 0.12)
    return normalize(reverb(mix(roar, crackle, boom), 0.9, 0.3), 0.9)


def sfx_water():
    d = 0.9
    splash = bandpass(noise(d), 500, 6000) * env_exp(d, 0.15)
    bubbles = np.zeros(int(d * SR))
    for i in range(10):
        st = int(rng.uniform(0.05, 0.7) * SR)
        f0 = rng.uniform(400, 1200)
        b = sine(freq_curve(f0, f0 * 1.8, 0.06), 0.06) * env_exp(0.06, 0.02) * 0.3
        bubbles[st:st + len(b)] += b
    return normalize(reverb(mix(splash, bubbles), 0.9, 0.3), 0.85)


def sfx_psychic():
    d = 1.0
    f = 300 + 120 * np.sin(2 * np.pi * 6 * tt(d))
    w = osc("sine", f, d) * adsr(d, 0.05, 0.2, 0.7, 0.4) * 0.5 + osc("sine", f * 1.5, d) * adsr(d, 0.1, 0.2, 0.5, 0.4) * 0.3
    return normalize(reverb(delay(w, 0.12, 0.4, 0.4), 1.2, 0.4), 0.8)


def sfx_rock():
    d = 0.8
    return normalize(reverb(mix(lowpass(noise(d), 600) * env_exp(d, 0.15) * 2,
                                sine(freq_curve(90, 30, d), d) * env_exp(d, 0.2) * 1.2,
                                bandpass(noise(0.1), 1000, 4000) * env_exp(0.1, 0.02)), 0.8, 0.25), 0.95)


def sfx_dragon():
    d = 1.0
    roar = lowpass(osc("saw", freq_curve(140, 90, d) * (1 + 0.05 * np.sin(2 * np.pi * 30 * tt(d))), d), 1500)
    return normalize(reverb(roar * adsr(d, 0.05, 0.2, 0.7, 0.4) + bandpass(noise(d), 300, 3000) *
                            adsr(d, 0.05, 0.2, 0.4, 0.4) * 0.4, 1.0, 0.3), 0.85)


def sfx_earthquake():
    d = 2.2
    rum = lowpass(noise(d), 120) * adsr(d, 0.2, 0.3, 0.8, 0.8) * 4
    return normalize(mix(rum, sine(35 + 5 * np.sin(2 * np.pi * 8 * tt(d)), d) * adsr(d, 0.2, 0.2, 0.7, 0.8)), 0.95)


def sfx_teleport():
    d = 0.4
    return normalize(osc("sine", freq_curve(2000, 200, d), d) * env_exp(d, 0.12) * 0.5 +
                     osc("sine", freq_curve(200, 2000, d), d) * env_exp(d, 0.12) * 0.3, 0.6)


def sfx_mew_giggle():
    notes = [88, 91, 93, 91, 96]
    return arpeggio(notes, step=0.07, dur=0.15, kind="sine", vol=0.5, verb=0.4)


def sfx_shield_break():
    d = 0.8
    glass = mix(*[sine(f, d) * env_exp(d, rng.uniform(0.05, 0.3)) * 0.2 for f in rng.uniform(2000, 7000, 10)])
    crash = highpass(noise(d), 2500) * env_exp(d, 0.08)
    return normalize(reverb(mix(glass, crash), 0.8, 0.3), 0.85)


def roar(base_f, dur=1.6, growl=1.0, bright=2500, seed=0):
    r = np.random.default_rng(seed)
    t = tt(dur)
    vib = 1 + 0.06 * np.sin(2 * np.pi * (5 + r.random() * 4) * t) + 0.02 * r.normal(0, 1, len(t))
    f = base_f * vib * np.interp(t, [0, dur * 0.2, dur * 0.7, dur], [0.8, 1.15, 1.0, 0.7])
    src = osc("saw", f, dur) * 0.6 + osc("square", f * 0.5, dur, 0.3) * 0.3 * growl
    src += bandpass(noise(dur), 300, bright) * 0.4 * growl
    # formants
    out = bandpass(src, 250, 900) * 1.0 + bandpass(src, 1000, 1800) * 0.6 +         bandpass(src, min(2200, bright - 400), bright + 200) * 0.3
    e = adsr(dur, 0.08, 0.3, 0.8, 0.6)
    return normalize(reverb(softclip(out * e, 2.0), 1.4, 0.35), 0.9)


ROARS = {
    "articuno": (520, 1.6, 0.5, 6000), "zapdos": (420, 1.4, 1.2, 5000), "moltres": (460, 1.6, 0.9, 5500),
    "raikou": (150, 1.8, 1.4, 3000), "entei": (120, 1.9, 1.6, 2800), "suicune": (300, 1.7, 0.6, 4500),
    "lugia": (240, 2.2, 0.6, 4000), "hooh": (380, 2.0, 0.8, 5000), "groudon": (70, 2.4, 2.0, 2000),
    "kyogre": (90, 2.4, 1.2, 2200), "rayquaza": (160, 2.2, 1.6, 3500), "mew": (900, 1.0, 0.2, 7000),
    "mewtwo": (110, 2.6, 1.5, 3000),
}


SFX = {
    "flipper_up": sfx_flipper_up, "flipper_down": sfx_flipper_down, "bumper": sfx_bumper, "sling": sfx_sling,
    "spinner": sfx_spinner, "rollover": sfx_rollover, "standup": sfx_standup, "drop": sfx_drop,
    "pokeball_hit": sfx_pokeball_hit, "scoop_in": sfx_scoop_in, "scoop_kick": sfx_kick, "kickback": sfx_kick,
    "ramp_enter": sfx_ramp_enter, "ramp_made": sfx_ramp_made, "ramp_fail": sfx_ramp_fail, "ramp_exit": sfx_standup,
    "orbit": sfx_orbit, "plunger": sfx_plunger, "autolaunch": sfx_plunger, "drain": sfx_drain,
    "ball_saved": sfx_ball_saved, "lane_change": sfx_lane_change, "lanes_complete": sfx_lanes_complete,
    "outlane": sfx_outlane, "nudge": sfx_nudge, "tilt_warning": sfx_tilt_warning, "tilt": sfx_tilt,
    "start": sfx_start, "add_player": sfx_add_player, "skill_shot": sfx_skill_shot, "combo": sfx_combo,
    "jackpot": sfx_jackpot, "super_jackpot": sfx_super_jackpot, "multiball_start": sfx_multiball_start,
    "extra_ball": sfx_extra_ball, "eb_lit": sfx_eb_lit, "mystery": sfx_mystery, "mode_lit": sfx_mode_lit,
    "select_open": sfx_select_open, "select_tick": sfx_select_tick, "select_confirm": sfx_select_confirm,
    "wild_appears": sfx_wild_appears, "gotcha_small": sfx_gotcha_small, "gotcha": sfx_gotcha, "shake": sfx_shake,
    "weakened": sfx_weakened, "break_free": sfx_break_free, "escaped": sfx_escaped, "evolve": sfx_evolve,
    "rocket_alarm": sfx_rocket_alarm, "rocket_blast": sfx_rocket_blast,
    "hit_Glace": sfx_ice, "hit_Électrik": sfx_zap, "hit_Feu": sfx_fire, "hit_Eau": sfx_water,
    "hit_Psy": sfx_psychic, "hit_Sol": sfx_rock, "hit_Dragon": sfx_dragon,
    "thunder": sfx_thunder, "charge_full": sfx_evolve, "fizzle": sfx_ramp_fail, "fireball": sfx_fire,
    "zap": sfx_zap, "eruption": sfx_rock, "splash": sfx_water, "aeroblast": sfx_psychic,
    "sacred_fire": sfx_fire, "earthquake": sfx_earthquake, "rock_smash": sfx_rock, "wave": sfx_water,
    "dragon": sfx_dragon, "teleport": sfx_teleport, "mew_giggle": sfx_mew_giggle, "shield_break": sfx_shield_break,
    "hit_wall": lambda: normalize(bandpass(noise(0.05), 600, 3000) * env_exp(0.05, 0.008), 0.5),
    "hit_rubber": lambda: normalize(mix(sine(freq_curve(200, 90, 0.08), 0.08) * env_exp(0.08, 0.02),
                                        bandpass(noise(0.05), 400, 2000) * env_exp(0.05, 0.01) * 0.5), 0.5),
    "hit_metal": lambda: normalize(mix(bandpass(noise(0.05), 2000, 8000) * env_exp(0.05, 0.006),
                                       sine(3100, 0.15) * env_exp(0.15, 0.04) * 0.3), 0.5),
    "ball_click": lambda: normalize(mix(sine(4200, 0.05) * env_exp(0.05, 0.01), highpass(noise(0.02), 3000) *
                                        env_exp(0.02, 0.003)), 0.6),
}
for _k, (_f, _d, _g, _b) in ROARS.items():
    SFX["roar_" + _k] = (lambda f=_f, d=_d, g=_g, b=_b, k=_k: roar(f, d, g, b, seed=hash(k) % 1000))


def loop_roll():
    """Grondement de roulement (boucle)."""
    d = 1.0
    x = lowpass(noise(d), 380) * 2.5 + bandpass(noise(d), 800, 2000) * 0.3
    x = normalize(x, 0.6)
    fade = int(0.05 * SR)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x


def loop_wire():
    d = 1.0
    x = bandpass(noise(d), 1500, 6000) * (0.6 + 0.4 * np.sin(2 * np.pi * 37 * tt(d)))
    x += sine(2900, d) * 0.05
    x = normalize(x, 0.5)
    fade = int(0.05 * SR)
    x[:fade] *= np.linspace(0, 1, fade)
    x[-fade:] *= np.linspace(1, 0, fade)
    return x
