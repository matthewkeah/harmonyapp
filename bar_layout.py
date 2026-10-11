"""bar_layout.py — Variable-time-signature bar arithmetic.

A BarLayout is a list of Bar objects, each knowing its start tick, its
length, its time signature, and its key signature. Time signatures and
key signatures can change at any bar. The layout rebuilds on demand and
supports note overflow detection.
"""

from dataclasses import dataclass
from typing import List, Tuple

from constants import (
    TIME_SIGNATURES, DEFAULT_TIME_SIGNATURE, KEY_SIGNATURES,
    ticks_per_bar_from_ts, beat_ticks_from_ts,
)


@dataclass
class Bar:
    index: int
    start_tick: int
    end_tick: int
    time_sig_name: str
    key_sig_name: str

    @property
    def ticks(self) -> int:
        return self.end_tick - self.start_tick

    @property
    def beat_ticks(self) -> int:
        return beat_ticks_from_ts(self.time_sig_name)

    @property
    def num(self) -> int:
        return TIME_SIGNATURES[self.time_sig_name]["num"]

    @property
    def den(self) -> int:
        return TIME_SIGNATURES[self.time_sig_name]["den"]

    @property
    def compound(self) -> bool:
        return TIME_SIGNATURES[self.time_sig_name]["compound"]


class BarLayout:
    def __init__(self, initial_time_sig=DEFAULT_TIME_SIGNATURE,
                 initial_key_sig="C Major", num_bars=1):
        self._changes: List[Tuple[int, str, str]] = [
            (0, initial_time_sig, initial_key_sig)
        ]
        self.bars: List[Bar] = []
        self.reflow(num_bars)

    # ---------- Change management ----------

    def set_initial(self, time_sig_name: str, key_sig_name: str):
        self._changes = [c for c in self._changes if c[0] != 0]
        self._changes.insert(0, (0, time_sig_name, key_sig_name))
        self._changes.sort(key=lambda c: c[0])

    def set_time_sig_at_bar(self, bar_index: int, time_sig_name: str):
        self._replace_change(bar_index, time_sig=time_sig_name)

    def set_key_sig_at_bar(self, bar_index: int, key_sig_name: str):
        self._replace_change(bar_index, key_sig=key_sig_name)

    def clear_changes_after(self, bar_index: int):
        self._changes = [c for c in self._changes if c[0] <= bar_index]

    def _replace_change(self, bar_index: int, time_sig=None, key_sig=None):
        cur_ts, cur_ks = self._effective_at(bar_index)
        new_ts = time_sig or cur_ts
        new_ks = key_sig or cur_ks
        self._changes = [c for c in self._changes if c[0] != bar_index]
        self._changes.append((bar_index, new_ts, new_ks))
        self._changes.sort(key=lambda c: c[0])

    def _effective_at(self, bar_index: int) -> Tuple[str, str]:
        ts = DEFAULT_TIME_SIGNATURE
        ks = "C Major"
        for (b, t, k) in self._changes:
            if b <= bar_index:
                ts, ks = t, k
            else:
                break
        return ts, ks

    # ---------- Rebuild the bar list ----------

    def reflow(self, num_bars: int):
        num_bars = max(1, num_bars)
        final_ts, final_ks = self._effective_at(num_bars)
        if not self._changes or self._changes[-1][0] != num_bars:
            self._changes.append((num_bars, final_ts, final_ks))
            self._changes.sort(key=lambda c: c[0])

        self.bars = []
        tick = 0
        for i in range(num_bars):
            ts, ks = self._effective_at(i)
            length = ticks_per_bar_from_ts(ts)
            self.bars.append(Bar(
                index=i,
                start_tick=tick,
                end_tick=tick + length,
                time_sig_name=ts,
                key_sig_name=ks,
            ))
            tick += length

    def ensure_bars(self, num_bars: int):
        if num_bars > len(self.bars):
            self.reflow(num_bars)

    # ---------- Lookups ----------

    def locate(self, tick: int) -> Tuple[int, int]:
        if tick < 0:
            return 0, 0
        for bar in self.bars:
            if bar.start_tick <= tick < bar.end_tick:
                return bar.index, tick - bar.start_tick
        last = self.bars[-1]
        return last.index, min(max(0, tick - last.start_tick), last.ticks - 1)

    def bar_at(self, tick: int) -> Bar:
        i, _ = self.locate(tick)
        return self.bars[i]

    @property
    def total_ticks(self) -> int:
        return self.bars[-1].end_tick if self.bars else 0

    @property
    def count(self) -> int:
        return len(self.bars)

    # ---------- Note overflow check ----------

    def note_overflows(self, note) -> bool:
        bar = self.bar_at(note["time_ticks"])
        return note["time_ticks"] + note["ticks"] > bar.end_tick

    def overflow_amount(self, note) -> int:
        bar = self.bar_at(note["time_ticks"])
        return max(0, note["time_ticks"] + note["ticks"] - bar.end_tick)

    # ---------- Bar tick accessors ----------

    def bar_starts(self) -> List[int]:
        return [b.start_tick for b in self.bars]

    def bar_ends(self) -> List[int]:
        return [b.end_tick for b in self.bars]