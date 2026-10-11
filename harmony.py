"""Pure musical logic: time math, voice assignment, stemming, placement rules."""

from constants import (
    TICKS_PER_WHOLE, SYSTEM_HEIGHT, BARLINE_NUDGE,
    TREBLE_MIDDLE_Y, BASS_MIDDLE_Y, STAFF_SPLIT_Y, Y_TO_PITCH,
    DEFAULT_BARS_PER_SYSTEM,
)
from engine import VerticalSlice, NoteNode


def _system_and_bar_in_system(tick, layout, bars_per_system):
    bar_idx, _ = layout.locate(tick)
    sys_idx = bar_idx // bars_per_system
    bar_in_sys = bar_idx % bars_per_system
    return sys_idx, bar_in_sys, bar_idx


def time_to_visual(tick, base_y, layout, start_x, bar_pixel_width,
                   bars_per_system=DEFAULT_BARS_PER_SYSTEM):
    sys_idx, bar_in_sys, bar_idx = _system_and_bar_in_system(
        tick, layout, bars_per_system)
    bar = layout.bars[bar_idx]
    tick_in_bar = tick - bar.start_tick
    bar_x_start = start_x + bar_in_sys * bar_pixel_width
    vis_x = bar_x_start + (tick_in_bar / max(1, bar.ticks)) * bar_pixel_width
    vis_y = base_y + sys_idx * SYSTEM_HEIGHT
    return vis_x, vis_y


