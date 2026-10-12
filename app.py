import importlib
import json
import os
import sys
from tkinter import filedialog, messagebox

import customtkinter as ctk

from engine import VerticalSlice, NoteNode, PlaybackEngine
from playback_controller import PlaybackController
from sheria import KeySignature, RomanNumeralAnalyzer, RulesEngine, SubmissionEngine
from settings_ui import SettingsModal
from quality import ProgressionQualityAnalyzer
from gradealgorithm import grade as standardize_grade
import annotation_formats

from constants import (
    GM_INSTRUMENTS, KEY_SIGNATURES, KEY_OFFSETS, KEYS, Y_TO_PITCH,
    DURATION_TICKS, DURATION_ORDER,
    SYSTEM_HEIGHT, NUMERAL_ROW_Y,
    BASE_START_X, RIGHT_MARGIN, MIN_BAR_PIXEL_WIDTH,
    QUALITY_COLORS, resource_path,
    TIME_SIGNATURE_ORDER, DEFAULT_TIME_SIGNATURE, DEFAULT_BARS_PER_SYSTEM,
)
from harmony import (
    time_to_visual, visual_to_time, note_visual_x, can_place_note,
    assign_voices, stem_for_voice, barline_nudge_for, find_beam_groups,
    build_vertical_slices, assign_offsets,
)
from rendering import (
    generate_note_assets, draw_staff, draw_ledger_lines, draw_note,
    draw_beam_group, draw_tie, draw_time_signature_change,
    draw_chord_accidentals,
)
from bar_layout import BarLayout
from figuration import harmonic_onsets


TIER_COLORS = {
    "PHYSICAL": "#FF8800",
    "VOICE_LEADING": "#D40000",
    "CONTEXTUAL": "#8800CC",
    "CHROMATIC": "#8800CC",
}

VOICE_INDEX = {"soprano": 0, "alto": 1, "tenor": 2, "bass": 3}

VOICE_COLORS = {
    0: "#1E88E5",
    1: "#00A67E",
    2: "#FB8C00",
    3: "#8E24AA",
}

VOICE_COLOR_RGB = {
    0: (30, 136, 229, 255),
    1: (0, 166, 126, 255),
    2: (251, 140, 0, 255),
    3: (142, 36, 170, 255),
}

DRAG_THRESHOLD_PX = 5
SNAP_RADIUS_PX = 18
TIMESIG_TO_NOTES_PAD = 50
MIN_PX_PER_ONSET = 40
PLAYHEAD_AUTOSCROLL_MARGIN = 50

NUMERAL_MAX_ROWS = 3


_MAJOR_ROMAN_INTERVALS = {
    "I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11,
}
_MINOR_ROMAN_INTERVALS = {
    "I": 0, "II": 2, "III": 3, "IV": 5, "V": 7, "VI": 8, "VII": 10,
}

_MAJOR_TRIAD_INTERVALS = {
    "I": (4, 7), "II": (3, 7), "III": (3, 7), "IV": (4, 7),
    "V": (4, 7), "VI": (3, 7), "VII": (3, 6),
}
_MINOR_TRIAD_INTERVALS = {
    "I": (3, 7), "II": (3, 6), "III": (4, 7), "IV": (3, 7),
    "V": (4, 7), "VI": (4, 7), "VII": (4, 7),
}

_ASTERISK = "*"

_FIGURE_CHARS = (
    "\u2070", "\u00B9", "\u00B2", "\u00B3", "\u2074", "\u2075",
    "\u2076", "\u2077", "\u2078", "\u2079",
    "\u2080", "\u2081", "\u2082", "\u2083", "\u2084", "\u2085",
    "\u2086", "\u2087", "\u2088", "\u2089",
    "\u00B0", "\u00F8", "+",
)


