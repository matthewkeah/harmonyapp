"""sheria_pass1.py — Rule handlers for Pass 1 (Units 1-5)."""

from sheria_base import (
    ErrorDetail, register_handlers, KeySignature, HarmonyRule,
    RomanNumeralAnalyzer,
)

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]

ALL_PAIRS = [
    ["soprano", "alto"], ["soprano", "tenor"], ["soprano", "bass"],
    ["alto", "tenor"], ["alto", "bass"], ["tenor", "bass"],
]

SEMITONE_MAP = {
    "PU": 0, "m2": 1, "M2": 2, "m3": 3, "M3": 4, "P4": 5, "TT": 6,
    "P5": 7, "m6": 8, "M6": 9, "m7": 10, "M7": 11, "P8": 12,
}

OVERLAP_MARGIN = 3

_A = RomanNumeralAnalyzer()


def voice_range(checker, rule, spec, chord, ctx, index):
    voice = spec["voice"]
    n = getattr(chord.slice, voice, None)
    if n is None:
        return []
    if not (spec.get("low", 0) <= n.pitch <= spec.get("high", 127)):
        return [ErrorDetail(f"{rule.error_message} (MIDI {n.pitch})",
                            rule.weight, chord.tick, voices=[voice])]
    return []


def voice_pair_interval(checker, rule, spec, chord, ctx, index):
    a = getattr(chord.slice, spec["voices"][0], None)
    b = getattr(chord.slice, spec["voices"][1], None)
    if a is None or b is None:
        return []
    interval = abs(a.pitch - b.pitch)
    if "max_semitones" in spec and interval > spec["max_semitones"]:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=list(spec["voices"]))]
    if "min_semitones" in spec and interval < spec["min_semitones"]:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=list(spec["voices"]))]
    return []


def voice_crossing(checker, rule, spec, chord, ctx, index):
    faults = []
    prev = checker._prev(ctx, index)
    for i in range(len(VOICE_ORDER) - 1):
        upper_name = VOICE_ORDER[i]
        lower_name = VOICE_ORDER[i + 1]
        upper = getattr(chord.slice, upper_name, None)
        lower = getattr(chord.slice, lower_name, None)
        if upper is None or lower is None:
            continue
        if upper.pitch >= lower.pitch:
            continue
        if prev is not None:
            p_upper = getattr(prev.slice, upper_name, None)
            p_lower = getattr(prev.slice, lower_name, None)
            if p_upper is not None and p_lower is not None \
                    and p_upper.pitch < p_lower.pitch:
                continue
        faults.append(ErrorDetail(
            f"{rule.error_message} "
            f"({upper_name.title()} below {lower_name.title()})",
            rule.weight, chord.tick,
            voices=[upper_name, lower_name]))
    return faults


