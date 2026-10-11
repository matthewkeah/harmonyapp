"""Canvas drawing helpers and note-asset generation."""

import os
from PIL import Image, ImageDraw, ImageTk

from constants import KEY_SIGNATURES, STEM_LENGTH, SYSTEM_HEIGHT, resource_path

_IMAGE_CACHE = {}


def generate_note_assets(base_color=(0, 0, 0, 255)):
    """Generate the note-asset dictionary tinted to `base_color`.

    Bare notehead glyphs (prefix `bn_`) contain only the notehead and
    are used for beamed groups; the beam code draws the stem. All
    other glyphs contain their stem, used for un-beamed notes.
    """
    def make_asset(draw_func, size, canvas_size):
        img = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
        draw_func(ImageDraw.Draw(img))
        return ImageTk.PhotoImage(img.resize(size, Image.Resampling.LANCZOS))

    NQ_CANVAS = (140, 450)
    NQ_SIZE = (14, 45)
    FLAG_CANVAS = (220, 450)
    FLAG_SIZE = (22, 45)

    def notehead_only(d, color, up=True, hollow=False):
        if up:
            if hollow:
                d.ellipse([0, 350, 140, 450], outline=color, width=22)
            else:
                d.ellipse([0, 350, 140, 450], fill=color)
        else:
            if hollow:
                d.ellipse([0, 0, 140, 100], outline=color, width=22)
            else:
                d.ellipse([0, 0, 140, 100], fill=color)

    def notehead_and_stem(d, color, up=True, hollow=False):
        if up:
            if hollow:
                d.ellipse([0, 350, 140, 450], outline=color, width=22)
            else:
                d.ellipse([0, 350, 140, 450], fill=color)
            d.rectangle([125, 0, 140, 400], fill=color)
        else:
            if hollow:
                d.ellipse([0, 0, 140, 100], outline=color, width=22)
            else:
                d.ellipse([0, 0, 140, 100], fill=color)
            d.rectangle([0, 50, 15, 450], fill=color)

    def draw_q(d, color, up=True):
        notehead_and_stem(d, color, up, hollow=False)

    def draw_h(d, color, up=True):
        notehead_and_stem(d, color, up, hollow=True)

    def draw_e(d, color, up=True):
        notehead_and_stem(d, color, up, hollow=False)
        if up:
            d.line([(140, 6), (162, 20), (180, 48), (186, 82),
                    (178, 112), (160, 128)],
                   fill=color, width=22, joint="curve")
        else:
            d.line([(15, 444), (37, 430), (55, 402), (61, 368),
                    (53, 338), (35, 322)],
                   fill=color, width=22, joint="curve")

    def draw_s(d, color, up=True):
        notehead_and_stem(d, color, up, hollow=False)
        if up:
            d.line([(140, 6), (162, 20), (180, 48), (186, 82),
                    (178, 112), (160, 128)],
                   fill=color, width=22, joint="curve")
            d.line([(140, 62), (162, 76), (180, 104), (186, 138),
                    (178, 168), (160, 184)],
                   fill=color, width=22, joint="curve")
        else:
            d.line([(15, 444), (37, 430), (55, 402), (61, 368),
                    (53, 338), (35, 322)],
                   fill=color, width=22, joint="curve")
            d.line([(15, 388), (37, 374), (55, 346), (61, 312),
                    (53, 282), (35, 266)],
                   fill=color, width=22, joint="curve")

    black = base_color
    cyan = (0, 162, 232, 255)
    A = {}

    A['w_note'] = make_asset(
        lambda d: d.ellipse([10, 10, 170, 110], outline=black, width=15),
        size=(18, 12), canvas_size=(180, 120))
    A['w_note_sel'] = make_asset(
        lambda d: d.ellipse([10, 10, 170, 110], outline=cyan, width=15),
        size=(18, 12), canvas_size=(180, 120))

    # Bare noteheads (no stem). Used for beamed notes.
    A['bn_up'] = make_asset(lambda d: notehead_only(d, black, True),
                            NQ_SIZE, NQ_CANVAS)
    A['bn_down'] = make_asset(lambda d: notehead_only(d, black, False),
                              NQ_SIZE, NQ_CANVAS)
    A['bn_up_sel'] = make_asset(lambda d: notehead_only(d, cyan, True),
                                NQ_SIZE, NQ_CANVAS)
    A['bn_down_sel'] = make_asset(lambda d: notehead_only(d, cyan, False),
                                  NQ_SIZE, NQ_CANVAS)

    A['h_up'] = make_asset(lambda d: draw_h(d, black, True), NQ_SIZE, NQ_CANVAS)
    A['h_down'] = make_asset(lambda d: draw_h(d, black, False), NQ_SIZE, NQ_CANVAS)
    A['h_up_sel'] = make_asset(lambda d: draw_h(d, cyan, True), NQ_SIZE, NQ_CANVAS)
    A['h_down_sel'] = make_asset(lambda d: draw_h(d, cyan, False), NQ_SIZE, NQ_CANVAS)

    A['q_up'] = make_asset(lambda d: draw_q(d, black, True), NQ_SIZE, NQ_CANVAS)
    A['q_down'] = make_asset(lambda d: draw_q(d, black, False), NQ_SIZE, NQ_CANVAS)
    A['q_up_sel'] = make_asset(lambda d: draw_q(d, cyan, True), NQ_SIZE, NQ_CANVAS)
    A['q_down_sel'] = make_asset(lambda d: draw_q(d, cyan, False), NQ_SIZE, NQ_CANVAS)

    A['e_up'] = make_asset(lambda d: draw_e(d, black, True), FLAG_SIZE, FLAG_CANVAS)
    A['e_down'] = make_asset(lambda d: draw_e(d, black, False), FLAG_SIZE, FLAG_CANVAS)
    A['e_up_sel'] = make_asset(lambda d: draw_e(d, cyan, True), FLAG_SIZE, FLAG_CANVAS)
    A['e_down_sel'] = make_asset(lambda d: draw_e(d, cyan, False), FLAG_SIZE, FLAG_CANVAS)

    A['s_up'] = make_asset(lambda d: draw_s(d, black, True), FLAG_SIZE, FLAG_CANVAS)
    A['s_down'] = make_asset(lambda d: draw_s(d, black, False), FLAG_SIZE, FLAG_CANVAS)
    A['s_up_sel'] = make_asset(lambda d: draw_s(d, cyan, True), FLAG_SIZE, FLAG_CANVAS)
    A['s_down_sel'] = make_asset(lambda d: draw_s(d, cyan, False), FLAG_SIZE, FLAG_CANVAS)

    return A


