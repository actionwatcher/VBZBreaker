"""Drill and sequence generation utilities for VBZBreaker.

This module provides small helpers to build the pair sequences and context
lines used by the various drill modes, and the DrillSpec dataclass which
encapsulates per-session parameters.
"""
from dataclasses import dataclass
from typing import List, Tuple
import random


def build_pair_sequences(pair: Tuple[str, str], lines: int = 6) -> List[str]:
    """Construct a list of A/B pattern lines for contrast/overspeed drills.

    Args:
        pair: Tuple of two characters (A, B).
        lines: Number of returned lines (max 6 in the template).

    Returns:
        A list of strings, each containing A/B patterns and spacing.
    """
    a, b = pair[0].upper(), pair[1].upper()
    base = [
        f"{a}{b}{a}{b}{a}  {b}{a}{a}{b}  {a}{b}{b}{b}{a}",
        f"{b}{a}{b}{a}{b}  {a}{b}{b}{a}  {b}{b}{a}{a}{b}",
        f"{a*4}  {b*4}  {a}{b}{a}{b}{a}{b}",
        f"{a}{a}{b}{b}  {b}{a}{a}{b}  {a}{b}{b}{a}{a}",
        f"{b}{b}{a}{a}  {a}{b}{a}{a}{b}  {b}{a}{b}{b}{a}",
        f"{a}{b}{a}{a}{b}  {b}{a}{b}{a}{a}  {a}{a}{b}{b}{a}",
    ]
    return base[:lines]


def build_context_lines(pair: Tuple[str, str], lines: int = 6) -> List[str]:
    """Generate synthetic call-like context lines that include the A/B pair.

    The lines are noisy, with random tokens and numeric inserts, to simulate
    realistic 'call' patterns for the context drill mode.
    """
    a, b = pair[0].upper(), pair[1].upper()
    tokens = []
    for _ in range(lines*3):
        left = random.choice(["W", "K", "N", "AA", "AB", "NU", "DL", "F", "I"])
        mid = ''.join(random.choices("0123456789", k=random.choice([1,2,3])))
        right = ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=random.choice([2,3])))
        s = f"{left}{mid}{right}"
        insert_at = random.randint(0, len(s))
        s = s[:insert_at] + a + s[insert_at:]
        insert_at = random.randint(0, len(s))
        s = s[:insert_at] + b + s[insert_at:]
        tokens.append(s)
    lines_out = []
    for i in range(0, len(tokens), 3):
        lines_out.append('  '.join(tokens[i:i+3]))
    return lines_out[:lines]


@dataclass
class DrillSpec:
    """Specification of a drill session.

    Fields are intentionally similar to the original code to keep the UI
    mapping trivial.
    """
    mode: str                      # 'reanchor' | 'contrast' | 'context' | 'overspeed'
    pair: Tuple[str, str]
    wpm: float
    tone_hz: float
    jitter_pct: float = 0.0
    wpm_jitter: float = 0.0
    tone_jitter_hz: float = 0.0
    stereo: bool = False
    pan_strength: float = 1.0
    low_wpm: float = 12.0
    high_wpm: float = 36.0
    block_seconds: float = 12.0
    overspeed_wpm: float = 30.0
