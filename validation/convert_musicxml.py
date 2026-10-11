"""validation/convert_musicxml.py — Convert Humdrum kern, MusicXML, or
MIDI files to .sharm.

Ties are preserved: a half tied to a quarter becomes two note events
with the tie flags set, and the app draws the connecting arc.

Tie detection
-------------
In MusicXML, ties are stored as a note-level attribute accessible via
`note.tie`. In Humdrum kern files parsed by music21, ties are often
stored as Spanner objects that span multiple notes, in which case
`note.tie` is None and the information lives in the spanner's
`getFirst()`/`getLast()` methods. Both representations are checked.
Additionally, `note.tie` may be a list when a note is tied in both
directions (a middle member of a tied chain); the extraction handles
this case explicitly.

Requires: pip install music21
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from constants import KEYS


QUARTER = 480

_LETTER_INDEX = {'C': 0, 'D': 1, 'E': 2, 'F': 3, 'G': 4, 'A': 5, 'B': 6}

_TREBLE_C4_Y = 200
_BASS_C4_Y = 280
_STEP = 5
_C4_DIATONIC = 4 * 7 + 0

_VOICE_LAYOUTS = {1: [0], 2: [0, 3], 3: [0, 1, 3], 4: [0, 1, 2, 3]}

SUPPORTED_EXTS = (".krn", ".xml", ".mxl", ".mid", ".midi")


def _voice_map_for(num_parts):
    if num_parts in _VOICE_LAYOUTS:
        return list(_VOICE_LAYOUTS[num_parts])
    return [0, 1, 2, 3] + [3] * (num_parts - 4)


def _diatonic_number(letter, octave):
    return octave * 7 + _LETTER_INDEX[letter]


def _y_for_note(letter, octave, voice):
    if voice is None:
        dn = _diatonic_number(letter, octave)
        if dn < _C4_DIATONIC:
            return _BASS_C4_Y - (dn - _C4_DIATONIC) * _STEP
        return _TREBLE_C4_Y - (dn - _C4_DIATONIC) * _STEP
    dn = _diatonic_number(letter, octave)
    if voice in (0, 1):
        return _TREBLE_C4_Y - (dn - _C4_DIATONIC) * _STEP
    return _BASS_C4_Y - (dn - _C4_DIATONIC) * _STEP


def _accidental_of(pitch_obj):
    acc = pitch_obj.accidental
    if acc is None:
        return None
    alter = getattr(acc, "alter", None)
    if alter == 1:
        return 'sharp'
    if alter == -1:
        return 'flat'
    if alter == 0:
        return 'natural'
    return None


def _match_key_name(tonic_name, mode):
    name = tonic_name.replace("-", "b")
    candidate = f"{name} {'Minor' if mode == 'minor' else 'Major'}"
    return candidate if candidate in KEYS else None


def _signature_for(key_name):
    info = KEYS.get(key_name, KEYS["C Major"])
    return info["signature"]


def _is_midi(path):
    return path.lower().endswith((".mid", ".midi"))


# --- Tie detection --------------------------------------------------

def _get_tie_info(elem):
    """Return (tie_out, tie_in) for a music21 Note or Chord.

    tie_out is True when this element begins a tie to the next note.
    tie_in  is True when this element ends a tie from the previous
    note. For middle members of a tied chain, both are True.

    Two sources are checked:

      1. The element-level `tie` attribute, which is a single Tie
         object in MusicXML and a list of Ties for middle-of-chain
         notes.
      2. Any Tie spanners the element participates in. Kern files
         parsed by music21 sometimes route ties through spanners
         rather than the note attribute.
    """
    tie_out = False
    tie_in = False

    # Source 1: element-level tie attribute.
    tie = getattr(elem, "tie", None)
    if tie is not None:
        ties = tie if isinstance(tie, (list, tuple)) else [tie]
        for t in ties:
            ttype = getattr(t, "type", None)
            if ttype in ("start", "continue"):
                tie_out = True
            if ttype in ("stop", "continue"):
                tie_in = True

    # Source 2: Tie spanners.
    try:
        spanners = elem.getSpannerSites()
    except Exception:
        spanners = []
    for spanner in spanners:
        try:
            class_names = [c.__name__ for c in spanner.classes]
        except Exception:
            class_names = []
        if "Tie" not in class_names:
            continue
        try:
            if spanner.getFirst() is elem:
                tie_out = True
            if spanner.getLast() is elem:
                tie_in = True
        except Exception:
            continue

    return tie_out, tie_in


# --- Mode detection --------------------------------------------------

def _relative_minor_name(major_key_name):
    info = KEYS.get(major_key_name)
    if info is None:
        return None
    sig = info["signature"]
    for name, cand in KEYS.items():
        if cand["mode"] == "minor" and cand["signature"] == sig:
            return name
    return None


def _extract_midis(elem):
    out = []
    pitches = getattr(elem, "pitches", None)
    if pitches:
        for p in pitches:
            m = getattr(p, "midi", None)
            if m is not None:
                out.append(m)
        if out:
            return out
    p = getattr(elem, "pitch", None)
    if p is not None:
        m = getattr(p, "midi", None)
        if m is not None:
            out.append(m)
    return out


def _final_bass_pc(parts):
    latest_off = None
    latest_midis = []
    for part in parts:
        try:
            elements = list(part.flatten().notes)
        except Exception:
            continue
        for elem in elements:
            off = getattr(elem, "offset", None)
            if off is None:
                continue
            if latest_off is None or off > latest_off + 1e-3:
                latest_off = off
                latest_midis = _extract_midis(elem)
            elif abs(off - latest_off) < 1e-3:
                latest_midis.extend(_extract_midis(elem))
    if not latest_midis:
        return None
    return min(latest_midis) % 12


def _content_key(score):
    try:
        analyzed = score.analyze("key")
    except Exception:
        return None
    try:
        return _match_key_name(analyzed.tonic.name, analyzed.mode)
    except Exception:
        return None


def _detect_real_mode(score, parts, reported_key, forced_key=None):
    if forced_key is not None:
        return forced_key, "forced by --key"
    info = KEYS.get(reported_key)
    if info is None or info["mode"] != "major":
        return reported_key, "reported key already minor (or unknown)"
    rel_minor = _relative_minor_name(reported_key)
    if rel_minor is None:
        return reported_key, "no relative minor for signature"
    major_tonic_pc = info["root"] % 12
    rel_tonic_pc = KEYS[rel_minor]["root"] % 12
    content_key = _content_key(score)
    final_bass_pc = _final_bass_pc(parts)
    reasons = []
    if content_key == rel_minor:
        reasons.append(f"content says {content_key}")
    if final_bass_pc is not None and final_bass_pc == rel_tonic_pc:
        reasons.append(f"final bass pc {final_bass_pc} matches {rel_minor} tonic")
    if final_bass_pc is not None and final_bass_pc == major_tonic_pc:
        reasons.append(f"final bass pc {final_bass_pc} matches {reported_key} tonic")
    if final_bass_pc is not None and final_bass_pc == major_tonic_pc:
        return reported_key, "; ".join(reasons)
    if content_key == rel_minor:
        return rel_minor, "; ".join(reasons)
    if final_bass_pc is not None and final_bass_pc == rel_tonic_pc:
        return rel_minor, "; ".join(reasons)
    return reported_key, (
        f"no override: content={content_key}, final_bass_pc={final_bass_pc}, "
        f"major_tonic_pc={major_tonic_pc}, rel_minor_tonic_pc={rel_tonic_pc}")


def _normalize_offsets(notes):
    if not notes:
        return notes
    min_tick = min(n["time_ticks"] for n in notes)
    if min_tick == 0:
        return notes
    return [{**n, "time_ticks": n["time_ticks"] - min_tick} for n in notes]


def convert_file(src_path, dst_path, forced_key=None, verbose=True):
    try:
        from music21 import converter, note as m21note, chord as m21chord
    except ImportError:
        print("music21 is not installed. Run: pip install music21")
        return False

    try:
        score = converter.parse(src_path)
    except Exception as e:
        print(f"  [skip] {os.path.basename(src_path)}: parse error {e}")
        return False

    parts = score.parts
    if len(parts) < 1:
        print(f"  [skip] {os.path.basename(src_path)}: no parts")
        return False

    num_parts = len(parts)
    from_midi = _is_midi(src_path)
    voice_for_part = _voice_map_for(num_parts) if not from_midi else None

    reported_key = "C Major"
    for part in parts:
        ks_list = list(part.recurse().getElementsByClass("KeySignature"))
        if not ks_list:
            continue
        key_obj = ks_list[0].asKey() if hasattr(ks_list[0], "asKey") else None
        if key_obj is None:
            continue
        candidate = _match_key_name(key_obj.tonic.name, key_obj.mode)
        if candidate:
            reported_key = candidate
        break

    key_name, reason = _detect_real_mode(
        score, parts, reported_key, forced_key=forced_key)

    if verbose:
        tag = "->" if key_name != reported_key else "  "
        print(f"  [key] {os.path.basename(src_path)}: "
              f"{reported_key} {tag} {key_name} ({reason})")

    signature_name = _signature_for(key_name)

    time_sig = "4/4"
    for part in parts:
        ts_list = list(part.recurse().getElementsByClass("TimeSignature"))
        if ts_list:
            time_sig = ts_list[0].ratioString
            break

    notes = []
    tie_count = 0
    for part_idx, part in enumerate(parts):
        if voice_for_part is None:
            v_idx = None
        elif part_idx < len(voice_for_part):
            v_idx = voice_for_part[part_idx]
        else:
            v_idx = voice_for_part[-1]

        flat = part.flatten()
        for elem in flat.notes:
            if isinstance(elem, m21note.Note):
                p = elem.pitch
            elif isinstance(elem, m21chord.Chord):
                p = min(elem.pitches, key=lambda x: x.midi)
            else:
                continue

            letter = p.name[0]
            if letter not in _LETTER_INDEX:
                continue
            octave = p.octave
            if octave is None:
                continue

            y = _y_for_note(letter, octave, v_idx)
            y = int(round(y / _STEP) * _STEP)

            tick = int(round(elem.offset * QUARTER))
            dur = int(round(elem.duration.quarterLength * QUARTER))
            if dur <= 0:
                continue

            tie_out, tie_in = _get_tie_info(elem)
            if tie_out or tie_in:
                tie_count += 1

            note_dict = {
                "time_ticks": tick,
                "base_y": y,
                "ticks": dur,
                "accidental": _accidental_of(p),
                "pitch": int(p.midi),
                "channel": 0,
                "tied_to_next": tie_out,
                "is_tied_target": tie_in,
            }
            if v_idx is not None:
                note_dict["voice"] = v_idx
            notes.append(note_dict)

    if not notes:
        print(f"  [skip] {os.path.basename(src_path)}: no notes extracted")
        return False

    notes = _normalize_offsets(notes)
    notes.sort(key=lambda n: (n["time_ticks"], n.get("voice", 0)))

    data = {
        "format": "SmartHarmonyWorkspace",
        "version": 2,
        "key": key_name,
        "time_sig": time_sig,
        "tempo": 90,
        "instruments": ["French Horn"] * 4,
        "volumes": [100, 100, 100, 100],
        "layout_changes": [[0, time_sig, signature_name]],
        "notes": notes,
    }

    with open(dst_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    kind = "MIDI" if from_midi else "score"
    print(f"  wrote {os.path.basename(dst_path)}: "
          f"{len(notes)} notes, {tie_count} tied endpoints "
          f"from {num_parts} part(s) [{kind}], "
          f"key={key_name}, time_sig={time_sig}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir")
    parser.add_argument("dst_dir")
    parser.add_argument("--key", default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    forced_key = args.key
    if forced_key is not None and forced_key not in KEYS:
        print(f"unknown key: {forced_key!r}")
        return 2

    os.makedirs(args.dst_dir, exist_ok=True)
    converted = 0
    skipped = 0
    for fname in sorted(os.listdir(args.src_dir)):
        if not fname.lower().endswith(SUPPORTED_EXTS):
            continue
        src = os.path.join(args.src_dir, fname)
        base = os.path.splitext(fname)[0]
        dst = os.path.join(args.dst_dir, base + ".sharm")
        if convert_file(src, dst, forced_key=forced_key,
                        verbose=not args.quiet):
            converted += 1
        else:
            skipped += 1
    print(f"\nconverted {converted} file(s), skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())