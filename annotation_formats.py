"""annotation_formats.py — Per-rule visual annotations for the canvas.

Every rule in the harmony system maps to a visual mark that identifies
its fault on the manuscript. The mark's shape, its position relative
to the notes it references, and its label are chosen to convey the
nature of the fault at a glance.

Public entry point:

    draw_fault(canvas, fault, ctx, color)

Where:
  * canvas — a tkinter Canvas.
  * fault  — an ErrorDetail with .rule_id, .voices, .tick_coordinate,
             .prev_tick, .error_message.
  * ctx    — an object providing:
                .note_at(tick, voice_name) -> note dict or None
                .note_xy(note) -> (x, y)
                .bar_layout
                .START_X
                .bar_pixel_width
                .bars_per_system
             Typically the SmartHarmonyAssistant instance.
  * color  — hex string for the annotation's stroke.

Every fault rule_id is mapped to a style in STYLE_MAP. Styles are
drawn by dedicated functions below. Unmapped rules fall back to the
generic circle.

To add a new rule: add its short label to LABELS, add its rule_id to
STYLE_MAP under the appropriate style, and (if you need a new visual
primitive) add a new drawer function and register it in _DRAWERS.
"""

from harmony import time_to_visual


# ================================================================
#  Short labels rendered next to each fault
# ================================================================

LABELS = {
    # --- Pass 1: ranges, spacing, voice integrity ---
    "RANGE-S": "R", "RANGE-A": "R", "RANGE-T": "R", "RANGE-B": "R",
    "SPACING-SA": "Sp", "SPACING-AT": "Sp", "SPACING-TB": "Sp",
    "SPACING-SB": "Sp", "SPACING-ST": "Sp",
    "CROSS-001": "X", "OVERLAP-001": "Over",

    # --- Pass 1: parallels and direct intervals ---
    "PARALLEL-P5": "P5", "PARALLEL-P8": "P8",
    "DIRECT-P5": "H5", "DIRECT-P8": "H8",

    # --- Pass 1: doubling and triad completeness ---
    "DOUBLING-LT": "LT", "DOUBLING-SEVENTH": "7th",
    "DOUBLING-MAJ3": "Db", "DOUBLING-MIN3": "Db", "DOUBLING-DIM3": "Db",
    "DOUBLING-ROOT-MAJ": "Db", "DOUBLING-ROOT-MIN": "Db",
    "INV2-DOUBLE-BASS": "Db",
    "TRIAD-THIRD-PRESENT": "3",

    # --- Pass 1: leaps ---
    "LEAP-SOPRANO": "Leap", "LEAP-ALTO": "Leap",
    "LEAP-TENOR": "Leap", "LEAP-BASS-OCTAVE": "Leap",

    # --- Pass 2: resolution ---
    "P2-RESOLVE-LT-OUTER": "LT", "P2-RESOLVE-LT-ANY": "LT",
    "P2-RESOLVE-SEVENTH": "7",
    "P2-V7-TO-I6": "7", "P2-V65-BASS-ASCEND": "^1",
    "P2-V42-TO-I6": "7", "P2-V43-RESOLUTION": "7",
    "P2-V7-I-DOUBLED-3RD": "3rd",

    # --- Pass 2: cadence ---
    "P2-CAD-ROOT-POS": "Cad", "P2-PAC-SOPRANO-1": "^1",
    "P2-CAD-LT-SOPRANO-RESOLVE": "LT",
    "P2-CAD-LT-BASS-RESOLVE": "LT",

    # --- Pass 2: cadential 6/4 ---
    "P2-CAD-6-4-BASS-DOUBLED": "Db",
    "P2-CAD-6-4-NO-DOUBLE-4": "4",
    "P2-CAD-6-4-RESOLVES-V": "6/4",
    "P2-CAD-6-4-STRONG-BEAT": "6/4",
    "P2-CAD-6-4-4TH-DESCENDS": "4\u2193",

    # --- Pass 2: formal position ---
    "P2-OPENING-TONIC": "Open",
    "P2-CLOSING-TONIC": "End",
    "P2-CADENCE-AT-END": "Cad",

    # --- Pass 2: harmonic syntax ---
    "P2-NO-RETRO": "Retro",
    "P2-INTERMEDIATE-TO-TONIC": "\u2190",
    "P2-WEAK-STRONG-SAME": "W\u2192S",

    # --- Pass 3 ---
    "P3-NO-MELODIC-A2": "A2",
    "P3-II7-INCOMPLETE": "ii\u2077",
    "P3-INTERMEDIATE-DESCEND": "\u2193",

    # --- Pass 4 ---
    "P4-ASC-FIFTH-RETRO": "Retro",
    "P4-ASC-THIRD-WEAK": "\u2190",
    "P4-MINOR-V-IN-MAJOR": "v",
    "P4-UNKNOWN-64": "6/4?",
    "P4-ACCENTED-NCT": "NCT",

    # --- Pass 5 ---
    "P5-APPLIED-LT-RESOLUTION": "ALT",
    "P5-DOUBLED-APPLIED-LT": "Db",
    "P5-MIXTURE-TONE": "b6",

    # --- Pass 6 ---
    "P6-AUG6-RESOLUTION": "A6",
    "P6-AUG6-TO-DOMINANT": "A6",
    "P6-NEAPOLITAN-B2": "b2",
    "P6-NEAPOLITAN-BASS": "N",
}


