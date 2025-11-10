"""Session and audio thread management for VBZBreaker.

This module runs the SessionRunner which orchestrates the drill flow and
an AudioThread consumer that writes numpy stereo frames to sounddevice.
"""
import threading
import os
import csv
import queue
import time
from typing import Optional, List

try:
    import numpy as np
    import sounddevice as sd
except (ImportError, ModuleNotFoundError):
    np = None
    sd = None

from vbz_synth import MorseSynth, SynthConfig
from vbz_drill import DrillSpec
from vbz_utils import DEFAULT_SAMPLE_RATE

# Audio processing constants
AUDIO_CHUNK_SIZE = 4096
AUDIO_QUEUE_MAX_SIZE = 8
QUEUE_PUT_TIMEOUT = 0.5

# Drill timing constants (in seconds)
DRILL_DURATION_SECONDS = 120  # 2 minutes
RAMP_DURATION_SECONDS = 0.005


class AudioThread(threading.Thread):
    """Background thread that pulls frames from a queue and writes them.

    The thread exits gracefully on receipt of None or when stop_flag is set.
    """
    def __init__(self, q_frames: queue.Queue, stop_flag: threading.Event):
        super().__init__(daemon=True)
        self.q_frames = q_frames
        self.stop_flag = stop_flag

    def run(self):
        """Continuously read frames and write to sound device output stream."""
        if sd is None or np is None:
            return
        try:
            with sd.OutputStream(channels=2, dtype='float32', samplerate=DEFAULT_SAMPLE_RATE) as stream:
                while not self.stop_flag.is_set():
                    try:
                        frame = self.q_frames.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if frame is None:
                        break
                    stream.write(frame)
        except Exception as e:
            print("Audio error:", e)


