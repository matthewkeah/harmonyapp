"""sheria_pass5.py — Rule handlers for Pass 5 (Units 22-26).

  * Unit 22 — leading-tone seventh chords. Generic seventh-resolution
              is handled by Pass 2 (via seventh_resolution). Pass 5
              adds the applied variants: vii°7/x and viiø7/x must
              resolve to x.

  * Unit 23 — mixture. The chromatically altered tone of a borrowed
              chord (b6 in a major key being the common case) must
              resolve in the direction of its tendency.

  * Unit 24 — apparent seventh chords and sequences. Informational
              only; no faults are emitted because the underlying
              slice-builder cannot distinguish a suspension-derived
              apparent seventh from a functional one.

  * Unit 25 — applied dominants and applied leading-tone chords. The
              applied leading tone of V/x (the third) or vii°/x (the
              root) must resolve up by half step to the tonic of the
              target. Don't double the applied leading tone.

  * Unit 26 — diatonic modulation. Handled at the quality layer for
              now; a full pivot-recognition pass is deferred.
"""

from sheria_base import ErrorDetail, register_handlers


# ----------------------------------------------------------------
#  Applied leading-tone resolution
#
#  The applied leading tone is:
#    * the third of V/x or V7/x (its root + 4 semitones), or
#    * the root of vii°/x, viiø7/x, or vii°7/x.
#
#  It must resolve up by half step to the tonic of the target key,
#  i.e., the pitch class one semitone above the applied LT. If the
#  current chord still contains the applied LT, the chord is a
#  prolongation of the applied dominant (V7/V → V7/V, V7/V → V6/5/V),
#  not a resolution, so no fault is emitted.
#
#  Only the outer voices (soprano and bass) are checked strictly. In
#  inner voices, textbook practice permits freer treatment of the
#  applied leading tone.
# ----------------------------------------------------------------

def applied_leading_tone_resolution(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []

    applied_lt_pc = None

    # Case 1: applied dominant — third of the chord is the applied LT.
    if prev.category == "secondary" and prev.quality in ("Major", "Dominant7"):
        applied_lt_pc = (prev.root_pc + 4) % 12
    # Case 2: applied leading-tone chord — root of the chord is the applied LT.
    elif prev.quality in ("Diminished", "HalfDim7", "FullDim7"):
        home_lt_pc = (ctx.key.root_pitch_class + 11) % 12
        if prev.root_pc != home_lt_pc:
            applied_lt_pc = prev.root_pc

    if applied_lt_pc is None:
        return []

    target_tonic_pc = (applied_lt_pc + 1) % 12

    # Prolongation: if the current chord still contains the applied LT,
    # the LT is being held over or transferred between voices.
    if any(n.pitch % 12 == applied_lt_pc for n in chord.slice.get_notes()):
        return []

    faults = []
    for vname in ("soprano", "bass"):
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if p.pitch % 12 != applied_lt_pc:
            continue
        if c.pitch == p.pitch + 1 and (c.pitch % 12) == target_tonic_pc:
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick, voices=[vname], prev_tick=prev.tick))
    return faults


# ----------------------------------------------------------------
#  Doubled applied leading tone
#
#  Pass 1's `doubling_leading_tone` only guards the home key's LT.
#  An applied leading tone is a chromatic pitch that Pass 1 cannot
#  identify, so we check it here.
# ----------------------------------------------------------------

def doubled_applied_leading_tone(checker, rule, spec, chord, ctx, index):
    applied_lt_pc = None

    if chord.category == "secondary" and chord.quality in ("Major", "Dominant7"):
        applied_lt_pc = (chord.root_pc + 4) % 12
    elif chord.quality in ("Diminished", "HalfDim7", "FullDim7"):
        home_lt_pc = (ctx.key.root_pitch_class + 11) % 12
        if chord.root_pc != home_lt_pc:
            applied_lt_pc = chord.root_pc

    if applied_lt_pc is None:
        return []

    count = sum(1 for n in chord.slice.get_notes()
                if n.pitch % 12 == applied_lt_pc)
    if count > 1:
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


# ----------------------------------------------------------------
#  Mixture chromatic tone resolution
#
#  The most common mixture in a major key is the borrowed
#  subdominant: iv (F-Ab-C in C major) or bVI (Ab-C-Eb in C major).
#  In both cases the chromatically altered tone is b6, which should
#  resolve down by step to 5 in the following chord.
#
#  If the following chord also contains b6, the borrowed sonority is
#  being prolonged — no fault. The rule is restricted to major keys
#  for now because KeySignature.mode is not yet wired through app.py.
# ----------------------------------------------------------------

def mixture_chromatic_tone_resolution(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []

    if ctx.key.mode != "major":
        return []
    if prev.category != "borrowed":
        return []

    key_pc = ctx.key.root_pitch_class
    flat6_pc = (key_pc + 8) % 12
    fifth_pc = (key_pc + 7) % 12

    # Only fire when the borrowed chord actually contains b6.
    if not any(n.pitch % 12 == flat6_pc for n in prev.slice.get_notes()):
        return []

    # Prolongation of the same borrowed sonority — skip.
    if any(n.pitch % 12 == flat6_pc for n in chord.slice.get_notes()):
        return []

    faults = []
    for vname in ("soprano", "bass"):
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        if p.pitch % 12 != flat6_pc:
            continue
        diff = c.pitch - p.pitch
        if diff in (-1, -2) and (c.pitch % 12) == fifth_pc:
            continue
        faults.append(ErrorDetail(
            f"{rule.error_message} ({vname.title()})",
            rule.weight, chord.tick, voices=[vname], prev_tick=prev.tick))
    return faults


# ----------------------------------------------------------------
#  Registration
# ----------------------------------------------------------------

register_handlers({
    "applied_leading_tone_resolution": applied_leading_tone_resolution,
    "doubled_applied_leading_tone": doubled_applied_leading_tone,
    "mixture_chromatic_tone_resolution": mixture_chromatic_tone_resolution,
})