# ================================================================
#  Style mapping
# ================================================================

STYLE_MAP = {
    # --- Pass 1 ---
    "RANGE-S": "bracket_horizontal",
    "RANGE-A": "bracket_horizontal",
    "RANGE-T": "bracket_horizontal",
    "RANGE-B": "bracket_horizontal",

    "SPACING-SA": "span", "SPACING-AT": "span", "SPACING-TB": "span",
    "SPACING-SB": "span", "SPACING-ST": "span",

    "CROSS-001": "crossing",
    "OVERLAP-001": "overlap",

    "PARALLEL-P5": "parallel", "PARALLEL-P8": "parallel",
    "DIRECT-P5": "parallel", "DIRECT-P8": "parallel",

    "DOUBLING-LT": "bracket_horizontal",
    "DOUBLING-SEVENTH": "bracket_horizontal",
    "DOUBLING-MAJ3": "bracket_horizontal",
    "DOUBLING-MIN3": "bracket_horizontal",
    "DOUBLING-DIM3": "bracket_horizontal",
    "DOUBLING-ROOT-MAJ": "bracket_horizontal",
    "DOUBLING-ROOT-MIN": "bracket_horizontal",
    "INV2-DOUBLE-BASS": "bracket_horizontal",
    "TRIAD-THIRD-PRESENT": "slash_3",

    "LEAP-SOPRANO": "arc", "LEAP-ALTO": "arc",
    "LEAP-TENOR": "arc", "LEAP-BASS-OCTAVE": "arc",

    # --- Pass 2 ---
    "P2-RESOLVE-LT-OUTER": "arrow_up",
    "P2-RESOLVE-LT-ANY": "arrow_up",
    "P2-RESOLVE-SEVENTH": "arrow_down",
    "P2-V7-TO-I6": "arrow_down",
    "P2-V65-BASS-ASCEND": "arrow_up",
    "P2-V42-TO-I6": "arrow_down",
    "P2-V43-RESOLUTION": "arrow_down",
    "P2-V7-I-DOUBLED-3RD": "label_box",

    "P2-CAD-ROOT-POS": "label_box",
    "P2-PAC-SOPRANO-1": "arrow_up",
    "P2-CAD-LT-SOPRANO-RESOLVE": "arrow_up",
    "P2-CAD-LT-BASS-RESOLVE": "arrow_up",

    "P2-CAD-6-4-BASS-DOUBLED": "bracket_horizontal",
    "P2-CAD-6-4-NO-DOUBLE-4": "bracket_horizontal",
    "P2-CAD-6-4-RESOLVES-V": "label_box",
    "P2-CAD-6-4-STRONG-BEAT": "label_box",
    "P2-CAD-6-4-4TH-DESCENDS": "arrow_down",

    "P2-OPENING-TONIC": "label_box",
    "P2-CLOSING-TONIC": "label_box",
    "P2-CADENCE-AT-END": "label_box",

    "P2-NO-RETRO": "arrow_back",
    "P2-INTERMEDIATE-TO-TONIC": "arrow_back",
    "P2-WEAK-STRONG-SAME": "label_box",

    # --- Pass 3 ---
    "P3-NO-MELODIC-A2": "arc",
    "P3-II7-INCOMPLETE": "label_box",
    "P3-INTERMEDIATE-DESCEND": "arrow_down",

    # --- Pass 4 ---
    "P4-ASC-FIFTH-RETRO": "arrow_back",
    "P4-ASC-THIRD-WEAK": "arrow_back",
    "P4-MINOR-V-IN-MAJOR": "circle",
    "P4-UNKNOWN-64": "label_box",
    "P4-ACCENTED-NCT": "arrow_down",

    # --- Pass 5 ---
    "P5-APPLIED-LT-RESOLUTION": "arrow_up",
    "P5-DOUBLED-APPLIED-LT": "bracket_horizontal",
    "P5-MIXTURE-TONE": "arrow_down",

    # --- Pass 6 ---
    "P6-AUG6-RESOLUTION": "arrow_outward",
    "P6-AUG6-TO-DOMINANT": "arrow_outward",
    "P6-NEAPOLITAN-B2": "arrow_down",
    "P6-NEAPOLITAN-BASS": "arrow_up",
}


