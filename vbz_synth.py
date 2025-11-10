"""Morse synthesizer module.

Contains the SynthConfig dataclass and MorseSynth which generates stereo
numpy audio buffers for symbols and strings of text.
"""
from dataclasses import dataclass
from typing import List, Tuple, Optional
import random
import numpy as np
from vbz_utils import DEFAULT_SAMPLE_RATE, DEFAULT_TONE_HZ, DEFAULT_WPM, MORSE_MAP, dit_seconds, env_ramp

# Audio envelope constants
RAMP_DURATION_SECONDS = 0.005


@dataclass
class SynthConfig:
    """Configuration for the synthesizer.

    Attributes mirror the original script's parameters and are intentionally
    small and explicit to make testing easier.
    """
    sample_rate: int = DEFAULT_SAMPLE_RATE
    tone_hz: float = DEFAULT_TONE_HZ
    wpm: float = DEFAULT_WPM
    jitter_pct: float = 0.0
    stereo_pair: Optional[Tuple[str, str]] = None
    pan_strength: float = 1.0
    tone_jitter_hz: float = 0.0
    wpm_jitter: float = 0.0
    gain: float = 0.25


class MorseSynth:
    """Generate Morse code audio buffers according to a SynthConfig.

    Public methods:
      - symbol_audio(symbol): return stereo buffer for a single character
      - string_audio(text): return stereo buffer for a full text string
    """
    def __init__(self, cfg: SynthConfig):
        """Store configuration object.

        Args:
            cfg: SynthConfig instance.
        """
        self.cfg = cfg

    def _jitter(self, base: float) -> float:
        """Apply jitter percentage to a base duration.

        If jitter_pct is zero, return the base unchanged. Ensures non-negative
        durations.
        """
        j = self.cfg.jitter_pct
        if j <= 0.0:
            return base
        delta = base * j
        return max(0.0, base + random.uniform(-delta, delta))

    def _symbol_to_units(self, symbol: str) -> List[Tuple[str, float]]:
        """Convert a symbol to a sequence of ('tone'|'sil', seconds) tuples.

        Args:
            symbol: Single character (A-Z, 0-9).

        Returns:
            A list of tuples denoting tone or silence durations.
        """
        wpm = self.cfg.wpm
        d = dit_seconds(wpm)
        dah = 3 * d
        intra = d
        parts: List[Tuple[str, float]] = []
        code = MORSE_MAP.get(symbol.upper(), '')
        for i, ch in enumerate(code):
            dur = d if ch == '.' else dah
            dur = self._jitter(dur)
            parts.append(('tone', dur))
            if i != len(code) - 1:
                parts.append(('sil', self._jitter(intra)))
        return parts

    def _char_gap(self) -> float:
        """Return jittered gap between characters (3 dits)."""
        return self._jitter(3 * dit_seconds(self.cfg.wpm))

    def _word_gap(self) -> float:
        """Return jittered gap between words (7 dits)."""
        return self._jitter(7 * dit_seconds(self.cfg.wpm))

    def _tone(self, seconds: float, freq: float, pan: Tuple[float, float]) -> 'np.ndarray':
        """Synthesize a stereo tone for given duration, frequency and pan.

        Args:
            seconds: duration in seconds
            freq: frequency in Hz
            pan: (left, right) multipliers

        Returns:
            A numpy array shape (n_samples, 2) float32 in [-1,1] scaled by gain.
        """
        sr = self.cfg.sample_rate
        n = max(1, int(seconds * sr))
        t = np.arange(n, dtype=np.float32) / sr
        sig = np.sin(2 * np.pi * freq * t).astype(np.float32)

        ramp_samps = max(1, int(RAMP_DURATION_SECONDS * sr))
        ramp = env_ramp(ramp_samps)
        sig[:ramp_samps] *= ramp
        sig[-ramp_samps:] *= ramp[::-1]

        left = (sig * pan[0]).reshape(-1, 1)
        right = (sig * pan[1]).reshape(-1, 1)
        stereo = np.concatenate([left, right], axis=1)
        return stereo * self.cfg.gain

    def _silence(self, seconds: float) -> 'np.ndarray':
        """Return a stereo silence buffer for ``seconds`` seconds."""
        sr = self.cfg.sample_rate
        n = max(1, int(seconds * sr))
        return np.zeros((n, 2), dtype=np.float32)

    def _pan_for_symbol(self, symbol: str) -> Tuple[float, float]:
        """Return left/right multipliers depending on stereo_pair and pan strength."""
        sp = self.cfg.stereo_pair
        if sp and symbol.upper() in sp:
            a, b = sp[0].upper(), sp[1].upper()
            s = min(1.0, max(0.0, self.cfg.pan_strength))
            if symbol.upper() == a:
                return (1.0, 1.0 - s)
            else:
                return (1.0 - s, 1.0)
        return (1.0, 1.0)

    def symbol_audio(self, symbol: str) -> 'np.ndarray':
        """Build audio for a single symbol.

        Jitter and tone variation are applied per the SynthConfig.
        """
        base_freq = self.cfg.tone_hz
        if self.cfg.tone_jitter_hz > 0:
            base_freq += random.uniform(-self.cfg.tone_jitter_hz, self.cfg.tone_jitter_hz)
        parts = self._symbol_to_units(symbol)
        pan = self._pan_for_symbol(symbol)
        chunks = []
        for kind, sec in parts:
            chunks.append(self._tone(sec, base_freq, pan) if kind == 'tone' else self._silence(sec))
        return np.concatenate(chunks, axis=0) if chunks else self._silence(0.1)

    def string_audio(self, text: str) -> 'np.ndarray':
        """Convert a text string into a concatenated stereo audio buffer.

        Non-mapped characters are ignored; spaces produce word gaps.
        """
        chunks = []
        for i, ch in enumerate(text):
            if ch == ' ':
                chunks.append(self._silence(self._word_gap()))
                continue
            if ch.upper() not in MORSE_MAP:
                continue
            chunks.append(self.symbol_audio(ch))
            if i != len(text) - 1 and text[i+1] != ' ':
                chunks.append(self._silence(self._char_gap()))
        if not chunks:
            return self._silence(0.1)
        return np.concatenate(chunks, axis=0)
