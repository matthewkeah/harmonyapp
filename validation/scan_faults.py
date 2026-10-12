"""validation/scan_faults.py — Batch diagnostic for unknown chords
and rule faults.

Iterates every .sharm file in a directory, runs the analyzer and
the rules engine on each, and prints:

  * every slice the analyzer could not name (unknown chord),
  * every fault the rules engine reports.

Output is grouped by file. A summary at the end counts faults by
rule_id and unknowns by pitch-class set, so that rules which fire
too often (too strict) or too rarely (too loose) stand out at a
glance.

Usage
-----
    python validation/scan_faults.py validation/chorales_sharm
    python validation/scan_faults.py validation/chorales_sharm --max 20

Options
-------
    --max N     stop after N files (useful while iterating)
    --faults    print only faults, skip unknown chord detail
    --unknowns  print only unknown chords, skip faults
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from harmony import build_vertical_slices, assign_voices
from sheria import (
    KeySignature, RulesEngine, SubmissionEngine, RomanNumeralAnalyzer,
)
from constants import (
    KEYS, KEY_OFFSETS, Y_TO_PITCH, ticks_per_bar_from_ts,
    DEFAULT_TIME_SIGNATURE,
)
from bar_layout import BarLayout

# Silence the module-level debug print in sheria_base so that the
# script's own formatted output isn't interleaved with raw lines.
# The env var still needs to be set for HARMONY_DEBUG to have any
# effect at all; we just override it before any analysis runs.
import sheria_base
sheria_base._DEBUG = False


def _recalculate_pitches(notes, key_name):
    info = KEYS.get(key_name, KEYS["C Major"])
    signature = info["signature"]
    offsets = KEY_OFFSETS.get(signature, {})

    for n in notes:
        if n.get("pitch") is not None:
            continue
        base = Y_TO_PITCH.get(n.get("base_y"))
        if base is None:
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
            n["pitch"] = base + offsets.get(base % 12, 0)


def _prepare_notes(data):
    notes = [dict(n) for n in data.get("notes", [])]
    key_name = data.get("key", "C Major")
    _recalculate_pitches(notes, key_name)
    if any("voice" not in n for n in notes):
        assign_voices(notes)
    return notes


def _build_layout(data):
    time_sig = data.get("time_sig", DEFAULT_TIME_SIGNATURE)
    key_name = data.get("key", "C Major")
    signature = KEYS.get(key_name, KEYS["C Major"])["signature"]

    notes = data.get("notes", [])
    last_tick = max((n["time_ticks"] + n["ticks"] for n in notes),
                    default=0)
    bar_ticks = ticks_per_bar_from_ts(time_sig)
    num_bars = max(1, (last_tick + bar_ticks - 1) // bar_ticks)

    layout = BarLayout(initial_time_sig=time_sig,
                       initial_key_sig=signature,
                       num_bars=num_bars)

    changes = data.get("layout_changes")
    if changes:
        layout._changes = [tuple(c) for c in changes]
        layout.reflow(max(num_bars, layout.count))
    return layout


def scan_file(path, analyzer, rules_engine, grader,
              faults_counter, unknown_pc_counter,
              show_faults=True, show_unknowns=True):
    """Analyze one .sharm. Return (num_unknown, num_faults)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [skip] {os.path.basename(path)}: {e}")
        return 0, 0

    key_name = data.get("key", "C Major")
    info = KEYS.get(key_name, KEYS["C Major"])
    key_sig = KeySignature(info["root"], mode=info["mode"])

    notes = _prepare_notes(data)
    slices = build_vertical_slices(notes)
    layout = _build_layout(data)

    filename = os.path.basename(path)
    print(f"\n{'=' * 72}")
    print(f"FILE: {filename}    key={key_name}    slices={len(slices)}")
    print(f"{'=' * 72}")

    # ---- Unknown chords -------------------------------------------
    unknowns = []
    for vs in slices:
        try:
            ci = analyzer.analyze(vs, key_sig)
        except Exception as e:
            print(f"    [analyze error] tick={vs.tick}: {e}")
            continue
        if ci.label == "?":
            pcs = sorted({n.pitch % 12 for n in vs.get_notes()})
            pitches = sorted(n.pitch for n in vs.get_notes())
            unknowns.append((vs, pcs, pitches))
            unknown_pc_counter[tuple(pcs)] += 1

    if show_unknowns and unknowns:
        print(f"\n  UNKNOWN CHORDS ({len(unknowns)}):")
        for vs, pcs, pitches in unknowns:
            voices = []
            for name in ("soprano", "alto", "tenor", "bass"):
                n = getattr(vs, name, None)
                if n is not None:
                    voices.append(f"{name[0].upper()}={n.pitch}")
            print(f"    tick={vs.tick:<6} "
                  f"pcs={pcs}  "
                  f"pitches={pitches}  "
                  f"[{' '.join(voices)}]")

    # ---- Faults ---------------------------------------------------
    try:
        report = grader.submit(slices, rules_engine.rules, key_sig,
                               layout=layout)
    except Exception as e:
        import traceback
        print(f"    [grader error] {e}")
        traceback.print_exc()
        return len(unknowns), 0

    faults = report.faults

    if show_faults and faults:
        print(f"\n  FAULTS ({len(faults)}):")
        for f in faults:
            faults_counter[f.rule_id] += 1
            voices = ",".join(f.voices) if f.voices else "-"
            print(f"    {f.rule_id:<32} "
                  f"w={f.penalty_weight:<2} "
                  f"tick={f.tick_coordinate:<6} "
                  f"voices=[{voices}]")
            print(f"      {f.error_message}")

    return len(unknowns), len(faults)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", help="directory of .sharm files")
    parser.add_argument("--max", type=int, default=None,
                        help="stop after N files")
    parser.add_argument("--faults", action="store_true",
                        help="print only faults")
    parser.add_argument("--unknowns", action="store_true",
                        help="print only unknown chords")
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"not a directory: {args.dir}")
        return 1

    show_faults = not args.unknowns
    show_unknowns = not args.faults

    files = sorted(f for f in os.listdir(args.dir)
                   if f.endswith(".sharm"))
    if args.max:
        files = files[:args.max]

    print(f"Scanning {len(files)} file(s) in {args.dir}\n")

    analyzer = RomanNumeralAnalyzer()
    rules_engine = RulesEngine()
    grader = SubmissionEngine()

    total_unknown = 0
    total_faults = 0
    files_with_unknowns = 0
    files_with_faults = 0
    faults_counter = Counter()
    unknown_pc_counter = Counter()

    for fname in files:
        path = os.path.join(args.dir, fname)
        u, f = scan_file(path, analyzer, rules_engine, grader,
                         faults_counter, unknown_pc_counter,
                         show_faults=show_faults,
                         show_unknowns=show_unknowns)
        if u:
            files_with_unknowns += 1
        if f:
            files_with_faults += 1
        total_unknown += u
        total_faults += f

    # ---- Summary --------------------------------------------------
    print(f"\n\n{'#' * 72}")
    print("# SUMMARY")
    print(f"{'#' * 72}")
    print(f"\nFiles scanned:              {len(files)}")
    print(f"Files with unknown chords:  {files_with_unknowns}")
    print(f"Files with faults:          {files_with_faults}")
    print(f"Total unknown chords:       {total_unknown}")
    print(f"Total faults:               {total_faults}")

    if unknown_pc_counter:
        print(f"\n{'=' * 72}")
        print("UNKNOWNS BY PITCH-CLASS SET (most frequent first):")
        print(f"{'=' * 72}")
        for pcs, count in unknown_pc_counter.most_common(40):
            print(f"  {count:>5}  pcs={list(pcs)}")

    if faults_counter:
        print(f"\n{'=' * 72}")
        print("FAULTS BY RULE (most frequent first):")
        print(f"{'=' * 72}")
        for rule_id, count in faults_counter.most_common():
            print(f"  {count:>5}  {rule_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())