# ================================================================
#  Helper functions
# ================================================================

def _label_for(fault):
    return LABELS.get(fault.rule_id, fault.rule_id[:3])


def _visible_notes(fault, ctx):
    """Return [(voice_name, note, (x, y))] for each voice in
    fault.voices that resolves to a note at fault.tick_coordinate."""
    out = []
    for v in (fault.voices or []):
        n = ctx._note_at(fault.tick_coordinate, v)
        if n is None:
            continue
        out.append((v, n, ctx._note_xy(n)))
    return out


def _fallback_xy(fault, ctx):
    """Position used when no voices are attached to the fault."""
    x, _ = time_to_visual(fault.tick_coordinate, 150,
                          ctx.bar_layout, ctx.START_X,
                          ctx.bar_pixel_width, ctx.bars_per_system)
    return (x, 130)


def _anchor_xy(fault, ctx):
    """Position used as the fault's centre-of-mass."""
    notes = _visible_notes(fault, ctx)
    if not notes:
        return _fallback_xy(fault, ctx)
    xs = [p[0] for _, _, p in notes]
    ys = [p[1] for _, _, p in notes]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


# ================================================================
#  Drawers
# ================================================================

def _draw_circle(canvas, fault, ctx, color):
    """Generic: circle around each referenced note, label to the right."""
    label = _label_for(fault)
    drawn = False
    for _, _, (x, y) in _visible_notes(fault, ctx):
        canvas.create_oval(x - 14, y - 14, x + 14, y + 14,
                           outline=color, width=2, tags="fault")
        if not drawn:
            canvas.create_text(x + 20, y - 14, text=label,
                               font=("Helvetica", 9, "bold"),
                               fill=color, tags="fault")
            drawn = True
    if not drawn:
        x, y = _fallback_xy(fault, ctx)
        canvas.create_oval(x - 14, y - 14, x + 14, y + 14,
                           outline=color, width=2, tags="fault")
        canvas.create_text(x + 20, y - 14, text=label,
                           font=("Helvetica", 9, "bold"),
                           fill=color, tags="fault")


def _draw_parallel(canvas, fault, ctx, color):
    """Two parallel lines connecting the two voices' prev-to-current
    motions. Used for parallel fifths/octaves and direct intervals."""
    label = _label_for(fault)
    top_y = 99999
    label_x = 0
    any_line = False
    for v in (fault.voices or []):
        p = ctx._note_at(fault.prev_tick, v) if fault.prev_tick is not None else None
        c = ctx._note_at(fault.tick_coordinate, v)
        if p is None or c is None:
            continue
        px, py = ctx._note_xy(p)
        cx, cy = ctx._note_xy(c)
        canvas.create_line(px, py, cx, cy, fill=color, width=2, tags="fault")
        canvas.create_oval(px - 3, py - 3, px + 3, py + 3,
                           fill=color, outline="", tags="fault")
        canvas.create_oval(cx - 3, cy - 3, cx + 3, cy + 3,
                           fill=color, outline="", tags="fault")
        any_line = True
        if cy < top_y:
            top_y = cy
            label_x = cx
    if any_line:
        canvas.create_text(label_x, top_y - 16, text=label,
                           font=("Helvetica", 9, "bold"),
                           fill=color, tags="fault")
    else:
        _draw_circle(canvas, fault, ctx, color)