def load_clef_image(path, width, height):
    cache_key = f"{path}_{width}x{height}"
    if cache_key not in _IMAGE_CACHE:
        if not os.path.exists(path):
            return None
        img = Image.open(path).convert("RGBA").resize(
            (width, height), Image.Resampling.LANCZOS)
        pixels = img.load()
        for x in range(img.width):
            for y in range(img.height):
                r, g, b, a = pixels[x, y]
                if a < 255:
                    pixels[x, y] = (0, 0, 0, a)
                else:
                    pixels[x, y] = (0, 0, 0, 255 - int((r + g + b) / 3))
        _IMAGE_CACHE[cache_key] = ImageTk.PhotoImage(img)
    return _IMAGE_CACHE[cache_key]


def draw_staff(canvas, y_offset, sys_w, key_name, time_sig_name="4/4"):
    for i in range(5):
        canvas.create_line(50, 150 + y_offset + i * 10, sys_w,
                           150 + y_offset + i * 10, fill="#000000", width=1)
    for i in range(5):
        canvas.create_line(50, 290 + y_offset + i * 10, sys_w,
                           290 + y_offset + i * 10, fill="#000000", width=1)

    canvas.create_line(50, 150 + y_offset, 50, 330 + y_offset,
                       fill="#000000", width=2)

    treble = load_clef_image(resource_path("assets/treble_clef.png"), 40, 90)
    bass = load_clef_image(resource_path("assets/bass_clef.png"), 35, 45)
    if treble:
        canvas.create_image(80, 180 + y_offset, image=treble)
    else:
        canvas.create_text(80, 180 + y_offset, text="\U0001D11E",
                           font=("Segoe UI Symbol", 52))
    if bass:
        canvas.create_image(80, 300 + y_offset, image=bass)
    else:
        canvas.create_text(80, 300 + y_offset, text="\U0001D122",
                           font=("Segoe UI Symbol", 52))

    current_x = 110
    for acc_type, t_y, b_y in KEY_SIGNATURES[key_name]["accidentals"]:
        char = "\u266F" if acc_type == "sharp" else "\u266D"
        y_shift = -3 if acc_type == "flat" else -2
        canvas.create_text(current_x, t_y + y_shift + y_offset, text=char,
                           font=("Segoe UI Symbol", 26))
        canvas.create_text(current_x, b_y + y_shift + y_offset, text=char,
                           font=("Segoe UI Symbol", 26))
        current_x += 16

    time_x = current_x + 15
    num, den = time_sig_name.split("/")
    canvas.create_text(time_x, 170 + y_offset, text=num,
                       font=("Times New Roman", 22, "bold"), fill="#000000")
    canvas.create_text(time_x, 190 + y_offset, text=den,
                       font=("Times New Roman", 22, "bold"), fill="#000000")
    canvas.create_text(time_x, 300 + y_offset, text=num,
                       font=("Times New Roman", 22, "bold"), fill="#000000")
    canvas.create_text(time_x, 320 + y_offset, text=den,
                       font=("Times New Roman", 22, "bold"), fill="#000000")

    return time_x + 30


