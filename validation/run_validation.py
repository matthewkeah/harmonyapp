"""validation/run_validation.py — Run every test chorale through the
grader and report whether the results match expectations.

Usage:
    python validation/run_validation.py

Exit code 0 means every chorale passed. Non-zero means at least one
did not.

You can also point it at a directory of .sharm files to validate
arbitrary scores:

    python validation/run_validation.py --dir path/to/sharm/files

Notes on voice and pitch handling
---------------------------------

The .sharm files produced by convert_musicxml.py already carry a
correct `voice` (0=S, 1=A, 2=T, 3=B) and a `pitch` field for every
note. This script trusts both when they are present:

  * Voice assignment is NOT re-derived. Re-deriving it from staff
    position destroys the per-part voice the converter established and
    silently scrambles every rule that depends on voice identity
    (LT resolution, doubling, etc.).

  * Pitch is NOT recomputed from `base_y` when the file already
    supplies it. Real chorales contain notes (e.g. high tenor G4)
    whose base_y falls outside Y_TO_PITCH. Recomputing would collapse
    those notes to a default C4.

Hand-crafted test chorales (test_chorales.py) supply neither, so the
fallback paths are still used there.
"""

import argparse
import json
import os
import sys

# Make the app's modules importable when this script is run directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from engine import VerticalSlice, NoteNode
from harmony import build_vertical_slices, assign_voices
from sheria import (
    KeySignature, RulesEngine, SubmissionEngine, RomanNumeralAnalyzer,
)
from quality import ProgressionQualityAnalyzer
from gradealgorithm import grade as standardize_grade
from constants import (
    KEYS, KEY_OFFSETS, Y_TO_PITCH, ticks_per_bar_from_ts,
    DEFAULT_TIME_SIGNATURE,
)
from bar_layout import BarLayout

from validation.test_chorales import CHORALES


# ----------------------------------------------------------------
#  Pitch and voice preparation
# ----------------------------------------------------------------

def _recalculate_pitches(notes, key_name):
    """Populate `pitch` on each note.

    If a note already carries an explicit `pitch` (as converted
    MusicXML files do), that value is trusted. Otherwise the pitch is
    computed from `base_y + accidental + key signature`, mirroring the
    app's _recalculate_pitch.
    """
    info = KEYS.get(key_name, KEYS["C Major"])
    signature = info["signature"]
    offsets = KEY_OFFSETS.get(signature, {})

    for n in notes:
        if n.get("pitch") is not None:
            continue
        base = Y_TO_PITCH.get(n.get("base_y"))
        if base is None:
            # Note is off the model staff entirely. Nothing sensible
            # to derive; fall back to C4 so the slice builder has a
            # value. In practice this only affects hand-built files
            # with invalid y-coordinates.
            n["pitch"] = 60
            continue
        acc = n.get("accidental")
        if acc == "sharp":
            n["pitch"] = base + 1
        elif acc == "flat":
            n["pitch"] = base - 1
        elif acc == "natural":
            n["pitch"] = base
        else:
            pc = base % 12
            n["pitch"] = base + offsets.get(pc, 0)


def _prepare_notes(data):
    """Turn a .sharm 'notes' list into engine-ready notes.

    Pitches are computed. Voices are preserved when the file supplies
    them; otherwise they are assigned from staff position (the
    hand-crafted test chorales rely on this path).
    """
    notes = [dict(n) for n in data.get("notes", [])]
    key_name = data.get("key", "C Major")
    _recalculate_pitches(notes, key_name)

    if any("voice" not in n for n in notes):
        assign_voices(notes)
    return notes


# ----------------------------------------------------------------
#  Layout construction
# ----------------------------------------------------------------

