"""engine.py — MIDI playback engine with cross-platform FluidSynth
initialisation.

The SoundFont playback path uses FluidSynth. On Windows the
appropriate driver is `dsound`; on macOS it is `coreaudio`; on Linux
the modern default is `pipewire`, with `pulseaudio` and `alsa` as
fallbacks for older or minimal systems.

If FluidSynth is not available or fails to start, the engine falls
back to the platform's built-in MIDI output (Windows winmm, or, on
Linux and macOS, no-op since there is no equivalent built-in).
"""

import ctypes
import platform
import threading
import time
from dataclasses import dataclass
from typing import List, Dict, Optional


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
        return [n for n in [self.soprano, self.alto, self.tenor, self.bass]
                if n is not None]

    def is_complete(self) -> bool:
        return len(self.get_notes()) == 4

    def get_max_ticks(self) -> int:
        notes = self.get_notes()
        return max([n.tick_length for n in notes]) if notes else 0


def _try_start_fluidsynth(sf2_path):
    """Attempt to start FluidSynth with an appropriate driver for
    this platform. Return (fs, sfid) on success, or (None, None) if
    FluidSynth is unavailable or every driver attempt fails.

    On success, prints a one-line diagnostic so that silent playback
    can be told apart from startup failures.
    """
    try:
        import fluidsynth
    except ImportError:
        print("[audio] pyfluidsynth not installed; using system MIDI fallback")
        return None, None

    system = platform.system()
    if system == "Windows":
        drivers = ["dsound"]
    elif system == "Darwin":
        drivers = ["coreaudio"]
    else:
        # Linux: try PipeWire first (Fedora 34+, Ubuntu 22.10+),
        # then PulseAudio (older systems), then ALSA (bare metal).
        drivers = ["pipewire", "pulseaudio", "alsa"]

    last_error = None
    fs = None
    for driver in drivers:
        try:
            fs = fluidsynth.Synth()
            fs.start(driver=driver)
            print(f"[audio] FluidSynth started with driver '{driver}'")
            break
        except Exception as e:
            last_error = e
            fs = None
            continue

    if fs is None:
        print(f"[audio] FluidSynth start failed on all drivers; "
              f"last error: {last_error}")
        return None, None

    try:
        sfid = fs.sfload(sf2_path)
    except Exception as e:
        print(f"[audio] SoundFont load raised: {e}")
        try:
            fs.delete()
        except Exception:
            pass
        return None, None

    if sfid is None or sfid < 0:
        print(f"[audio] SoundFont failed to load: {sf2_path}")
        try:
            fs.delete()
        except Exception:
            pass
        return None, None

    print(f"[audio] SoundFont loaded: {sf2_path}")
    return fs, sfid


class PlaybackEngine:
    def __init__(self, sf2_path: str = "FluidR3_GM.sf2"):
        self.use_fluidsynth = False
        self.fs = None
        self.sfid = None
        self.winmm = None
        self.midi_out = None

        fs, sfid = _try_start_fluidsynth(sf2_path)
        if fs is not None:
            self.fs = fs
            self.sfid = sfid
            self.use_fluidsynth = True
        else:
            # Windows fallback: winmm built-in MIDI.
            if platform.system() == "Windows":
                try:
                    winmm = ctypes.windll.winmm
                    midi_out = ctypes.c_void_p()
                    winmm.midiOutOpen(ctypes.byref(midi_out), -1, 0, 0, 0)
                    self.winmm = winmm
                    self.midi_out = midi_out
                    print("[audio] Falling back to Windows winmm MIDI")
                except Exception:
                    self.winmm = None
                    self.midi_out = None
                    print("[audio] No audio output available")
            else:
                print("[audio] No audio output available")

        # Initialise the four channels regardless of which backend
        # is active. If FluidSynth is not running these are no-ops.
        for channel in range(4):
            self.set_instrument(channel, 60)
            self.set_volume(channel, 100)

    def set_instrument(self, channel: int, patch_id: int):
        if self.use_fluidsynth:
            self.fs.program_select(channel, self.sfid, 0, patch_id)
        elif self.winmm:
            self.winmm.midiOutShortMsg(
                self.midi_out, 0xC0 | channel | (patch_id << 8))

    def set_volume(self, channel: int, volume: int):
        if self.use_fluidsynth:
            self.fs.cc(channel, 7, volume)
        elif self.winmm:
            self.winmm.midiOutShortMsg(
                self.midi_out, 0xB0 | channel | (7 << 8) | (volume << 16))

    def play_note(self, pitch: int, ticks: int, bpm: int = 120,
                  channel: int = 0) -> None:
        def sound():
            dur = (ticks / 480.0) * (60.0 / bpm)
            if self.use_fluidsynth:
                self.fs.noteon(channel, pitch, 100)
                time.sleep(dur)
                self.fs.noteoff(channel, pitch)
            elif self.winmm:
                self.winmm.midiOutShortMsg(
                    self.midi_out,
                    0x90 | channel | (pitch << 8) | (100 << 16))
                time.sleep(dur)
                self.winmm.midiOutShortMsg(
                    self.midi_out,
                    0x80 | channel | (pitch << 8) | (0 << 16))
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
                            self.midi_out,
                            0x90 | e['ch'] | (e['pitch'] << 8) | (100 << 16))
                else:
                    if self.use_fluidsynth:
                        self.fs.noteoff(e['ch'], e['pitch'])
                    elif self.winmm:
                        self.winmm.midiOutShortMsg(
                            self.midi_out,
                            0x80 | e['ch'] | (e['pitch'] << 8) | (0 << 16))

        threading.Thread(target=run_sequencer, daemon=True).start()