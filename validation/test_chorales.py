"""validation/test_chorales.py — Hand-crafted SATB examples that a
theory professor would accept as correct.

Each entry is a Python dict in the same shape as a .sharm file. The
`expected_faults` field lists rule_ids that are legitimately allowed to
fire (usually empty).

These are the ground truth for regression: if the engine reports any
fault on a chorale whose expected_faults list is empty, we have a bug
in the rule layer or the analyzer.

Layout conventions
------------------

The Y_TO_PITCH map in constants.py defines the staff positions this
app uses. For a note to be assigned to the correct voice, EVERY chord
must have exactly:

    * 2 notes on the treble staff  (y < 240)
    * 2 notes on the bass staff    (y >= 240)

If a chord has 3 notes on one staff, assign_voices silently
overwrites the third one's voice number, and every subsequent rule
fires on the wrong data.

Pitch reference for the y-coordinates used below:

    Treble staff:
      y=155 -> E5 (76)     y=160 -> D5 (74)     y=165 -> C5 (72)
      y=170 -> B4 (71)     y=175 -> A4 (69)     y=180 -> G4 (67)
      y=185 -> F4 (65)     y=190 -> E4 (64)     y=195 -> D4 (62)
      y=200 -> C4 (60)

    Bass staff:
      y=270 -> E4 (64)     y=275 -> D4 (62)     y=280 -> C4 (60)
      y=285 -> B3 (59)     y=290 -> A3 (57)     y=295 -> G3 (55)
      y=300 -> F3 (53)     y=305 -> E3 (52)     y=310 -> D3 (50)
      y=315 -> C3 (48)     y=320 -> B2 (47)     y=325 -> A2 (45)

Note that F4 (65) is only available at y=185 on the treble staff
(there is no y-coordinate for it on the bass staff).
"""

# Whole note in 4/4 = 1920 ticks.
_BAR = 1920


def _note(tick, y, ticks=_BAR, accidental=None):
    return {
        "time_ticks": tick,
        "base_y": y,
        "ticks": ticks,
        "accidental": accidental,
        "channel": 0,
        "tied_to_next": False,
        "is_tied_target": False,
    }


def _blank_score(key_name, sig_name, n_bars):
    return {
        "format": "SmartHarmonyWorkspace",
        "version": 2,
        "key": key_name,
        "time_sig": "4/4",
        "tempo": 120,
        "instruments": ["Piano"] * 4,
        "volumes": [100, 100, 100, 100],
        "layout_changes": [[0, "4/4", sig_name]],
        "notes": [],
    }


# ------------------------------------------------------------------
#  Chorale 1 — I-IV-V-I in C major (4 bars, whole notes)
# ------------------------------------------------------------------
#
#  Bar 1 (I):  S=C5  A=E4  T=G3  B=C3
#  Bar 2 (IV): S=C5  A=F4  T=A3  B=F3
#  Bar 3 (V):  S=B4  A=G4  T=D4  B=G3
#  Bar 4 (I):  S=C5  A=E4  T=G3  B=C3
#
#  Cadence: V -> I, root position, soprano ends on C = PAC.
#  Leading tone B4 (bar 3 soprano) resolves up to C5 (bar 4 soprano).

CHORALE_1 = {
    "name": "I-IV-V-I in C major",
    "expected_faults": [],
    "data": dict(_blank_score("C Major", "C Major", 4), notes=[
        # Bar 1 (I)
        _note(0,    165),   # S = C5  (72)
        _note(0,    190),   # A = E4  (64)
        _note(0,    295),   # T = G3  (55)
        _note(0,    315),   # B = C3  (48)
        # Bar 2 (IV)
        _note(_BAR, 165),   # S = C5
        _note(_BAR, 185),   # A = F4  (65)
        _note(_BAR, 290),   # T = A3  (57)
        _note(_BAR, 300),   # B = F3  (53)
        # Bar 3 (V)
        _note(2 * _BAR, 170),  # S = B4  (71)  — leading tone
        _note(2 * _BAR, 180),  # A = G4  (67)
        _note(2 * _BAR, 195),  # T = D4  (62)
        _note(2 * _BAR, 295),  # B = G3  (55)
        # Bar 4 (I)
        _note(3 * _BAR, 165),  # S = C5
        _note(3 * _BAR, 190),  # A = E4
        _note(3 * _BAR, 295),  # T = G3
        _note(3 * _BAR, 315),  # B = C3
    ]),
}


