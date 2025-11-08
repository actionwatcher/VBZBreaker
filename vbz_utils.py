"""Utility functions and constants for VBZBreaker.

This module holds shared constants (MORSE_MAP, defaults) and small helpers
used across the package: timing math, envelope generation, normalization and
levenshtein distance computation.
"""
from typing import Dict
import re
import numpy as np

# Morse mapping for A-Z and 0-9
MORSE_MAP: Dict[str, str] = {
    'A': '.-',    'B': '-...',  'C': '-.-.', 'D': '-..',  'E': '.',
    'F': '..-.',  'G': '--.',   'H': '....', 'I': '..',   'J': '.---',
    'K': '-.-',   'L': '.-..',  'M': '--',   'N': '-.',   'O': '---',
    'P': '.--.',  'Q': '--.-',  'R': '.-.',  'S': '...',  'T': '-',
    'U': '..-',   'V': '...-',  'W': '.--',  'X': '-..-', 'Y': '-.--',
    'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---','3': '...--','4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..','9': '----.'
}

# Default audio/speed constants
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_TONE_HZ = 650.0
DEFAULT_WPM = 25.0


def dit_seconds(wpm: float) -> float:
    """Convert words-per-minute (WPM) to the duration of a 'dit' in seconds.

    Args:
        wpm: Words per minute (must be > 0).

    Returns:
        Duration in seconds for a single dit element.
    """
    return 1.2 / max(1, wpm)


def env_ramp(samples: int) -> 'np.ndarray':
    """Generate a cosine-shaped envelope ramp of length ``samples``.

    The ramp is useful to apply short fade-in/fade-out on tones to avoid clicks.

    Args:
        samples: Number of ramp samples (int).

    Returns:
        A numpy float32 array containing the ramp from ~0 to 1.
    """
    t = np.arange(samples, dtype=np.float32)
    ramp = 0.5 * (1 - np.cos(np.pi * (t + 1) / (samples + 1)))
    return ramp.astype(np.float32)


def norm_text(s: str) -> str:
    """Normalize text for scoring: uppercase and strip everything except A-Z0-9.

    Args:
        s: Input string.

    Returns:
        Normalized string suitable for comparison/scoring.
    """
    return re.sub(r'[^A-Z0-9]', '', s.upper())


def levenshtein(a: str, b: str) -> int:
    """Compute the Levenshtein (edit) distance between two strings.

    This is a memory-efficient dynamic programming implementation.

    Args:
        a: First string.
        b: Second string.

    Returns:
        The integer Levenshtein distance.
    """
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(prev[j] + 1,      # deletion
                           cur[j-1] + 1,     # insertion
                           prev[j-1] + cost  # substitution
                           ))
        prev = cur
    return prev[-1]