def draw_time_signature_change(canvas, barline_x, y_offset, time_sig_name):
    num, den = time_sig_name.split("/")
    canvas.create_text(barline_x + 12, 168 + y_offset, text=num,
                       font=("Times New Roman", 18, "bold"), fill="#000000")
    canvas.create_text(barline_x + 12, 186 + y_offset, text=den,
                       font=("Times New Roman", 18, "bold"), fill="#000000")
    canvas.create_text(barline_x + 12, 298 + y_offset, text=num,
                       font=("Times New Roman", 18, "bold"), fill="#000000")
    canvas.create_text(barline_x + 12, 316 + y_offset, text=den,
                       font=("Times New Roman", 18, "bold"), fill="#000000")


# ---------------------------------------------------------------------
#  Ledger lines
#
#  Staff line positions in canvas coordinates (before system offset):
#    Treble top line:    150
#    Treble bottom line: 190
#    Bass top line:      290
#    Bass bottom line:   330
#
#  Ledger lines sit at every 10-pixel mark extending outward from the
#  nearest staff edge. A note sitting ON a ledger's y-coordinate needs
#  that ledger drawn. A note sitting in the space above a ledger needs
#  only the ledger below it.
#
#  The previous implementation had a branch gap: y=270 (E4 in the
#  bass staff) fell into the "middle of the gap" case and got no
#  ledgers at all, despite needing two (280 and 270). The rewrite
#  uses explicit outward walks so every boundary is covered.
# ---------------------------------------------------------------------