def visual_to_time(vis_x, vis_y, layout, start_x, bar_pixel_width,
                   bars_per_system, snap_ticks):
    sys_idx = max(0, int(vis_y) // SYSTEM_HEIGHT)
    base_y = int(vis_y) % SYSTEM_HEIGHT
    base_y = round(base_y / 5) * 5

    local_x = vis_x - start_x
    bar_in_sys = int(local_x // bar_pixel_width)
    if bar_in_sys < 0:
        bar_in_sys = 0
    bar_idx = sys_idx * bars_per_system + bar_in_sys
    if bar_idx >= layout.count:
        bar_idx = layout.count - 1
        bar_in_sys = bar_idx % bars_per_system

    bar = layout.bars[bar_idx]
    bar_x_start = start_x + bar_in_sys * bar_pixel_width
    x_within_bar = vis_x - bar_x_start
    frac = max(0.0, min(1.0, x_within_bar / bar_pixel_width))

    raw_ticks = frac * bar.ticks
    snapped = round(raw_ticks / snap_ticks) * snap_ticks
    max_tick = max(0, bar.ticks - snap_ticks)
    snapped = max(0, min(snapped, max_tick))

    time_ticks = bar.start_tick + snapped
    return time_ticks, base_y


def barline_nudge_for(time_ticks, layout):
    if time_ticks <= 0:
        return 0
    for bar in layout.bars:
        if time_ticks == bar.start_tick and bar.index > 0:
            return BARLINE_NUDGE
    return 0


def note_visual_x(note, layout, start_x, bar_pixel_width, bars_per_system):
    vis_x, _ = time_to_visual(note['time_ticks'], note['base_y'],
                              layout, start_x, bar_pixel_width, bars_per_system)
    vis_x += note.get('offset_x', 0)
    vis_x += barline_nudge_for(note['time_ticks'], layout)
    return vis_x


def can_place_note(notes_db, layout, time_ticks, base_y, ticks):
    same_pos = [n for n in notes_db
                if n['time_ticks'] == time_ticks and n['base_y'] == base_y]
    if len(same_pos) >= 2:
        return False
    bar = layout.bar_at(time_ticks)
    if time_ticks + ticks > bar.end_tick:
        return False
    return True


def _staff_voice(base_y):
    if base_y < STAFF_SPLIT_Y:
        return 0 if base_y < TREBLE_MIDDLE_Y else 1
    return 2 if base_y < BASS_MIDDLE_Y else 3


def assign_voices(notes_db):
    for n in notes_db:
        if "pitch" not in n and "base_y" in n:
            n["pitch"] = Y_TO_PITCH.get(n["base_y"], 60)

    groups = {}
    for n in notes_db:
        groups.setdefault(n['time_ticks'], []).append(n)

    sorted_ticks = sorted(groups.keys())

    for n in notes_db:
        n['_prev_voice'] = n.get('voice', 99)

    for t in sorted_ticks:
        notes = groups[t]
        treble = sorted([n for n in notes if n['base_y'] < STAFF_SPLIT_Y],
                        key=lambda x: (x['base_y'], x['_prev_voice']))
        bass = sorted([n for n in notes if n['base_y'] >= STAFF_SPLIT_Y],
                      key=lambda x: (x['base_y'], x['_prev_voice']))
        for i, n in enumerate(treble):
            n['voice'] = 0 if i == 0 else 1
        for i, n in enumerate(bass):
            n['voice'] = 2 if i == 0 else 3

    for t in sorted_ticks:
        notes = groups[t]
        if len(notes) != 1:
            continue
        n = notes[0]
        on_treble = n['base_y'] < STAFF_SPLIT_Y
        best_ctx, best_dist = None, float('inf')
        for t2 in sorted_ticks:
            if t2 == t or len(groups[t2]) < 2:
                continue
            same_staff = [x for x in groups[t2]
                          if (x['base_y'] < STAFF_SPLIT_Y) == on_treble]
            if not same_staff:
                continue
            d = abs(t2 - t)
            if d < best_dist:
                best_dist, best_ctx = d, same_staff
        if best_ctx:
            closest = min(best_ctx, key=lambda c: abs(c['pitch'] - n['pitch']))
            n['voice'] = closest.get('voice', _staff_voice(n['base_y']))
        else:
            n['voice'] = _staff_voice(n['base_y'])

    for n in notes_db:
        n.pop('_prev_voice', None)


def stem_for_voice(voice):
    return "up" if voice in (0, 2) else "down"


def find_beam_groups(notes_db, layout):
    """Return a list of tuples, each containing 2 or more consecutive
    notes in the same voice that should be beamed together.

    Two notes belong to the same beam group when they are adjacent in
    their voice (next.onset == prev.onset + prev.duration), both have
    duration <= 360 ticks (quaver, dotted quaver, semiquaver, and
    shorter), and both fall inside the same metric beat.
    """
    by_voice = {}
    for n in notes_db:
        by_voice.setdefault(n.get('voice', 0), []).append(n)

    groups = []
    for notes in by_voice.values():
        notes.sort(key=lambda x: x['time_ticks'])
        i = 0
        while i < len(notes):
            if notes[i].get('ticks', 0) > 360:
                i += 1
                continue

            bar = layout.bar_at(notes[i]['time_ticks'])
            beat_ticks = bar.beat_ticks * (3 if bar.compound else 1)
            beat_idx = (notes[i]['time_ticks'] - bar.start_tick) // beat_ticks

            group = [notes[i]]
            j = i + 1
            while j < len(notes):
                n = notes[j]
                if n.get('ticks', 0) > 360:
                    break
                prev = group[-1]
                if n['time_ticks'] != prev['time_ticks'] + prev['ticks']:
                    break
                bar2 = layout.bar_at(n['time_ticks'])
                if bar2.index != bar.index:
                    break
                b2 = (n['time_ticks'] - bar2.start_tick) // beat_ticks
                if b2 != beat_idx:
                    break
                group.append(n)
                j += 1

            if len(group) >= 2:
                groups.append(tuple(group))
                i = j
            else:
                i += 1
    return groups


def build_vertical_slices(notes_db, filter_figuration=True, layout=None):
    if not notes_db:
        return []

    if filter_figuration:
        from figuration import harmonic_onsets
        harmonic = harmonic_onsets(notes_db, layout=layout)
    else:
        harmonic = None

    onsets = sorted({n['time_ticks'] for n in notes_db})
    slices = []

    for t in onsets:
        if harmonic is not None and t not in harmonic:
            continue
        sounding = [n for n in notes_db
                    if n['time_ticks'] <= t < n['time_ticks'] + n['ticks']]
        if not sounding:
            continue
        voices = {}
        for n in sounding:
            v = n.get('voice', 0)
            if v not in voices or n['pitch'] > voices[v]['pitch']:
                voices[v] = n
        if len(voices) < 2:
            continue
        vs = VerticalSlice(tick=t)
        for v, n in voices.items():
            remaining = max(1, n['ticks'] - (t - n['time_ticks']))
            nn = NoteNode(n['pitch'], remaining)
            if v == 0:
                vs.soprano = nn
            elif v == 1:
                vs.alto = nn
            elif v == 2:
                vs.tenor = nn
            elif v == 3:
                vs.bass = nn
        slices.append(vs)
    return slices


def assign_offsets(notes):
    for n in notes:
        n['offset_x'] = 0
    ordered = sorted(notes, key=lambda x: x['base_y'])
    for i in range(len(ordered) - 1):
        upper = ordered[i]
        lower = ordered[i + 1]
        dy = lower['base_y'] - upper['base_y']
        if dy == 0:
            upper['offset_x'] = -8
            lower['offset_x'] = 8
        elif dy == 5:
            upper['offset_x'] = 16