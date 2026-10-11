import threading
import time
import ctypes
from typing import List, Dict, Optional
from dataclasses import dataclass


class NoteNode:
    def __init__(self, pitch: int, tick_length: int):
        self.pitch = pitch
        self.tick_length = tick_length


@dataclass
class VerticalSlice:
    tick: int = 0
    soprano: Optional[NoteNode] = None
    alto: Optional[NoteNode] = None
    tenor: Optional[NoteNode] = None
    bass: Optional[NoteNode] = None

    def get_notes(self) -> List[NoteNode]:
        return [n for n in [self.soprano, self.alto, self.tenor, self.bass] if n is not None]

    def is_complete(self) -> bool:
        return len(self.get_notes()) == 4

    def get_max_ticks(self) -> int:
        notes = self.get_notes()
        return max([n.tick_length for n in notes]) if notes else 0


class PlaybackEngine:
    def __init__(self, sf2_path: str = "FluidR3_GM.sf2"):
        self.use_fluidsynth = False
        self.fs = None
        self.sfid = None
        self.winmm = None
        self.midi_out = None

        try:
            import fluidsynth
            self.fs = fluidsynth.Synth()
            self.fs.start(driver="dsound")
            self.sfid = self.fs.sfload(sf2_path)
            if self.sfid is None or self.sfid < 0:
                raise RuntimeError("Failed to load SoundFont")
            self.use_fluidsynth = True
        except Exception:
            self.fs = None
            self.sfid = None
            self.use_fluidsynth = False
            try:
                winmm = ctypes.windll.winmm
                midi_out = ctypes.c_void_p()
                winmm.midiOutOpen(ctypes.byref(midi_out), -1, 0, 0, 0)
                self.winmm = winmm
                self.midi_out = midi_out
            except Exception:
                self.winmm = None
                self.midi_out = None

        for channel in range(4):
            self.set_instrument(channel, 60)
            self.set_volume(channel, 100)

    def set_instrument(self, channel: int, patch_id: int):
        if self.use_fluidsynth:
            self.fs.program_select(channel, self.sfid, 0, patch_id)
        elif self.winmm:
            self.winmm.midiOutShortMsg(self.midi_out, 0xC0 | channel | (patch_id << 8))

    def set_volume(self, channel: int, volume: int):
        if self.use_fluidsynth:
            self.fs.cc(channel, 7, volume)
        elif self.winmm:
            self.winmm.midiOutShortMsg(self.midi_out, 0xB0 | channel | (7 << 8) | (volume << 16))

    def play_note(self, pitch: int, ticks: int, bpm: int = 120, channel: int = 0) -> None:
        def sound():
            dur = (ticks / 480.0) * (60.0 / bpm)
            if self.use_fluidsynth:
                self.fs.noteon(channel, pitch, 100)
                time.sleep(dur)
                self.fs.noteoff(channel, pitch)
            elif self.winmm:
                self.winmm.midiOutShortMsg(self.midi_out, 0x90 | channel | (pitch << 8) | (100 << 16))
                time.sleep(dur)
                self.winmm.midiOutShortMsg(self.midi_out, 0x80 | channel | (pitch << 8) | (0 << 16))
        threading.Thread(target=sound, daemon=True).start()

    def play_timeline(self, notes_db: List[Dict], bpm: int = 120) -> None:
        if not notes_db:
            return
        events = []

        for n in notes_db:
            start_sec = (n['time_ticks'] / 480.0) * (60.0 / bpm)
            dur_sec = (n['ticks'] / 480.0) * (60.0 / bpm)

            if not n.get('is_tied_target', False):
                events.append({'time': start_sec, 'type': 'on',
                               'pitch': n['pitch'], 'ch': n['channel']})

            if not n.get('tied_to_next', False):
                events.append({'time': start_sec + dur_sec, 'type': 'off',
                               'pitch': n['pitch'], 'ch': n['channel']})

        events.sort(key=lambda e: e['time'])

        def run_sequencer():
            current_time = 0.0
            for e in events:
                delta = e['time'] - current_time
                if delta > 0:
                    time.sleep(delta)
                current_time = e['time']

                if e['type'] == "on":
                    if self.use_fluidsynth:
                        self.fs.noteon(e['ch'], e['pitch'], 100)
                    elif self.winmm:
                        self.winmm.midiOutShortMsg(
                            self.midi_out, 0x90 | e['ch'] | (e['pitch'] << 8) | (100 << 16))
                else:
                    if self.use_fluidsynth:
                        self.fs.noteoff(e['ch'], e['pitch'])
                    elif self.winmm:
                        self.winmm.midiOutShortMsg(
                            self.midi_out, 0x80 | e['ch'] | (e['pitch'] << 8) | (0 << 16))

        threading.Thread(target=run_sequencer, daemon=True).start()