def voice_overlap(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    faults = []
    for i in range(1, len(VOICE_ORDER)):
        higher = VOICE_ORDER[i - 1]
        lower = VOICE_ORDER[i]

        p_higher = getattr(prev.slice, higher, None)
        p_lower = getattr(prev.slice, lower, None)
        c_higher = getattr(chord.slice, higher, None)
        c_lower = getattr(chord.slice, lower, None)

        if None in (p_higher, p_lower, c_higher, c_lower):
            continue

        lower_overshoot = c_lower.pitch - p_higher.pitch
        if lower_overshoot >= OVERLAP_MARGIN and c_lower.pitch < c_higher.pitch:
            faults.append(ErrorDetail(
                f"{rule.error_message} "
                f"({lower.title()} overlaps previous {higher.title()})",
                rule.weight, chord.tick,
                voices=[lower, higher],
                prev_tick=prev.tick))

        higher_overshoot = p_lower.pitch - c_higher.pitch
        if higher_overshoot >= OVERLAP_MARGIN and c_higher.pitch > c_lower.pitch:
            faults.append(ErrorDetail(
                f"{rule.error_message} "
                f"({higher.title()} overlaps previous {lower.title()})",
                rule.weight, chord.tick,
                voices=[higher, lower],
                prev_tick=prev.tick))
    return faults


def parallel_perfects(checker, rule, spec, chord, ctx, index):
    """Parallel fifths and octaves.

    The error message now includes the previous and current pitches
    of both voices so that a false positive can be told apart from a
    genuine parallel in the fault report.
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    pairs = spec.get("voices") or ALL_PAIRS
    forbidden = spec.get("intervals", ["P5", "P8"])
    faults = []
    for pair in pairs:
        p_top = getattr(prev.slice, pair[0], None)
        p_bot = getattr(prev.slice, pair[1], None)
        c_top = getattr(chord.slice, pair[0], None)
        c_bot = getattr(chord.slice, pair[1], None)
        if None in (p_top, p_bot, c_top, c_bot):
            continue

        top_moved = p_top.pitch != c_top.pitch
        bot_moved = p_bot.pitch != c_bot.pitch
        if not (top_moved and bot_moved):
            continue

        prev_int = abs(p_top.pitch - p_bot.pitch) % 12
        curr_int = abs(c_top.pitch - c_bot.pitch) % 12
        for name in forbidden:
            s = SEMITONE_MAP.get(name, -1) % 12
            if prev_int == s and curr_int == s:
                faults.append(ErrorDetail(
                    f"{rule.error_message} "
                    f"({pair[0].title()}/{pair[1].title()}: "
                    f"{p_top.pitch}-{p_bot.pitch} \u2192 "
                    f"{c_top.pitch}-{c_bot.pitch})",
                    rule.weight, chord.tick,
                    voices=list(pair),
                    prev_tick=prev.tick))
                break
    return faults


def direct_perfects(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if None in (prev.slice.soprano, prev.slice.bass,
                chord.slice.soprano, chord.slice.bass):
        return []

    prev_int = abs(prev.slice.soprano.pitch - prev.slice.bass.pitch) % 12
    curr_int = abs(chord.slice.soprano.pitch - chord.slice.bass.pitch) % 12
    sop_motion = chord.slice.soprano.pitch - prev.slice.soprano.pitch
    bass_motion = chord.slice.bass.pitch - prev.slice.bass.pitch

    if sop_motion == 0 or bass_motion == 0:
        return []

    same_dir = (sop_motion > 0 and bass_motion > 0) or \
               (sop_motion < 0 and bass_motion < 0)
    if not same_dir:
        return []

    sop_step = abs(sop_motion) <= 4
    bass_step = abs(bass_motion) <= 2

    target = spec.get("intervals", ["P5", "P8"])
    for name in target:
        s = SEMITONE_MAP.get(name, -1) % 12
        if curr_int != s or prev_int == s:
            continue
        if sop_step or bass_step:
            continue
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["soprano", "bass"],
                            prev_tick=prev.tick)]
    return []


def doubling_leading_tone(checker, rule, spec, chord, ctx, index):
    if chord.function not in ("dominant", "secondary"):
        return []
    lt_pc = (ctx.key.root_pitch_class + 11) % 12
    max_count = spec.get("max_count", 1)
    hits = [v for v in VOICE_ORDER
            if getattr(chord.slice, v, None) is not None
            and getattr(chord.slice, v).pitch % 12 == lt_pc]
    if len(hits) <= max_count:
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick, voices=hits)]


def doubling_chord_tone(checker, rule, spec, chord, ctx, index):
    if "six_four_types" in spec:
        if chord.six_four_type not in spec["six_four_types"]:
            return []

    info = _A.analyze(chord.slice, ctx.key)
    if info.root_pc == -1 or "7" in info.quality:
        return []
    if "qualities" in spec and info.quality not in spec["qualities"]:
        return []
    if "inversion" in spec and info.inversion != spec["inversion"]:
        return []

    root_pc, quality = info.root_pc, info.quality
    if spec.get("target") == "root":
        target_pc = root_pc
    elif spec.get("target") == "third":
        target_pc = (root_pc + (4 if quality == "Major" else 3)) % 12
    elif spec.get("target") == "fifth":
        if quality in ("Major", "Minor"):
            target_pc = (root_pc + 7) % 12
        elif quality == "Diminished":
            target_pc = (root_pc + 6) % 12
        else:
            target_pc = (root_pc + 8) % 12
    else:
        return []

    hits = [v for v in VOICE_ORDER
            if getattr(chord.slice, v, None) is not None
            and getattr(chord.slice, v).pitch % 12 == target_pc]

    if "max_count" in spec and len(hits) > spec["max_count"]:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick, voices=hits)]
    if "min_count" in spec and len(hits) < spec["min_count"]:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick, voices=hits)]
    return []


def doubling_seventh(checker, rule, spec, chord, ctx, index):
    info = _A.analyze(chord.slice, ctx.key)
    q = info.quality
    if q not in ("Major7", "Dominant7", "Minor7", "HalfDim7", "FullDim7"):
        return []
    root_pc = info.root_pc
    if q == "Major7":
        seventh_pc = (root_pc + 11) % 12
    elif q == "FullDim7":
        seventh_pc = (root_pc + 9) % 12
    else:
        seventh_pc = (root_pc + 10) % 12
    hits = [v for v in VOICE_ORDER
            if getattr(chord.slice, v, None) is not None
            and getattr(chord.slice, v).pitch % 12 == seventh_pc]
    if len(hits) > 1:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=hits)]
    return []


def triad_completeness(checker, rule, spec, chord, ctx, index):
    if chord.metric_position != "strong":
        return []
    if chord.inversion == "64":
        return []
    info = _A.analyze(chord.slice, ctx.key)
    q = info.quality
    if q not in ("Major", "Minor", "Diminished", "Augmented"):
        return []
    root_pc = info.root_pc
    if q in ("Major", "Augmented"):
        third_pc = (root_pc + 4) % 12
    else:
        third_pc = (root_pc + 3) % 12
    hits = [v for v in VOICE_ORDER
            if getattr(chord.slice, v, None) is not None
            and getattr(chord.slice, v).pitch % 12 == third_pc]
    if not hits:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


def no_large_leap(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    voices = spec.get("voices", VOICE_ORDER)
    max_leap = spec.get("max_semitones", 12)
    faults = []
    for vname in voices:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        diff = abs(c.pitch - p.pitch)
        if diff <= max_leap:
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick, voices=[vname], prev_tick=prev.tick))
    return faults


register_handlers({
    "voice_range": voice_range,
    "voice_pair_interval": voice_pair_interval,
    "voice_crossing": voice_crossing,
    "voice_overlap": voice_overlap,
    "parallel_perfects": parallel_perfects,
    "direct_perfects": direct_perfects,
    "doubling_leading_tone": doubling_leading_tone,
    "doubling_chord_tone": doubling_chord_tone,
    "doubling_seventh": doubling_seventh,
    "triad_completeness": triad_completeness,
    "no_large_leap": no_large_leap,
})