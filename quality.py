"""Progression quality analyzer. Loads one or more quality JSON files.

Two levels of matching:

  root numeral   - bare Roman root, ignores inversion and quality.
                   'V' matches V, V6, V7, V65, V43, V42.
                   Applied chords like 'V/V' preserve the slash.

  chord key      - root + ASCII figured-bass figure, preserves inversion.
                   'V65' matches only first-inversion V7.

Suspended chords (Vsus4, V7sus4, ...) and incomplete-triad labels
(I*, I6*) are normalised to their base form for matching, so 'V'
matches 'V', 'Vsus4', and 'V*'.

When no specific rule matches, the fallback describes what the two
chords are and how they relate functionally. Modal cadences (VII→i,
v→i), applied chords (V/x, vii°/x), and diminished sonorities are
called out explicitly. The generic "no strong functional pull"
placeholder is gone.
"""

import json
import os


QUALITY_LEVELS = ["excellent", "good", "fair", "discouraged", "bad"]

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _discover_pass_files():
    names = []
    for name in os.listdir(_BASE_DIR):
        if name.startswith("quality_pass") and name.endswith(".json"):
            names.append(name)
    def key(n):
        digits = "".join(c for c in n if c.isdigit())
        return int(digits) if digits else 0
    names.sort(key=key)
    return [os.path.join(_BASE_DIR, n) for n in names]


_SUP_TO_ASCII = str.maketrans(
    "\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079",
    "0123456789",
)
_SUB_TO_ASCII = str.maketrans(
    "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089",
    "0123456789",
)

_SUS_MARKERS = ("sus4", "sus2", "sus")


def _strip_sus(s):
    for m in _SUS_MARKERS:
        s = s.replace(m, "")
    return s


def root_numeral(label):
    """Return the bare root numeral, dropping figures, quality marks,
    sus modifiers, and the trailing asterisk used for incomplete
    triads. Applied chords keep their denominator.
    """
    if not label or label in ("?", ""):
        return "?"
    if "/" in label:
        num, _, den = label.partition("/")
        return root_numeral(num) + "/" + den
    label = _strip_sus(label)
    stop = set("0123456789"
               "\u2070\u00B9\u00B2\u00B3\u2074\u2075\u2076\u2077\u2078\u2079"
               "\u2080\u2081\u2082\u2083\u2084\u2085\u2086\u2087\u2088\u2089"
               "\u1D39\u00F8\u00B0+*")
    out = ""
    for c in label:
        if c in stop:
            break
        out += c
    return out or "?"


def chord_key(label):
    """Return root + ASCII figured-bass figure."""
    if not label or label in ("?", ""):
        return "?"
    s = label.replace("\u1D39", "M")
    s = s.translate(_SUP_TO_ASCII).translate(_SUB_TO_ASCII)
    s = _strip_sus(s).replace("*", "")
    return s


def _strip_all_marks(label):
    """Strip every figure and quality mark, leaving only the bare
    numeral (or applied-chord numerator). Used only for modal
    recognition in the fallback."""
    if not label:
        return ""
    base = label
    for ch in "0123456789+-*":
        base = base.replace(ch, "")
    for ch in ("\u2070", "\u00B9", "\u00B2", "\u00B3", "\u2074",
               "\u2075", "\u2076", "\u2077", "\u2078", "\u2079",
               "\u2080", "\u2081", "\u2082", "\u2083", "\u2084",
               "\u2085", "\u2086", "\u2087", "\u2088", "\u2089"):
        base = base.replace(ch, "")
    base = base.replace("\u1D39", "").replace("\u00F8", "").replace("\u00B0", "")
    return base


def _matches(patterns, root, chord):
    """Match a list of rule patterns against a root and chord.
    Supports '*', 'V/*' (any applied dominant of V numerator), and
    '*/V' (any applied chord targeting V).
    """
    for p in patterns:
        if p == "*":
            return True
        if p == root or p == chord:
            return True
        if p.endswith("/*"):
            num = p[:-2]
            if root.startswith(num + "/") or chord.startswith(num + "/"):
                return True
        if p.startswith("*/"):
            den = p[2:]
            if root.endswith("/" + den) or chord.endswith("/" + den):
                return True
    return False


_NUMERAL_INTERVAL = {
    "I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11,
    "i": 0, "ii": 2, "iii": 4, "iv": 5, "v": 7, "vi": 9, "vii": 11,
}