def _draw_span(canvas, fault, ctx, color):
    """Vertical brace between two voices at the same tick."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if len(notes) < 2:
        _draw_circle(canvas, fault, ctx, color)
        return
    ax, ay = notes[0][2]
    bx, by = notes[1][2]
    top_y, bot_y = min(ay, by), max(ay, by)
    brac_x = (ax + bx) / 2 - 26
    cap = 6
    canvas.create_line(brac_x, top_y, brac_x, bot_y,
                       fill=color, width=2, tags="fault")
    canvas.create_line(brac_x, top_y, brac_x + cap, top_y,
                       fill=color, width=2, tags="fault")
    canvas.create_line(brac_x, bot_y, brac_x + cap, bot_y,
                       fill=color, width=2, tags="fault")
    canvas.create_text(brac_x - 8, (top_y + bot_y) / 2, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_crossing(canvas, fault, ctx, color):
    """X mark at the midpoint between the two crossing voices."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if len(notes) < 2:
        _draw_circle(canvas, fault, ctx, color)
        return
    ax, ay = notes[0][2]
    bx, by = notes[1][2]
    mx, my = (ax + bx) / 2, (ay + by) / 2
    r = 8
    canvas.create_line(mx - r, my - r, mx + r, my + r,
                       fill=color, width=2, tags="fault")
    canvas.create_line(mx - r, my + r, mx + r, my - r,
                       fill=color, width=2, tags="fault")
    canvas.create_text(mx + 12, my - 12, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_overlap(canvas, fault, ctx, color):
    """Arrow from the previous position to the current position, plus
    a small perpendicular tick to highlight the overlap boundary."""
    label = _label_for(fault)
    if fault.prev_tick is None:
        _draw_circle(canvas, fault, ctx, color)
        return
    drew = False
    for v in (fault.voices or []):
        p = ctx._note_at(fault.prev_tick, v)
        c = ctx._note_at(fault.tick_coordinate, v)
        if p is None or c is None:
            continue
        px, py = ctx._note_xy(p)
        cx, cy = ctx._note_xy(c)
        canvas.create_line(px, py, cx, cy, fill=color,
                           width=2, arrow="last", tags="fault")
        canvas.create_line(cx - 5, cy, cx + 5, cy,
                           fill=color, width=2, tags="fault")
        drew = True
    if drew:
        x, y = _anchor_xy(fault, ctx)
        canvas.create_text(x + 12, y - 14, text=label,
                           font=("Helvetica", 9, "bold"),
                           fill=color, tags="fault")
    else:
        _draw_circle(canvas, fault, ctx, color)


def _draw_arrow_up(canvas, fault, ctx, color):
    """Upward arrow at the referenced note(s)."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        _draw_circle(canvas, fault, ctx, color)
        return
    for _, _, (x, y) in notes:
        tip = (x, y - 24)
        base = (x, y - 10)
        canvas.create_line(base[0], base[1], tip[0], tip[1],
                           fill=color, width=2, arrow="last", tags="fault")
    x, y = notes[0][2]
    canvas.create_text(x + 8, y - 26, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_arrow_down(canvas, fault, ctx, color):
    """Downward arrow at the referenced note(s)."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        _draw_circle(canvas, fault, ctx, color)
        return
    for _, _, (x, y) in notes:
        tip = (x, y + 24)
        base = (x, y + 10)
        canvas.create_line(base[0], base[1], tip[0], tip[1],
                           fill=color, width=2, arrow="last", tags="fault")
    x, y = notes[0][2]
    canvas.create_text(x + 8, y + 26, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_arrow_outward(canvas, fault, ctx, color):
    """Two arrows diverging from a central point above the notes."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        _draw_circle(canvas, fault, ctx, color)
        return
    x, y = _anchor_xy(fault, ctx)
    top = y - 26
    canvas.create_line(x - 8, top, x - 18, top,
                       fill=color, width=2, arrow="last", tags="fault")
    canvas.create_line(x + 8, top, x + 18, top,
                       fill=color, width=2, arrow="last", tags="fault")
    canvas.create_text(x, top - 10, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_arrow_back(canvas, fault, ctx, color):
    """Leftward arrow indicating a backward (retrogressive) motion."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        x, y = _fallback_xy(fault, ctx)
    else:
        x, y = notes[0][2]
    top = y - 22
    canvas.create_line(x + 22, top, x - 6, top,
                       fill=color, width=2, arrow="last", tags="fault")
    canvas.create_text(x + 26, top, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


def _draw_arc(canvas, fault, ctx, color):
    """Curved arc over the melodic interval."""
    label = _label_for(fault)
    if fault.prev_tick is None:
        _draw_circle(canvas, fault, ctx, color)
        return
    drew = False
    for v in (fault.voices or []):
        p = ctx._note_at(fault.prev_tick, v)
        c = ctx._note_at(fault.tick_coordinate, v)
        if p is None or c is None:
            continue
        px, py = ctx._note_xy(p)
        cx, cy = ctx._note_xy(c)
        top = min(py, cy) - 6
        canvas.create_arc(px, top, cx, top + 20,
                          start=0, extent=180, style="arc",
                          outline=color, width=2, tags="fault")
        drew = True
    if drew:
        x, y = _anchor_xy(fault, ctx)
        canvas.create_text(x, y - 30, text=label,
                           font=("Helvetica", 9, "bold"),
                           fill=color, tags="fault")
    else:
        _draw_circle(canvas, fault, ctx, color)


def _draw_bracket_horizontal(canvas, fault, ctx, color):
    """Horizontal bracket that spans the referenced notes."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        _draw_circle(canvas, fault, ctx, color)
        return
    xs = [p[0] for _, _, p in notes]
    ys = [p[1] for _, _, p in notes]
    left, right = min(xs) - 12, max(xs) + 12
    top = min(ys) - 20
    cap = 6
    canvas.create_line(left, top + cap, left, top,
                       fill=color, width=2, tags="fault")
    canvas.create_line(left, top, right, top,
                       fill=color, width=2, tags="fault")
    canvas.create_line(right, top, right, top + cap,
                       fill=color, width=2, tags="fault")
    canvas.create_text(left - 4, top - 6, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, anchor="sw", tags="fault")


def _draw_slash_3(canvas, fault, ctx, color):
    """Circle with a diagonal slash through it and '3' inside."""
    label = _label_for(fault)
    notes = _visible_notes(fault, ctx)
    if not notes:
        _draw_circle(canvas, fault, ctx, color)
        return
    for _, _, (x, y) in notes:
        r = 12
        canvas.create_oval(x - r, y - r, x + r, y + r,
                           outline=color, width=2, tags="fault")
        canvas.create_line(x - r + 2, y + r - 2, x + r - 2, y - r + 2,
                           fill=color, width=2, tags="fault")
        canvas.create_text(x, y, text=label,
                           font=("Helvetica", 9, "bold"),
                           fill=color, tags="fault")
    x, y = notes[0][2]
    canvas.create_text(x + 18, y - 12, text="missing",
                       font=("Helvetica", 8, "italic"),
                       fill=color, tags="fault")


def _draw_label_box(canvas, fault, ctx, color):
    """Rounded box with the fault label, placed above the anchor."""
    label = _label_for(fault)
    x, y = _anchor_xy(fault, ctx)
    top = y - 30
    pad = 5
    w = max(28, len(label) * 7 + 2 * pad)
    h = 16
    canvas.create_rectangle(x - w / 2, top - h / 2,
                            x + w / 2, top + h / 2,
                            outline=color, width=1.5, tags="fault")
    canvas.create_text(x, top, text=label,
                       font=("Helvetica", 9, "bold"),
                       fill=color, tags="fault")


# ================================================================
#  Dispatch
# ================================================================

_DRAWERS = {
    "circle": _draw_circle,
    "parallel": _draw_parallel,
    "span": _draw_span,
    "crossing": _draw_crossing,
    "overlap": _draw_overlap,
    "arrow_up": _draw_arrow_up,
    "arrow_down": _draw_arrow_down,
    "arrow_outward": _draw_arrow_outward,
    "arrow_back": _draw_arrow_back,
    "arc": _draw_arc,
    "bracket_horizontal": _draw_bracket_horizontal,
    "slash_3": _draw_slash_3,
    "label_box": _draw_label_box,
}


def draw_fault(canvas, fault, ctx, color):
    """Render the visual annotation for a single fault."""
    style = STYLE_MAP.get(fault.rule_id, "circle")
    drawer = _DRAWERS.get(style, _draw_circle)
    drawer(canvas, fault, ctx, color)