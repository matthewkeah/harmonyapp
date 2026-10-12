"""sheria_base.py — Foundation shared by all rule passes."""

import json
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable

from engine import VerticalSlice, NoteNode
from harmony_context import (
    analyze_composition, CompositionContext, AnalyzedChord,
    metric_position, function_of, BAR_TICKS, BEAT_TICKS,
)


_DEBUG = os.environ.get("HARMONY_DEBUG", "") == "1"


_SUP = str.maketrans(
    "0123456789+-",
    "\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079\u207A\u207B",
)
_SUB = str.maketrans(
    "0123456789+-",
    "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089\u208A\u208B",
)
def _sup(s): return s.translate(_SUP)
def _sub(s): return s.translate(_SUB)


class KeySignature:
    def __init__(self, root_pitch: int, mode: str = "major"):
        self.root_pitch_class = root_pitch % 12
        self.mode = mode

    def is_leading_tone(self, pitch: int) -> bool:
        return (pitch % 12) == ((self.root_pitch_class + 11) % 12)

    def is_tonic(self, pitch: int) -> bool:
        return (pitch % 12) == self.root_pitch_class


@dataclass
class ChordInfo:
    label: str = "?"
    category: str = "unknown"
    root_pc: int = -1
    quality: str = ""
    inversion: str = ""
    bass_pc: int = -1
    key_pc: int = 0


_MAJOR_DEGREES = (0, 2, 4, 5, 7, 9, 11)
_MINOR_DEGREES = (0, 2, 3, 5, 7, 8, 10)

_MAJOR_APPLIED_TARGETS = (2, 4, 5, 7, 9, 11)
_MINOR_APPLIED_TARGETS = (2, 3, 5, 7, 8, 10)

_MAJOR_NUMERALS = {
    0: "I", 2: "II", 4: "III", 5: "IV", 7: "V", 9: "VI", 11: "VII",
}
_MINOR_NUMERALS = {
    0: "I", 2: "II", 3: "III", 5: "IV", 7: "V", 8: "VI", 10: "VII", 11: "VII",
}

_MAJOR_TRIADS = {
    0:  ("Major", 4, 7),
    2:  ("Minor", 3, 7),
    4:  ("Minor", 3, 7),
    5:  ("Major", 4, 7),
    7:  ("Major", 4, 7),
    9:  ("Minor", 3, 7),
    11: ("Diminished", 3, 6),
}
_MINOR_TRIADS = {
    0:  ("Minor", 3, 7),
    2:  ("Diminished", 3, 6),
    3:  ("Major", 4, 7),
    5:  ("Minor", 3, 7),
    7:  ("Major", 4, 7),
    8:  ("Major", 4, 7),
    10: ("Major", 4, 7),
}


