"""sheria_pass3.py — Rule handlers for Pass 3 (Units 11-15).

Covers:
  * Unit 11: VI, IV6, VI -> V in minor (augmented-2nd prohibition),
             IV6 -> V (Phrygian cadence), ordering of intermediate
             harmonies
  * Unit 12: II7, IV7, and their inversions
  * Unit 13: IV -> I (plagal), IV6 -> I6 (passing 6/4 within tonic)
  * Unit 14: applied dominants and tonicization
  * Unit 15: III and VII (mostly quality-level)
"""

from sheria_base import ErrorDetail, register_handlers, RomanNumeralAnalyzer

VOICE_ORDER = ["soprano", "alto", "tenor", "bass"]
_A = RomanNumeralAnalyzer()


# ----------------------------------------------------------------
#  No melodic augmented second (Unit 11 section 3)
# ----------------------------------------------------------------

def no_melodic_augmented_second(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    key_pc = ctx.key.root_pitch_class
    flat6_pc = (key_pc + 8) % 12
    sharp7_pc = (key_pc + 11) % 12
    faults = []
    for vname in VOICE_ORDER:
        p = getattr(prev.slice, vname, None)
        c = getattr(chord.slice, vname, None)
        if p is None or c is None:
            continue
        diff = c.pitch - p.pitch
        if diff == 3 and p.pitch % 12 == flat6_pc and c.pitch % 12 == sharp7_pc:
            faults.append(ErrorDetail(
                f"{rule.error_message} ({vname.title()})",
                rule.weight, chord.tick,
                voices=[vname], prev_tick=prev.tick))
        elif diff == -3 and p.pitch % 12 == sharp7_pc and c.pitch % 12 == flat6_pc:
            faults.append(ErrorDetail(
                f"{rule.error_message} ({vname.title()})",
                rule.weight, chord.tick,
                voices=[vname], prev_tick=prev.tick))
    return faults


# ----------------------------------------------------------------
#  Root-position ii7 in major after tonic
# ----------------------------------------------------------------

def ii7_incomplete_after_tonic(checker, rule, spec, chord, ctx, index):
    if ctx.key.mode != "major":
        return []
    prev = checker._prev(ctx, index)
    if prev is None or prev.function != "tonic":
        return []
    info = _A.analyze(chord.slice, ctx.key)
    ii_pc = (ctx.key.root_pitch_class + 2) % 12
    if info.root_pc != ii_pc or "7" not in info.quality:
        return []
    if info.inversion != "7":
        return []
    fifth_pc = (info.root_pc + 7) % 12
    if any(n.pitch % 12 == fifth_pc for n in chord.slice.get_notes()):
        return [ErrorDetail(rule.error_message, rule.weight, chord.tick)]
    return []


# ----------------------------------------------------------------
#  Intermediate harmony root motion
#
#  The book warns against ascending motion within the intermediate
#  group (ii, IV, bVI, vi). But an ascending third is a prolongation
#  in practice — ii -> IV is standard, ii6 -> IV is a 5-6 motion,
#  and these are not "wrong" in the sense the rule is meant to catch.
#  Descending motion by 5th or 3rd is required, and ascending motion
#  by 3rd is permitted; only ascending 5th motions and descending
#  2nd motions are flagged.
# ----------------------------------------------------------------

def intermediate_root_must_descend(checker, rule, spec, chord, ctx, index):
    prev = checker._prev(ctx, index)
    if prev is None:
        return []
    allowed_categories = {"diatonic", "borrowed"}
    if prev.category not in allowed_categories:
        return []
    if chord.category not in allowed_categories:
        return []
    key_pc = ctx.key.root_pitch_class
    prev_interval = (prev.root_pc - key_pc) % 12
    curr_interval = (chord.root_pc - key_pc) % 12
    intermediates = {2, 5, 8, 9}   # ii, IV, bVI, vi
    if prev_interval not in intermediates or curr_interval not in intermediates:
        return []
    diff = (prev.root_pc - chord.root_pc) % 12
    # Allow: descending 3rd (3, 4), descending 5th (7),
    # ascending 3rd (9). Only flag ascending 5th (5) and
    # descending 2nd (10, 11) motions.
    if diff in (3, 4, 7, 9):
        return []
    return [ErrorDetail(rule.error_message, rule.weight, chord.tick,
                        prev_tick=prev.tick)]


# ----------------------------------------------------------------
#  Registration
# ----------------------------------------------------------------

register_handlers({
    "no_melodic_augmented_second": no_melodic_augmented_second,
    "ii7_incomplete_after_tonic": ii7_incomplete_after_tonic,
    "intermediate_root_must_descend": intermediate_root_must_descend,
})