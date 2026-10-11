"""sheria_pass2.py — Rule handlers for Pass 2 (Units 6-10)."""

from sheria_base import (
    ErrorDetail, register_handlers, RomanNumeralAnalyzer,
)

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]
_A = RomanNumeralAnalyzer()


def _is_identifiable(chord):
    """True when the chord has a real root, function, and label.

    The chord's Roman numeral label is stored in `numeral`, not
    `label` — see the AnalyzedChord dataclass in harmony_context.py.
    """
    if chord.category in ("sparse", "unknown"):
        return False
    if chord.root_pc == -1:
        return False
    if not chord.numeral or chord.numeral in ("", "?"):
        return False
    return True


def leading_tone_resolution(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []

    if prev.function != "dominant":
        return []

    lt_pc = (ctx.key.root_pitch_class + 11) % 12

    if any(n.pitch % 12 == lt_pc for n in chord.slice.get_notes()):
        return []

    voices = spec.get("voices", VOICE_ORDER)
    fifth_pc = (ctx.key.root_pitch_class + 7) % 12
    tonic_pc = ctx.key.root_pitch_class

    faults = []
    for vname in voices:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if not ctx.key.is_leading_tone(p.pitch):
            continue

        diff = c.pitch - p.pitch
        target_pc = c.pitch % 12

        if diff == 1 and target_pc == tonic_pc:
            continue

        if vname in ("alto", "tenor") and abs(diff) <= 2:
            continue

        if vname in ("alto", "tenor") and target_pc == fifth_pc:
            continue

        if prev.inversion == "43" and chord.inversion == "6" and diff > 0:
            continue

        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick,
            voices=[vname], prev_tick=prev.tick))
    return faults


def seventh_resolution(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    prev_info = _A.analyze(prev.slice, ctx.key)
    if prev_info.root_pc == -1 or "7" not in prev_info.quality:
        return []

    if prev.category not in ("diatonic", "secondary"):
        return []

    root_pc = prev_info.root_pc
    quality = prev_info.quality
    if quality == "Major7":
        seventh_pc = (root_pc + 11) % 12
    elif quality == "FullDim7":
        seventh_pc = (root_pc + 9) % 12
    else:
        seventh_pc = (root_pc + 10) % 12

    if any(n.pitch % 12 == seventh_pc for n in chord.slice.get_notes()):
        return []

    allow_upward = (prev.inversion == "43" and chord.inversion == "6")
    faults = []
    for vname in VOICE_ORDER:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if p.pitch % 12 != seventh_pc:
            continue
        diff = c.pitch - p.pitch
        if diff in (-1, -2):
            continue
        if allow_upward and diff in (1, 2):
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick,
            voices=[vname], prev_tick=prev.tick))
    return faults


def cadence_requires_root_position(checker, rule, spec, chord, ctx, index):
    if chord.cadence_type not in ("perfect_authentic", "imperfect_authentic"):
        return []
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.inversion != "root" or chord.inversion != "root":
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    return []


def perfect_authentic_requires_tonic_soprano(checker, rule, spec, chord, ctx, index):
    if chord.cadence_type != "perfect_authentic":
        return []
    if chord.slice.soprano is None:
        return []
    if (chord.slice.soprano.pitch % 12) != ctx.key.root_pitch_class:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["soprano"])]
    return []


def leading_tone_must_resolve_at_cadence(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if chord.cadence_type not in ("perfect_authentic", "imperfect_authentic"):
        return []
    voices = spec.get("voices", ["soprano", "bass"])
    faults = []
    for vname in voices:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if not ctx.key.is_leading_tone(p.pitch):
            continue
        if c.pitch == p.pitch + 1 and ctx.key.is_tonic(c.pitch):
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick,
            voices=[vname], prev_tick=prev.tick))
    return faults