class SmartHarmonyAssistant(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Smart Harmony Assistant (Prototype)")
        self.geometry("1400x900")
        self.configure(fg_color="#FFFDD0")

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1, minsize=350)

        self.START_X = 170
        self.bars_per_system = DEFAULT_BARS_PER_SYSTEM
        self.bar_pixel_width = 200
        self.notes_db = []
        self.selected_note = None

        self._undo_stack = []
        self._voices_from_file = False
        self.filter_figuration = True
        self._last_mouse_xy = (0, 0)

        self._drag_note = None
        self._drag_start_xy = None
        self._drag_start_tick = None
        self._drag_start_base_y = None
        self._is_dragging = False
        self._drag_target = None

        self.report_faults = []
        self.active_fault_indices = set()

        self.progression_quality = {}
        self.numeral_hitboxes = []
        self.active_quality_tick = None

        self._numeral_font_px = 14
        self._numeral_placed = []

        self.current_key_name = "C Major"
        self.current_signature_name = "C Major"
        self.current_mode = "major"
        self.current_time_sig = DEFAULT_TIME_SIGNATURE
        self.current_tempo = 120
        self.active_insts = ["French Horn"] * 4
        self.active_vols = [100, 100, 100, 100]

        self.bar_layout = BarLayout(
            initial_time_sig=self.current_time_sig,
            initial_key_sig=self.current_signature_name,
            num_bars=self.bars_per_system,
        )

        self.analyzer = RomanNumeralAnalyzer()
        self.playback_engine = PlaybackEngine(sf2_path=resource_path("FluidR3_GM.sf2"))
        self.playback = PlaybackController(self.playback_engine,
                                           tempo=self.current_tempo)
        self.playback.on_finish = self._on_playback_finished
        self.rules_engine = RulesEngine()
        self.grader = SubmissionEngine()
        self.quality_analyzer = ProgressionQualityAnalyzer()

        self.key_signature = KeySignature(
            KEYS[self.current_key_name]["root"],
            mode=KEYS[self.current_key_name]["mode"])
        self.START_X = self._compute_start_x_for_signature(
            self.current_signature_name)

        self.note_assets_default = generate_note_assets()
        self.note_assets_by_voice = {
            v: generate_note_assets(base_color=rgb)
            for v, rgb in VOICE_COLOR_RGB.items()
        }
        self.note_assets = self.note_assets_default
        self.color_voices_enabled = True

        self._playhead_poll_id = None
        self._playhead_active = False
        self._barline_hitboxes = []
        self._last_loaded_path = None

        self._build_navbar()
        self._build_canvas()
        self._build_side_panel()
        self._bind_events()
        self._update_key_label()

    # ---------------------------------------------------------------
    # Layout helpers
    # ---------------------------------------------------------------
    def _compute_start_x_for_signature(self, signature_name):
        info = KEY_SIGNATURES.get(signature_name, KEY_SIGNATURES["C Major"])
        return 110 + len(info["accidentals"]) * 16 + 15 + TIMESIG_TO_NOTES_PAD

    def _compute_effective_bars_per_system(self):
        canvas_w = self.canvas.winfo_width()
        if canvas_w < 200:
            canvas_w = 1100
        available = canvas_w - RIGHT_MARGIN - self.START_X
        if available <= 0:
            return 1
        max_onsets = 1
        if self.notes_db and self.bar_layout.count > 0:
            onsets_by_bar = {}
            for n in self.notes_db:
                bar_idx, _ = self.bar_layout.locate(n['time_ticks'])
                onsets_by_bar.setdefault(bar_idx, set()).add(n['time_ticks'])
            if onsets_by_bar:
                max_onsets = max(len(s) for s in onsets_by_bar.values())
        required = max(MIN_BAR_PIXEL_WIDTH, max_onsets * MIN_PX_PER_ONSET)
        target = DEFAULT_BARS_PER_SYSTEM
        while target > 1 and available / target < required:
            target -= 1
        return max(1, target)

    # ---------------------------------------------------------------
    # Numeral label placement
    # ---------------------------------------------------------------
    def _compute_numeral_font_px(self, harmonic_onsets_set):
        if not self.notes_db:
            return 14
        onsets = sorted({n['time_ticks'] for n in self.notes_db})
        if harmonic_onsets_set is None:
            num_harmonic = len(onsets)
        else:
            num_harmonic = sum(1 for t in onsets if t in harmonic_onsets_set)
        num_bars = max(1, self.bar_layout.count)
        avg = num_harmonic / num_bars
        if avg >= 8:
            return 9
        if avg >= 6:
            return 10
        if avg >= 4:
            return 12
        return 14

    def _place_numeral_label(self, x, base_y, text):
        size = self._numeral_font_px
        width = len(text) * size * 0.58 + 6
        left = x - width / 2
        right = x + width / 2
        label_h = size + 4
        row_spacing = size + 8

        for row in range(NUMERAL_MAX_ROWS):
            center_y = base_y + row * row_spacing
            top = center_y - label_h / 2
            bot = center_y + label_h / 2
            hit = False
            for (l, r, pt, pb) in self._numeral_placed:
                if (not (right < l or left > r)) and \
                   (not (bot < pt or top > pb)):
                    hit = True
                    break
            if not hit:
                self._numeral_placed.append((left, right, top, bot))
                return (x, center_y)
        return None

    # ---------------------------------------------------------------
    # Incomplete-triad explanation
    # ---------------------------------------------------------------
    def _describe_missing_tone(self, vs, label, key_sig):
        base = label
        if base.endswith(_ASTERISK):
            base = base[:-1]
        for fig in _FIGURE_CHARS:
            base = base.replace(fig, "")
        base = base.upper()
        if not base:
            return ""

        mode = getattr(key_sig, "mode", "major")
        interval_table = (_MINOR_ROMAN_INTERVALS if mode == "minor"
                          else _MAJOR_ROMAN_INTERVALS)
        interval = interval_table.get(base)
        if interval is None:
            return ""

        triad_table = (_MINOR_TRIAD_INTERVALS if mode == "minor"
                       else _MAJOR_TRIAD_INTERVALS)
        third_int, fifth_int = triad_table.get(base, (4, 7))

        key_pc = key_sig.root_pitch_class
        root_pc = (key_pc + interval) % 12
        third_pc = (root_pc + third_int) % 12
        fifth_pc = (root_pc + fifth_int) % 12

        present = {n.pitch % 12 for n in vs.get_notes()}
        missing = []
        if root_pc not in present:
            missing.append("root")
        if third_pc not in present:
            missing.append("third")
        if fifth_pc not in present:
            missing.append("fifth")

        if not missing:
            return ""
        if len(missing) == 1:
            return (f"Incomplete triad — the {missing[0]} has dropped "
                    f"out of the texture.")
        return (f"Incomplete triad — the {' and '.join(missing)} have "
                f"dropped out of the texture.")

    # ---------------------------------------------------------------
    # Undo stack
    # ---------------------------------------------------------------
    def _push_undo(self):
        snapshot = {
            "notes": [dict(n) for n in self.notes_db],
            "time_sig": self.current_time_sig,
            "key": self.current_key_name,
            "layout_changes": list(self.bar_layout._changes),
            "voices_from_file": self._voices_from_file,
        }
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _undo(self, event=None):
        if not self._undo_stack:
            self._set_status_message("Nothing to undo.")
            return
        snap = self._undo_stack.pop()
        self.notes_db = snap["notes"]
        self.current_time_sig = snap["time_sig"]
        self.current_key_name = snap["key"]
        self._voices_from_file = snap.get("voices_from_file", False)
        self._apply_key(self.current_key_name)
        self.bar_layout._changes = list(snap["layout_changes"])
        self.bar_layout.reflow(max(self.bars_per_system, self.bar_layout.count))
        self.key_signature = KeySignature(
            KEYS[self.current_key_name]["root"],
            mode=KEYS[self.current_key_name]["mode"])
        self.selected_note = None
        self._clear_annotations()

    def _apply_key(self, key_name):
        info = KEYS.get(key_name, KEYS["C Major"])
        self.current_key_name = key_name if key_name in KEYS else "C Major"
        self.current_signature_name = info["signature"]
        self.current_mode = info["mode"]
        self.key_signature = KeySignature(info["root"], mode=info["mode"])
        self.START_X = self._compute_start_x_for_signature(
            self.current_signature_name)
        self._update_key_label()
        self._redraw_all()

    def _update_key_label(self):
        label = getattr(self, "key_label", None)
        if label is None:
            return
        label.configure(text=f"Key: {self.current_key_name}  "
                             f"({self.current_mode.capitalize()})")

    # ---------------------------------------------------------------
    # UI construction
    # ---------------------------------------------------------------
    def _build_navbar(self):
        self.navbar = ctk.CTkFrame(self, fg_color="#F5F5DC", corner_radius=0, height=60)
        self.navbar.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.active_duration = ctk.StringVar(value="Quarter")
        ctk.CTkSegmentedButton(
            self.navbar, values=DURATION_ORDER, variable=self.active_duration,
            selected_color="#008080", selected_hover_color="#006666"
        ).pack(side="left", padx=20, pady=15)

        ctk.CTkButton(self.navbar, text="Tie (T)", width=70, fg_color="#555555",
                      command=self._tie_note).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.navbar, text="Repeat (R)", width=80, fg_color="#555555",
                      command=self._repeat_last_note).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.navbar, text="Undo (Ctrl+Z)", width=110, fg_color="#666666",
                      command=self._undo).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.navbar, text="Save", width=60, fg_color="#4B7B7B",
                      command=self._save_workspace).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.navbar, text="Load", width=60, fg_color="#4B7B7B",
                      command=self._load_workspace).pack(side="left", padx=(0, 6))
        ctk.CTkButton(self.navbar, text="Import", width=80, fg_color="#4B7B7B",
                      command=self._import_musicxml).pack(side="left", padx=(0, 6))

        self.color_voices_var = ctk.BooleanVar(value=True)
        voice_toggle_frame = ctk.CTkFrame(self.navbar, fg_color="transparent")
        voice_toggle_frame.pack(side="right", padx=(0, 20))
        ctk.CTkLabel(voice_toggle_frame, text="Voice Colors:",
                     font=("Helvetica", 11), text_color="#333333"
                     ).pack(side="left", padx=(0, 6))
        self.color_voices_switch = ctk.CTkSwitch(
            voice_toggle_frame, text="", variable=self.color_voices_var,
            command=self._on_color_toggle, onvalue=True, offvalue=False,
            progress_color="#008080", width=40)
        self.color_voices_switch.pack(side="left")

        ctk.CTkButton(self.navbar, text="Settings", fg_color="#008080",
                      command=self._open_settings).pack(side="right", padx=20)

    def _on_color_toggle(self):
        self.color_voices_enabled = bool(self.color_voices_var.get())
        self._redraw_all()

    def _build_canvas(self):
        self.canvas_scroll = ctk.CTkScrollableFrame(self, fg_color="#FFFFFF", corner_radius=0)
        self.canvas_scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        self.canvas = ctk.CTkCanvas(self.canvas_scroll, bg="#FFFDF5",
                                    highlightthickness=0, height=1200)
        self.canvas.pack(fill="both", expand=True)

    def _build_side_panel(self):
        self.side_panel = ctk.CTkFrame(self, fg_color="#F5F5DC", corner_radius=0)
        self.side_panel.grid(row=1, column=1, sticky="nsew")

        ctk.CTkLabel(self.side_panel, text="Red Pen Report",
                     font=("Helvetica", 18, "bold"),
                     text_color="#008080").pack(pady=(16, 4))

        self.key_label = ctk.CTkLabel(self.side_panel,
                                      text="Key: C Major  (Major)",
                                      font=("Helvetica", 12, "bold"),
                                      text_color="#555555")
        self.key_label.pack(pady=(0, 8))

        ctk.CTkButton(self.side_panel, text="Submit Harmony",
                      fg_color="#008080", corner_radius=0, height=32,
                      command=self.on_submit).pack(pady=4, padx=20, fill="x")

        controls = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        controls.pack(pady=(4, 2), padx=20, fill="x")
        for c in range(4):
            controls.grid_columnconfigure(c, weight=1)
        ctk.CTkButton(controls, text="\u23EE", width=36, height=32,
                      fg_color="#4B7B7B", hover_color="#3A6161",
                      command=self._playback_to_start
                      ).grid(row=0, column=0, padx=1)
        ctk.CTkButton(controls, text="\u23EA", width=36, height=32,
                      fg_color="#4B7B7B", hover_color="#3A6161",
                      command=self._playback_back_bar
                      ).grid(row=0, column=1, padx=1)
        self.play_btn = ctk.CTkButton(
            controls, text="\u25B6 Play", height=32, fg_color="#005580",
            hover_color="#003F5C", command=self._playback_toggle)
        self.play_btn.grid(row=0, column=2, padx=1, sticky="ew")
        ctk.CTkButton(controls, text="\u23E9", width=36, height=32,
                      fg_color="#4B7B7B", hover_color="#3A6161",
                      command=self._playback_forward_bar
                      ).grid(row=0, column=3, padx=1)

        self.position_slider = ctk.CTkSlider(
            self.side_panel, from_=0, to=1, height=14,
            fg_color="#CCCCCC", progress_color="#005580",
            button_color="#005580", button_hover_color="#003F5C",
            command=self._on_slider_move)
        self.position_slider.pack(pady=(6, 0), padx=24, fill="x")
        self.position_slider.set(0)
        self._slider_dragging = False
        self.position_slider.bind("<ButtonPress-1>",
                                  lambda e: self._on_slider_press())
        self.position_slider.bind("<ButtonRelease-1>",
                                  lambda e: self._on_slider_release())

        ctk.CTkLabel(self.side_panel, text="Position",
                     font=("Helvetica", 9, "italic"),
                     text_color="#888888").pack(pady=(0, 6))

        legend = ctk.CTkFrame(self.side_panel, fg_color="transparent")
        legend.pack(pady=(4, 0), padx=16, fill="x")
        legend.grid_columnconfigure(0, weight=1)
        legend.grid_columnconfigure(1, weight=1)

        tier_frame = ctk.CTkFrame(legend, fg_color="transparent")
        tier_frame.grid(row=0, column=0, sticky="nw")
        for tier, color in TIER_COLORS.items():
            row = ctk.CTkFrame(tier_frame, fg_color="transparent")
            row.pack(anchor="w")
            ctk.CTkLabel(row, text="\u25CF", text_color=color,
                         font=("Helvetica", 11)).pack(side="left")
            ctk.CTkLabel(row, text=" " + tier.replace("_", " ").title(),
                         font=("Helvetica", 9), text_color="#555555").pack(side="left")

        q_frame = ctk.CTkFrame(legend, fg_color="transparent")
        q_frame.grid(row=0, column=1, sticky="nw")
        for q in ["excellent", "good", "fair", "discouraged", "bad"]:
            row = ctk.CTkFrame(q_frame, fg_color="transparent")
            row.pack(anchor="w")
            ctk.CTkLabel(row, text="\u25CF", text_color=QUALITY_COLORS[q],
                         font=("Helvetica", 11)).pack(side="left")
            ctk.CTkLabel(row, text=" " + q.title(),
                         font=("Helvetica", 9), text_color="#555555").pack(side="left")

        voice_legend = ctk.CTkFrame(legend, fg_color="transparent")
        voice_legend.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ctk.CTkLabel(voice_legend, text="Voices:  ",
                     font=("Helvetica", 9), text_color="#555555").pack(side="left")
        for v_idx, short in [(0, "S"), (1, "A"), (2, "T"), (3, "B")]:
            ctk.CTkLabel(voice_legend, text="\u25CF ",
                         text_color=VOICE_COLORS[v_idx],
                         font=("Helvetica", 13, "bold")).pack(side="left")
            ctk.CTkLabel(voice_legend, text=f"{short}   ",
                         font=("Helvetica", 10), text_color="#333333").pack(side="left")

        ctk.CTkLabel(self.side_panel,
                     text="(click a fault to toggle its mark  \u2022  "
                          "click a numeral for analysis  \u2022  "
                          "click a barline to change its meter  \u2022  "
                          "Shift+click a barline for key)",
                     font=("Helvetica", 9, "italic"),
                     text_color="#888888",
                     wraplength=320, justify="center").pack(pady=(6, 4), padx=10)

        self.report_frame = ctk.CTkScrollableFrame(self.side_panel, fg_color="transparent")
        self.report_frame.pack(fill="both", expand=True, pady=(4, 4), padx=6)

        hint = ctk.CTkFrame(self.side_panel, fg_color="#E8E8D0", corner_radius=0)
        hint.pack(side="bottom", fill="x", pady=(4, 0))
        ctk.CTkLabel(
            hint,
            text=("Editing:  drag a note  \u2022  Del removes  \u2022  "
                  "click empty space to add  \u2022  Ctrl+Z undoes  \u2022  "
                  "space bar plays/pauses  \u2022  \u2190/\u2192 skip a bar"),
            font=("Helvetica", 9, "italic"),
            text_color="#555555",
            wraplength=320, justify="left",
        ).pack(padx=10, pady=6)

    def _bind_events(self):
        self.canvas.bind("<Configure>", lambda e: self._redraw_all())
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_drag_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_release)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", lambda e: self.canvas.configure(cursor=""))
        self.bind("<Up>", self._on_up_arrow)
        self.bind("<Down>", self._on_down_arrow)
        self.bind("<BackSpace>", self._on_delete_key)
        self.bind("<Delete>", self._on_delete_key)
        self.bind("<Control-z>", self._undo)
        self.bind("<Control-Z>", self._undo)
        self.bind("t", lambda e: self._tie_note())
        self.bind("T", lambda e: self._tie_note())
        self.bind("r", self._repeat_last_note)
        self.bind("R", self._repeat_last_note)
        self.bind("<space>", lambda e: self._playback_toggle())
        for key, acc in (("s", "sharp"), ("S", "sharp"),
                         ("f", "flat"), ("F", "flat"),
                         ("n", "natural"), ("N", "natural")):
            self.bind(key, lambda e, a=acc: self._set_accidental(a))
        self.bind("<Control-d>", self._dump_last_slices)

    # ---------------------------------------------------------------
    # Playback
    # ---------------------------------------------------------------
    def _on_playback_finished(self):
        self.after(0, self._playback_stopped_ui)

    def _playback_stopped_ui(self):
        self._playhead_active = False
        if self._playhead_poll_id is not None:
            try:
                self.after_cancel(self._playhead_poll_id)
            except Exception:
                pass
            self._playhead_poll_id = None
        self.play_btn.configure(text="\u25B6 Play")
        self.canvas.delete("playhead")

    def _playback_toggle(self):
        if self.playback.is_playing:
            self.playback.pause()
            self.play_btn.configure(text="\u25B6 Play")
            self._playhead_active = False
            return
        if self.playback.is_paused:
            self.playback.resume()
            self.play_btn.configure(text="\u23F8 Pause")
            self._playhead_active = True
            self._start_playhead_poll()
            return
        if not self.notes_db:
            self._set_status_message("Nothing to play.")
            return
        self.playback.set_tempo(self.current_tempo)
        self.playback.play(self.notes_db, from_tick=self.playback.current_tick)
        self.play_btn.configure(text="\u23F8 Pause")
        self._playhead_active = True
        self._start_playhead_poll()

    def _playback_to_start(self):
        self.playback.stop()
        self.playback.seek(0)
        self.play_btn.configure(text="\u25B6 Play")
        self._playhead_active = False
        self.canvas.delete("playhead")
        self.position_slider.set(0)

    def _playback_back_bar(self):
        tick = self.playback.current_tick
        bar_idx, _ = self.bar_layout.locate(tick)
        bar = self.bar_layout.bars[bar_idx]
        if tick - bar.start_tick > 100 and bar_idx > 0:
            target = bar.start_tick
        else:
            target = self.bar_layout.bars[max(0, bar_idx - 1)].start_tick
        self._playback_seek(target)

    def _playback_forward_bar(self):
        tick = self.playback.current_tick
        bar_idx, _ = self.bar_layout.locate(tick)
        next_idx = min(bar_idx + 1, self.bar_layout.count - 1)
        self._playback_seek(self.bar_layout.bars[next_idx].start_tick)

    def _playback_seek(self, tick):
        was_playing = self.playback.is_playing
        self.playback.seek(tick)
        if was_playing:
            self._playhead_active = True
            self._start_playhead_poll()
        else:
            self._playhead_active = False
            self._draw_playhead()
        self._update_slider_from_tick(tick)

    def _start_playhead_poll(self):
        if self._playhead_poll_id is not None:
            try:
                self.after_cancel(self._playhead_poll_id)
            except Exception:
                pass
        self._poll_playhead()

    def _poll_playhead(self):
        if not self._playhead_active:
            self._playhead_poll_id = None
            return
        y = self._draw_playhead()
        if y is not None:
            self._autoscroll_to(y)
        self._update_slider_from_tick(self.playback.current_tick)
        self._playhead_poll_id = self.after(33, self._poll_playhead)

    def _draw_playhead(self):
        self.canvas.delete("playhead")
        tick = self.playback.current_tick
        if tick is None:
            return None
        bar_idx, _ = self.bar_layout.locate(tick)
        sys_idx = bar_idx // max(1, self.bars_per_system)
        y_offset = sys_idx * SYSTEM_HEIGHT
        x, _ = time_to_visual(tick, 0, self.bar_layout,
                              self.START_X, self.bar_pixel_width,
                              self.bars_per_system)
        self.canvas.create_line(x, 145 + y_offset, x, 335 + y_offset,
                                fill="#E53935", width=2, tags="playhead")
        self.canvas.create_polygon(x - 5, 143 + y_offset,
                                   x + 5, 143 + y_offset,
                                   x, 152 + y_offset,
                                   fill="#E53935", outline="",
                                   tags="playhead")
        return y_offset + 240

    def _autoscroll_to(self, y_in_canvas):
        if self._is_dragging or self._slider_dragging:
            return
        try:
            parent = self.canvas_scroll._parent_canvas
        except AttributeError:
            return
        view_h = parent.winfo_height()
        if view_h < 60:
            return
        content_h = self.canvas.winfo_reqheight()
        if content_h < 1:
            return
        top_frac, bot_frac = parent.yview()
        visible_top = top_frac * content_h
        visible_bot = bot_frac * content_h
        margin = PLAYHEAD_AUTOSCROLL_MARGIN
        if y_in_canvas < visible_top + margin:
            target_top = max(0, y_in_canvas - margin)
        elif y_in_canvas > visible_bot - margin:
            target_top = y_in_canvas - view_h + margin
        else:
            return
        new_frac = max(0.0, min(1.0, target_top / max(1, content_h)))
        try:
            parent.yview_moveto(new_frac)
        except Exception:
            pass

    def _update_slider_from_tick(self, tick):
        if self._slider_dragging:
            return
        total = max(1, self.bar_layout.total_ticks)
        try:
            self.position_slider.set(min(1.0, tick / total))
        except Exception:
            pass

    def _on_slider_press(self):
        self._slider_dragging = True

    def _on_slider_release(self):
        self._slider_dragging = False

    def _on_slider_move(self, value):
        if not self._slider_dragging:
            return
        total = max(1, self.bar_layout.total_ticks)
        tick = int(value * total)
        self.playback.stop()
        self.play_btn.configure(text="\u25B6 Play")
        self.playback.seek(tick)
        self._playhead_active = False
        self._draw_playhead()

    # ---------------------------------------------------------------
    # Diagnostics
    # ---------------------------------------------------------------
    def _dump_last_slices(self, event=None):
        slices = build_vertical_slices(
            self.notes_db,
            filter_figuration=self.filter_figuration,
            layout=self.bar_layout)
        print("\n\n########## SLICE DUMP ##########")
        print(f"key name = {self.current_key_name}")
        print(f"total slices: {len(slices)}\n")
        for idx, vs in enumerate(slices):
            print(f"=== slice [{idx}] at tick {vs.tick} ===")
            for name in ("soprano", "alto", "tenor", "bass"):
                n = getattr(vs, name, None)
                if n is None:
                    print(f"  {name:8s}  --")
                else:
                    print(f"  {name:8s}  pitch={n.pitch:3d}  "
                          f"({n.tick_length} ticks)")
        print("########## END SLICE DUMP ##########\n")

    # ---------------------------------------------------------------
    # Assets
    # ---------------------------------------------------------------
    def _assets_for_note(self, n):
        if not self.color_voices_enabled:
            return self.note_assets_default, "#000000"
        voice = n.get('voice', 0)
        assets = self.note_assets_by_voice.get(voice, self.note_assets_default)
        color = VOICE_COLORS.get(voice, "#000000")
        return assets, color

    # ---------------------------------------------------------------
    # Settings
    # ---------------------------------------------------------------
    def _open_settings(self):
        SettingsModal(self, GM_INSTRUMENTS, self.current_key_name,
                      self.current_tempo, self.active_insts, self.active_vols,
                      self._apply_settings,
                      current_time_sig=self.current_time_sig)

    def _apply_settings(self, settings):
        self._push_undo()
        self.current_key_name = settings["key"]
        self.current_tempo = settings["tempo"]
        self.current_time_sig = settings.get("time_sig", self.current_time_sig)
        self.active_insts = settings["instruments"]
        self.active_vols = settings["volumes"]

        info = KEYS.get(self.current_key_name, KEYS["C Major"])
        self.key_signature = KeySignature(info["root"], mode=info["mode"])
        self.current_signature_name = info["signature"]
        self.current_mode = info["mode"]

        self.bar_layout.set_initial(self.current_time_sig,
                                    self.current_signature_name)
        self.bar_layout.reflow(max(self.bars_per_system, self.bar_layout.count))

        self.START_X = self._compute_start_x_for_signature(
            self.current_signature_name)
        self._update_key_label()
        self.playback.set_tempo(self.current_tempo)

        for ch, inst_name in enumerate(self.active_insts):
            self.playback_engine.set_instrument(ch, GM_INSTRUMENTS.get(inst_name, 60))
        for ch, vol in enumerate(self.active_vols):
            self.playback_engine.set_volume(ch, vol)

        for n in self.notes_db:
            self._recalculate_pitch(n)
        self._clear_annotations()
        self._redraw_all()

    def _get_active_ticks(self):
        return DURATION_TICKS.get(self.active_duration.get(), 480)

    def _clear_annotations(self):
        self.report_faults = []
        self.active_fault_indices = set()
        self.progression_quality = {}
        self.active_quality_tick = None

    def _invalidate_file_voices(self):
        self._voices_from_file = False

    # ---------------------------------------------------------------
    # Save / Load / Import
    # ---------------------------------------------------------------
    def _save_workspace(self):
        path = filedialog.asksaveasfilename(
            parent=self, defaultextension=".sharm",
            filetypes=[("Smart Harmony Workspace", "*.sharm"),
                       ("JSON", "*.json")],
            title="Save Workspace",
        )
        if not path:
            return
        data = {
            "format": "SmartHarmonyWorkspace",
            "version": 2,
            "key": self.current_key_name,
            "time_sig": self.current_time_sig,
            "tempo": self.current_tempo,
            "instruments": list(self.active_insts),
            "volumes": list(self.active_vols),
            "layout_changes": [list(c) for c in self.bar_layout._changes],
            "notes": self.notes_db,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            self._set_status_message(f"Save failed: {e}")
        else:
            self._set_status_message(f"Saved to {os.path.basename(path)}")

    def _load_workspace(self):
        path = filedialog.askopenfilename(
            parent=self,
            filetypes=[("Smart Harmony Workspace", "*.sharm"),
                       ("JSON", "*.json")],
            title="Load Workspace",
        )
        if not path:
            return
        self._load_from_path(path)

    def _load_from_path(self, path):
        self._last_loaded_path = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            self._set_status_message(f"Load failed: {e}")
            return

        self.playback.stop()
        self._playback_stopped_ui()

        self._push_undo()

        self.current_key_name = data.get("key", "C Major")
        self.current_time_sig = data.get("time_sig", DEFAULT_TIME_SIGNATURE)
        self.current_tempo = data.get("tempo", 120)
        raw_insts = list(data.get("instruments", self.active_insts))
        self.active_insts = [
            "French Horn" if name == "Piano" else name
            for name in raw_insts
        ]
        self.active_vols = list(data.get("volumes", self.active_vols))

        changes = data.get("layout_changes")
        self._apply_key(self.current_key_name)

        if changes:
            self.bar_layout._changes = [tuple(c) for c in changes]
        else:
            self.bar_layout.set_initial(self.current_time_sig,
                                        self.current_signature_name)
        self.bar_layout.reflow(max(self.bars_per_system, self.bar_layout.count))

        self.notes_db = []
        for src in data.get("notes", []):
            n = dict(src)
            n.setdefault("tied_to_next", False)
            n.setdefault("is_tied_target", False)
            n.setdefault("accidental", None)
            n.setdefault("channel", 0)
            n.pop("voice_override", None)
            self._recalculate_pitch(n)
            self.notes_db.append(n)

        self._voices_from_file = any("voice" in n for n in self.notes_db)

        for ch, inst_name in enumerate(self.active_insts):
            self.playback_engine.set_instrument(ch, GM_INSTRUMENTS.get(inst_name, 60))
        for ch, vol in enumerate(self.active_vols):
            self.playback_engine.set_volume(ch, vol)

        self.playback.set_notes(self.notes_db)
        self.playback.set_tempo(self.current_tempo)
        self.playback.seek(0)

        self.selected_note = None
        self._clear_annotations()
        self._redraw_all()
        self._set_status_message(
            f"Loaded {os.path.basename(path)} \u2014 "
            f"analysing in {self.current_key_name}")

    def _import_musicxml(self):
        src_path = filedialog.askopenfilename(
            parent=self,
            filetypes=[
                ("MIDI", "*.mid"),
                ("MIDI", "*.midi"),
                ("Karaoke MIDI", "*.kar"),
                ("Standard MIDI File", "*.smf"),
                ("MusicXML (compressed)", "*.mxl"),
                ("MusicXML (uncompressed)", "*.xml"),
                ("Humdrum kern", "*.krn"),
                ("All files", "*.*"),
            ],
            title="Import score or MIDI",
        )
        if not src_path:
            return

        base, _ = os.path.splitext(src_path)
        dst_path = base + ".sharm"

        if os.path.exists(dst_path):
            proceed = messagebox.askyesno(
                "Overwrite existing file?",
                f"{os.path.basename(dst_path)} already exists.\n\n"
                f"Overwrite it?",
                parent=self,
            )
            if not proceed:
                return

        convert_file = self._resolve_converter()
        if convert_file is None:
            return

        ok = convert_file(src_path, dst_path)
        if not ok:
            self._set_status_message(
                f"Could not convert {os.path.basename(src_path)}. "
                f"See the terminal for details."
            )
            return

        self._load_from_path(dst_path)

    def _resolve_converter(self):
        candidates = ("validation.convert_musicxml", "convert_musicxml")
        for name in candidates:
            try:
                module = importlib.import_module(name)
            except ImportError:
                continue
            fn = getattr(module, "convert_file", None)
            if fn is not None:
                return fn
        self._set_status_message(
            "Could not import the converter.\n\n"
            "Make sure validation/convert_musicxml.py is present, and "
            "install music21 with:  pip install music21"
        )
        return None

    def _set_status_message(self, msg):
        for widget in self.report_frame.winfo_children():
            widget.destroy()
        ctk.CTkLabel(self.report_frame, text=msg,
                     font=("Helvetica", 11, "italic"),
                     text_color="#006666", wraplength=300).pack(pady=10)

    # ---------------------------------------------------------------
    # Barlines
    # ---------------------------------------------------------------
    def _find_barline_at(self, x, y):
        for (xl, xr, yt, yb, bar_idx) in self._barline_hitboxes:
            if xl <= x <= xr and yt <= y <= yb:
                return bar_idx
        return None

    def _open_barline_menu(self, bar_index, key_mode=False):
        bar = self.bar_layout.bars[bar_index]
        dlg = ctk.CTkToplevel(self)
        dlg.title(("Key" if key_mode else "Time") + f" Signature — Bar {bar_index + 1}")
        dlg.geometry("360x200")
        dlg.attributes("-topmost", True)
        dlg.configure(fg_color="#F5F5DC")

        ctk.CTkLabel(dlg, text=f"Bar {bar_index + 1}",
                     font=("Helvetica", 14, "bold"),
                     text_color="#008080").pack(pady=(16, 4))

        if key_mode:
            ctk.CTkLabel(dlg, text=f"Current: {bar.key_sig_name}",
                         text_color="#555555").pack()
            var = ctk.StringVar(value=bar.key_sig_name)
            combo = ctk.CTkComboBox(dlg, variable=var,
                                    values=list(KEY_SIGNATURES.keys()))
            combo.pack(padx=20, pady=(10, 6), fill="x")
        else:
            ctk.CTkLabel(dlg, text=f"Current: {bar.time_sig_name}",
                         text_color="#555555").pack()
            var = ctk.StringVar(value=bar.time_sig_name)
            combo = ctk.CTkComboBox(dlg, variable=var,
                                    values=TIME_SIGNATURE_ORDER)
            combo.pack(padx=20, pady=(10, 6), fill="x")

        def apply_and_close():
            choice = var.get().strip()
            if key_mode:
                if choice not in KEY_SIGNATURES:
                    return
                self._push_undo()
                self.bar_layout.set_key_sig_at_bar(bar_index, choice)
            else:
                if choice not in TIME_SIGNATURE_ORDER:
                    return
                self._push_undo()
                self.bar_layout.set_time_sig_at_bar(bar_index, choice)
                self.bar_layout.reflow(max(self.bars_per_system, self.bar_layout.count))
                overflow = [n for n in self.notes_db
                            if self.bar_layout.note_overflows(n)]
                if overflow:
                    self._set_status_message(
                        f"Time signature changed. {len(overflow)} note(s) now exceed their bar; "
                        f"marked with a red circle.")
            self._clear_annotations()
            self._redraw_all()
            dlg.destroy()

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=10)
        ctk.CTkButton(btns, text="Apply", fg_color="#008080",
                      command=apply_and_close).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancel", fg_color="#888888",
                      command=dlg.destroy).pack(side="left", padx=6)

    # ---------------------------------------------------------------
    # Interaction
    # ---------------------------------------------------------------
    def _find_note_at(self, x, y):
        best_note, best_score = None, 1.0
        for n in self.notes_db:
            cached = n.get('_screen_pos')
            if cached is not None:
                nx, ny = cached
            else:
                nx = note_visual_x(n, self.bar_layout, self.START_X,
                                   self.bar_pixel_width, self.bars_per_system)
                _, ny = time_to_visual(n['time_ticks'], n['base_y'],
                                       self.bar_layout, self.START_X,
                                       self.bar_pixel_width, self.bars_per_system)
            dx = (x - nx) / 8.0
            dy = (y - ny) / 5.0
            score = dx * dx + dy * dy
            if score < best_score:
                best_score = score
                best_note = n
        return best_note

    def _find_snap_target(self, tx, ty, exclude=None, radius=SNAP_RADIUS_PX):
        best_note = None
        best_dist = radius * radius
        for n in self.notes_db:
            if n is exclude:
                continue
            nx = note_visual_x(n, self.bar_layout, self.START_X,
                               self.bar_pixel_width, self.bars_per_system)
            _, ny = time_to_visual(n['time_ticks'], n['base_y'],
                                   self.bar_layout, self.START_X,
                                   self.bar_pixel_width, self.bars_per_system)
            dx = tx - nx
            dy = ty - ny
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                best_note = n
        return best_note

    def _find_numeral_at(self, x, y):
        for entry in self.numeral_hitboxes:
            tick, nx, ny, fb, q, lbl, prev = entry
            if abs(x - nx) < 32 and abs(y - ny) < 14:
                return entry
        return None

    def _on_mouse_move(self, event):
        if self._is_dragging:
            return
        lx, ly = self._last_mouse_xy
        if abs(event.x - lx) < 3 and abs(event.y - ly) < 3:
            return
        self._last_mouse_xy = (event.x, event.y)

        self.canvas.delete("ghost")
        tx = self.canvas.canvasx(event.x)
        ty = self.canvas.canvasy(event.y)

        if self._find_barline_at(tx, ty) is not None:
            self.canvas.configure(cursor="hand2")
        elif self._find_numeral_at(tx, ty) is not None:
            self.canvas.configure(cursor="hand2")
        elif self._find_note_at(tx, ty) is not None:
            self.canvas.configure(cursor="fleur")
        else:
            self.canvas.configure(cursor="")

        time_ticks, base_y = visual_to_time(tx, ty, self.bar_layout,
                                            self.START_X, self.bar_pixel_width,
                                            self.bars_per_system,
                                            self._get_active_ticks())
        if time_ticks < 0:
            return
        vx, vy = time_to_visual(time_ticks, base_y, self.bar_layout,
                                self.START_X, self.bar_pixel_width,
                                self.bars_per_system)
        vx += barline_nudge_for(time_ticks, self.bar_layout)
        if base_y in Y_TO_PITCH:
            self.canvas.create_oval(vx - 6, vy - 4, vx + 6, vy + 4,
                                    fill="#D3D3D3", outline="#A9A9A9", tags="ghost")
            draw_ledger_lines(self.canvas, vx, vy, tag="ghost", color="#A9A9A9")

    def _on_canvas_click(self, event):
        self.focus_set()
        tx = self.canvas.canvasx(event.x)
        ty = self.canvas.canvasy(event.y)

        bar_idx = self._find_barline_at(tx, ty)
        if bar_idx is not None:
            key_mode = bool(event.state & 0x0001)
            self._open_barline_menu(bar_idx, key_mode=key_mode)
            return

        hit = self._find_note_at(tx, ty)
        if hit is not None:
            self._drag_note = hit
            self._drag_start_xy = (tx, ty)
            self._drag_start_tick = hit['time_ticks']
            self._drag_start_base_y = hit['base_y']
            self._is_dragging = False
            self._drag_target = None
            self.selected_note = hit
            self._clear_annotations()
            self._redraw_all()
            self.playback_engine.play_note(hit["pitch"], 240,
                                           self.current_tempo, hit["channel"])
            return

        numeral = self._find_numeral_at(tx, ty)
        if numeral is not None:
            tick = numeral[0]
            if not numeral[3]:
                return
            if self.active_quality_tick == tick:
                self.active_quality_tick = None
            else:
                self.active_quality_tick = tick
            self._redraw_all()
            return
        if self.active_quality_tick is not None:
            self.active_quality_tick = None
            self._redraw_all()
            return

        time_ticks, base_y = visual_to_time(tx, ty, self.bar_layout,
                                            self.START_X, self.bar_pixel_width,
                                            self.bars_per_system,
                                            self._get_active_ticks())
        if time_ticks < 0:
            return
        if base_y not in Y_TO_PITCH:
            self.selected_note = None
            self._clear_annotations()
            self._redraw_all()
            return

        ticks = self._get_active_ticks()
        if not can_place_note(self.notes_db, self.bar_layout,
                              time_ticks, base_y, ticks):
            self._set_status_message(
                "Cannot place note: it would cross a barline or overlap "
                "an existing note.")
            return

        self._push_undo()
        self._invalidate_file_voices()
        new_note = {
            "time_ticks": time_ticks, "base_y": base_y, "ticks": ticks,
            "accidental": None, "channel": 0,
            "tied_to_next": False, "is_tied_target": False,
        }
        self._recalculate_pitch(new_note)
        self.notes_db.append(new_note)
        self.selected_note = new_note
        self._clear_annotations()
        self._redraw_all()
        self.playback.set_notes(self.notes_db)
        self.playback_engine.play_note(new_note["pitch"], new_note["ticks"],
                                       self.current_tempo, new_note["channel"])

    def _on_drag_motion(self, event):
        if self._drag_note is None or self._drag_start_xy is None:
            return
        tx = self.canvas.canvasx(event.x)
        ty = self.canvas.canvasy(event.y)
        sx, sy = self._drag_start_xy
        if not self._is_dragging:
            if abs(tx - sx) < DRAG_THRESHOLD_PX and abs(ty - sy) < DRAG_THRESHOLD_PX:
                return
            self._is_dragging = True

        new_tick, new_y = visual_to_time(tx, ty, self.bar_layout,
                                         self.START_X, self.bar_pixel_width,
                                         self.bars_per_system,
                                         self._get_active_ticks())
        if new_y not in Y_TO_PITCH:
            return

        snap = self._find_snap_target(tx, ty, exclude=self._drag_note)
        if snap is not None:
            new_tick = snap['time_ticks']
            new_y = snap['base_y']

        self._drag_target = (new_tick, new_y)

        self.canvas.delete("drag_ghost")
        vx, vy = time_to_visual(new_tick, new_y, self.bar_layout,
                                self.START_X, self.bar_pixel_width,
                                self.bars_per_system)
        vx += barline_nudge_for(new_tick, self.bar_layout)
        self.canvas.create_oval(vx - 9, vy - 7, vx + 9, vy + 7,
                                outline="#0080FF", width=2, tags="drag_ghost")
        ox, oy = time_to_visual(self._drag_start_tick, self._drag_start_base_y,
                                self.bar_layout, self.START_X,
                                self.bar_pixel_width, self.bars_per_system)
        ox += barline_nudge_for(self._drag_start_tick, self.bar_layout)
        self.canvas.create_line(ox, oy, vx, vy,
                                fill="#0080FF", dash=(3, 3), width=1,
                                tags="drag_ghost")

    def _on_drag_release(self, event):
        was_dragging = self._is_dragging
        note = self._drag_note
        target = self._drag_target
        self._drag_note = None
        self._drag_start_xy = None
        self._drag_start_tick = None
        self._drag_start_base_y = None
        self._is_dragging = False
        self._drag_target = None
        self.canvas.delete("drag_ghost")
        if not was_dragging or note is None or target is None:
            return

        new_tick, new_y = target
        same_pos = [n for n in self.notes_db
                    if n is not note
                    and n['time_ticks'] == new_tick
                    and n['base_y'] == new_y]
        if len(same_pos) >= 2:
            self._set_status_message(
                "Cannot move: two notes are already at that position.")
            self._redraw_all()
            return

        self._push_undo()
        self._invalidate_file_voices()
        note['time_ticks'] = new_tick
        note['base_y'] = new_y
        self._recalculate_pitch(note)
        self._clear_annotations()
        self._redraw_all()
        self.playback.set_notes(self.notes_db)
        self.playback_engine.play_note(note['pitch'], 240,
                                       self.current_tempo, note['channel'])

    def _repeat_last_note(self, event=None):
        if not self.selected_note:
            return
        src = self.selected_note
        new_ticks = src['time_ticks'] + src['ticks']
        if not can_place_note(self.notes_db, self.bar_layout,
                              new_ticks, src['base_y'], src['ticks']):
            return
        self._push_undo()
        self._invalidate_file_voices()
        new_note = {
            "time_ticks": new_ticks,
            "base_y": src['base_y'],
            "ticks": src['ticks'],
            "accidental": src.get('accidental'),
            "channel": 0,
            "tied_to_next": False,
            "is_tied_target": False,
        }
        self._recalculate_pitch(new_note)
        self.notes_db.append(new_note)
        self.selected_note = new_note
        self._clear_annotations()
        self._redraw_all()
        self.playback.set_notes(self.notes_db)
        self.playback_engine.play_note(new_note["pitch"], new_note["ticks"],
                                       self.current_tempo, new_note["channel"])

    def _tie_note(self):
        if not self.selected_note:
            return
        current_voice = self.selected_note.get('voice')
        if current_voice is None:
            return
        times = sorted({n['time_ticks'] for n in self.notes_db})
        t_idx = times.index(self.selected_note['time_ticks'])
        if t_idx >= len(times) - 1:
            return
        next_time = times[t_idx + 1]
        group = [n for n in self.notes_db
                 if n['time_ticks'] == next_time and n.get('voice') == current_voice]
        if not group:
            return
        nxt = group[0]
        if nxt['pitch'] != self.selected_note['pitch']:
            return
        self._push_undo()
        self.selected_note['tied_to_next'] = not self.selected_note.get('tied_to_next', False)
        nxt['is_tied_target'] = self.selected_note['tied_to_next']
        self._clear_annotations()
        self._redraw_all()

    # ---------------------------------------------------------------
    # Pitch / voice / edit helpers
    # ---------------------------------------------------------------
    def _extrapolate_pitch(self, base_y, voice):
        c4_y = 200 if voice in (0, 1) else 280
        steps = (c4_y - base_y) // 5
        offsets = [0, 2, 4, 5, 7, 9, 11]
        octave = 4 + steps // 7
        letter = steps % 7
        return 60 + (octave - 4) * 12 + offsets[letter]

    def _recalculate_pitch(self, note):
        base_y = note.get("base_y")
        voice = note.get("voice", 0)
        if base_y in Y_TO_PITCH:
            base_pitch = Y_TO_PITCH[base_y]
        elif base_y is not None:
            base_pitch = self._extrapolate_pitch(base_y, voice)
        else:
            base_pitch = 60

        acc = note.get("accidental")
        if acc == "sharp":
            note["pitch"] = base_pitch + 1
        elif acc == "flat":
            note["pitch"] = base_pitch - 1
        elif acc == "natural":
            note["pitch"] = base_pitch
        else:
            pc = base_pitch % 12
            bar = self.bar_layout.bar_at(note["time_ticks"])
            key_of_note = bar.key_sig_name

            offsets = KEY_OFFSETS.get(key_of_note)
            if offsets is None:
                info = KEYS.get(key_of_note)
                if info is not None:
                    offsets = KEY_OFFSETS.get(info["signature"], {})
                else:
                    offsets = {}
            note["pitch"] = base_pitch + offsets.get(pc, 0)

    def _set_accidental(self, acc_type):
        if not self.selected_note:
            return
        self._push_undo()
        cur = self.selected_note.get("accidental")
        self.selected_note["accidental"] = None if cur == acc_type else acc_type
        self._recalculate_pitch(self.selected_note)
        self._clear_annotations()
        self.playback_engine.play_note(self.selected_note["pitch"], 480,
                                       self.current_tempo, self.selected_note["channel"])
        self._redraw_all()

    def _step_to_adjacent_chord(self, direction):
        if not self.selected_note:
            return
        current_voice = self.selected_note.get('voice')
        if current_voice is None:
            return
        times = sorted({n['time_ticks'] for n in self.notes_db})
        t_idx = times.index(self.selected_note['time_ticks'])
        new_idx = t_idx + direction
        if not (0 <= new_idx < len(times)):
            return
        target_time = times[new_idx]
        candidates = [n for n in self.notes_db
                      if n['time_ticks'] == target_time
                      and n.get('voice') == current_voice]
        if not candidates:
            return
        self.selected_note = candidates[0]
        self._redraw_all()

    def _shift_selected_pitch(self, direction):
        ys = sorted(Y_TO_PITCH.keys())
        idx = ys.index(self.selected_note["base_y"])
        new_idx = idx + direction
        if not (0 <= new_idx < len(ys)):
            return
        new_y = ys[new_idx]
        same_pos = [n for n in self.notes_db
                    if n is not self.selected_note
                    and n['time_ticks'] == self.selected_note['time_ticks']
                    and n['base_y'] == new_y]
        if len(same_pos) >= 2:
            return
        self._push_undo()
        self._invalidate_file_voices()
        self.selected_note["base_y"] = new_y
        self._recalculate_pitch(self.selected_note)
        self._clear_annotations()
        self._redraw_all()
        self.playback.set_notes(self.notes_db)
        self.playback_engine.play_note(self.selected_note["pitch"], 480,
                                       self.current_tempo, self.selected_note["channel"])

    def _on_up_arrow(self, event):
        if self.selected_note:
            self._shift_selected_pitch(-1)

    def _on_down_arrow(self, event):
        if self.selected_note:
            self._shift_selected_pitch(1)

    def _on_delete_key(self, event):
        if self.selected_note in self.notes_db:
            self._push_undo()
            self._invalidate_file_voices()
            self.notes_db.remove(self.selected_note)
            self.selected_note = None
            self._clear_annotations()
            self._redraw_all()
            self.playback.set_notes(self.notes_db)

    # ---------------------------------------------------------------
    # Redraw
    # ---------------------------------------------------------------
    def _ensure_bars_for_notes(self):
        if not self.notes_db:
            if self.bar_layout.count < 1:
                self.bar_layout.reflow(1)
            return
        last_note_end = max(n['time_ticks'] + n['ticks'] for n in self.notes_db)
        needed = self.bar_layout.count
        while self.bar_layout.total_ticks <= last_note_end:
            needed += 1
            self.bar_layout.reflow(needed)

    def _redraw_all(self):
        self.canvas.delete("all")
        self._barline_hitboxes = []

        self._ensure_bars_for_notes()
        self.bars_per_system = self._compute_effective_bars_per_system()

        canvas_w = self.canvas.winfo_width()
        if canvas_w < 200:
            canvas_w = 1100

        self.bar_pixel_width = max(
            MIN_BAR_PIXEL_WIDTH,
            (canvas_w - RIGHT_MARGIN - self.START_X) / self.bars_per_system
        )

        num_systems = max(1, (self.bar_layout.count + self.bars_per_system - 1)
                          // self.bars_per_system)
        self.canvas.configure(height=num_systems * SYSTEM_HEIGHT + 50)

        sys_w = self.START_X + self.bar_pixel_width * self.bars_per_system

        for sys_idx in range(num_systems):
            y_offset = sys_idx * SYSTEM_HEIGHT
            first_bar_idx = sys_idx * self.bars_per_system
            if first_bar_idx >= self.bar_layout.count:
                break
            first_bar = self.bar_layout.bars[first_bar_idx]

            draw_staff(self.canvas, y_offset, sys_w,
                       first_bar.key_sig_name, first_bar.time_sig_name)

            for local_i in range(self.bars_per_system):
                global_i = sys_idx * self.bars_per_system + local_i
                if global_i >= self.bar_layout.count:
                    break
                bar_right_x = self.START_X + (local_i + 1) * self.bar_pixel_width
                is_last = (global_i == self.bar_layout.count - 1)
                if is_last:
                    self.canvas.create_line(bar_right_x, 150 + y_offset,
                                            bar_right_x, 330 + y_offset,
                                            fill="#000000", width=3)
                    self.canvas.create_line(bar_right_x + 6, 150 + y_offset,
                                            bar_right_x + 6, 330 + y_offset,
                                            fill="#000000", width=1)
                else:
                    self.canvas.create_line(bar_right_x, 150 + y_offset,
                                            bar_right_x, 330 + y_offset,
                                            fill="#000000", width=1.5)
                    self._barline_hitboxes.append((
                        bar_right_x - 5, bar_right_x + 5,
                        140 + y_offset, 340 + y_offset,
                        global_i,
                    ))

                if global_i > 0:
                    bar = self.bar_layout.bars[global_i]
                    prev_bar = self.bar_layout.bars[global_i - 1]
                    if bar.time_sig_name != prev_bar.time_sig_name:
                        bar_left_x = self.START_X + local_i * self.bar_pixel_width
                        draw_time_signature_change(self.canvas, bar_left_x,
                                                   y_offset, bar.time_sig_name)

        if not self._voices_from_file:
            assign_voices(self.notes_db)

        beam_groups = find_beam_groups(self.notes_db, self.bar_layout)
        beamed_ids = set()
        for group in beam_groups:
            for n in group:
                beamed_ids.add(id(n))

        sorted_notes = sorted(self.notes_db,
                              key=lambda n: (n['time_ticks'], -n['pitch']))
        time_groups = {}
        for n in sorted_notes:
            time_groups.setdefault(n['time_ticks'], []).append(n)

        if self.filter_figuration:
            harmonic = harmonic_onsets(self.notes_db, layout=self.bar_layout)
        else:
            harmonic = None

        self._numeral_font_px = self._compute_numeral_font_px(harmonic)
        self._numeral_placed = []

        self.grading_composition = []
        self.numeral_hitboxes = []

        drawn_notes = {}

        for t_ticks, notes in time_groups.items():
            assign_offsets(notes)
            vs = VerticalSlice(tick=t_ticks)
            for n in notes:
                n['channel'] = n.get('voice', 0)
                stem = stem_for_voice(n.get('voice', 0))
                vx, vy = time_to_visual(n['time_ticks'], n['base_y'],
                                        self.bar_layout, self.START_X,
                                        self.bar_pixel_width, self.bars_per_system)
                draw_x = vx + n.get('offset_x', 0) + \
                    barline_nudge_for(n['time_ticks'], self.bar_layout)
                n['_screen_pos'] = (draw_x, vy)
                drawn_notes[id(n)] = (draw_x, vy)

                is_sel = (self.selected_note == n)
                is_overflow = self.bar_layout.note_overflows(n)
                assets, note_color = self._assets_for_note(n)

                draw_note(self.canvas, draw_x, vy, n['ticks'], stem,
                          is_sel, n.get("accidental"), assets,
                          is_beamed=(id(n) in beamed_ids),
                          overflow=is_overflow,
                          note_color=note_color,
                          skip_accidental=True)

                nn = NoteNode(n['pitch'], n['ticks'])
                v = n.get('voice', 0)
                if v == 0 and vs.soprano is None:
                    vs.soprano = nn
                elif v == 1 and vs.alto is None:
                    vs.alto = nn
                elif v == 2 and vs.tenor is None:
                    vs.tenor = nn
                elif v == 3 and vs.bass is None:
                    vs.bass = nn

            # Draw all accidentals for this onset as a single stacked
            # column, left of the leftmost notehead.
            acc_entries = []
            for n in notes:
                acc = n.get("accidental")
                if not acc:
                    continue
                sx, sy = n['_screen_pos']
                is_sel = (self.selected_note == n)
                _, note_color = self._assets_for_note(n)
                color = "#00A2E8" if is_sel else note_color
                acc_entries.append((sx, sy, acc, color))
            if acc_entries:
                draw_chord_accidentals(self.canvas, acc_entries)

            # Fill any still-empty voice slots from held-over notes.
            for n in self.notes_db:
                onset = n['time_ticks']
                if not (onset < t_ticks < onset + n['ticks']):
                    continue
                v = n.get('voice', 0)
                remaining = n['ticks'] - (t_ticks - onset)
                if v == 0 and vs.soprano is None:
                    vs.soprano = NoteNode(n['pitch'], remaining)
                elif v == 1 and vs.alto is None:
                    vs.alto = NoteNode(n['pitch'], remaining)
                elif v == 2 and vs.tenor is None:
                    vs.tenor = NoteNode(n['pitch'], remaining)
                elif v == 3 and vs.bass is None:
                    vs.bass = NoteNode(n['pitch'], remaining)

            is_harmonic = (harmonic is None) or (t_ticks in harmonic)
            if not is_harmonic:
                continue

            self.grading_composition.append(vs)

            if len(vs.get_notes()) >= 2:
                numeral = self.analyzer.trigger_snap_analysis(vs, self.key_signature)
                q_info = self.progression_quality.get(t_ticks)
                if q_info:
                    color, feedback, quality = q_info
                else:
                    color, feedback, quality = QUALITY_COLORS["default"], "", "default"

                prev_label = ""
                earlier = [e for e in self.numeral_hitboxes if e[0] < t_ticks]
                if earlier:
                    prev_label = earlier[-1][5]

                vx, vy = time_to_visual(t_ticks, NUMERAL_ROW_Y,
                                        self.bar_layout, self.START_X,
                                        self.bar_pixel_width,
                                        self.bars_per_system)

                if numeral == "":
                    n_pcs = len({n.pitch % 12 for n in vs.get_notes()})
                    if n_pcs < 2:
                        feedback = (
                            "Only one distinct pitch class in this slice "
                            "— a unison or octave doubling. There is no "
                            "chord to name."
                        )
                    else:
                        feedback = (
                            "Two distinct pitch classes that fit more "
                            "than one diatonic triad. There is no "
                            "unambiguous Roman numeral."
                        )
                    display_text = "\u00B7"
                    marker_color = "#CCCCCC"
                    quality = "default"
                elif numeral == "?":
                    display_text = "?"
                    marker_color = "#999999"
                    feedback = (
                        "The analyzer could not name this chord. "
                        "Three or more pitch classes are present, but "
                        "they do not fit any recognised triad, seventh, "
                        "or chromatic pattern."
                    )
                    quality = "default"
                else:
                    display_text = numeral
                    marker_color = color
                    if numeral.endswith(_ASTERISK):
                        missing_sentence = self._describe_missing_tone(
                            vs, numeral, self.key_signature)
                        if missing_sentence:
                            if feedback:
                                feedback = missing_sentence + " " + feedback
                            else:
                                feedback = missing_sentence

                placed = self._place_numeral_label(vx, vy, display_text)
                if placed is None:
                    continue
                lx, ly = placed

                self.canvas.create_text(
                    lx, ly, text=display_text,
                    font=("Helvetica", self._numeral_font_px, "bold"),
                    fill=marker_color)
                self.numeral_hitboxes.append(
                    (t_ticks, lx, ly, feedback, quality,
                     numeral if numeral else "\u00B7", prev_label))

        # Ties
        for n in self.notes_db:
            if not n.get('tied_to_next'):
                continue
            cur = drawn_notes.get(id(n))
            if cur is None:
                continue
            partner = None
            for m in self.notes_db:
                if (m is not n
                        and m.get('voice') == n.get('voice')
                        and m['time_ticks'] == n['time_ticks'] + n['ticks']
                        and m['pitch'] == n['pitch']):
                    partner = m
                    break
            if partner is None:
                continue
            nxt = drawn_notes.get(id(partner))
            if nxt is None:
                continue
            _, note_color = self._assets_for_note(n)
            stem_dir = stem_for_voice(n.get('voice', 0))
            draw_tie(self.canvas, cur[0], cur[1], nxt[0], nxt[1],
                     note_color, stem_dir)

        # Beams
        for group in beam_groups:
            pts = []
            for n in group:
                pos = drawn_notes.get(id(n))
                if pos is None:
                    break
                pts.append((pos[0], pos[1], n['ticks']))
            if len(pts) < 2:
                continue
            stem_dir = stem_for_voice(group[0].get('voice', 0))
            if self.color_voices_enabled:
                beam_color = VOICE_COLORS.get(group[0].get('voice', 0), "#000000")
            else:
                beam_color = "#000000"
            draw_beam_group(self.canvas, pts, stem_dir, color=beam_color)

        for i in sorted(self.active_fault_indices):
            if 0 <= i < len(self.report_faults):
                self._draw_fault_annotation(self.report_faults[i])

        if self.active_quality_tick is not None:
            for entry in self.numeral_hitboxes:
                if entry[0] == self.active_quality_tick and entry[3]:
                    self._draw_quality_popup(*entry[1:])
                    break

        self._draw_playhead()

    # ---------------------------------------------------------------
    # Fault annotations
    # ---------------------------------------------------------------
    def _draw_fault_annotation(self, fault):
        color = TIER_COLORS.get(fault.tier, "#DD0000")
        annotation_formats.draw_fault(self.canvas, fault, self, color)

    def _note_at(self, tick, voice_name):
        vi = VOICE_INDEX.get(voice_name.lower())
        if vi is None:
            return None
        for n in self.notes_db:
            if n.get('voice') == vi and n['time_ticks'] == tick:
                return n
        for n in self.notes_db:
            if (n.get('voice') == vi
                    and n['time_ticks'] <= tick < n['time_ticks'] + n['ticks']):
                return n
        return None

    def _note_xy(self, n):
        x = note_visual_x(n, self.bar_layout, self.START_X,
                          self.bar_pixel_width, self.bars_per_system)
        _, y = time_to_visual(n['time_ticks'], n['base_y'],
                              self.bar_layout, self.START_X,
                              self.bar_pixel_width, self.bars_per_system)
        return x, y

    def _draw_quality_popup(self, x, y, feedback, quality, label, prev_label):
        pad = 12
        line_h = 18
        max_chars = 48
        title = f"{prev_label} \u2192 {label}" if prev_label else f"Opening: {label}"
        body = feedback or "No specific analysis for this transition."

        def wrap(text, width):
            words = text.split()
            lines, cur = [], ""
            for w in words:
                trial = (cur + " " + w).strip()
                if len(trial) > width:
                    lines.append(cur)
                    cur = w
                else:
                    cur = trial
            if cur:
                lines.append(cur)
            return lines

        body_lines = wrap(body, max_chars)
        all_lines = [title, ""] + body_lines
        w = max(240, min(max(len(l) for l in all_lines) * 7 + 2 * pad, 420))
        h = len(all_lines) * line_h + 2 * pad
        x0 = x - w / 2
        y0 = y - h - 24
        color = QUALITY_COLORS.get(quality, "#008080")

        self.canvas.create_rectangle(x0, y0, x0 + w, y0 + h,
                                     fill="#FFFDF0", outline=color, width=2,
                                     tags="popup")
        self.canvas.create_text(x0 + pad, y0 + pad,
                                text=title, anchor="nw",
                                font=("Helvetica", 11, "bold"),
                                fill=color, tags="popup")
        self.canvas.create_text(x0 + pad, y0 + pad + line_h,
                                text="\n".join(body_lines), anchor="nw",
                                font=("Helvetica", 10),
                                fill="#222222", tags="popup")

    def _toggle_fault(self, index):
        if index in self.active_fault_indices:
            self.active_fault_indices.discard(index)
        else:
            self.active_fault_indices.add(index)
        self._redraw_all()
        self._refresh_report()

    def _refresh_report(self):
        for widget in self.report_frame.winfo_children():
            widget.destroy()
        if not self.report_faults:
            ctk.CTkLabel(self.report_frame, text="Perfect Harmony!",
                         text_color="#008000",
                         font=("Helvetica", 12)).pack(pady=20)
            return
        for i, fault in enumerate(self.report_faults):
            self._make_fault_entry(i, fault)

    def _make_fault_entry(self, index, fault):
        tier_color = TIER_COLORS.get(fault.tier, "#CC0000")
        is_active = index in self.active_fault_indices
        bg = "#FFF4C0" if is_active else "#E8E8D0"

        f_frame = ctk.CTkFrame(self.report_frame, fg_color=bg, corner_radius=4)
        f_frame.pack(padx=6, pady=3, fill="x")

        def toggle(e=None, i=index):
            self._toggle_fault(i)

        f_frame.bind("<Button-1>", toggle)

        header = ctk.CTkFrame(f_frame, fg_color="transparent")
        header.pack(anchor="w", padx=8, pady=(6, 0), fill="x")
        header.bind("<Button-1>", toggle)

        dot = ctk.CTkLabel(header, text="\u25CF", text_color=tier_color,
                           font=("Helvetica", 13))
        dot.pack(side="left")
        dot.bind("<Button-1>", toggle)

        title = ctk.CTkLabel(header, text=f"  {index + 1}. {fault.rule_id}",
                             font=("Helvetica", 10, "bold"),
                             text_color="#333333")
        title.pack(side="left")
        title.bind("<Button-1>", toggle)

        msg = ctk.CTkLabel(f_frame, text=fault.error_message,
                           justify="left", wraplength=240,
                           text_color="#333333", font=("Helvetica", 11))
        msg.pack(anchor="w", padx=10, pady=(2, 8))
        msg.bind("<Button-1>", toggle)

    def on_play(self):
        self._playback_toggle()

    def _write_fault_report(self, report, slices,
                            final_score, raw_penalty):
        """Write a per-chorale fault report for post-mortem
        fine-tuning.

        The file goes to <project_root>/reports/<basename>.faults.txt.
        If no .sharm file was loaded, the report is named
        untitled.faults.txt. Reports are plain text, ordered by tick,
        with a grouped summary at the end.
        """
        import datetime
        from collections import Counter

        if self._last_loaded_path:
            base = os.path.splitext(
                os.path.basename(self._last_loaded_path))[0]
        else:
            base = "untitled"

        reports_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        report_path = os.path.join(reports_dir, f"{base}.faults.txt")

        lines = []
        lines.append(f"FAULT REPORT \u2014 {base}.sharm")
        lines.append(f"Generated: "
                     f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Key: {self.current_key_name}    "
                     f"Time: {self.current_time_sig}    "
                     f"Tempo: {self.current_tempo}")
        lines.append(f"Slices: {len(slices)}    "
                     f"Score: {final_score}/100    "
                     f"Raw penalty: {raw_penalty}")
        lines.append("")

        faults = list(report.faults)

        lines.append("=" * 72)
        lines.append(f"FAULTS IN ORDER ({len(faults)})")
        lines.append("=" * 72)
        lines.append("")

        for i, f in enumerate(faults, 1):
            voices = ",".join(f.voices) if f.voices else "-"
            prev = "" if f.prev_tick is None else \
                f"  prev_tick={f.prev_tick}"
            lines.append(f"{i:>3}. {f.rule_id:<32} "
                         f"w={f.penalty_weight:<2} "
                         f"tick={f.tick_coordinate:<6} "
                         f"voices=[{voices}]{prev}")
            lines.append(f"      {f.error_message}")
            lines.append("")

        counts = Counter(f.rule_id for f in faults)
        if counts:
            lines.append("=" * 72)
            lines.append("FAULTS BY RULE")
            lines.append("=" * 72)
            for rule_id, count in counts.most_common():
                lines.append(f"  {count:>5}  {rule_id}")
            lines.append("")

        unknowns = []
        for vs in slices:
            try:
                ci = self.analyzer.analyze(vs, self.key_signature)
            except Exception:
                continue
            if ci.label == "?":
                pcs = sorted({n.pitch % 12 for n in vs.get_notes()})
                unknowns.append((vs.tick, pcs))

        if unknowns:
            lines.append("=" * 72)
            lines.append(f"UNKNOWN CHORDS ({len(unknowns)})")
            lines.append("=" * 72)
            for tick, pcs in unknowns:
                lines.append(f"  tick={tick:<6}  pcs={pcs}")
            lines.append("")

        with open(report_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

        print(f"[report] wrote {report_path}")

    def on_submit(self):
        for widget in self.report_frame.winfo_children():
            widget.destroy()

        horizontal_slices = build_vertical_slices(
            self.notes_db,
            filter_figuration=self.filter_figuration,
            layout=self.bar_layout)

        report = self.grader.submit(horizontal_slices,
                                    self.rules_engine.rules,
                                    self.key_signature,
                                    layout=self.bar_layout)

        total_rule_weight = sum(r.weight for r in self.rules_engine.rules)
        final_score, raw, nb, max_per_bar = standardize_grade(
            horizontal_slices, report.faults, total_rule_weight,
            layout=self.bar_layout)

        self.report_faults = list(report.faults)
        self.active_fault_indices = set()

        labels, ticks = [], []
        for vs in self.grading_composition:
            if len(vs.get_notes()) >= 2:
                labels.append(self.analyzer.trigger_snap_analysis(vs, self.key_signature))
                ticks.append(vs.tick)
        quality_results = self.quality_analyzer.analyze(labels)
        self.progression_quality = {}
        for tick, (q, fb) in zip(ticks, quality_results):
            self.progression_quality[tick] = (QUALITY_COLORS.get(q, "#008080"), fb, q)
        self.active_quality_tick = None

        self._redraw_all()

        # Write a per-chorale fault report for post-mortem fine-tuning.
        self._write_fault_report(report, horizontal_slices,
                                 final_score, raw)

        score_color = "#008000" if final_score >= 80 else (
            "#C8A800" if final_score >= 60 else "#CC0000")
        ctk.CTkLabel(self.report_frame,
                     text=f"Final Score: {final_score}/100",
                     font=("Helvetica", 18, "bold"),
                     text_color=score_color).pack(pady=(4, 0))
        ctk.CTkLabel(self.report_frame,
                     text=f"({raw} raw penalty over {nb} bar"
                          f"{'s' if nb != 1 else ''})",
                     font=("Helvetica", 9, "italic"),
                     text_color="#888888").pack(pady=(0, 8))

        if not self.report_faults:
            ctk.CTkLabel(self.report_frame, text="Perfect Harmony!",
                         text_color="#008000",
                         font=("Helvetica", 12)).pack(pady=10)
        else:
            for i, fault in enumerate(self.report_faults):
                self._make_fault_entry(i, fault)


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    SmartHarmonyAssistant().mainloop()