def _infer_function(root):
    """Rough functional category from a bare root numeral."""
    if not root or root == "?":
        return "unknown"
    if "/" in root:
        return "chromatic"
    base = root
    for marker in ("\u00B0", "\u00F8", "+"):
        base = base.replace(marker, "")
    interval = _NUMERAL_INTERVAL.get(base)
    if interval is None:
        return "unknown"
    if interval == 0:
        return "tonic"
    if interval in (2, 5):
        return "predominant"
    if interval in (7, 10, 11):
        return "dominant"
    if interval in (4, 9):
        return "mediant"
    return "unknown"


def _direction_phrase(prev_fn, curr_fn):
    order = {"tonic": 0, "predominant": 1, "dominant": 2}
    if prev_fn in order and curr_fn in order:
        d = order[curr_fn] - order[prev_fn]
        if d > 0:
            return "forward motion along the functional cycle"
        if d == 0:
            return "a prolongation of the same function"
        return "a retrogression against the functional cycle"
    if prev_fn == "chromatic" or curr_fn == "chromatic":
        return "chromatic intensification"
    return "an ambiguous motion"


def _describe_modal(prev_root, curr_root):
    """Detect modal idioms that lack a specific rule. Returns a
    feedback string, or None if the pair is not a recognised modal
    gesture.
    """
    if not prev_root or not curr_root:
        return None
    prev_base = _strip_all_marks(prev_root)
    curr_base = _strip_all_marks(curr_root)

    # Subtonic to tonic — the modal cadence.
    if curr_base in ("I", "i") and prev_base in ("VII", "vII"):
        return (
            f"{prev_root} \u2192 {curr_root}: a modal cadence. "
            f"The subtonic approaches the tonic by whole step rather "
            f"than by the leading-tone half step. This is idiomatic "
            f"in modal, folk, and Renaissance-derived writing; it "
            f"produces a close that is settled but not fully "
            f"functional."
        )

    # Minor (Dorian) dominant to tonic.
    if curr_base == "i" and prev_base == "v":
        return (
            f"{prev_root} \u2192 {curr_root}: minor (Dorian) dominant "
            f"to tonic. Without the raised leading tone, the "
            f"resolution is softer than a harmonic-minor V\u2013i."
        )

    # Tonic to minor (modal) dominant.
    if curr_base == "v" and prev_base in ("i", "I"):
        return (
            f"{prev_root} \u2192 {curr_root}: a Dorian motion from "
            f"tonic to the modal minor dominant. The ear hears the "
            f"dominant degree without the leading-tone pull of a "
            f"major V."
        )

    # Minor dominant → minor subdominant (Dorian step-back).
    if curr_base == "iv" and prev_base == "v":
        return (
            f"{prev_root} \u2192 {curr_root}: minor dominant to minor "
            f"subdominant. A Dorian motion \u2014 stepwise descent in "
            f"the bass toward the prevailing subdominant colour of "
            f"the mode."
        )

    # Minor subdominant → minor (modal) dominant.
    if curr_base == "v" and prev_base == "iv":
        return (
            f"{prev_root} \u2192 {curr_root}: minor subdominant to "
            f"minor (modal) dominant. Dorian-flavoured stepwise "
            f"motion."
        )

    # Mediant → subtonic in minor: modal step-down.
    if curr_base == "VII" and prev_base in ("III", "iii"):
        return (
            f"{prev_root} \u2192 {curr_root}: mediant to subtonic in "
            f"minor \u2014 \u266DIII to \u266DVII. Idiomatic in modal "
            f"and folk-influenced writing."
        )

    # Minor subdominant → subtonic (any figure): prepares a modal
    # cadence.
    if curr_base == "VII" and prev_base in ("iv",):
        return (
            f"{prev_root} \u2192 {curr_root}: minor subdominant to "
            f"subtonic. The motion prepares a modal cadence on i or I "
            f"using the lowered seventh degree."
        )

    # Minor subdominant → applied leading-tone chord.
    if "/" in curr_root and prev_base == "iv":
        return (
            f"{prev_root} \u2192 {curr_root}: chromatic intensification. "
            f"The applied chord tonicizes its target; the diminished "
            f"seventh (or diminished triad) has a strong tendency to "
            f"resolve into the target's tonic."
        )

    return None


