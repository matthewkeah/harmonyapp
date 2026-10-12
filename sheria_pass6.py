"""sheria_pass6.py — Rule handlers for Pass 6 (Units 27-32).

Focused on the chromatic chords whose analysis is already wired into
sheria_base (augmented sixth and Neapolitan) and whose resolutions
are well-defined enough to enforce programmatically.

  * Unit 28 — Neapolitan (N, N⁶, N⁶⁴). The chromatically lowered b2
              resolves down by half step to 1 when the chord resolves
              to I / I⁶⁴, and ascends chromatically by half step to 2
              when it resolves to V / V⁷. Both directions are
              idiomatic and both are accepted here.

  * Unit 29 — Augmented sixth chords (It⁶, Fr⁴₃, Ger⁶₅). The two
              tendency tones (b6 and #4) resolve outward by half step
              to 5. The following chord must contain scale degree 5.

Not implemented, with reasons:
  * Unit 27 (added-dissonance chords) — the slice-builder only handles
    up to 4 pitches per slice cleanly, and the analyzer does not
    recognise 5-note chords.
  * Unit 30 (altered dominants, augmented triads, common-tone dim7)
    — outside the analyzer's pitch-class vocabulary.
  * Unit 31 (chromatic sequences, equal division of the octave) —
    requires a new sequence-detection architecture.
  * Unit 32 (modulation, chromatic tonal areas) — requires a sliding-
    key architecture that the app does not currently have.
"""

from sheria_base import ErrorDetail, register_handlers

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]


# ================================================================
#  Unit 29 — Augmented sixth resolution
# ================================================================

def augmented_sixth_resolution(checker, rule, spec, chord, ctx, index):
    """The b6 and #4 of an augmented sixth chord must resolve outward
    by half step to 5.

    If the following chord still contains b6 or #4, the augmented
    sixth interval is being held over or transferred between voices
    (chromatic sequence), and no resolution has happened yet. In that
    case we skip the check entirely.
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.category != "aug6":
        return []

    key_pc = ctx.key.root_pitch_class
    flat6_pc = (key_pc + 8) % 12
    sharp4_pc = (key_pc + 6) % 12
    fifth_pc = (key_pc + 7) % 12

    current_pcs = {n.pitch % 12 for n in chord.slice.get_notes()}
    if flat6_pc in current_pcs or sharp4_pc in current_pcs:
        return []

    faults = []
    for vname in VOICE_ORDER:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if p.pitch % 12 == flat6_pc:
            if c.pitch == p.pitch - 1 and (c.pitch % 12) == fifth_pc:
                continue
            faults.append(ErrorDetail(
                f"{rule.error_message} — b6 in {vname.title()} did not "
                f"descend by half step to 5",
                rule.weight, chord.tick,
                voices=[vname], prev_tick=prev.tick))
        elif p.pitch % 12 == sharp4_pc:
            if c.pitch == p.pitch + 1 and (c.pitch % 12) == fifth_pc:
                continue
            faults.append(ErrorDetail(
                f"{rule.error_message} — #4 in {vname.title()} did not "
                f"ascend by half step to 5",
                rule.weight, chord.tick,
                voices=[vname], prev_tick=prev.tick))
    return faults


def augmented_sixth_must_reach_dominant(checker, rule, spec, chord, ctx, index):
    """After an augmented sixth chord, the following chord must contain
    scale degree 5.

    The augmented sixth is a chromatic preparation for the dominant.
    It resolves to V, V7, I64 (which acts as a dominant intensifier),
    or another dominant-function chord — all of which contain 5.
    Landing on a chord that does not contain 5 means the augmented
    sixth has been deflected away from its function.
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.category != "aug6":
        return []

    key_pc = ctx.key.root_pitch_class
    fifth_pc = (key_pc + 7) % 12
    if any(n.pitch % 12 == fifth_pc for n in chord.slice.get_notes()):
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        prev_tick=prev.tick)]


# ================================================================
#  Unit 28 — Neapolitan resolution
# ================================================================

def neapolitan_b2_resolution(checker, rule, spec, chord, ctx, index):
    """The chromatically lowered b2 of a Neapolitan has two idiomatic
    resolutions:

      * N⁶ → I / I⁶⁴: b2 descends by half step to 1 (the tonic).
      * N⁶ → V / V⁷: b2 ascends chromatically by half step to 2
        (the fifth of the dominant).

    If the following chord still contains b2, the Neapolitan is being
    prolonged (N⁶ → N, N⁶ → N⁶⁴, etc.), and no resolution has happened
    yet — we skip the check.
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.category != "neapolitan":
        return []

    key_pc = ctx.key.root_pitch_class
    flat2_pc = (key_pc + 1) % 12
    tonic_pc = key_pc
    second_pc = (key_pc + 2) % 12

    current_pcs = {n.pitch % 12 for n in chord.slice.get_notes()}
    if flat2_pc in current_pcs:
        return []

    faults = []
    for vname in VOICE_ORDER:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if p.pitch % 12 != flat2_pc:
            continue
        diff = c.pitch - p.pitch
        # b2 -> 1 (down by half step)
        if diff == -1 and (c.pitch % 12) == tonic_pc:
            continue
        # b2 -> 2 (up by half step, the fifth of V)
        if diff == 1 and (c.pitch % 12) == second_pc:
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick,
            voices=[vname], prev_tick=prev.tick))
    return faults


def neapolitan_bass_motion(checker, rule, spec, chord, ctx, index):
    """N⁶ has scale degree 4 in the bass, which normally ascends by
    step to 5 as the Neapolitan resolves into a dominant sonority. It
    may also descend to 3 for I⁶, or continue to a chromatic sonority
    whose bass is b6 (as in the common N⁶ → Ger⁶₅ approach).

    We do not fire when the Neapolitan is being prolonged or when the
    following chord is itself chromatic (augmented sixth, another
    Neapolitan, or an applied chord).
    """
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    if prev.category != "neapolitan":
        return []
    if prev.inversion != "6":
        return []
    if chord.category in ("neapolitan", "aug6", "secondary"):
        return []
    if prev.slice.bass is None or chord.slice.bass is None:
        return []

    key_pc = ctx.key.root_pitch_class
    four_pc = (key_pc + 5) % 12
    if prev.slice.bass.pitch % 12 != four_pc:
        return []

    next_bass_pc = chord.slice.bass.pitch % 12
    five_pc = (key_pc + 7) % 12
    three_pc = (key_pc + 4) % 12

    if next_bass_pc in (five_pc, three_pc):
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        voices=["bass"], prev_tick=prev.tick)]


# ================================================================
#  Registration
# ================================================================

register_handlers({
    "augmented_sixth_resolution": augmented_sixth_resolution,
    "augmented_sixth_must_reach_dominant": augmented_sixth_must_reach_dominant,
    "neapolitan_b2_resolution": neapolitan_b2_resolution,
    "neapolitan_bass_motion": neapolitan_bass_motion,
})