# ------------------------------------------------------------------
#  Chorale 2 — I-vi-IV-ii6-V-I in C major (6 bars)
# ------------------------------------------------------------------
#
#  Bar 1 (I):   S=G4  A=E4  T=C4  B=C3
#  Bar 2 (vi):  S=C5  A=A4  T=C4  B=A3
#  Bar 3 (IV):  S=F4  A=C4  T=A3  B=F3
#  Bar 4 (ii6): S=D5  A=A4  T=D4  B=F3
#  Bar 5 (V):   S=D5  A=G4  T=B3  B=G3
#  Bar 6 (I):   S=C5  A=E4  T=G3  B=C3
#
#  Cadence: V -> I, root position, soprano ends on C = PAC.
#  Leading tone B3 (bar 5 tenor) resolves up to C4 (bar 6 tenor).

CHORALE_2 = {
    "name": "I-vi-IV-ii6-V-I in C major",
    "expected_faults": [],
    "data": dict(_blank_score("C Major", "C Major", 6), notes=[
        # Bar 1 (I)
        _note(0,          180),   # S = G4  (67)
        _note(0,          190),   # A = E4  (64)
        _note(0,          280),   # T = C4  (60)
        _note(0,          315),   # B = C3  (48)
        # Bar 2 (vi)
        _note(_BAR,       165),   # S = C5  (72)
        _note(_BAR,       175),   # A = A4  (69)
        _note(_BAR,       280),   # T = C4  (60)
        _note(_BAR,       290),   # B = A3  (57)
        # Bar 3 (IV)
        _note(2 * _BAR,   185),   # S = F4  (65)
        _note(2 * _BAR,   200),   # A = C4  (60)
        _note(2 * _BAR,   290),   # T = A3  (57)
        _note(2 * _BAR,   300),   # B = F3  (53)
        # Bar 4 (ii6)
        _note(3 * _BAR,   160),   # S = D5  (74)
        _note(3 * _BAR,   175),   # A = A4  (69)
        _note(3 * _BAR,   275),   # T = D4  (62)
        _note(3 * _BAR,   300),   # B = F3  (53)
        # Bar 5 (V)
        _note(4 * _BAR,   160),   # S = D5  (74)
        _note(4 * _BAR,   180),   # A = G4  (67)
        _note(4 * _BAR,   285),   # T = B3  (59)  — leading tone
        _note(4 * _BAR,   295),   # B = G3  (55)
        # Bar 6 (I)
        _note(5 * _BAR,   165),   # S = C5  (72)
        _note(5 * _BAR,   190),   # A = E4  (64)
        _note(5 * _BAR,   295),   # T = G3  (55)
        _note(5 * _BAR,   315),   # B = C3  (48)
    ]),
}


# ------------------------------------------------------------------
#  Chorale 3 — i-iv-V-i in A minor (4 bars)
# ------------------------------------------------------------------
#
#  Bar 1 (i):  S=E4  A=C4  T=A3  B=A2
#  Bar 2 (iv): S=F4  A=D4  T=A3  B=D3
#  Bar 3 (V):  S=B4  A=G#4 T=E4  B=E3      (G# = raised 7th)
#  Bar 4 (i):  S=A4  A=E4  T=C4  B=A2
#
#  Cadence: V -> i, root position, soprano ends on A = PAC.
#  Leading tone G#4 (bar 3 alto) moves to E4 (bar 4 alto), which is
#  the fifth of the tonic triad — the LT rule allows this for inner
#  voices.
#
#  G# requires an explicit sharp accidental because the C-major
#  signature has G natural.