def cadential_6_4_bass_doubled(checker, rule, spec, chord, ctx, index):
    if chord.six_four_type != "cadential":
        return []
    if chord.slice.bass is None:
        return []
    bass_pc = chord.slice.bass.pitch % 12
    count = sum(1 for n in chord.slice.get_notes() if n.pitch % 12 == bass_pc)
    if count < spec.get("min_count", 2):
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"])]
    return []


def cadential_6_4_no_doubled_fourth(checker, rule, spec, chord, ctx, index):
    if chord.six_four_type != "cadential":
        return []
    if chord.slice.bass is None:
        return []
    fourth_pc = (chord.slice.bass.pitch + 5) % 12
    count = sum(1 for n in chord.slice.get_notes() if n.pitch % 12 == fourth_pc)
    if count >= 2:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


def cadential_6_4_must_resolve_to_V(checker, rule, spec, chord, ctx, index):
    if chord.six_four_type != "cadential":
        return []
    nxt = checker._next(ctx, index)
    if nxt is None:
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if nxt.root_pc != v_pc:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


def cadential_6_4_strong_beat(checker, rule, spec, chord, ctx, index):
    if chord.six_four_type != "cadential":
        return []
    if chord.metric_position == "weak":
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


def cadential_6_4_4th_resolution(checker, rule, spec, chord, ctx, index):
    if chord.six_four_type != "cadential":
        return []
    nxt = checker._next(ctx, index)
    if nxt is None:
        return []
    tonic_pc = ctx.key.root_pitch_class
    faults = []
    for vname in ("soprano", "alto", "tenor"):
        n = getattr(chord.slice, vname, None)
        if n is None:
            continue
        if n.pitch % 12 != tonic_pc:
            continue
        nn = getattr(nxt.slice, vname, None)
        if nn is None:
            continue
        diff = nn.pitch - n.pitch
        if diff not in (-1, -2):
            faults.append(ErrorDetail(rule.error_message, rule.weight,
                                      chord.tick, voices=[vname],
                                      prev_tick=chord.tick))
    return faults


def opening_chord_must_be_tonic(checker, rule, spec, chord, ctx, index):
    if index != 0:
        return []
    if not _is_identifiable(chord):
        return []
    if chord.function == "tonic":
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]


def closing_chord_must_be_tonic(checker, rule, spec, chord, ctx, index):
    if index != len(ctx.chords) - 1:
        return []
    if not _is_identifiable(chord):
        return []
    if chord.function != "tonic":
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    if chord.inversion != "root":
        return [ErrorDetail(rule.error_message + " (must be root position)",
                            rule.weight, chord.tick)]
    return []


def cadence_at_closing(checker, rule, spec, chord, ctx, index):
    if index != len(ctx.chords) - 1:
        return []
    if not _is_identifiable(chord):
        return []
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if not _is_identifiable(prev):
        return []
    if chord.cadence_type in ("perfect_authentic", "imperfect_authentic"):
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]


def no_retrogression(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if not _is_identifiable(prev) or not _is_identifiable(chord):
        return []
    if prev.function == "dominant" and chord.function == "predominant":
        if chord.root_pc == (ctx.key.root_pitch_class + 9) % 12:
            return []
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            prev_tick=prev.tick)]
    return []


def intermediate_must_not_resolve_to_tonic(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if not _is_identifiable(prev) or not _is_identifiable(chord):
        return []
    if prev.function != "predominant":
        return []
    if chord.function != "tonic":
        return []
    key_pc = ctx.key.root_pitch_class
    iv_pc = (key_pc + 5) % 12
    if prev.root_pc == iv_pc:
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        prev_tick=prev.tick)]


def v7_must_not_go_to_i6(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if prev.root_pc != v_pc:
        return []
    if "7" not in prev.quality:
        return []
    key_pc = ctx.key.root_pitch_class
    if chord.root_pc != key_pc:
        return []
    if chord.inversion != "6":
        return []
    if prev.inversion == "43":
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        voices=["bass"], prev_tick=prev.tick)]