def draw_ledger_lines(canvas, x, y, tag=None, color="#000000"):
    line_args = {"fill": color, "width": 1.5}
    if tag:
        line_args["tags"] = tag

    sys_idx = int(y // SYSTEM_HEIGHT)
    y_local = y - sys_idx * SYSTEM_HEIGHT
    offset = sys_idx * SYSTEM_HEIGHT

    positions = []
    MAX = 12

    if y_local < 150:
        # Above treble staff. Ledgers at 140, 130, 120, ...
        p = 140
        while p >= y_local and len(positions) < MAX:
            positions.append(p)
            p -= 10
    elif 190 < y_local < 250:
        # Below treble staff, before the middle gap. Ledgers at
        # 200, 210, 220, ...
        p = 200
        while p <= y_local and len(positions) < MAX:
            positions.append(p)
            p += 10
    elif 250 <= y_local < 290:
        # Above bass staff. Ledgers at 280, 270, 260, ...
        # This branch covers y=270 (E4 in bass), which the previous
        # version silently dropped.
        p = 280
        while p >= y_local and len(positions) < MAX:
            positions.append(p)
            p -= 10
    elif y_local > 330:
        # Below bass staff. Ledgers at 340, 350, 360, ...
        p = 340
        while p <= y_local and len(positions) < MAX:
            positions.append(p)
            p += 10

    for p in positions:
        canvas.create_line(x - 14, p + offset, x + 14, p + offset, **line_args)


def _classify_duration(ticks):
    table = [
        (1920, 'whole'),
        (960, 'half'),
        (480, 'quarter'),
        (240, 'quaver'),
        (120, 'semiquaver'),
    ]
    for base_ticks, base_name in table:
        for dots, mult in ((2, 1.75), (1, 1.5), (0, 1.0)):
            if abs(ticks - base_ticks * mult) < 1:
                return base_name, dots
    if ticks >= 1440:
        return 'whole', 0
    if ticks >= 720:
        return 'half', 0
    if ticks >= 360:
        return 'quarter', 0
    if ticks >= 180:
        return 'quaver', 0
    return 'semiquaver', 0


def _draw_dots(canvas, x, y, dots, color):
    if dots <= 0:
        return
    start_x = x + 11
    spacing = 6
    r = 1.8
    for i in range(dots):
        dx = start_x + i * spacing
        canvas.create_oval(dx - r, y - r, dx + r, y + r,
                           fill=color, outline="")


def draw_note(canvas, x, y, ticks, stem, is_selected, accidental, assets,
              is_beamed=False, overflow=False, note_color=None):
    if note_color is None:
        note_color = "#000000"

    ledger_color = "#00A2E8" if is_selected else note_color
    draw_ledger_lines(canvas, x, y, color=ledger_color)

    if overflow:
        canvas.create_oval(x - 16, y - 15, x + 16, y + 15,
                           outline="#D40000", width=2, tags="overflow")

    acc_color = "#00A2E8" if is_selected else note_color
    if accidental == "sharp":
        canvas.create_text(x - 24, y, text="\u266F",
                           font=("Segoe UI Symbol", 26), fill=acc_color)
    elif accidental == "flat":
        canvas.create_text(x - 24, y - 4, text="\u266D",
                           font=("Segoe UI Symbol", 30), fill=acc_color)
    elif accidental == "natural":
        canvas.create_text(x - 24, y, text="\u266E",
                           font=("Segoe UI Symbol", 26), fill=acc_color)

    base, dots = _classify_duration(ticks)
    suffix = 'up' if stem == "up" else 'down'
    sel = '_sel' if is_selected else ''

    if base == 'whole':
        canvas.create_image(x, y, image=assets[f'w_note{sel}'])
        _draw_dots(canvas, x + 2, y, dots, acc_color)
    elif base == 'half':
        canvas.create_image(x, y - 17 if stem == "up" else y + 17,
                            image=assets[f'h_{suffix}{sel}'])
        _draw_dots(canvas, x + 4, y, dots, acc_color)
    elif base == 'quarter':
        canvas.create_image(x, y - 17 if stem == "up" else y + 17,
                            image=assets[f'q_{suffix}{sel}'])
        _draw_dots(canvas, x + 4, y, dots, acc_color)
    elif base == 'quaver':
        glyph = 'bn' if is_beamed else 'e'
        canvas.create_image(x, y - 17 if stem == "up" else y + 17,
                            image=assets[f'{glyph}_{suffix}{sel}'])
        _draw_dots(canvas, x + 4, y, dots, acc_color)
    else:
        glyph = 'bn' if is_beamed else 's'
        canvas.create_image(x, y - 17 if stem == "up" else y + 17,
                            image=assets[f'{glyph}_{suffix}{sel}'])
        _draw_dots(canvas, x + 4, y, dots, acc_color)


def draw_tie(canvas, x1, y1, x2, y2, color, stem_dir):
    """Draw a shallow curved tie between two noteheads."""
    if abs(x2 - x1) < 4:
        return
    left = min(x1, x2)
    right = max(x1, x2)
    if stem_dir == "up":
        canvas.create_arc(left + 5, y1 - 14, right - 5, y1 - 2,
                          start=0, extent=180, style="arc",
                          outline=color, width=2, tags="tie")
    else:
        canvas.create_arc(left + 5, y1 + 2, right - 5, y1 + 14,
                          start=180, extent=180, style="arc",
                          outline=color, width=2, tags="tie")


def draw_beam_group(canvas, points, stem_dir, color="#000000"):
    """Draw a beam group across two or more notes.

    points: list of (x, y, ticks) in score order.

    The primary beam connects the outermost stems. Secondary beams
    (for semiquavers and shorter) are drawn only over *runs of
    consecutive* short notes, not across the entire group. This
    matters for mixed rhythms like quaver–semiquaver–semiquaver–quaver,
    where the secondary beam should span only the two middle notes.
    """
    if len(points) < 2:
        return

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    stem_thickness = 1.5
    beam_thickness = 4
    beam_spacing = 6

    if stem_dir == "up":
        beam_base = min(ys) - STEM_LENGTH
        stem_x_offset = 6
    else:
        beam_base = max(ys) + STEM_LENGTH
        stem_x_offset = -6

    # Primary beam and stems.
    for x, y, _ in points:
        canvas.create_line(x + stem_x_offset, y,
                           x + stem_x_offset, beam_base,
                           fill=color, width=stem_thickness, tags="beam")
    canvas.create_line(xs[0] + stem_x_offset, beam_base,
                       xs[-1] + stem_x_offset, beam_base,
                       fill=color, width=beam_thickness, tags="beam")

    # Find consecutive runs of semiquavers (or shorter).
    runs = []
    current = []
    for x, y, t in points:
        if t <= 180:
            current.append((x, y, t))
        else:
            if len(current) >= 2:
                runs.append(current)
            current = []
    if len(current) >= 2:
        runs.append(current)

    secondary_y = beam_base + beam_spacing if stem_dir == "up" \
        else beam_base - beam_spacing
    for run in runs:
        x1 = run[0][0] + stem_x_offset
        x2 = run[-1][0] + stem_x_offset
        canvas.create_line(x1, secondary_y, x2, secondary_y,
                           fill=color, width=beam_thickness, tags="beam")