CHORALE_3 = {
    "name": "i-iv-V-i in A minor",
    "expected_faults": [],
    "data": dict(_blank_score("A Minor", "C Major", 4), notes=[
        # Bar 1 (i)
        _note(0,          190),   # S = E4  (64)
        _note(0,          200),   # A = C4  (60)
        _note(0,          290),   # T = A3  (57)
        _note(0,          325),   # B = A2  (45)
        # Bar 2 (iv)
        _note(_BAR,       185),   # S = F4  (65)
        _note(_BAR,       195),   # A = D4  (62)
        _note(_BAR,       290),   # T = A3  (57)
        _note(_BAR,       310),   # B = D3  (50)
        # Bar 3 (V) — G# is the leading tone of A minor
        _note(2 * _BAR,   170),                     # S = B4  (71)
        _note(2 * _BAR,   180, accidental="sharp"), # A = G#4 (68)
        _note(2 * _BAR,   270),                     # T = E4  (64)
        _note(2 * _BAR,   305),                     # B = E3  (52)
        # Bar 4 (i)
        _note(3 * _BAR,   175),   # S = A4  (69)
        _note(3 * _BAR,   190),   # A = E4  (64)
        _note(3 * _BAR,   280),   # T = C4  (60)
        _note(3 * _BAR,   325),   # B = A2  (45)
    ]),
}


# ------------------------------------------------------------------
#  Chorale 4 — I-IV-Ger65-V-I in C major (5 bars)
# ------------------------------------------------------------------
#
#  Bar 1 (I):      S=G4  A=E4  T=C4  B=C3
#  Bar 2 (IV):     S=A4  A=F4  T=C4  B=F3
#  Bar 3 (Ger65):  S=Ab4 A=Eb4 T=C4  B=F#3   (written enharmonically)
#  Bar 4 (V):      S=G4  A=D4  T=B3  B=G3
#  Bar 5 (I):      S=G4  A=E4  T=C4  B=C3
#
#  The Ger65 (Ab-C-Eb-F#) resolves outward on the augmented sixth:
#    * Ab4 (soprano) descends by half step to G4 (bar 4 soprano).
#    * F#3 (bass) ascends by half step to G3 (bar 4 bass).
#
#  Cadence: V -> I, root position, soprano ends on G = IAC (imperfect
#  authentic cadence). Not a PAC, but authentic.
#
#  Note on spelling: this file writes Ab4 as G#4 (sharp at y=180) and
#  Eb4 as Eb4 (flat at y=190). The analyzer works with pitch classes,
#  so enharmonic equivalents are fine for validation.

CHORALE_4 = {
    "name": "I-IV-Ger65-V-I in C major",
    "expected_faults": [],
    "data": dict(_blank_score("C Major", "C Major", 5), notes=[
        # Bar 1 (I)
        _note(0,          180),   # S = G4  (67)
        _note(0,          190),   # A = E4  (64)
        _note(0,          280),   # T = C4  (60)
        _note(0,          315),   # B = C3  (48)
        # Bar 2 (IV)
        _note(_BAR,       175),   # S = A4  (69)
        _note(_BAR,       185),   # A = F4  (65)
        _note(_BAR,       280),   # T = C4  (60)
        _note(_BAR,       300),   # B = F3  (53)
        # Bar 3 (Ger65) — Ab-C-Eb-F#
        _note(2 * _BAR,   180, accidental="sharp"),  # S = G#4 = Ab4 (68)
        _note(2 * _BAR,   190, accidental="flat"),   # A = Eb4 (63)
        _note(2 * _BAR,   280),                       # T = C4  (60)
        _note(2 * _BAR,   300, accidental="sharp"),  # B = F#3 (54)
        # Bar 4 (V)
        _note(3 * _BAR,   180),   # S = G4  (67)
        _note(3 * _BAR,   195),   # A = D4  (62)
        _note(3 * _BAR,   285),   # T = B3  (59)
        _note(3 * _BAR,   295),   # B = G3  (55)
        # Bar 5 (I)
        _note(4 * _BAR,   180),   # S = G4  (67)
        _note(4 * _BAR,   190),   # A = E4  (64)
        _note(4 * _BAR,   280),   # T = C4  (60)
        _note(4 * _BAR,   315),   # B = C3  (48)
    ]),
}


CHORALES = [CHORALE_1, CHORALE_2, CHORALE_3, CHORALE_4]