class RomanNumeralAnalyzer:
    NUMERAL_MAP = _MAJOR_NUMERALS

    def trigger_snap_analysis(self, chord_slice, key_signature):
        return self.analyze(chord_slice, key_signature).label

    @staticmethod
    def _degrees(mode):
        return _MINOR_DEGREES if mode == "minor" else _MAJOR_DEGREES

    @staticmethod
    def _applied_targets(mode):
        return (_MINOR_APPLIED_TARGETS if mode == "minor"
                else _MAJOR_APPLIED_TARGETS)

    @staticmethod
    def _numeral_for(interval, mode):
        table = _MINOR_NUMERALS if mode == "minor" else _MAJOR_NUMERALS
        return table.get(interval, "?")

    @staticmethod
    def _scale_pcs(key_pc, mode):
        if mode == "minor":
            return {(key_pc + d) % 12 for d in (0, 2, 3, 5, 7, 8, 10, 11)}
        return {(key_pc + d) % 12 for d in (0, 2, 4, 5, 7, 9, 11)}

    # ---- Main entry point --------------------------------------

    def analyze(self, chord_slice, key_signature) -> ChordInfo:
        notes = chord_slice.get_notes()
        if len(notes) < 1:
            return ChordInfo(label="", category="sparse")

        pitches = [n.pitch for n in notes]
        pcs = {p % 12 for p in pitches}
        bass_pc = min(pitches) % 12
        key_pc = key_signature.root_pitch_class
        mode = getattr(key_signature, "mode", "major")

        if len(pcs) == 2:
            recovered = self._recover_two_pc(pcs, bass_pc, key_pc, mode)
            if recovered is not None:
                return recovered
            return ChordInfo(label="", category="sparse",
                             bass_pc=bass_pc, key_pc=key_pc)

        if len(pcs) < 2:
            return ChordInfo(label="", category="sparse",
                             bass_pc=bass_pc, key_pc=key_pc)

        aug6 = self._try_augmented_sixth(pcs, bass_pc, key_pc)
        if aug6:
            return aug6
        neap = self._try_neapolitan(pcs, bass_pc, key_pc)
        if neap:
            return neap

        root_pc, quality = self._identify(pcs)
        if root_pc == -1:
            root_pc, quality = self._identify_subset(pitches)
        if root_pc == -1:
            if _DEBUG:
                print(f"[unknown chord] pcs={sorted(pcs)} "
                      f"pitches={sorted(pitches)} "
                      f"key_pc={key_pc} mode={mode}")
            return ChordInfo(label="?", category="unknown",
                             bass_pc=bass_pc, key_pc=key_pc)

        if quality == "FullDim7":
            root_pc = self._resolve_dim7_root(pcs, bass_pc, key_pc, mode)

        if quality == "Major7":
            seventh_pc = (root_pc + 11) % 12
            voices_with_seventh = 0
            for v in (chord_slice.soprano, chord_slice.alto,
                      chord_slice.tenor, chord_slice.bass):
                if v is not None and (v.pitch % 12) == seventh_pc:
                    voices_with_seventh += 1
            if voices_with_seventh <= 1:
                trimmed = pcs - {seventh_pc}
                t_root, t_quality = self._identify(trimmed)
                if t_root != -1:
                    root_pc, quality = t_root, t_quality
                    pcs = trimmed

        if mode == "minor" and root_pc == key_pc and quality == "Major":
            inv = self._triad_inversion(root_pc, bass_pc)
            if inv == "6":
                fig = _sup("6")
            elif inv == "64":
                fig = _sup("6") + _sup("4")
            else:
                fig = ""
            return ChordInfo(label=f"I{fig}", category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)

        scale_pcs = self._scale_pcs(key_pc, mode)
        if pcs.issubset(scale_pcs):
            return self._format_diatonic(
                root_pc, quality, bass_pc, key_pc, mode)

        secondary = self._try_secondary_dominant(
            root_pc, quality, bass_pc, key_pc, mode)
        if secondary:
            return secondary
        applied_lt = self._try_applied_leading_tone(
            root_pc, quality, bass_pc, key_pc, mode)
        if applied_lt:
            return applied_lt
        borrowed = self._try_borrowed(root_pc, quality, bass_pc, key_pc, mode)
        if borrowed:
            return borrowed

        return self._format_diatonic(root_pc, quality, bass_pc, key_pc, mode)

    # ---- Two-pitch-class recovery ------------------------------

    @staticmethod
    def _recover_two_pc(pcs, bass_pc, key_pc, mode):
        table = _MINOR_TRIADS if mode == "minor" else _MAJOR_TRIADS
        matches = []
        for degree, (quality, third_int, fifth_int) in table.items():
            root_pc = (key_pc + degree) % 12
            third_pc = (root_pc + third_int) % 12
            fifth_pc = (root_pc + fifth_int) % 12
            triad_pcs = {root_pc, third_pc, fifth_pc}
            if pcs.issubset(triad_pcs):
                matches.append((degree, quality, root_pc,
                                third_pc, fifth_pc, triad_pcs))

        if not matches:
            return None

        if len(matches) > 1:
            root_matches = [m for m in matches if m[2] == bass_pc]
            if root_matches:
                matches = root_matches
            else:
                third_matches = [m for m in matches if m[3] == bass_pc]
                if third_matches:
                    matches = third_matches
                else:
                    fifth_matches = [m for m in matches if m[4] == bass_pc]
                    if fifth_matches:
                        matches = fifth_matches
                    else:
                        matches = [min(matches, key=lambda m: m[0])]
            if len(matches) > 1:
                matches = [min(matches, key=lambda m: m[0])]

        degree, quality, root_pc, third_pc, fifth_pc, triad_pcs = matches[0]
        present = set(pcs)

        missing_root = root_pc not in present
        missing_third = third_pc not in present
        missing_fifth = fifth_pc not in present
        missing_count = sum([missing_root, missing_third, missing_fifth])

        if missing_count != 1:
            return None

        base = RomanNumeralAnalyzer._numeral_for(degree, mode)
        if quality == "Major":
            roman = base.upper()
        elif quality == "Minor":
            roman = base.lower()
        elif quality == "Diminished":
            roman = base.lower() + "\u00B0"
        else:
            roman = base

        inv = RomanNumeralAnalyzer._triad_inversion(root_pc, bass_pc)
        if inv == "6":
            fig = _sup("6")
        elif inv == "64":
            fig = _sup("6") + _sup("4")
        else:
            fig = ""

        return ChordInfo(label=f"{roman}{fig}*", category="diatonic",
                         root_pc=root_pc, quality=quality,
                         inversion=inv, bass_pc=bass_pc,
                         key_pc=key_pc)

    # ---- Augmented sixth and Neapolitan ------------------------

    @staticmethod
    def _try_augmented_sixth(pcs, bass_pc, key_pc):
        flat6  = (key_pc + 8) % 12
        tonic  =  key_pc      % 12
        sharp4 = (key_pc + 6) % 12
        two    = (key_pc + 2) % 12
        flat3  = (key_pc + 3) % 12

        if pcs == {flat6, tonic, sharp4}:
            return ChordInfo(label="It" + _sup("6"), category="aug6",
                             root_pc=flat6, quality="aug6-it",
                             inversion="6", bass_pc=bass_pc, key_pc=key_pc)
        if pcs == {flat6, tonic, two, sharp4}:
            return ChordInfo(label="Fr" + _sup("4") + _sub("3"), category="aug6",
                             root_pc=flat6, quality="aug6-fr",
                             inversion="43", bass_pc=bass_pc, key_pc=key_pc)
        if pcs == {flat6, tonic, flat3, sharp4}:
            return ChordInfo(label="Ger" + _sup("6") + _sub("5"), category="aug6",
                             root_pc=flat6, quality="aug6-ger",
                             inversion="65", bass_pc=bass_pc, key_pc=key_pc)
        if pcs == {flat6, two, sharp4}:
            return ChordInfo(label="Fr" + _sup("4") + _sub("3"), category="aug6",
                             root_pc=flat6, quality="aug6-fr",
                             inversion="43", bass_pc=bass_pc, key_pc=key_pc)
        if pcs == {flat6, flat3, sharp4}:
            return ChordInfo(label="Ger" + _sup("6") + _sub("5"), category="aug6",
                             root_pc=flat6, quality="aug6-ger",
                             inversion="65", bass_pc=bass_pc, key_pc=key_pc)
        return None

    @staticmethod
    def _try_neapolitan(pcs, bass_pc, key_pc):
        flat2 = (key_pc + 1) % 12
        four = (key_pc + 5) % 12
        flat6 = (key_pc + 8) % 12
        if pcs == {flat2, four, flat6}:
            if bass_pc == four:
                return ChordInfo(label="N" + _sup("6"), category="neapolitan",
                                 root_pc=flat2, quality="Major", inversion="6",
                                 bass_pc=bass_pc, key_pc=key_pc)
            elif bass_pc == flat2:
                return ChordInfo(label="N", category="neapolitan",
                                 root_pc=flat2, quality="Major", inversion="root",
                                 bass_pc=bass_pc, key_pc=key_pc)
            else:
                return ChordInfo(label="N" + _sup("6") + _sup("4"),
                                 category="neapolitan",
                                 root_pc=flat2, quality="Major", inversion="64",
                                 bass_pc=bass_pc, key_pc=key_pc)
        return None

    # ---- Pitch-class pattern recognition -----------------------

    @staticmethod
    def _identify(pcs):
        pcs = set(pcs)
        if len(pcs) == 3:
            for pc in sorted(pcs):
                # Complete triads
                if (pc + 4) % 12 in pcs and (pc + 7) % 12 in pcs:
                    return (pc, "Major")
                if (pc + 3) % 12 in pcs and (pc + 7) % 12 in pcs:
                    return (pc, "Minor")
                if (pc + 3) % 12 in pcs and (pc + 6) % 12 in pcs:
                    return (pc, "Diminished")
                if (pc + 4) % 12 in pcs and (pc + 8) % 12 in pcs:
                    return (pc, "Augmented")
                # Suspended triads
                if (pc + 5) % 12 in pcs and (pc + 7) % 12 in pcs:
                    return (pc, "Sus4")
                if (pc + 2) % 12 in pcs and (pc + 7) % 12 in pcs:
                    return (pc, "Sus2")
                # Seventh chords with the fifth omitted
                if (pc + 4) % 12 in pcs and (pc + 10) % 12 in pcs:
                    return (pc, "Dominant7")
                if (pc + 3) % 12 in pcs and (pc + 10) % 12 in pcs:
                    return (pc, "Minor7")
                if (pc + 4) % 12 in pcs and (pc + 11) % 12 in pcs:
                    return (pc, "Major7")
                if (pc + 3) % 12 in pcs and (pc + 9) % 12 in pcs:
                    return (pc, "FullDim7")
                # Shell seventh chords: root + fifth + seventh
                if (pc + 7) % 12 in pcs and (pc + 10) % 12 in pcs:
                    return (pc, "ShellDom7")
                if (pc + 7) % 12 in pcs and (pc + 11) % 12 in pcs:
                    return (pc, "ShellMaj7")
                # Dominant 7b5 shell: root + tritone + minor seventh.
                # Third and perfect fifth both omitted; the tritone is
                # the altered fifth rather than the third.
                if (pc + 6) % 12 in pcs and (pc + 10) % 12 in pcs:
                    return (pc, "Dom7b5Shell")
        if len(pcs) == 4:
            for pc in sorted(pcs):
                maj2 = (pc + 2) % 12 in pcs
                min2 = (pc + 1) % 12 in pcs
                min3 = (pc + 3) % 12 in pcs
                maj3 = (pc + 4) % 12 in pcs
                perf4 = (pc + 5) % 12 in pcs
                dim5 = (pc + 6) % 12 in pcs
                perf5 = (pc + 7) % 12 in pcs
                aug5 = (pc + 8) % 12 in pcs
                maj6 = (pc + 9) % 12 in pcs
                min7 = (pc + 10) % 12 in pcs
                maj7 = (pc + 11) % 12 in pcs
                # Standard seventh chords
                if maj3 and perf5 and maj7:
                    return (pc, "Major7")
                if maj3 and perf5 and min7:
                    return (pc, "Dominant7")
                if min3 and perf5 and min7:
                    return (pc, "Minor7")
                if min3 and dim5 and min7:
                    return (pc, "HalfDim7")
                if min3 and dim5 and maj6:
                    return (pc, "FullDim7")
                # Dominant ninth (fifth omitted)
                if maj3 and min7 and maj2:
                    return (pc, "Dominant9")
                # Augmented major seventh
                if maj3 and aug5 and maj7:
                    return (pc, "AugMajor7")
                # Add9 chords
                if maj3 and perf5 and maj2:
                    return (pc, "MajorAdd9")
                if min3 and perf5 and maj2:
                    return (pc, "MinorAdd9")
                # Add4: triad + perfect fourth
                if maj3 and perf5 and perf4:
                    return (pc, "Add4")
                # Major-ninth shell: root + M2 + P5 + M7
                if maj2 and perf5 and maj7:
                    return (pc, "ShellMaj9")
                # Dominant-thirteenth shell: root + M3 + P5 + m7 + M6
                if maj3 and perf5 and min7 and maj6:
                    return (pc, "Dominant13")
                # Dominant 7 with an added 11th (third still present):
                # root + M3 + P4 + m7.
                if maj3 and perf4 and min7:
                    return (pc, "Dominant7Add11")
                # Dominant 7b9 without the third: root + m2 + P5 + m7.
                # The flat nine supplies the chromatic tension in
                # place of the missing third.
                if min2 and perf5 and min7:
                    return (pc, "Dom7b9No3")
                # Suspended seventh chords
                if perf4 and perf5 and min7:
                    return (pc, "7sus4")
                if maj2 and perf5 and min7:
                    return (pc, "7sus2")
        return (-1, "")

    @staticmethod
    def _identify_subset(pitches):
        bass_pc = min(pitches) % 12
        best = (-1, "")
        best_score = -1
        uniq = sorted(set(pitches))
        n = len(uniq)

        for size in (4, 3):
            if size > n:
                continue
            for i in range(n):
                for j in range(i + 1, n):
                    for k in range(j + 1, n):
                        if size == 3:
                            sub_pcs = {uniq[i] % 12,
                                       uniq[j] % 12,
                                       uniq[k] % 12}
                            root_pc, quality = RomanNumeralAnalyzer._identify(sub_pcs)
                            if root_pc == -1:
                                continue
                            bass_bonus = 2 if bass_pc in sub_pcs else 0
                            score = bass_bonus * 10 + size
                            if score > best_score:
                                best_score = score
                                best = (root_pc, quality)
                        else:
                            for l in range(k + 1, n):
                                sub_pcs = {uniq[i] % 12,
                                           uniq[j] % 12,
                                           uniq[k] % 12,
                                           uniq[l] % 12}
                                root_pc, quality = RomanNumeralAnalyzer._identify(sub_pcs)
                                if root_pc == -1:
                                    continue
                                bass_bonus = 2 if bass_pc in sub_pcs else 0
                                score = bass_bonus * 10 + size
                                if score > best_score:
                                    best_score = score
                                    best = (root_pc, quality)
        return best

    @staticmethod
    def _resolve_dim7_root(pcs, bass_pc, key_pc, mode="major"):
        candidates = []
        for pc in pcs:
            if ((pc + 3) % 12 in pcs
                    and (pc + 6) % 12 in pcs
                    and (pc + 9) % 12 in pcs):
                candidates.append(pc)
        if not candidates:
            return min(pcs)

        home_lt_pc = (key_pc + 11) % 12
        if home_lt_pc in candidates:
            return home_lt_pc

        targets = (_MINOR_APPLIED_TARGETS if mode == "minor"
                   else _MAJOR_APPLIED_TARGETS)
        for target_interval in targets:
            target_pc = (key_pc + target_interval) % 12
            candidate_root = (target_pc - 1) % 12
            if candidate_root in candidates:
                return candidate_root

        if bass_pc in candidates:
            return bass_pc

        return min(candidates)

    # ---- Secondary-function detection --------------------------

    def _try_secondary_dominant(self, root_pc, quality, bass_pc, key_pc, mode):
        if quality not in ("Major", "Dominant7", "Dominant9",
                           "ShellDom7", "Dominant13", "MajorAdd9",
                           "Dominant7Add11", "Dom7b9No3", "Dom7b5Shell"):
            return None
        for degree in self._applied_targets(mode):
            dom_root = (key_pc + degree + 7) % 12
            if root_pc == dom_root:
                target = self._numeral_for(degree, mode)
                if quality == "Major":
                    label = f"V/{target}"
                    inv = self._triad_inversion(root_pc, bass_pc)
                elif quality == "MajorAdd9":
                    label = f"V{_sup('add9')}/{target}"
                    inv = self._triad_inversion(root_pc, bass_pc)
                elif quality == "Dominant13":
                    label = f"V{_sup('13')}/{target}"
                    inv = self._seventh_inversion(root_pc, bass_pc)
                elif quality == "Dominant7Add11":
                    label = f"V{_sup('7')}{_sup('add11')}/{target}"
                    inv = self._seventh_inversion(root_pc, bass_pc)
                elif quality == "Dom7b9No3":
                    label = f"V{_sup('7')}{_sup('b9')}/{target}"
                    inv = self._seventh_inversion(root_pc, bass_pc)
                elif quality == "Dom7b5Shell":
                    label = f"V{_sup('7')}{_sup('b5')}/{target}"
                    inv = self._seventh_inversion(root_pc, bass_pc)
                else:
                    label = f"V{_sup('7')}/{target}"
                    inv = self._seventh_inversion(root_pc, bass_pc)
                return ChordInfo(label=label, category="secondary",
                                 root_pc=root_pc, quality=quality,
                                 inversion=inv, bass_pc=bass_pc, key_pc=key_pc)
        return None

    def _try_applied_leading_tone(self, root_pc, quality, bass_pc, key_pc, mode):
        if quality not in ("Diminished", "HalfDim7", "FullDim7"):
            return None

        home_lt_pc = (key_pc + 11) % 12
        if root_pc == home_lt_pc:
            return None

        target_pc = (root_pc + 1) % 12
        interval = (target_pc - key_pc) % 12
        if interval not in self._degrees(mode):
            return None

        target_name = self._numeral_for(interval, mode)
        if target_name == "?":
            return None

        if quality == "Diminished":
            inv = self._triad_inversion(root_pc, bass_pc)
            if inv == "6":
                fig = _sup("6")
            elif inv == "64":
                fig = _sup("6") + _sup("4")
            else:
                fig = ""
            label = f"vii\u00B0{fig}/{target_name}"
        else:
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            dim_mark = "\u00F8" if quality == "HalfDim7" else "\u00B0"
            label = f"vii{dim_mark}{fig}/{target_name}"

        return ChordInfo(label=label, category="secondary",
                         root_pc=root_pc, quality=quality,
                         inversion=inv, bass_pc=bass_pc, key_pc=key_pc)

    def _try_borrowed(self, root_pc, quality, bass_pc, key_pc, mode):
        if mode == "minor":
            return None
        interval = (root_pc - key_pc) % 12
        if quality == "Minor" and interval == 5:
            inv = self._triad_inversion(root_pc, bass_pc)
            return ChordInfo(label=f"iv{inv}", category="borrowed",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)
        if quality == "Major" and interval == 3:
            inv = self._triad_inversion(root_pc, bass_pc)
            return ChordInfo(label=f"\u266DIII{inv}", category="borrowed",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)
        if quality == "Major" and interval == 8:
            inv = self._triad_inversion(root_pc, bass_pc)
            return ChordInfo(label=f"\u266DVI{inv}", category="borrowed",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)
        if quality == "Major" and interval == 10:
            inv = self._triad_inversion(root_pc, bass_pc)
            return ChordInfo(label=f"\u266DVII{inv}", category="borrowed",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)
        return None

    @staticmethod
    def _triad_inversion(root_pc, bass_pc):
        if bass_pc == root_pc:
            return "root"
        if bass_pc in ((root_pc + 3) % 12, (root_pc + 4) % 12):
            return "6"
        if bass_pc in ((root_pc + 6) % 12,
                       (root_pc + 7) % 12,
                       (root_pc + 8) % 12):
            return "64"
        return ""

    @staticmethod
    def _seventh_inversion(root_pc, bass_pc):
        if bass_pc == root_pc:
            return "7"
        if bass_pc in ((root_pc + 3) % 12, (root_pc + 4) % 12):
            return "65"
        if bass_pc in ((root_pc + 6) % 12, (root_pc + 7) % 12):
            return "43"
        return "42"

    def _format_diatonic(self, root_pc, quality, bass_pc, key_pc, mode):
        interval = (root_pc - key_pc) % 12
        base = self._numeral_for(interval, mode)
        if base == "?":
            return ChordInfo(label="?", category="unknown",
                             root_pc=root_pc, quality=quality,
                             bass_pc=bass_pc, key_pc=key_pc)

        if quality in ("Major", "Major7", "Dominant7", "Dominant9",
                       "ShellDom7", "ShellMaj7", "ShellMaj9",
                       "AugMajor7", "Dominant13",
                       "MajorAdd9", "Add4",
                       "Dominant7Add11", "Dom7b9No3", "Dom7b5Shell",
                       "Sus4", "Sus2", "7sus4", "7sus2"):
            roman = base.upper()
        elif quality in ("Minor", "Minor7", "MinorAdd9"):
            roman = base.lower()
        elif quality == "Diminished":
            roman = base.lower() + "\u00B0"
        elif quality == "Augmented":
            roman = base.upper() + "+"
        elif quality == "HalfDim7":
            roman = base.lower() + "\u00F8"
        elif quality == "FullDim7":
            roman = base.lower() + "\u00B0"
        else:
            roman = base

        if quality == "Sus4":
            return ChordInfo(label=f"{roman}sus4", category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion="root", bass_pc=bass_pc, key_pc=key_pc)
        if quality == "Sus2":
            return ChordInfo(label=f"{roman}sus2", category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion="root", bass_pc=bass_pc, key_pc=key_pc)

        if quality in ("7sus4", "7sus2"):
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{fig}{quality}",
                             category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)

        if quality in ("MajorAdd9", "MinorAdd9"):
            inv = self._triad_inversion(root_pc, bass_pc)
            if inv == "6":
                fig = _sup("6")
            elif inv == "64":
                fig = _sup("6") + _sup("4")
            else:
                fig = ""
            return ChordInfo(label=f"{roman}{fig}add9",
                             category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Add4":
            inv = self._triad_inversion(root_pc, bass_pc)
            if inv == "6":
                fig = _sup("6")
            elif inv == "64":
                fig = _sup("6") + _sup("4")
            else:
                fig = ""
            return ChordInfo(label=f"{roman}{fig}add4",
                             category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality in ("ShellDom7", "ShellMaj7"):
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            real_quality = "Dominant7" if quality == "ShellDom7" else "Major7"
            major_mark = "\u1D39" if quality == "ShellMaj7" else ""
            return ChordInfo(label=f"{roman}{major_mark}{fig}*",
                             category="diatonic",
                             root_pc=root_pc, quality=real_quality,
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "ShellMaj9":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}\u1D39{_sup('9')}{fig}*",
                             category="diatonic",
                             root_pc=root_pc, quality="Major9",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Dominant9":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{_sup('9')}{fig}",
                             category="diatonic",
                             root_pc=root_pc, quality="Dominant9",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Dominant13":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{_sup('13')}{fig}",
                             category="diatonic",
                             root_pc=root_pc, quality="Dominant13",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Dominant7Add11":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{_sup('7')}{fig}{_sup('add11')}",
                             category="diatonic",
                             root_pc=root_pc, quality="Dominant7",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Dom7b9No3":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{_sup('7')}{_sup('b9')}{fig}*",
                             category="diatonic",
                             root_pc=root_pc, quality="Dominant7",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "Dom7b5Shell":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{_sup('7')}{_sup('b5')}{fig}*",
                             category="diatonic",
                             root_pc=root_pc, quality="Dominant7",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if quality == "AugMajor7":
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}+{fig}",
                             category="diatonic",
                             root_pc=root_pc, quality="AugMajor7",
                             inversion=inv, bass_pc=bass_pc,
                             key_pc=key_pc)

        if "7" in quality:
            if quality == "Major7":
                roman += "\u1D39"
            inv = self._seventh_inversion(root_pc, bass_pc)
            if inv == "7":
                fig = _sup("7")
            elif inv == "65":
                fig = _sup("6") + _sub("5")
            elif inv == "43":
                fig = _sup("4") + _sub("3")
            else:
                fig = _sup("4") + _sub("2")
            return ChordInfo(label=f"{roman}{fig}", category="diatonic",
                             root_pc=root_pc, quality=quality,
                             inversion=inv, bass_pc=bass_pc, key_pc=key_pc)

        inv = self._triad_inversion(root_pc, bass_pc)
        if inv == "6":
            fig = _sup("6")
        elif inv == "64":
            fig = _sup("6") + _sup("4")
        else:
            fig = ""
        return ChordInfo(label=f"{roman}{fig}", category="diatonic",
                         root_pc=root_pc, quality=quality,
                         inversion=inv, bass_pc=bass_pc, key_pc=key_pc)