class SessionRunner(threading.Thread):
    """Drive a drill session: generate audio and log events.

    Responsibilities:
      - Create a synth for each block
      - Push audio chunks into a bounded queue for playback
      - Log events to CSV
    """
    def __init__(self, spec: DrillSpec, log_path: str, update_ui_cb):
        super().__init__(daemon=True)
        self.spec = spec
        self.log_path = log_path
        self.update_ui_cb = update_ui_cb
        self.stop_flag = threading.Event()
        self.q_frames: 'queue.Queue' = queue.Queue(maxsize=AUDIO_QUEUE_MAX_SIZE)
        self.sent_lines: List[str] = []  # ground-truth lines for Context/Overspeed
        self._sent_lines_lock = threading.Lock()  # Protect sent_lines from concurrent access

    def stop(self):
        """Signal the runner to stop and attempt to unblock the audio thread."""
        self.stop_flag.set()
        try:
            self.q_frames.put(None, timeout=0.1)
        except queue.Full:
            pass  # Queue is full, thread will exit via stop_flag

    def _make_synth(self, wpm=None, tone=None, stereo=None) -> MorseSynth:
        """Build a MorseSynth configured for a block of audio.

        Optional overrides for wpm/tone/stereo are accepted.
        """
        wpm_eff = self.spec.wpm if wpm is None else wpm
        tone_eff = self.spec.tone_hz if tone is None else tone
        allow_stereo = (self.spec.mode in ("reanchor", "contrast"))
        want_stereo = (stereo if stereo is not None else self.spec.stereo)
        stereo_pair = self.spec.pair if (allow_stereo and want_stereo) else None
        cfg = SynthConfig(
            sample_rate=DEFAULT_SAMPLE_RATE,
            tone_hz=tone_eff,
            wpm=wpm_eff,
            jitter_pct=self.spec.jitter_pct,
            stereo_pair=stereo_pair,
            pan_strength=self.spec.pan_strength,
            tone_jitter_hz=self.spec.tone_jitter_hz,
            wpm_jitter=self.spec.wpm_jitter,
            gain=0.25
        )
        return MorseSynth(cfg)

    def _enqueue_audio(self, audio):
        """Break audio into chunks and enqueue them for playback.

        This method handles queue.Full by retrying with a short timeout so
        the function remains responsive to stop requests.
        """
        for i in range(0, len(audio), AUDIO_CHUNK_SIZE):
            if self.stop_flag.is_set():
                return
            placed = False
            while not placed:
                if self.stop_flag.is_set():
                    return
                try:
                    # small timeout to remain interruptible
                    self.q_frames.put(audio[i:i+AUDIO_CHUNK_SIZE], timeout=QUEUE_PUT_TIMEOUT)
                    placed = True
                except queue.Full:
                    continue

    def run(self):
        """Main thread run: open log file, start audio thread and run the selected mode."""
        if np is None:
            self.update_ui_cb("NumPy is not available. Install numpy to run audio.")
            return
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "mode", "pair", "event", "info"])

            audio_thr = AudioThread(self.q_frames, self.stop_flag)
            audio_thr.start()

            mode = self.spec.mode
            completed_naturally = False
            if mode == 'reanchor':
                completed_naturally = self._run_reanchor(writer)
            elif mode == 'contrast':
                completed_naturally = self._run_contrast(writer)
            elif mode == 'context':
                completed_naturally = self._run_context(writer)
            elif mode == 'overspeed':
                completed_naturally = self._run_overspeed(writer)
            else:
                self.update_ui_cb("Unknown mode")

            try:
                self.q_frames.put(None, timeout=0.5)
            except queue.Full:
                pass  # Audio thread will exit naturally

            # Notify completion if the drill ended naturally (not stopped by user)
            if completed_naturally and not self.stop_flag.is_set():
                self.update_ui_cb("SESSION_COMPLETE")

    # ---- Drill runners are thin wrappers delegated to synth/drill ----
    def _run_reanchor(self, writer):
        """Run the re-anchor drill loop, alternating slow/fast blocks.

        The method logs block events and pushes synthesized audio into the queue.

        Returns:
            True if completed naturally, False if stopped early.
        """
        from vbz_drill import build_pair_sequences
        a, b = self.spec.pair[0].upper(), self.spec.pair[1].upper()
        pattern = f"{a}{b}" * 8
        t_end = time.time() + DRILL_DURATION_SECONDS
        self.update_ui_cb("Re-anchor mode:\nListen (or send) alternating A/B at slow↔fast speeds. Focus on FEEL of rhythm (no copying).")
        while not self.stop_flag.is_set() and time.time() < t_end:
            writer.writerow([time.time(), self.spec.mode, a+b, "block", f"{self.spec.low_wpm}wpm"])
            syn = self._make_synth(wpm=self.spec.low_wpm)
            self._enqueue_audio(syn.string_audio(pattern))
            if self.stop_flag.is_set():
                return False
            writer.writerow([time.time(), self.spec.mode, a+b, "block", f"{self.spec.high_wpm}wpm"])
            syn = self._make_synth(wpm=self.spec.high_wpm)
            self._enqueue_audio(syn.string_audio(pattern))
        return time.time() >= t_end  # True if we completed the full duration

    def _run_contrast(self, writer):
        """Run the contrast drill: play short dense A/B lines for copying.

        Returns:
            True if completed naturally, False if stopped early.
        """
        from vbz_drill import build_pair_sequences
        a, b = self.spec.pair[0].upper(), self.spec.pair[1].upper()
        lines = build_pair_sequences((a, b), lines=6)
        syn = self._make_synth()
        self.update_ui_cb("Contrast mode:\nCopy short, dense A/B lines at normal speed. Accuracy matters. Stop if you need to replay.")
        # Repeat lines 4 times without creating copies in memory
        for _ in range(4):
            for line in lines:
                if self.stop_flag.is_set():
                    return False
                writer.writerow([time.time(), self.spec.mode, a+b, "line", line])
                self._enqueue_audio(syn.string_audio(line))
                self._enqueue_audio(syn.string_audio("   "))
            if self.stop_flag.is_set():
                return False
        return True  # Completed all lines

    def _run_context(self, writer):
        """Run the context drill: play call-like context lines and record ground truth.

        Returns:
            True if completed naturally, False if stopped early.
        """
        from vbz_drill import build_context_lines
        a, b = self.spec.pair[0].upper(), self.spec.pair[1].upper()
        lines = build_context_lines((a, b), lines=6)
        syn = self._make_synth(stereo=False)
        self.update_ui_cb("Context mode:\nCopy what you hear into the input box below (no punctuation). Compare will run on Stop.")
        # Repeat lines 4 times without creating copies in memory
        for _ in range(4):
            for line in lines:
                if self.stop_flag.is_set():
                    return False
                with self._sent_lines_lock:
                    self.sent_lines.append(line)
                writer.writerow([time.time(), self.spec.mode, a+b, "ctx", line])
                self._enqueue_audio(syn.string_audio(line))
                self._enqueue_audio(syn.string_audio("   "))
            if self.stop_flag.is_set():
                return False
        return True  # Completed all lines

    def _run_overspeed(self, writer):
        """Run the overspeed drill: continuous short, high-WPM bursts.

        Returns:
            True if completed naturally, False if stopped early.
        """
        from vbz_drill import build_pair_sequences
        a, b = self.spec.pair[0].upper(), self.spec.pair[1].upper()
        syn = self._make_synth(wpm=self.spec.overspeed_wpm, stereo=False)
        pattern_lines = build_pair_sequences((a, b), lines=6)
        t_end = time.time() + DRILL_DURATION_SECONDS
        self.update_ui_cb("Overspeed mode:\nShort high-WPM burst. Copy into the input box below; scoring runs on Stop.")
        i = 0
        while not self.stop_flag.is_set() and time.time() < t_end:
            line = pattern_lines[i % len(pattern_lines)]
            with self._sent_lines_lock:
                self.sent_lines.append(line)
            writer.writerow([time.time(), self.spec.mode, a+b, "overspeed_line", line])
            self._enqueue_audio(syn.string_audio(line))
            self._enqueue_audio(syn.string_audio("   "))
            i += 1
        return time.time() >= t_end  # True if we completed the full duration
