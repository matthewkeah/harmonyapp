"""figuration.py — Identify decorative notes so the harmony analyzer
sees underlying chords, not surface figuration.

Two rules, applied together:

  1. Beat-relative duration ceiling. Figuration may be any note whose
     duration is shorter than or equal to the local beat. The "or
     equal" case is what lets a quarter-note unaccented passing tone
     be recognized in 4/4; without it, quarter-note figuration in
     quarter-beat meters is always structural.

  2. Single-voice attack. An onset is figuration only if exactly one
     voice has a fresh attack there. Two or more simultaneous
     attacks always count as a chord change.

Pitch shape is then checked: the single attacking voice must be a
step from its previous pitch and toward its next (passing, neighbour,
or anticipation). Held-over voices are never tested.

Public entry point:

    harmonic_onsets(notes_db, layout=None) -> set[int]
"""

STEP_SEMITONES = 2

STRUCTURAL = "S"
PASSING = "P"
NEIGHBOR = "N"
ANTICIPATION = "A"

DEFAULT_BEAT_TICKS = 480


def _beat_ticks_for(note, layout):
    if layout is None:
        return DEFAULT_BEAT_TICKS
    try:
        bar = layout.bar_at(note["time_ticks"])
    except Exception:
        return DEFAULT_BEAT_TICKS
    if bar.compound:
        return bar.beat_ticks * 3
    return bar.beat_ticks


def _tracks_by_voice(notes_db):
    tracks = {}
    for n in notes_db:
        tracks.setdefault(n.get("voice", 0), []).append(n)
    for track in tracks.values():
        track.sort(key=lambda x: (x["time_ticks"], -x["pitch"]))
    return tracks


def _neighbors_in_track(track, i):
    tick = track[i]["time_ticks"]
    prev_n = None
    for j in range(i - 1, -1, -1):
        if track[j]["time_ticks"] < tick:
            prev_n = track[j]
            break
    next_n = None
    for j in range(i + 1, len(track)):
        if track[j]["time_ticks"] > tick:
            next_n = track[j]
            break
    return prev_n, next_n


def _classify_attack(note, prev_note, next_note, layout):
    if prev_note is None or next_note is None:
        return STRUCTURAL

    # Duration ceiling: allow <= beat so unaccented quarter-note
    # passing tones count. Only notes strictly longer than the beat
    # are automatically structural.
    beat = _beat_ticks_for(note, layout)
    if note.get("ticks", 0) > beat:
        return STRUCTURAL

    p = note["pitch"]
    pp = prev_note["pitch"]
    np = next_note["pitch"]

    if p == np:
        return ANTICIPATION

    d_prev = p - pp
    d_next = np - p

    if abs(d_prev) <= STEP_SEMITONES and abs(d_next) <= STEP_SEMITONES:
        if d_prev * d_next > 0:
            return PASSING
        if d_prev == -d_next:
            return NEIGHBOR

    return STRUCTURAL


def classify_all(notes_db, layout=None):
    tracks = _tracks_by_voice(notes_db)
    out = {}
    for track in tracks.values():
        for i, n in enumerate(track):
            prev_n, next_n = _neighbors_in_track(track, i)
            out[id(n)] = _classify_attack(n, prev_n, next_n, layout)
    return out


def harmonic_onsets(notes_db, layout=None):
    if not notes_db:
        return set()

    onsets = sorted({n["time_ticks"] for n in notes_db})
    classification = classify_all(notes_db, layout)

    harmonic = {onsets[0]}
    for tick in onsets[1:]:
        attackers = [n for n in notes_db if n["time_ticks"] == tick]
        if not attackers:
            continue
        attacking_voices = {n.get("voice", 0) for n in attackers}
        if len(attacking_voices) != 1:
            harmonic.add(tick)
            continue
        attacker = attackers[0]
        if classification.get(id(attacker), STRUCTURAL) == STRUCTURAL:
            harmonic.add(tick)
    return harmonic