@dataclass
class HarmonyRule:
    rule_id: str
    tier: str
    weight: int
    error_message: str
    check: Dict[str, Any] = field(default_factory=dict)
    category: str = ""
    pass_number: int = 0


@dataclass
class ErrorDetail:
    error_message: str
    penalty_weight: int
    tick_coordinate: int
    voices: List[str] = field(default_factory=list)
    tier: str = ""
    rule_id: str = ""
    prev_tick: Optional[int] = None

    def to_dict(self):
        return {
            "rule_id": self.rule_id,
            "tier": self.tier,
            "weight": self.penalty_weight,
            "tick": self.tick_coordinate,
            "prev_tick": self.prev_tick,
            "voices": list(self.voices),
            "message": self.error_message,
        }


@dataclass
class GradingReport:
    faults: List[ErrorDetail] = field(default_factory=list)
    final_score: int = 100
    context: Optional[Any] = None

    def add_fault(self, fault: ErrorDetail) -> None:
        self.faults.append(fault)
        self.final_score -= fault.penalty_weight

    def to_dict(self):
        return {
            "final_score": self.final_score,
            "faults": [f.to_dict() for f in self.faults],
        }


_HANDLERS: Dict[str, Callable] = {}


def register_handlers(mapping: Dict[str, Callable]) -> None:
    for name, fn in mapping.items():
        if name in _HANDLERS:
            raise ValueError(
                f"Handler '{name}' already registered — check for a "
                f"name collision between pass modules."
            )
        _HANDLERS[name] = fn