def v65_bass_must_ascend(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.inversion != "65":
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if prev.root_pc != v_pc:
        return []
    if None in (prev.slice.bass, chord.slice.bass):
        return []
    if chord.slice.bass.pitch <= prev.slice.bass.pitch:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    return []


def v42_must_resolve_to_i6(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.inversion != "42":
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if prev.root_pc != v_pc:
        return []
    key_pc = ctx.key.root_pitch_class
    if chord.root_pc != key_pc:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    if chord.inversion != "6":
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    return []


def v43_resolution_appropriate(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.inversion != "43":
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if prev.root_pc != v_pc:
        return []
    key_pc = ctx.key.root_pitch_class
    if chord.root_pc != key_pc:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    if chord.inversion not in ("6", "root"):
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=["bass"], prev_tick=prev.tick)]
    return []


def weak_strong_same_chord(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if not _is_identifiable(prev) or not _is_identifiable(chord):
        return []
    if prev.metric_position != "weak":
        return []
    if chord.metric_position not in ("strong", "medium"):
        return []
    if prev.root_pc == chord.root_pc and prev.inversion == chord.inversion:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            prev_tick=prev.tick)]
    return []


def v7_i_similar_to_doubled_3rd(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if "7" not in prev.quality:
        return []
    v_pc = (ctx.key.root_pitch_class + 7) % 12
    if prev.root_pc != v_pc:
        return []
    key_pc = ctx.key.root_pitch_class
    if chord.root_pc != key_pc:
        return []
    if chord.inversion != "root":
        return []
    third_pc = (key_pc + 4) % 12
    hits = [v for v in VOICE_ORDER
            if getattr(chord.slice, v, None) is not None
            and getattr(chord.slice, v).pitch % 12 == third_pc]
    if len(hits) < 2:
        return []
    if None in (prev.slice.soprano, prev.slice.bass,
                chord.slice.soprano, chord.slice.bass):
        return []
    sop_diff = chord.slice.soprano.pitch - prev.slice.soprano.pitch
    bass_diff = chord.slice.bass.pitch - prev.slice.bass.pitch
    same_dir = (sop_diff > 0 and bass_diff > 0) or (sop_diff < 0 and bass_diff < 0)
    if same_dir:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                            voices=hits, prev_tick=prev.tick)]
    return []


register_handlers({
    "leading_tone_resolution": leading_tone_resolution,
    "seventh_resolution": seventh_resolution,
    "cadence_requires_root_position": cadence_requires_root_position,
    "perfect_authentic_requires_tonic_soprano": perfect_authentic_requires_tonic_soprano,
    "leading_tone_must_resolve_at_cadence": leading_tone_must_resolve_at_cadence,
    "cadential_6_4_bass_doubled": cadential_6_4_bass_doubled,
    "cadential_6_4_no_doubled_fourth": cadential_6_4_no_doubled_fourth,
    "cadential_6_4_must_resolve_to_V": cadential_6_4_must_resolve_to_V,
    "cadential_6_4_strong_beat": cadential_6_4_strong_beat,
    "cadential_6_4_4th_resolution": cadential_6_4_4th_resolution,
    "opening_chord_must_be_tonic": opening_chord_must_be_tonic,
    "closing_chord_must_be_tonic": closing_chord_must_be_tonic,
    "cadence_at_closing": cadence_at_closing,
    "no_retrogression": no_retrogression,
    "intermediate_must_not_resolve_to_tonic": intermediate_must_not_resolve_to_tonic,
    "v7_must_not_go_to_i6": v7_must_not_go_to_i6,
    "v65_bass_must_ascend": v65_bass_must_ascend,
    "v42_must_resolve_to_i6": v42_must_resolve_to_i6,
    "v43_resolution_appropriate": v43_resolution_appropriate,
    "weak_strong_same_chord": weak_strong_same_chord,
    "v7_i_similar_to_doubled_3rd": v7_i_similar_to_doubled_3rd,
})