class ProgressionQualityAnalyzer:
    def __init__(self, paths=None):
        if paths is None:
            paths = _discover_pass_files()
        elif isinstance(paths, str):
            paths = [paths]

        self.rules = []
        loaded_summary = []
        for p in paths:
            rules = self._load(p)
            self.rules.extend(rules)
            loaded_summary.append((os.path.basename(p), len(rules)))

        # Catch-all rules are tried last.
        specific = []
        catch_alls = []
        for r in self.rules:
            f = r.get("from", [])
            t = r.get("to", [])
            if ("*" in f) and ("*" in t):
                catch_alls.append(r)
            else:
                specific.append(r)
        self.rules = specific + catch_alls

        if loaded_summary:
            print(f"[quality] loaded {len(self.rules)} rules: {loaded_summary}")
        else:
            print("[quality] WARNING: no quality_passN.json files found; "
                  "every chord will default to 'fair'.")

    def _load(self, path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"[quality] could not load {path}: {e}")
            return []
        return data.get("rules", [])

    def analyze(self, labels):
        results = []
        for i, label in enumerate(labels):
            root = root_numeral(label)
            chord = chord_key(label)
            if i > 0:
                prev_root = root_numeral(labels[i - 1])
                prev_chord = chord_key(labels[i - 1])
            else:
                prev_root, prev_chord = None, None
            is_first = (i == 0)
            q, fb = self._match(prev_root, prev_chord, root, chord, is_first)
            results.append((q, fb))
        return results

    def _match(self, prev_root, prev_chord, root, chord, is_first):
        for rule in self.rules:
            if rule.get("id") == "STATIC-ANY-ANY":
                if prev_chord is not None and prev_chord == chord:
                    return rule.get("quality", "fair"), rule.get("feedback", "")
                continue

            f = rule.get("from", [])
            t = rule.get("to", [])

            if is_first:
                if f and "*" not in f:
                    continue
            else:
                if not _matches(f, prev_root, prev_chord):
                    continue

            if not _matches(t, root, chord):
                continue
            return rule.get("quality", "fair"), rule.get("feedback", "")

        return self._fallback(prev_root, root, prev_chord, chord)

    def _fallback(self, prev_root, curr_root, prev_chord, curr_chord):
        """Describe the transition when no rule matched.

        Rather than a generic placeholder, we name the two chords and
        give a functional reading. Modal idioms, applied chords, and
        diminished sonorities get specific descriptions. This keeps
        the app useful on the many idiomatic progressions the rule
        set doesn't enumerate.
        """
        if not curr_root or curr_root == "?":
            return "fair", (
                "The analyzer could not name the current sonority, so no "
                "progression rule applies. Check the voicing for a mis-"
                "identified chord."
            )

        # Applied chords (any label with a slash).
        if "/" in curr_root:
            target = curr_root.rsplit("/", 1)[1]
            return "fair", (
                f"{prev_root} \u2192 {curr_root}: applied chord "
                f"tonicizing {target}. Its local function is dominant "
                f"of {target}; in the home key this reads as a "
                f"chromatic intensification. No specific rule covers "
                f"this pair, but the tonicization is musically "
                f"coherent \u2014 check the resolution by ear."
            )

        # Diminished sonorities.
        if "\u00B0" in curr_root or "\u00F8" in curr_root:
            return "fair", (
                f"{prev_root} \u2192 {curr_root}: diminished sonority. "
                f"Its tendency tones (the leading tone and, if "
                f"present, the chordal seventh) pull strongly toward "
                f"the following resolution. No specific rule covers "
                f"this pair \u2014 check that the diminished fifth "
                f"descends by step and the leading tone ascends by "
                f"half step."
            )

        # Modal idioms.
        modal = _describe_modal(prev_root, curr_root)
        if modal:
            return "fair", modal

        # Generic functional reading.
        prev_fn = _infer_function(prev_root) if prev_root else "unknown"
        curr_fn = _infer_function(curr_root)
        direction = _direction_phrase(prev_fn, curr_fn)

        if prev_fn == "unknown" and curr_fn == "unknown":
            return "fair", (
                f"{prev_root} \u2192 {curr_root}: chromatic or otherwise "
                f"unclassified transition. No specific rule in the "
                f"loaded set describes this pair."
            )

        return "fair", (
            f"{prev_root} \u2192 {curr_root}: a {curr_fn} harmony "
            f"following a {prev_fn} harmony \u2014 {direction}. No "
            f"specific rule in the loaded set describes this exact "
            f"pair."
        )