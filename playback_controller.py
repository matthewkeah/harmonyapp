"""playback_controller.py — Threaded MIDI playback with pause, seek,
and tick reporting.

The controller plays the notes on a background thread and reports its
current position via an `on_tick` callback. The app uses that callback
to drive a playhead indicator.

    pause()  freezes the internal clock. Sounding notes are silenced.
    resume() unfreezes.
    seek()   jumps to a specific tick. If playing, restarts from there.
    stop()   ends the thread and silences everything.

The controller never touches the UI directly. It only emits ticks and
finish events, both of which the app marshals onto the main thread.
"""

import threading
import time


TICKS_PER_QUARTER = 480


class PlaybackController:
    def __init__(self, engine, tempo=120):
        self.engine = engine
        self.tempo = tempo
        self.notes_db = []

        self._thread = None
        self._stop_flag = False
        self._paused = False
        self._paused_at = 0.0
        self._paused_total = 0.0
        self._current_tick = 0
        self._active_notes = set()
        self._lock = threading.Lock()

        # Callbacks. Set these before calling play().
        self.on_tick = None     # fn(tick)
        self.on_finish = None   # fn()

    # -----------------------------------------------------------
    # Public properties and API
    # -----------------------------------------------------------
    @property
    def current_tick(self):
        with self._lock:
            return self._current_tick

    @property
    def is_playing(self):
        return (self._thread is not None
                and self._thread.is_alive()
                and not self._paused)

    @property
    def is_paused(self):
        return self._paused and self.is_active

    @property
    def is_active(self):
        return self._thread is not None and self._thread.is_alive()

    def set_tempo(self, tempo):
        self.tempo = tempo

    def set_notes(self, notes_db):
        self.notes_db = list(notes_db)

    def play(self, notes_db=None, from_tick=None):
        if notes_db is not None:
            self.notes_db = list(notes_db)
        if from_tick is None:
            from_tick = self.current_tick

        self.stop()
        self._stop_flag = False
        self._paused = False
        self._paused_total = 0.0
        with self._lock:
            self._current_tick = from_tick

        self._thread = threading.Thread(
            target=self._run, args=(from_tick,), daemon=True)
        self._thread.start()

    def pause(self):
        if not self.is_active or self._paused:
            return
        self._paused = True
        self._paused_at = time.time()
        self._silence_active_notes()

    def resume(self):
        if not self._paused:
            return
        self._paused_total += time.time() - self._paused_at
        self._paused = False

    def stop(self):
        self._stop_flag = True
        self._paused = False
        t = self._thread
        if t is not None:
            t.join(timeout=1.0)
        self._thread = None
        self._silence_active_notes()

    def seek(self, tick):
        tick = max(0, int(tick))
        if self.is_active:
            self.play(from_tick=tick)
        else:
            with self._lock:
                self._current_tick = tick
            self._fire_tick()

    # -----------------------------------------------------------
    # Internals
    # -----------------------------------------------------------
    def _seconds_per_tick(self):
        return (60.0 / max(1, self.tempo)) / TICKS_PER_QUARTER

    def _fire_tick(self):
        if self.on_tick is not None:
            try:
                self.on_tick(self.current_tick)
            except Exception:
                pass

    def _silence_active_notes(self):
        for (ch, pitch) in list(self._active_notes):
            try:
                if self.engine.use_fluidsynth:
                    self.engine.fs.noteoff(ch, pitch)
                elif self.engine.winmm:
                    self.engine.winmm.midiOutShortMsg(
                        self.engine.midi_out,
                        0x80 | ch | (pitch << 8) | (0 << 16))
            except Exception:
                pass
        self._active_notes.clear()

    def _build_events(self, from_tick):
        sps = self._seconds_per_tick()
        events = []
        for n in self.notes_db:
            n_end = n['time_ticks'] + n['ticks']
            if n_end <= from_tick:
                continue

            offset_sec = (n['time_ticks'] - from_tick) * sps
            dur_sec = n['ticks'] * sps
            if offset_sec < 0:
                offset_sec = 0.0
                dur_sec = (n_end - from_tick) * sps

            ch = n.get('channel', n.get('voice', 0))

            if not n.get('is_tied_target', False):
                events.append({'time_sec': offset_sec, 'type': 'on',
                               'pitch': n['pitch'], 'ch': ch})
            if not n.get('tied_to_next', False):
                events.append({'time_sec': offset_sec + dur_sec, 'type': 'off',
                               'pitch': n['pitch'], 'ch': ch})

        events.sort(key=lambda e: (e['time_sec'], 0 if e['type'] == 'on' else 1))
        return events

    def _emit(self, e):
        try:
            if e['type'] == 'on':
                if self.engine.use_fluidsynth:
                    self.engine.fs.noteon(e['ch'], e['pitch'], 100)
                elif self.engine.winmm:
                    self.engine.winmm.midiOutShortMsg(
                        self.engine.midi_out,
                        0x90 | e['ch'] | (e['pitch'] << 8) | (100 << 16))
                self._active_notes.add((e['ch'], e['pitch']))
            else:
                if self.engine.use_fluidsynth:
                    self.engine.fs.noteoff(e['ch'], e['pitch'])
                elif self.engine.winmm:
                    self.engine.winmm.midiOutShortMsg(
                        self.engine.midi_out,
                        0x80 | e['ch'] | (e['pitch'] << 8) | (0 << 16))
                self._active_notes.discard((e['ch'], e['pitch']))
        except Exception:
            pass

    def _run(self, from_tick):
        sps = self._seconds_per_tick()
        events = self._build_events(from_tick)

        start_wall = time.time()
        self._paused_total = 0.0

        for e in events:
            if self._stop_flag:
                return

            # Poll until the event's scheduled wall time is reached,
            # so pause/stop take effect within ~20ms.
            while True:
                if self._stop_flag:
                    return
                if self._paused:
                    time.sleep(0.02)
                    continue

                elapsed = time.time() - start_wall - self._paused_total
                wait = e['time_sec'] - elapsed
                if wait <= 0:
                    break

                time.sleep(min(wait, 0.02))

                elapsed = time.time() - start_wall - self._paused_total
                tick_now = from_tick + int(elapsed / sps)
                with self._lock:
                    self._current_tick = tick_now
                self._fire_tick()

            if self._stop_flag:
                return

            self._emit(e)

            tick_now = from_tick + int(e['time_sec'] / sps)
            with self._lock:
                self._current_tick = tick_now
            self._fire_tick()

        if not self._stop_flag and self.on_finish is not None:
            try:
                self.on_finish()
            except Exception:
                pass