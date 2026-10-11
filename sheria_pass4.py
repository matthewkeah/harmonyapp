"""sheria_pass4.py — Rule handlers for Pass 4 (Units 16-21)."""

from sheria_base import ErrorDetail, register_handlers, RomanNumeralAnalyzer

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]
_A = RomanNumeralAnalyzer()

_INTERMEDIATE_DEGREES = {2, 5, 8, 9}


def _signed_diff(pc1, pc2):
    d = (pc2 - pc1) % 12
    if d > 6:
        d -= 12
    return d


def _in_sequence(ctx, index, lookback=3):
    chords = ctx.chords
    n = len(chords)

    def motion(i):
        if i < 0 or i + 1 >= n:
            return None
        c1 = chords[i]
        c2 = chords[i + 1]
        if c1.root_pc == -1 or c2.root_pc == -1:
            return None
        return _signed_diff(c1.root_pc, c2.root_pc)

    def matches(ms):
        if any(m is None or m == 0 for m in ms):
            return False
        if (ms[0] > 0) != (ms[1] > 0):
            return False
        return abs(abs(ms[0]) - abs(ms[1])) <= 1

    if index >= lookback:
        ms = [motion(i) for i in range(index - lookback, index)]
        if len(ms) == lookback and all(
                matches(ms[i:i + 2]) for i in range(len(ms) - 1)):
            return True

    if index + lookback <= n - 1:
        ms = [motion(i) for i in range(index, index + lookback)]
        if len(ms) == lookback and all(
                matches(ms[i:i + 2]) for i in range(len(ms) - 1)):
            return True

    return False


def _both_intermediate(prev, chord, ctx):
    key_pc = ctx.key.root_pitch_class
    prev_i = (prev.root_pc - key_pc) % 12
    curr_i = (chord.root_pc - key_pc) % 12
    return (prev_i in _INTERMEDIATE_DEGREES
            and curr_i in _INTERMEDIATE_DEGREES)


def ascending_fifth_retrogression(checker, rule, spec, chord, ctx, index):
    """Root motion by ascending 5th (equivalent to descending 4th in
    the reverse direction).

    Exemptions:
      * I → V (tonic prolongation)
      * IV → I (plagal cadence)
      * Inside a sequence
      * Both chords are intermediates
      * Previous chord is a cadential 6/4
      * Previous chord is an inverted dominant (V6, V65, V43, V42)
      * Target is a descending-2nd motion (V→IV, which is caught
        by P2-NO-RETRO instead; V→ii is the ascending-5th case
        that this rule is designed for)
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.root_pc == -1 or chord.root_pc == -1:
        return []
    if prev.six_four_type == "cadential" or chord.six_four_type == "cadential":
        return []
    if _in_sequence(ctx, index):
        return []
    if _both_intermediate(prev, chord, ctx):
        return []
    diff = (chord.root_pc - prev.root_pc) % 12
    if diff != 7:
        return []
    key_pc = ctx.key.root_pitch_class
    prev_interval = (prev.root_pc - key_pc) % 12
    curr_interval = (chord.root_pc - key_pc) % 12
    if prev_interval == 0 and curr_interval == 7:
        return []
    if prev_interval == 5 and curr_interval == 0:
        return []
    # Skip V → IV (descending 2nd motion, not ascending 5th from ii).
    # Actually V(7) → IV(5) is diff = 10, not 7, so it wouldn't reach
    # here anyway. Kept the check as documentation.
    if prev.function == "dominant" and prev.inversion not in ("root", "7"):
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        prev_tick=prev.tick)]


def minor_v_in_major(checker, rule, spec, chord, ctx, index):
    if ctx.key.mode != "major":
        return []
    info = _A.analyze(chord.slice, ctx.key)
    if info.root_pc == -1:
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if info.root_pc != v_pc:
        return []
    if info.quality != "Minor":
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]


def unknown_consonant_six_four(checker, rule, spec, chord, ctx, index):
    if chord.inversion != "64":
        return []
    if chord.six_four_type in ("cadential", "passing", "neighboring",
                                "arpeggiated"):
        return []
    if chord.metric_position != "strong":
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        voices=["bass"])]


def unresolved_accented_non_chord_tone(checker, rule, spec, chord, ctx, index):
    if chord.metric_position != "strong":
        return []
    if chord.category in ("aug6", "neapolitan", "secondary", "borrowed"):
        return []
    info = _A.analyze(chord.slice, ctx.key)
    if info.root_pc == -1:
        return []
    if "7" in info.quality:
        return []
    if info.quality in ("Sus4", "Sus2", "Add4",
                        "MajorAdd9", "MinorAdd9"):
        return []

    if info.quality == "Major":
        chord_tone_pcs = {info.root_pc,
                          (info.root_pc + 4) % 12,
                          (info.root_pc + 7) % 12}
    elif info.quality == "Minor":
        chord_tone_pcs = {info.root_pc,
                          (info.root_pc + 3) % 12,
                          (info.root_pc + 7) % 12}
    elif info.quality == "Diminished":
        chord_tone_pcs = {info.root_pc,
                          (info.root_pc + 3) % 12,
                          (info.root_pc + 6) % 12}
    elif info.quality == "Augmented":
        chord_tone_pcs = {info.root_pc,
                          (info.root_pc + 4) % 12,
                          (info.root_pc + 8) % 12}
    else:
        return []

    prev = checker._prev(ctx, index)
    nxt = checker._next(ctx, index)
    faults = []
    for vname in VOICE_ORDER:
        n = getattr(chord.slice, vname, None)
        if n is None:
            continue
        if (n.pitch % 12) in chord_tone_pcs:
            continue
        if prev is not None:
            p = getattr(prev.slice, vname, None)
            if p is not None and abs(p.pitch - n.pitch) <= 2:
                continue
        if nxt is not None:
            nn = getattr(nxt.slice, vname, None)
            if nn is not None and abs(nn.pitch - n.pitch) in (1, 2):
                continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick, voices=[vname]))
    return faults


register_handlers({
    "ascending_fifth_retrogression": ascending_fifth_retrogression,
    "minor_v_in_major": minor_v_in_major,
    "unknown_consonant_six_four": unknown_consonant_six_four,
    "unresolved_accented_non_chord_tone": unresolved_accented_non_chord_tone,
})