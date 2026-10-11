"""Shared data constants for the Smart Harmony Assistant."""

import os
import sys


def resource_path(relative):
    """Resolve a bundled resource whether running from source or a one-file exe."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.abspath("."), relative)


TICKS_PER_BEAT = 480
TICKS_PER_WHOLE = 1920

# Legacy aliases kept so older modules (gradealgorithm, test_engine) still
# import cleanly. The bar-layout system replaces these with per-bar values,
# but nothing in the new code path uses them for anything load-bearing.
BAR_TICKS = 1920
SYSTEM_TICKS = 1920 * 4

SYSTEM_HEIGHT = 460
BASE_START_X = 140
RIGHT_MARGIN = 40
MIN_BAR_PIXEL_WIDTH = 180
MIN_PIXELS_PER_BEAT = 30
BARLINE_NUDGE = 16
TREBLE_MIDDLE_Y = 170
BASS_MIDDLE_Y = 310
STAFF_SPLIT_Y = 240
NUMERAL_ROW_Y = 420
STEM_LENGTH = 39
DEFAULT_BARS_PER_SYSTEM = 4

DURATION_TICKS = {
    "Whole": 1920, "Half": 960, "Quarter": 480,
    "Quaver": 240, "Semiquaver": 120,
}
DURATION_ORDER = ["Whole", "Half", "Quarter", "Quaver", "Semiquaver"]

# ---------------------------------------------------------------
#  Time signatures
# ---------------------------------------------------------------

TIME_SIGNATURES = {
    "2/4":  {"num": 2,  "den": 4,  "compound": False},
    "3/4":  {"num": 3,  "den": 4,  "compound": False},
    "4/4":  {"num": 4,  "den": 4,  "compound": False},
    "2/2":  {"num": 2,  "den": 2,  "compound": False},
    "3/2":  {"num": 3,  "den": 2,  "compound": False},
    "4/2":  {"num": 4,  "den": 2,  "compound": False},
    "2/8":  {"num": 2,  "den": 8,  "compound": False},
    "3/8":  {"num": 3,  "den": 8,  "compound": False},
    "4/8":  {"num": 4,  "den": 8,  "compound": False},
    "6/8":  {"num": 6,  "den": 8,  "compound": True},
    "9/8":  {"num": 9,  "den": 8,  "compound": True},
    "12/8": {"num": 12, "den": 8,  "compound": True},
    "6/4":  {"num": 6,  "den": 4,  "compound": True},
}

TIME_SIGNATURE_ORDER = [
    "2/4", "3/4", "4/4", "2/2", "3/2", "4/2",
    "3/8", "6/8", "9/8", "12/8",
    "2/8", "4/8", "6/4",
]

DEFAULT_TIME_SIGNATURE = "4/4"


def ticks_per_bar_from_ts(ts_name):
    """Return the tick length of one bar in the given time signature."""
    info = TIME_SIGNATURES.get(ts_name)
    if info is None:
        return TICKS_PER_WHOLE
    return int(info["num"] * (TICKS_PER_WHOLE / info["den"]))


def beat_ticks_from_ts(ts_name):
    """Return the tick length of one beat in the given time signature."""
    info = TIME_SIGNATURES.get(ts_name)
    if info is None:
        return TICKS_PER_BEAT
    return int(TICKS_PER_WHOLE / info["den"])


Y_TO_PITCH = {
    120: 88, 125: 86, 130: 84, 135: 83, 140: 81, 145: 79, 150: 77, 155: 76,
    160: 74, 165: 72, 170: 71, 175: 69, 180: 67, 185: 65, 190: 64, 195: 62,
    200: 60, 205: 59, 210: 57,
    270: 64, 275: 62, 280: 60, 285: 59, 290: 57, 295: 55, 300: 53, 305: 52,
    310: 50, 315: 48, 320: 47, 325: 45, 330: 43, 335: 41, 340: 40, 345: 38, 350: 36,
}

# ---------------------------------------------------------------
#  Key signatures — all fifteen major keys, including enharmonic
#  duplicates.
#
#  Each entry holds the tonic pitch (MIDI) and the accidentals
#  drawn at the start of each system. The accidentals list contains
#  (type, treble_y, bass_y) tuples where type is "sharp" or "flat",
#  and the y-coordinates are the staff positions on the treble and
#  bass staves respectively.
#
#  Sharps are laid out in the standard order F C G D A E B; flats
#  in the standard order B E A D G C F. Positions match the treble
#  and bass staffs as rendered by rendering.draw_staff.
# ---------------------------------------------------------------

KEY_SIGNATURES = {
    # --- Sharp keys ---
    "C Major": {
        "root": 60,
        "accidentals": [],
    },
    "G Major": {
        "root": 67,
        "accidentals": [("sharp", 150, 300)],
    },
    "D Major": {
        "root": 62,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315),
        ],
    },
    "A Major": {
        "root": 69,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315), ("sharp", 145, 295),
        ],
    },
    "E Major": {
        "root": 64,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315),
            ("sharp", 145, 295), ("sharp", 160, 310),
        ],
    },
    "B Major": {
        "root": 71,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315),
            ("sharp", 145, 295), ("sharp", 160, 310), ("sharp", 175, 325),
        ],
    },
    "F# Major": {
        "root": 66,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315),
            ("sharp", 145, 295), ("sharp", 160, 310),
            ("sharp", 175, 325), ("sharp", 155, 305),
        ],
    },
    "C# Major": {
        "root": 61,
        "accidentals": [
            ("sharp", 150, 300), ("sharp", 165, 315),
            ("sharp", 145, 295), ("sharp", 160, 310),
            ("sharp", 175, 325), ("sharp", 155, 305),
            ("sharp", 170, 320),
        ],
    },

    # --- Flat keys ---
    "F Major": {
        "root": 65,
        "accidentals": [("flat", 170, 320)],
    },
    "Bb Major": {
        "root": 70,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305),
        ],
    },
    "Eb Major": {
        "root": 63,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305), ("flat", 175, 325),
        ],
    },
    "Ab Major": {
        "root": 68,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305),
            ("flat", 175, 325), ("flat", 160, 310),
        ],
    },
    "Db Major": {
        "root": 61,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305),
            ("flat", 175, 325), ("flat", 160, 310), ("flat", 180, 330),
        ],
    },
    "Gb Major": {
        "root": 66,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305),
            ("flat", 175, 325), ("flat", 160, 310),
            ("flat", 180, 330), ("flat", 165, 315),
        ],
    },
    "Cb Major": {
        "root": 71,
        "accidentals": [
            ("flat", 170, 320), ("flat", 155, 305),
            ("flat", 175, 325), ("flat", 160, 310),
            ("flat", 180, 330), ("flat", 165, 315),
            ("flat", 185, 300),
        ],
    },
}

# ---------------------------------------------------------------
#  Key offsets — per signature, the pitch-class adjustments applied
#  to natural note positions when a key signature is active.
#
#  A sharp raises a natural note by one semitone; a flat lowers it.
#  E# is enharmonically F natural, so its pitch class (5) gets +1
#  to produce E# (pc 5, but the pitch is F). Same for B# and Cb.
# ---------------------------------------------------------------

KEY_OFFSETS = {
    # Sharp keys
    "C Major":  {},
    "G Major":  {5: 1},
    "D Major":  {5: 1, 0: 1},
    "A Major":  {5: 1, 0: 1, 7: 1},
    "E Major":  {5: 1, 0: 1, 7: 1, 2: 1},
    "B Major":  {5: 1, 0: 1, 7: 1, 2: 1, 9: 1},
    "F# Major": {5: 1, 0: 1, 7: 1, 2: 1, 9: 1, 4: 1},
    "C# Major": {5: 1, 0: 1, 7: 1, 2: 1, 9: 1, 4: 1, 11: 1},
    # Flat keys
    "F Major":  {11: -1},
    "Bb Major": {11: -1, 4: -1},
    "Eb Major": {11: -1, 4: -1, 9: -1},
    "Ab Major": {11: -1, 4: -1, 9: -1, 2: -1},
    "Db Major": {11: -1, 4: -1, 9: -1, 2: -1, 7: -1},
    "Gb Major": {11: -1, 4: -1, 9: -1, 2: -1, 7: -1, 0: -1},
    "Cb Major": {11: -1, 4: -1, 9: -1, 2: -1, 7: -1, 0: -1, 5: -1},
}

# ---------------------------------------------------------------
#  KEYS — the full menu of selectable keys.
#
#  Each entry maps a user-facing key name to its tonic pitch, the
#  signature it uses for the staff (always the major key that owns
#  the accidentals), and its mode. Enharmonic equivalents are listed
#  as separate entries so the user can spell the piece the way they
#  want; internally they will analyse identically.
# ---------------------------------------------------------------

KEYS = {
    # --- Major keys, sharp signatures ---
    "C Major":  {"root": 60, "signature": "C Major",  "mode": "major"},
    "G Major":  {"root": 67, "signature": "G Major",  "mode": "major"},
    "D Major":  {"root": 62, "signature": "D Major",  "mode": "major"},
    "A Major":  {"root": 69, "signature": "A Major",  "mode": "major"},
    "E Major":  {"root": 64, "signature": "E Major",  "mode": "major"},
    "B Major":  {"root": 71, "signature": "B Major",  "mode": "major"},
    "F# Major": {"root": 66, "signature": "F# Major", "mode": "major"},
    "C# Major": {"root": 61, "signature": "C# Major", "mode": "major"},

    # --- Major keys, flat signatures ---
    "F Major":  {"root": 65, "signature": "F Major",  "mode": "major"},
    "Bb Major": {"root": 70, "signature": "Bb Major", "mode": "major"},
    "Eb Major": {"root": 63, "signature": "Eb Major", "mode": "major"},
    "Ab Major": {"root": 68, "signature": "Ab Major", "mode": "major"},
    "Db Major": {"root": 61, "signature": "Db Major", "mode": "major"},
    "Gb Major": {"root": 66, "signature": "Gb Major", "mode": "major"},
    "Cb Major": {"root": 71, "signature": "Cb Major", "mode": "major"},

    # --- Minor keys, sharp signatures ---
    "A Minor":  {"root": 69, "signature": "C Major",  "mode": "minor"},
    "E Minor":  {"root": 64, "signature": "G Major",  "mode": "minor"},
    "B Minor":  {"root": 71, "signature": "D Major",  "mode": "minor"},
    "F# Minor": {"root": 66, "signature": "A Major",  "mode": "minor"},
    "C# Minor": {"root": 61, "signature": "E Major",  "mode": "minor"},
    "G# Minor": {"root": 68, "signature": "B Major",  "mode": "minor"},
    "D# Minor": {"root": 63, "signature": "F# Major", "mode": "minor"},
    "A# Minor": {"root": 70, "signature": "C# Major", "mode": "minor"},

    # --- Minor keys, flat signatures ---
    "D Minor":  {"root": 62, "signature": "F Major",  "mode": "minor"},
    "G Minor":  {"root": 67, "signature": "Bb Major", "mode": "minor"},
    "C Minor":  {"root": 60, "signature": "Eb Major", "mode": "minor"},
    "F Minor":  {"root": 65, "signature": "Ab Major", "mode": "minor"},
    "Bb Minor": {"root": 70, "signature": "Db Major", "mode": "minor"},
    "Eb Minor": {"root": 63, "signature": "Gb Major", "mode": "minor"},
    "Ab Minor": {"root": 68, "signature": "Cb Major", "mode": "minor"},
}

GM_INSTRUMENTS = {
    "Acoustic Grand Piano": 0, "Bright Acoustic Piano": 1, "Electric Grand Piano": 2,
    "Honky-tonk Piano": 3, "Electric Piano 1": 4, "Electric Piano 2": 5,
    "Harpsichord": 6, "Clavinet": 7,
    "Celesta": 8, "Glockenspiel": 9, "Music Box": 10, "Vibraphone": 11,
    "Marimba": 12, "Xylophone": 13, "Tubular Bells": 14, "Dulcimer": 15,
    "Drawbar Organ": 16, "Percussive Organ": 17, "Rock Organ": 18,
    "Church Organ": 19, "Reed Organ": 20, "Accordion": 21,
    "Harmonica": 22, "Tango Accordion": 23,
    "Acoustic Guitar (nylon)": 24, "Acoustic Guitar (steel)": 25,
    "Electric Guitar (jazz)": 26, "Electric Guitar (clean)": 27,
    "Electric Guitar (muted)": 28, "Overdriven Guitar": 29,
    "Distortion Guitar": 30, "Guitar Harmonics": 31,
    "Acoustic Bass": 32, "Electric Bass (finger)": 33,
    "Electric Bass (pick)": 34, "Fretless Bass": 35,
    "Slap Bass 1": 36, "Slap Bass 2": 37, "Synth Bass 1": 38, "Synth Bass 2": 39,
    "Violin": 40, "Viola": 41, "Cello": 42, "Contrabass": 43,
    "Tremolo Strings": 44, "Pizzicato Strings": 45,
    "Orchestral Harp": 46, "Timpani": 47,
    "String Ensemble 1": 48, "String Ensemble 2": 49,
    "SynthStrings 1": 50, "SynthStrings 2": 51,
    "Choir Aahs": 52, "Voice Oohs": 53, "Synth Voice": 54, "Orchestra Hit": 55,
    "Trumpet": 56, "Trombone": 57, "Tuba": 58, "Muted Trumpet": 59,
    "French Horn": 60, "Brass Section": 61, "SynthBrass 1": 62, "SynthBrass 2": 63,
    "Soprano Sax": 64, "Alto Sax": 65, "Tenor Sax": 66, "Baritone Sax": 67,
    "Oboe": 68, "English Horn": 69, "Bassoon": 70, "Clarinet": 71,
    "Piccolo": 72, "Flute": 73, "Recorder": 74, "Pan Flute": 75,
    "Blown Bottle": 76, "Shakuhachi": 77, "Whistle": 78, "Ocarina": 79,
    "Lead 1 (square)": 80, "Lead 2 (sawtooth)": 81,
    "Lead 3 (calliope)": 82, "Lead 4 (chiff)": 83,
    "Lead 5 (charang)": 84, "Lead 6 (voice)": 85,
    "Lead 7 (fifths)": 86, "Lead 8 (bass + lead)": 87,
    "Pad 1 (new age)": 88, "Pad 2 (warm)": 89, "Pad 3 (polysynth)": 90,
    "Pad 4 (choir)": 91, "Pad 5 (bowed)": 92, "Pad 6 (metallic)": 93,
    "Pad 7 (halo)": 94, "Pad 8 (sweep)": 95,
    "FX 1 (rain)": 96, "FX 2 (soundtrack)": 97, "FX 3 (crystal)": 98,
    "FX 4 (atmosphere)": 99, "FX 5 (brightness)": 100, "FX 6 (goblins)": 101,
    "FX 7 (echoes)": 102, "FX 8 (sci-fi)": 103,
    "Sitar": 104, "Banjo": 105, "Shamisen": 106, "Koto": 107,
    "Kalimba": 108, "Bagpipe": 109, "Fiddle": 110, "Shanai": 111,
    "Tinkle Bell": 112, "Agogo": 113, "Steel Drums": 114, "Woodblock": 115,
    "Taiko Drum": 116, "Melodic Tom": 117, "Synth Drum": 118, "Reverse Cymbal": 119,
    "Guitar Fret Noise": 120, "Breath Noise": 121, "Seashore": 122,
    "Bird Tweet": 123, "Telephone Ring": 124, "Helicopter": 125,
    "Applause": 126, "Gunshot": 127,
}

QUALITY_COLORS = {
    "excellent":    "#017327",
    "good":         "#96D4E0",
    "fair":         "#F8E80D",
    "discouraged":  "#FF7B00",
    "bad":          "#D40000",
    "default":      "#F605AE",
}