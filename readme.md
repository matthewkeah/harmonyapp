# Smart Harmony Assistant

A desktop application for the analysis and critique of four-part
harmony. The app loads any four-voice piece — a Bach chorale, a
student exercise, a passage from the literature — and produces a
detailed analytical report in the tradition of Aldwell & Schachter's
*Harmony and Voice Leading*.

Every chord is identified, every voice-leading fault is flagged, every
cadence is marked, and every transition is rated for idiomatic quality.
The output is presented both as a visual overlay on the manuscript and
as a scrollable "Red Pen Report" listing each fault with its tier,
weight, and a plain-English explanation.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Screenshots](#screenshots)
3. [Installation](#installation)
4. [Running the app](#running-the-app)
5. [Importing music](#importing-music)
6. [The analytical engine](#the-analytical-engine)
7. [Project structure](#project-structure)
8. [The `.sharm` file format](#the-sharm-file-format)
9. [Adding new rules](#adding-new-rules)
10. [Converting a corpus of chorales](#converting-a-corpus-of-chorales)
11. [Validation and testing](#validation-and-testing)
12. [Building a standalone executable](#building-a-standalone-executable)
13. [Known limitations](#known-limitations)
14. [Dependencies](#dependencies)
15. [Contributing](#contributing)

---

## What it does

### Analysis

The engine runs in two independent layers.

**Rules passes 1–6** identify *faults*: hard voice-leading violations
with weights and error messages. These are the things a theory teacher
would mark in red — parallel fifths, unresolved leading tones, doubled
chordal sevenths, unidiomatic leaps, forbidden parallels, unmet
cadence conditions, out-of-range notes.

**Quality passes 1–7** rate *transitions*: how idiomatic each
chord-to-chord motion is, on a five-level scale from "excellent" to
"bad". These are the things a theory teacher would comment on in the
margin — "the ear hears this as a prolongation", "this is a modal
cadence, not a functional one", "an applied chord tonicizing the
dominant".

The two layers are independent. A piece can have faults but idiomatic
transitions, or be fault-free but full of limp progressions.

### What is recognised

- **Diatonic chords** in every inversion, with correct figured-bass
  labels (I, I⁶, I⁶⁴, V⁷, V⁶⁵, V⁴³, V⁴², etc.)
- **Applied chords** (V/V, V⁷/IV, vii°⁷/V, and every other degree)
- **Borrowed chords** (♭III, ♭VI, ♭VII, iv)
- **Augmented sixth chords** (It⁶, Fr⁴₃, Ger⁶⁵), including the common
  incomplete forms where the tonic is omitted
- **Neapolitan chords** (N, N⁶, N⁶⁴)
- **Modal progressions** in minor (natural VII, Dorian v, the
  descending tetrachord i–VII–VI–V)
- **Add9, add4, shell seventh, and dominant-ninth chords** — the
  sonorities that appear constantly in real chorale textures when a
  voice drops out for voice-leading reasons
- **Incomplete triads** with the asterisk convention (I*, I⁶*, I⁶⁴*)
  so that an incomplete root-position triad is never confused with a
  first-inversion triad

### What is reported

- Roman numeral analysis under each chord
- Quality rating with an explanatory popup on click
- Cadence detection (PAC, IAC, half, plagal, deceptive, phrygian,
  modal)
- Phrase boundaries via cadence and duration heuristics
- Metric position of each chord (strong, medium, weak)
- Voice-leading faults, sorted by tier (Physical, Voice Leading,
  Contextual, Chromatic)
- A final score out of 100, standardised for bar count

---

## Screenshots

*(Add your screenshots here. Suggested: one showing the main window
with a chorale loaded and the Red Pen Report populated, one showing a
clicked numeral popup, one showing the Settings dialog, one showing an
AI feedback panel once that feature lands.)*

---

## Installation

### Requirements

- Python 3.10 or later (3.14 tested)
- A working audio output for playback
- Optional: `music21` for converting MusicXML, MIDI, or kern files

### Install

```bash
git clone <your-repo-url>
cd harmonyapp
pip install -r requirements.txt
```

If you plan to import MusicXML, MIDI, or Humdrum kern files, install
`music21` as well:

```bash
pip install music21
```

### SoundFont (optional, for high-quality playback)

The playback engine falls back to the Windows MIDI synthesiser if no
SoundFont is present. For better playback quality, download a General
MIDI SoundFont and place it in the project root:

- Recommended: `FluidR3_GM.sf2` (~140 MB)
- Available from many public archives

If the file is absent, the app still runs and plays through the
system MIDI. Quality will be lower; functionality is unaffected.

---

## Running the app

```bash
python app.py
```

On Windows, if `python` resolves to the Microsoft Store stub rather
than your installed interpreter, use the launcher instead:

```bash
py app.py
```

### First-time setup

1. Launch the app.
2. Load a `.sharm` file with the **Load** button, or import a raw
   MusicXML / MIDI / kern file with the **Import** button.
3. Press **Submit Harmony** to run the analysis.
4. Click any fault in the Red Pen Report to toggle its annotation on
   the manuscript.
5. Click any Roman numeral to open the quality popup for that
   transition.
6. Click a barline to change its time signature; Shift+click to change
   its key signature.

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+Z` | Undo |
| `Space` | Play / pause |
| `←` / `→` | Seek to previous / next bar |
| `T` | Tie the selected note to the next |
| `R` | Repeat the selected note |
| `S` | Toggle sharp |
| `F` | Toggle flat |
| `N` | Toggle natural |
| `Del` / `Backspace` | Delete the selected note |
| `↑` / `↓` | Move the selected note up / down a step |
| `Ctrl+D` | Dump the current slice analysis to the terminal |

---

## Importing music

### Supported formats

The **Import** button accepts any of these source formats and writes a
converted `.sharm` file alongside the original:

| Format | Extension | Notes |
|---|---|---|
| MusicXML | `.xml`, `.mxl` | Best fidelity; preserves voice assignment |
| MIDI | `.mid`, `.midi` | Voice assignment inferred from part order |
| Humdrum kern | `.krn` | The Bach chorale corpus format |
| Karaoke MIDI | `.kar` | Same as MIDI |

Conversion requires `music21`:

```bash
pip install music21
```

### Automatic key detection

The converter infers the key from the score's key signature, the
analysis of its pitch content, and the final bass pitch. Major keys
that are actually the relative minor (a piece notated in C major that
ends on A and uses A as a tonal centre) are re-labelled automatically.

### Ties

Ties are preserved as two separate notes with `tied_to_next` and
`is_tied_target` flags. The app draws the connecting arc and the
playback engine sustains them as a single note rather than two
attacks.

---

## The analytical engine

### Two-pass architecture

Every piece is analysed in two independent passes.

**Vertical analysis.** Notes are grouped by onset into *slices* — one
note per voice per onset. Each slice is classified as a chord (or as
a figuration onset, which is skipped for chord naming but shown in
the manuscript). A slice with fewer than three distinct pitch classes
is marked as *sparse*; a slice with three or more that fits no known
pattern is marked as *unknown*.

**Horizontal analysis.** The chord sequence is walked pairwise. Each
transition is scored against the quality rule set. Simultaneously, the
fault rule set is applied to each chord in its context.

### Figuration filtering

Not every onset is a chord change. A single voice moving by step
between two structural pitches is a *passing tone*, a *neighbour
tone*, or an *anticipation*. These are identified by
`figuration.harmonic_onsets` and skipped by the chord analyser, but
they remain visible in the manuscript. This is what lets the app
recognise underlying harmony beneath surface figuration.

### The quality rule set

Quality rules live in seven JSON files, `quality_pass1.json` through
`quality_pass7.json`. Each rule describes a transition:

```json
{
  "id": "CORE-V-I",
  "quality": "excellent",
  "from": ["V", "V7"],
  "to": ["I", "i"],
  "feedback": "Dominant to tonic. Root motion by descending 5th..."
}
```

Rules are tried in load order (pass 1 first, pass 7 last). The first
match wins. Catch-all rules with `from: ["*"]` and `to: ["*"]` are
automatically reordered to the end so they never shadow specific
rules.

Supported pattern syntax:

| Pattern | Matches |
|---|---|
| `"V"` | V, V⁶, V⁶⁴, V⁷, V⁶⁵, V⁴³, V⁴² |
| `"V65"` | Only first-inversion V⁷ |
| `"V/V"` | Applied dominant of V, any inversion |
| `"V/*"` | Any applied dominant with V as numerator |
| `"*/V"` | Any applied chord targeting V |
| `"*"` | Anything |

When no rule matches, the fallback describes the transition based on
the two chords' functions and, where applicable, recognises modal,
applied, and diminished idioms.

### The fault rule set

Fault rules live in six JSON files, `rules_pass1.json` through
`rules_pass6.json`. Each fault rule names a handler function, a
weight, and an error message:

```json
{
  "rule_id": "PARALLEL-P5",
  "tier": "VOICE_LEADING",
  "category": "Parallel Intervals",
  "weight": 10,
  "error_message": "Parallel fifths between consecutive chords",
  "check": { "type": "parallel_perfects", "intervals": ["P5"] }
}
```

The `check.type` field names a handler registered by one of the six
`sheria_pass*.py` modules. Every handler receives:

- `checker` — a helper with `_prev(ctx, i)` and `_next(ctx, i)`
- `rule` — the `HarmonyRule` object
- `spec` — the `check` dict
- `chord` — the current `AnalyzedChord`
- `ctx` — the full `CompositionContext`
- `index` — the position of the current chord in the context

and returns a list of `ErrorDetail` objects (empty if no fault).

### Tiers

Faults are assigned to one of four tiers, which govern the colour of
their annotation on the manuscript:

| Tier | Colour | Meaning |
|---|---|---|
| PHYSICAL | Orange | Range, spacing, doubling, leaps |
| VOICE_LEADING | Red | Resolution, parallels, direct intervals |
| CONTEXTUAL | Purple | Cadence, syntax, formal position |
| CHROMATIC | Purple | Augmented sixths, Neapolitans, mixture |

### Grading

The final score is computed as `100 × (1 − raw_penalty / (bars ×
threshold))`, where `threshold` is `80` points per bar. This makes the
score fair across pieces of different length: a piece with many faults
spread over many bars scores higher than the same faults concentrated
into one bar.

---

## Project structure

```
harmonyapp/
├── app.py                     # Main application (GUI, event loop)
├── engine.py                  # MIDI playback + slice data model
├── harmony.py                 # Time math, voice assignment, placement
├── harmony_context.py         # Composition-level analysis
├── bar_layout.py              # Variable-time-signature bar arithmetic
├── figuration.py              # Passing/neighbour/anticipation detection
├── rendering.py               # Canvas drawing helpers
├── gradealgorithm.py          # Score standardisation
├── quality.py                 # Quality rule matcher
├── settings_ui.py             # Settings modal
├── annotation_formats.py      # Per-fault visual annotations
│
├── sheria.py                  # Public API for the rule system
├── sheria_base.py             # Analyzer, RuleEngine, SubmissionEngine
├── sheria_pass1.py … _pass6.py  # Rule handler implementations
│
├── rules_pass1.json … _pass6.json     # Fault rule definitions
├── quality_pass1.json … _pass7.json   # Quality rule definitions
│
├── constants.py               # Shared constants (keys, time sigs, etc.)
│
├── assets/                    # Clef images (bundled resources)
├── validation/                # Test chorales + converter + batch runner
│   ├── convert_musicxml.py    # MusicXML/kern/MIDI → .sharm converter
│   ├── run_validation.py      # Batch validation runner
│   └── test_chorales.py       # Hand-crafted test cases
│
├── bach-370-chorales/         # (Optional) source corpus
│   └── kern/
│
└── validation/chorales_sharm/ # (Optional) converted corpus
```

---

## The `.sharm` file format

`.sharm` files are JSON. They store a piece's notes, layout changes,
and metadata in a compact, human-readable form.

```json
{
  "format": "SmartHarmonyWorkspace",
  "version": 2,
  "key": "A Minor",
  "time_sig": "4/4",
  "tempo": 90,
  "instruments": ["French Horn", "French Horn", "French Horn", "French Horn"],
  "volumes": [100, 100, 100, 100],
  "layout_changes": [[0, "4/4", "C Major"]],
  "notes": [
    {
      "time_ticks": 0,
      "base_y": 165,
      "ticks": 480,
      "accidental": null,
      "pitch": 72,
      "channel": 0,
      "tied_to_next": false,
      "is_tied_target": false,
      "voice": 0
    },
    ...
  ]
}
```

### Field reference

| Field | Meaning |
|---|---|
| `key` | The piece's key name (e.g. `"A Minor"`) |
| `time_sig` | Initial time signature |
| `tempo` | Playback tempo in BPM |
| `instruments` | One General MIDI instrument name per voice |
| `volumes` | One MIDI volume per voice (0–127) |
| `layout_changes` | List of `[bar_index, time_sig, key_sig]` triples |
| `notes` | The note list |

### Note fields

| Field | Meaning |
|---|---|
| `time_ticks` | Onset in ticks (480 = one quarter note) |
| `base_y` | Vertical staff position, in pixels from the top |
| `ticks` | Duration in ticks |
| `accidental` | `null`, `"sharp"`, `"flat"`, or `"natural"` |
| `pitch` | MIDI pitch (explicit; not derived from `base_y`) |
| `channel` | MIDI channel (equal to `voice` for playback) |
| `tied_to_next` | True if tied forward to the next note |
| `is_tied_target` | True if tied backward from the previous note |
| `voice` | 0 = soprano, 1 = alto, 2 = tenor, 3 = bass |

**Why both `base_y` and `pitch`?** `base_y` controls vertical placement
on the staff; `pitch` controls playback and analysis. For most notes
they agree, but a note outside the modelled staff range can have a
`base_y` that doesn't map to a `pitch` in `Y_TO_PITCH`, so `pitch`
carries an explicit value.

---

## Adding new rules

### Adding a fault rule

1. Add an entry to the appropriate `rules_passN.json`.
2. Ensure `check.type` names a handler that exists (registered by one
   of the `sheria_passN.py` modules).
3. Add a short label to `LABELS` and a style to `STYLE_MAP` in
   `annotation_formats.py` if you want a custom visual.
4. Restart the app. The rule is loaded automatically.

### Adding a quality rule

1. Add an entry to the appropriate `quality_passN.json`.
2. Pick a quality from `excellent`, `good`, `fair`, `discouraged`,
   `bad`.
3. Write the feedback in plain English.
4. Restart the app. The rule is loaded automatically.

### Adding a new handler

If your rule needs a new check type, add a function to the appropriate
`sheria_passN.py` and register it:

```python
def my_check(checker, rule, spec, chord, ctx, index):
    faults = []
    # ... your logic ...
    return faults

register_handlers({
    # ... existing handlers ...
    "my_check": my_check,
})
```

The `checker` helper gives you `_prev(ctx, i)` and `_next(ctx, i)` for
access to the previous and next chords in the composition.

---

## Converting a corpus of chorales

The `validation/convert_musicxml.py` script converts MusicXML, MIDI,
and Humdrum kern files into the app's `.sharm` format.

```bash
python validation/convert_musicxml.py <source_dir> <dest_dir>
```

Example: converting the Bach 370 chorales:

```bash
python validation/convert_musicxml.py bach-370-chorales/kern validation/chorales_sharm
```

Optional flags:

| Flag | Effect |
|---|---|
| `--key "C Major"` | Force the key for every file |
| `--quiet` | Suppress per-file progress output |

The converter prints one line per file with the detected key, time
signature, note count, and (importantly) the number of tie endpoints
found. If the tie count is zero for every file, the source data does
not carry ties in a form `music21` recognises.

---

## Validation and testing

### Running the built-in test chorales

```bash
python validation/run_validation.py
```

This runs the hand-crafted test chorales in
`validation/test_chorales.py` through the grader and compares the
faults found against the ones expected. Exit code 0 means all tests
passed.

### Validating a directory of converted chorales

```bash
python validation/run_validation.py --dir validation/chorales_sharm
```

This produces a per-file report and a summary count of faults grouped
by rule. A healthy engine produces a small number of faults per
chorale — the number of times Bach actually departed from the
textbook rules. A sudden spike in any single rule's count is usually a
sign of a bug in the rule or the analyzer, not a property of the
music.

### Debug output

Set `HARMONY_DEBUG=1` before launching to print every unidentified
slice to the terminal:

```bash
# PowerShell
$env:HARMONY_DEBUG = "1"
py app.py

# Bash
HARMONY_DEBUG=1 python app.py
```

Every slice the analyzer could not name appears as a line:

```
[unknown chord] pcs=[0, 2, 4, 6] pitches=[52, 62, 66, 72] key_pc=9 mode=minor
```

This is the diagnostic you want when investigating why a particular
chord is being marked with `?`.

---

## Building a standalone executable

The app can be bundled into a single `.exe` with PyInstaller. The end
user does not need Python installed.

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build

From the project root:

```bash
pyinstaller --onefile --windowed ^
    --name SmartHarmonyAssistant ^
    --add-data "assets;assets" ^
    --add-data "*.json;." ^
    --hidden-import customtkinter ^
    app.py
```

On Windows, the `^` character continues a command across lines. On
Linux/macOS use `\` instead, and change the `--add-data` separator
from `;` to `:`.

If you want to bundle a SoundFont for FluidSynth playback, add:

```
    --add-data "FluidR3_GM.sf2;."
```

Note that this will make the resulting `.exe` roughly 140 MB larger.

### Output

The bundled executable appears at `dist/SmartHarmonyAssistant.exe`.
Copy it anywhere; it is self-contained.

---

## Known limitations

The engine is designed to cover the material in Aldwell & Schachter's
*Harmony and Voice Leading* comprehensively, but there are gaps.

### Not implemented

- **Modulation tracking.** The whole piece is analysed in one home key.
  Transient modulations appear as strings of applied dominants and
  borrowed chords. A phrase-level key annotation is planned but not
  yet implemented.
- **Ninth, eleventh, and thirteenth chords as primary sonorities.**
  These appear as unrecognised or approximated. Add9 and dominant-9
  shells are recognised; full extended chords are not.
- **Altered dominants** (V⁷♭⁵, V⁷♯⁵) and **augmented triads** outside
  the six-four context.
- **Common-tone diminished seventh chords** in their full generality.
  The pass-7 rules cover the tonic-ornamenting case; other contexts
  may show as unknown.
- **Chromatic sequences and equal division of the octave.** Requires
  a sequence-detection layer.

### Behaviour to be aware of

- **Two-pitch-class slices** are labelled with an asterisk (`I*`,
  `I⁶*`) when the analyzer can identify the underlying triad. If the
  slice is genuinely ambiguous, it is left as a sparse dot.
- **Figuration onsets** are skipped by the numeral row but still shown
  in the manuscript. This is intentional — passing tones are not
  chords.
- **Roman numeral quality ratings** describe transitions, not chords.
  A `V` chord with no preceding context cannot be rated.

---

## Dependencies

| Package | Purpose |
|---|---|
| `customtkinter` | Modern Tkinter widgets |
| `Pillow` | Image processing for note assets and clefs |
| `music21` (optional) | MusicXML, MIDI, and kern conversion |
| `fluidsynth` (optional) | High-quality MIDI playback via SoundFont |
| `pyinstaller` (optional) | Building the standalone executable |

Create `requirements.txt` in the project root:

```
customtkinter>=5.2.0
Pillow>=10.0.0
music21>=9.0.0
```

FluidSynth is installed separately as a system library or Python
binding, depending on platform. The engine falls back to the Windows
MIDI API if FluidSynth is not present.

---

## Contributing

### Workflow

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/my-change`).
3. Make your changes.
4. Add tests for new rules or new behaviours.
5. Run `python validation/run_validation.py` to verify nothing broke.
6. Commit with a clear message.
7. Open a pull request.

### Code style

- Python code follows PEP 8 with a 79-column line length.
- JSON files should be indented with 2 spaces.
- New rule IDs use uppercase-with-hyphens
  (`P2-RESOLVE-LT-OUTER`, `MODAL-VII-I`).
- New quality rule IDs use the same convention
  (`CORE-I-V`, `TONICIZE-VII`).

### Reporting bugs

When reporting a bug, please include:

- The `.sharm` file that triggered it, if possible.
- The `HARMONY_DEBUG=1` output for the affected chord or transition.
- A screenshot of the manuscript showing the chord in question.

### Feature requests

Before requesting a new analytical feature, please check the
[Known limitations](#known-limitations) section. If the feature
corresponds to a specific unit in Aldwell & Schachter, cite the unit
number — the codebase is organised to mirror the book's structure.

---

## Acknowledgements

The analytical framework follows Aldwell & Schachter's *Harmony and
Voice Leading* (3rd edition), which serves as the theoretical reference
for the rule set.

The rule engine, quality analyzer, and rendering pipeline are
original. The MusicXML converter uses `music21` for parsing.

---

## License

*(Add your license here. If you intend the project to be open source,
the MIT License is a common choice for small educational tools. If
you intend it to be used with copyrighted material — like the Bach
chorales — check the terms under which your corpus is distributed.)*