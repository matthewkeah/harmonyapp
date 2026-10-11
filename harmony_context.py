"""Context analysis for harmonic rules."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from engine import VerticalSlice, NoteNode


BAR_TICKS = 1920
BEAT_TICKS = 480


def metric_position(tick: int) -> str:
    beat_in_bar = (tick % BAR_TICKS) // BEAT_TICKS
    if beat_in_bar == 0:
        return "strong"
    if beat_in_bar == 2:
        return "medium"
    return "weak"


def metric_position_from_bar(bar, tick_in_bar: int) -> str:
    beat = tick_in_bar // bar.beat_ticks
    if beat == 0:
        return "strong"
    if bar.num >= 4 and not bar.compound and beat == bar.num // 2:
        return "medium"
    return "weak"


def phrase_position(index: int, total: int) -> str:
    if index == 0:
        return "opening"
    if index == total - 1:
        return "closing"
    if index >= total - 3:
        return "penultimate"
    return "interior"


# Interval 10 is VII (natural subtonic). In minor it acts as a modal
# dominant; in major it is a borrowed chord that functions like VII in
# modal contexts. Either way, treat it as dominant-function for the
# purposes of function_of, so the analyzer doesn't call it a mediant.
TONIC_DEGREES       = {0}
PREDOMINANT_DEGREES = {2, 5}
DOMINANT_DEGREES    = {7, 10, 11}


def function_of(root_pc: int, key_pc: int, category: str) -> str:
    if category in ("neapolitan", "aug6", "borrowed"):
        return "chromatic"
    if category == "secondary":
        return "dominant"
    if root_pc == -1:
        return "unknown"
    interval = (root_pc - key_pc) % 12
    if interval in TONIC_DEGREES:
        return "tonic"
    if interval in PREDOMINANT_DEGREES:
        return "predominant"
    if interval in DOMINANT_DEGREES:
        return "dominant"
    return "mediant"


def _is_root_position(chord) -> bool:
    return chord.inversion in ("root", "")


def _identify_cadence(prev, curr, key) -> str:
    if prev is None or curr is None:
        return ""
    prev_root = prev.root_pc
    curr_root = curr.root_pc
    key_pc = key.root_pitch_class

    if prev_root == (key_pc + 7) % 12 and curr_root == key_pc:
        if _is_root_position(prev) and _is_root_position(curr):
            if curr.slice.soprano is not None and \
               (curr.slice.soprano.pitch % 12) == key_pc:
                return "perfect_authentic"
            return "imperfect_authentic"

    if prev_root == (key_pc + 5) % 12 and curr_root == key_pc:
        if _is_root_position(prev) and _is_root_position(curr):
            return "plagal"

    if prev_root == (key_pc + 7) % 12 and curr_root == (key_pc + 9) % 12:
        return "deceptive"

    if prev.inversion == "6" and prev.quality == "Minor" and \
       curr_root == (key_pc + 7) % 12:
        return "phrygian"

    return ""


def _is_half_cadence(prev, curr, key) -> bool:
    """Half cadence: any chord moving to a root-position V. First-
    inversion V6 arrivals are not half cadences in the standard
    sense — V6 is a passing chord, not a point of repose.
    """
    if prev is None or curr is None:
        return False
    if curr.root_pc == -1:
        return False
    key_pc = key.root_pitch_class
    if curr.root_pc != (key_pc + 7) % 12:
        return False
    if not _is_root_position(curr):
        return False
    if prev.function in ("predominant", "tonic", "mediant"):
        return True
    return False


def classify_six_four(chords, i, key) -> str:
    ch = chords[i]
    if ch.inversion != "64":
        return ""
    prev = chords[i - 1] if i > 0 else None
    nxt = chords[i + 1] if i + 1 < len(chords) else None
    key_pc = key.root_pitch_class

    if ch.metric_position == "strong" and nxt is not None:
        if nxt.root_pc == (key_pc + 7) % 12:
            if ch.slice.bass is not None and \
               (ch.slice.bass.pitch % 12) == (key_pc + 7) % 12:
                return "cadential"

    if prev is not None and nxt is not None:
        if prev.root_pc == nxt.root_pc and \
           prev.function == nxt.function and \
           prev.inversion != "64" and nxt.inversion != "64":
            return "passing"

    if prev is not None and nxt is not None:
        if prev.root_pc == nxt.root_pc and \
           prev.inversion == nxt.inversion and \
           prev.inversion != "64":
            return "neighboring"

    if prev is not None and nxt is not None:
        if prev.root_pc == key_pc and nxt.root_pc == key_pc:
            return "arpeggiated"

    return "unknown"


def detect_phrases(chords) -> List[Tuple[int, int]]:
    if not chords:
        return []
    boundaries = [0]
    for i in range(len(chords) - 1):
        ch = chords[i]
        nxt = chords[i + 1]
        if ch.cadence_type in ("perfect_authentic", "imperfect_authentic",
                               "plagal", "half", "phrygian", "deceptive"):
            boundaries.append(i + 1)
            continue
        ch_max = ch.slice.get_max_ticks()
        nxt_max = nxt.slice.get_max_ticks()
        if ch_max >= 2 * nxt_max:
            boundaries.append(i + 1)
    boundaries.append(len(chords))
    boundaries = sorted(set(boundaries))
    return [(boundaries[i], boundaries[i + 1] - 1)
            for i in range(len(boundaries) - 1)
            if boundaries[i] <= boundaries[i + 1] - 1]


@dataclass
class AnalyzedChord:
    tick: int
    slice: VerticalSlice
    numeral: str = "?"
    root_pc: int = -1
    quality: str = ""
    inversion: str = ""
    category: str = "unknown"
    function: str = "unknown"
    metric_position: str = "weak"
    phrase_position: str = "interior"
    cadence_type: str = ""
    six_four_type: str = ""
    is_phrase_start: bool = False
    is_phrase_end: bool = False
    prev_chord: Optional["AnalyzedChord"] = None
    next_chord: Optional["AnalyzedChord"] = None


@dataclass
class CompositionContext:
    key: object
    layout: object = None
    chords: List[AnalyzedChord] = field(default_factory=list)
    phrases: List[Tuple[int, int]] = field(default_factory=list)


def analyze_composition(slices, key, analyzer, layout=None) -> CompositionContext:
    ctx = CompositionContext(key=key, layout=layout)
    if not slices:
        return ctx

    for vs in slices:
        info = analyzer.analyze(vs, key)
        ac = AnalyzedChord(
            tick=vs.tick,
            slice=vs,
            numeral=info.label,
            root_pc=info.root_pc,
            quality=info.quality,
            inversion=info.inversion,
            category=info.category,
        )
        if layout is not None:
            bar = layout.bar_at(vs.tick)
            tick_in_bar = vs.tick - bar.start_tick
            ac.metric_position = metric_position_from_bar(bar, tick_in_bar)
        else:
            beat_in_bar = (vs.tick % 1920) // 480
            ac.metric_position = (
                "strong" if beat_in_bar == 0
                else "medium" if beat_in_bar == 2
                else "weak"
            )
        ac.function = function_of(info.root_pc, key.root_pitch_class, info.category)
        ctx.chords.append(ac)

    n = len(ctx.chords)
    for i in range(n):
        if i > 0:
            ctx.chords[i].prev_chord = ctx.chords[i - 1]
        if i < n - 1:
            ctx.chords[i].next_chord = ctx.chords[i + 1]

    for i, ac in enumerate(ctx.chords):
        prev = ctx.chords[i - 1] if i > 0 else None
        cad = _identify_cadence(prev, ac, key)
        if not cad and _is_half_cadence(prev, ac, key):
            cad = "half"
        ac.cadence_type = cad

    for i, ac in enumerate(ctx.chords):
        if ac.inversion == "64":
            ac.six_four_type = classify_six_four(ctx.chords, i, key)

    ctx.phrases = detect_phrases(ctx.chords)
    for (start, end) in ctx.phrases:
        ctx.chords[start].is_phrase_start = True
        ctx.chords[end].is_phrase_end = True

    for (start, end) in ctx.phrases:
        length = end - start + 1
        for i in range(start, end + 1):
            ctx.chords[i].phrase_position = phrase_position(i - start, length)

    return ctx