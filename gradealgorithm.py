"""Standardize raw fault penalties into a fair 0-100 score.

When a BarLayout is provided, the bar count respects the piece's
actual time signatures. Otherwise it falls back to a 4/4 assumption
via the legacy BAR_TICKS constant.
"""

from constants import BAR_TICKS

DAMAGE_THRESHOLD = 80.0


def count_bars(slices, layout=None):
    if layout is not None:
        if not slices:
            return max(1, layout.count)
        last_tick = max(s.tick for s in slices)
        bar_idx, _ = layout.locate(last_tick)
        return max(1, bar_idx + 1)
    if not slices:
        return 1
    last_tick = max(s.tick for s in slices)
    return max(1, (last_tick // BAR_TICKS) + 1)


def grade(slices, faults, total_rule_weight=None, layout=None):
    """Return (score, raw_penalty, num_bars, threshold). Score is 0-100."""
    raw = sum(f.penalty_weight for f in faults)
    nb = count_bars(slices, layout=layout)
    avg_per_bar = raw / nb
    score = 100.0 * (1.0 - avg_per_bar / DAMAGE_THRESHOLD)
    return max(0, min(100, int(round(score)))), raw, nb, DAMAGE_THRESHOLD