def get_handler(name: str) -> Optional[Callable]:
    return _HANDLERS.get(name)


def list_handlers() -> List[str]:
    return sorted(_HANDLERS.keys())


class RulesEngine:
    def __init__(self, json_paths):
        if isinstance(json_paths, str):
            json_paths = [json_paths]
        self.rules: List[HarmonyRule] = []
        loaded_summary = []
        for i, path in enumerate(json_paths, start=1):
            rules = self._parse(path, i)
            self.rules.extend(rules)
            loaded_summary.append((os.path.basename(path), len(rules)))
        print(f"[rules] loaded {len(self.rules)} rules: {loaded_summary}")

    def _parse(self, file_path, pass_number):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[rules] could not load {file_path}: {e}")
            return []
        out = []
        for r in data.get("rules", []):
            fields = {k: v for k, v in r.items()
                      if k in HarmonyRule.__dataclass_fields__}
            fields.setdefault("pass_number", pass_number)
            out.append(HarmonyRule(**fields))
        return out

    def rules_for_pass(self, n):
        return [r for r in self.rules if r.pass_number == n]


class _RuleChecker:
    def _prev(self, ctx, i):
        return ctx.chords[i - 1] if i > 0 else None

    def _next(self, ctx, i):
        return ctx.chords[i + 1] if i + 1 < len(ctx.chords) else None


class SubmissionEngine:
    def __init__(self):
        self.analyzer = RomanNumeralAnalyzer()
        self._checker = _RuleChecker()
        self._missing = set()

    def submit(self, composition, rules, key_signature, layout=None) -> GradingReport:
        report = GradingReport()
        if not composition:
            return report
        ctx = analyze_composition(composition, key_signature,
                                  self.analyzer, layout=layout)
        report.context = ctx
        for index, chord in enumerate(ctx.chords):
            for rule in rules:
                check = rule.check or {}
                ctype = check.get("type", "")
                handler = get_handler(ctype)
                if handler is None:
                    self._missing.add(ctype)
                    continue
                for fault in handler(self._checker, rule, check,
                                     chord, ctx, index):
                    fault.tier = rule.tier
                    fault.rule_id = rule.rule_id
                    report.add_fault(fault)
        return report

    @property
    def missing_handlers(self):
        return sorted(self._missing)