def _build_layout(data):
    """Build a BarLayout from the file's time signature, key, and
    layout_changes so that metric_position is computed correctly
    instead of assuming 4/4 for every bar.
    """
    time_sig = data.get("time_sig", DEFAULT_TIME_SIGNATURE)
    key_name = data.get("key", "C Major")
    signature = KEYS.get(key_name, KEYS["C Major"])["signature"]

    notes = data.get("notes", [])
    if notes:
        last_tick = max(n["time_ticks"] + n["ticks"] for n in notes)
    else:
        last_tick = 0
    bar_ticks = ticks_per_bar_from_ts(time_sig)
    num_bars = max(1, (last_tick + bar_ticks - 1) // bar_ticks)

    layout = BarLayout(initial_time_sig=time_sig,
                       initial_key_sig=signature,
                       num_bars=num_bars)

    changes = data.get("layout_changes")
    if changes:
        # BarLayout accepts change tuples directly; this mirrors what
        # app.py._load_workspace does.
        layout._changes = [tuple(c) for c in changes]
        layout.reflow(max(num_bars, layout.count))
    return layout


# ----------------------------------------------------------------
#  One run
# ----------------------------------------------------------------

def _run_one(data):
    key_name = data.get("key", "C Major")
    info = KEYS.get(key_name, KEYS["C Major"])
    key_sig = KeySignature(info["root"], mode=info["mode"])

    notes = _prepare_notes(data)
    slices = build_vertical_slices(notes)
    layout = _build_layout(data)

    rules_engine = RulesEngine()
    grader = SubmissionEngine()
    report = grader.submit(slices, rules_engine.rules, key_sig,
                           layout=layout)
    return report, key_sig


def _print_faults(faults):
    for i, f in enumerate(faults, 1):
        print(f"    {i:>3}. tick={f.tick_coordinate:<5} "
              f"prev_tick={str(f.prev_tick):<6} "
              f"rule={f.rule_id:<32} "
              f"voices={f.voices}")
        print(f"         {f.error_message}")


# ----------------------------------------------------------------
#  Built-in chorale validation
# ----------------------------------------------------------------

def validate_builtin():
    total_pass = 0
    total_fail = 0

    for chorale in CHORALES:
        name = chorale["name"]
        expected = set(chorale.get("expected_faults", []))
        print(f"\n=== {name} ===")

        try:
            report, _ = _run_one(chorale["data"])
        except Exception as e:
            import traceback
            print(f"  [ERROR] {type(e).__name__}: {e}")
            traceback.print_exc()
            total_fail += 1
            continue

        actual = set(f.rule_id for f in report.faults)

        unexpected = actual - expected
        missed = expected - actual

        if not unexpected and not missed:
            print(f"  PASS — {len(report.faults)} fault(s), all expected")
            total_pass += 1
            continue

        total_fail += 1
        print(f"  FAIL")
        if unexpected:
            print(f"  Unexpected faults ({len(unexpected)}):")
            _print_faults([f for f in report.faults if f.rule_id in unexpected])
        if missed:
            print(f"  Expected faults that did not fire: {sorted(missed)}")

    print(f"\n{'=' * 60}")
    print(f"RESULT: {total_pass} passed, {total_fail} failed")
    return total_fail


# ----------------------------------------------------------------
#  Directory validation
# ----------------------------------------------------------------

def validate_directory(path):
    files = sorted(f for f in os.listdir(path) if f.endswith(".sharm"))
    if not files:
        print(f"no .sharm files in {path}")
        return 0

    print(f"validating {len(files)} file(s) in {path}\n")
    summary = {}

    for fname in files:
        full = os.path.join(path, fname)
        try:
            with open(full, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [skip] {fname}: {e}")
            continue

        try:
            report, _ = _run_one(data)
        except Exception as e:
            print(f"  [error] {fname}: {type(e).__name__}: {e}")
            continue

        print(f"--- {fname} ({len(report.faults)} faults) ---")
        for f in report.faults:
            summary[f.rule_id] = summary.get(f.rule_id, 0) + 1
            print(f"    tick={f.tick_coordinate:<5} {f.rule_id:<32} "
                  f"voices={f.voices}")
        print()

    print("=" * 60)
    print("Fault count by rule across the whole batch:")
    for rule_id in sorted(summary, key=lambda k: -summary[k]):
        print(f"  {summary[rule_id]:>4}  {rule_id}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", help="directory of .sharm files")
    args = parser.parse_args()

    if args.dir:
        return validate_directory(args.dir)
    return validate_builtin()


if __name__ == "__main__":
    sys.exit(main())