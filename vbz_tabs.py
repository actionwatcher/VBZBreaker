"""Tab classes for VBZBreaker drill modes."""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, Protocol, runtime_checkable
from vbz_drill import DrillSpec
from vbz_utils import MORSE_MAP


# Standalone utility functions for validation
def validate_pair(pair_var: tk.StringVar) -> tuple[Optional[tuple], Optional[str]]:
    """Validate pair input. Returns ((a, b), None) or (None, error_message)."""
    pair_str = pair_var.get().replace(" ", "")
    if "," not in pair_str:
        return None, "Enter active pair as A,B (e.g., H,5)"

    parts = pair_str.split(",")
    if len(parts) != 2:
        return None, "Enter exactly two characters separated by comma"

    a, b = parts[0].strip().upper(), parts[1].strip().upper()
    if not a or not b:
        return None, "Both characters must be non-empty"

    if a not in MORSE_MAP:
        return None, f"Character '{a}' is not valid. Use A-Z or 0-9."
    if b not in MORSE_MAP:
        return None, f"Character '{b}' is not valid. Use A-Z or 0-9."

    return (a, b), None


def validate_tone(tone_var: tk.DoubleVar) -> Optional[str]:
    """Validate tone frequency. Returns error message or None if valid."""
    tone_hz = tone_var.get()
    if tone_hz < 100 or tone_hz > 2000:
        return "Tone frequency must be between 100 and 2000 Hz"
    return None


@runtime_checkable
class DrillTabProtocol(Protocol):
    """Protocol defining the interface for drill mode tabs.

    Tabs must implement this interface to work with the App.
    No inheritance required - tabs just need these methods/attributes.
    """
    mode_name: str

    def get_drill_spec(self) -> Optional[DrillSpec]: ...
    def on_session_start(self) -> None: ...
    def on_session_stop(self, sent_lines=None) -> Optional[str]: ...
    def validate_inputs(self) -> Optional[str]: ...
    def get_params(self) -> Dict[str, Any]: ...
    def set_params(self, params: Dict[str, Any]) -> None: ...


class ReanchorTab(ttk.Frame):
    """Re-anchor drill mode: Listening only, alternating slow/fast blocks."""

    def __init__(self, parent, start_callback, stop_callback, active_pair: tk.StringVar, swap_lr: tk.BooleanVar, sep_pct: tk.DoubleVar):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.mode_name = "reanchor"

        # Variables
        self.pair = active_pair
        self.swap_lr = swap_lr  # Shared across stereo tabs
        self.sep_pct = sep_pct  # Shared across stereo tabs
        self.tone = tk.DoubleVar(value=650.0)
        self.jitter = tk.DoubleVar(value=0.10)
        self.tone_jitter = tk.DoubleVar(value=0.0)
        self.low_wpm = tk.DoubleVar(value=14.0)
        self.high_wpm = tk.DoubleVar(value=32.0)
        self.timing_balance = tk.DoubleVar(value=1.0)  # 0=equal chars, 1=equal time

        self._build_ui()

    def _build_ui(self):
        # Instructions
        inst_frame = ttk.LabelFrame(self, text="Re-anchor Mode")
        inst_frame.pack(fill="x", padx=8, pady=8)
        ttk.Label(inst_frame, text="• Alternate slow↔fast A/B blocks\n"
                                   "• Focus on FEEL of rhythm; do NOT copy\n"
                                   "• Separation slider pans A left, B right\n"
                                   "• Jitter/variation helps de-normalize timing",
                  justify="left").pack(padx=8, pady=8, anchor="w")

        # Pair settings
        pair_frame = ttk.LabelFrame(self, text="Pair Settings")
        pair_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(pair_frame, text="Active pair (A,B):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(pair_frame, textvariable=self.pair, width=10).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        # Audio settings
        audio_frame = ttk.LabelFrame(self, text="Audio Settings")
        audio_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(audio_frame, text="Tone (Hz):").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=300, to=1000, increment=10, textvariable=self.tone, width=7).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(audio_frame, text="Jitter (±%):").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=0.3, increment=0.01, textvariable=self.jitter, width=6).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(audio_frame, text="Tone jitter (±Hz):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=300.0, increment=10.0, textvariable=self.tone_jitter, width=7).grid(row=0, column=5, padx=4, pady=4)

        # Stereo settings
        # stereo_frame = ttk.LabelFrame(self, text="Stereo Separation")
        # stereo_frame.pack(fill="x", padx=8, pady=4)

        sep__row = 1
        sep_len = 4
        ttk.Label(audio_frame, text="Separation:").grid(row=sep__row, column=0, sticky="e", padx=4, pady=4)
        sep = ttk.Scale(audio_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        ttk.Label(audio_frame, text="mono").grid(row=sep__row, column=1, sticky="w", padx=4)
        sep.grid(row=sep__row, column=2, padx=4, pady=4, columnspan=sep_len, sticky="ew")
        ttk.Label(audio_frame, text="fully split").grid(row=sep__row, column=sep_len+2, sticky="w", padx=4)
        ttk.Checkbutton(audio_frame, text="Swap L/R ears", variable=self.swap_lr).grid(row=sep__row, column=sep_len+3, sticky="w", padx=8)

        # Snap separation slider to 0.25 steps
        def snap_sep(*_):
            v = self.sep_pct.get()
            snapped = round(v / 0.25) * 0.25
            self.sep_pct.set(min(1.0, max(0.0, snapped)))
        self.sep_pct.trace_add("write", snap_sep)

        # Speed settings
        speed_frame = ttk.LabelFrame(self, text="Speed Settings")
        speed_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(speed_frame, text="Low WPM:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(speed_frame, from_=6, to=30, increment=1, textvariable=self.low_wpm, width=6).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(speed_frame, text="High WPM:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(speed_frame, from_=20, to=50, increment=1, textvariable=self.high_wpm, width=6).grid(row=0, column=3, padx=4, pady=4)

        # Timing balance control (right side of speed settings)
        ttk.Label(speed_frame, text="Timing Balance:").grid(row=0, column=4, sticky="e", padx=(16, 4), pady=4)

        timing_slider = ttk.Scale(speed_frame, from_=0.0, to=1.0, orient="horizontal",
                                   variable=self.timing_balance, length=200)
        timing_slider.grid(row=0, column=5, padx=4, pady=4, sticky="ew")
        speed_frame.columnconfigure(5, weight=1)

        # Add labels for the slider positions
        labels_frame = ttk.Frame(speed_frame)
        labels_frame.grid(row=1, column=5, sticky="ew", padx=4)

        ttk.Label(labels_frame, text="Equal Chars", font=('', 8)).pack(side="left")
        ttk.Label(labels_frame, text="Balanced", font=('', 8)).pack(side="left", expand=True)
        ttk.Label(labels_frame, text="Equal Time", font=('', 8)).pack(side="right")

        # Snap timing slider to 5 positions: 0.0, 0.25, 0.5, 0.75, 1.0
        def snap_timing(*_):
            v = self.timing_balance.get()
            # Snap to 5 positions: 0.0, 0.25, 0.5, 0.75, 1.0
            if v < 0.125:
                snapped = 0.0
            elif v < 0.375:
                snapped = 0.25
            elif v < 0.625:
                snapped = 0.5
            elif v < 0.875:
                snapped = 0.75
            else:
                snapped = 1.0
            self.timing_balance.set(snapped)
        self.timing_balance.trace_add("write", snap_timing)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Re-anchor", command=lambda: self.start_callback(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_callback, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # Status
        status_frame = ttk.LabelFrame(self, text="Status")
        status_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.status_label = ttk.Label(status_frame, text="Ready", anchor="w", justify="left")
        self.status_label.pack(fill="both", expand=True, padx=8, pady=8)

    def validate_inputs(self) -> Optional[str]:
        pair, err = validate_pair(self.pair)
        if err:
            return err

        err = validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        # Trust that validate_inputs() already validated the pair
        pair_str = self.pair.get().replace(" ", "")
        parts = pair_str.split(",")
        pair = (parts[0].strip().upper(), parts[1].strip().upper())

        return DrillSpec(
            mode="reanchor",
            pair=pair,
            wpm=self.low_wpm.get(),
            tone_hz=self.tone.get(),
            jitter_pct=self.jitter.get(),
            tone_jitter_hz=self.tone_jitter.get(),
            stereo=(self.sep_pct.get() > 0.0),
            pan_strength=self.sep_pct.get(),
            low_wpm=self.low_wpm.get(),
            high_wpm=self.high_wpm.get(),
            timing_balance=self.timing_balance.get(),
            swap_channels=self.swap_lr.get()
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Session running... Listen to alternating slow/fast blocks.")

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Session stopped.")

    def get_params(self) -> Dict[str, Any]:
        """Get current parameter values for persistence."""
        return {
            'tone': self.tone.get(),
            'jitter': self.jitter.get(),
            'tone_jitter': self.tone_jitter.get(),
            'low_wpm': self.low_wpm.get(),
            'high_wpm': self.high_wpm.get(),
            'timing_balance': self.timing_balance.get()
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        """Restore parameter values from saved config."""
        if 'tone' in params:
            self.tone.set(params['tone'])
        if 'jitter' in params:
            self.jitter.set(params['jitter'])
        if 'tone_jitter' in params:
            self.tone_jitter.set(params['tone_jitter'])
        if 'low_wpm' in params:
            self.low_wpm.set(params['low_wpm'])
        if 'high_wpm' in params:
            self.high_wpm.set(params['high_wpm'])
        if 'timing_balance' in params:
            self.timing_balance.set(params['timing_balance'])


class ContrastTab(ttk.Frame):
    """Contrast drill mode: Listening only, copy dense A/B lines."""

    def __init__(self, parent, start_callback, stop_callback, active_pair: tk.StringVar, swap_lr: tk.BooleanVar, sep_pct: tk.DoubleVar):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.mode_name = "contrast"

        # Variables
        self.pair = active_pair
        self.swap_lr = swap_lr  # Shared across stereo tabs
        self.sep_pct = sep_pct  # Shared across stereo tabs
        self.wpm = tk.DoubleVar(value=25.0)
        self.tone = tk.DoubleVar(value=650.0)
        self.jitter = tk.DoubleVar(value=0.10)
        self.wpm_jitter = tk.DoubleVar(value=0.0)
        self.tone_jitter = tk.DoubleVar(value=0.0)

        self._build_ui()

    def _build_ui(self):
        # Instructions
        inst_frame = ttk.LabelFrame(self, text="Contrast Mode")
        inst_frame.pack(fill="x", padx=8, pady=8)
        ttk.Label(inst_frame, text="• Copy dense A/B minimal-pair strings\n"
                                   "• Accuracy matters; copy on paper\n"
                                   "• Separation slider pans A left, B right\n"
                                   "• Stop and replay lines as needed",
                  justify="left").pack(padx=8, pady=8, anchor="w")

        # Pair settings
        pair_frame = ttk.LabelFrame(self, text="Pair Settings")
        pair_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(pair_frame, text="Active pair (A,B):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(pair_frame, textvariable=self.pair, width=10).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(pair_frame, text="WPM:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(pair_frame, from_=8, to=50, increment=1, textvariable=self.wpm, width=6).grid(row=0, column=3, padx=4, pady=4)

        # Audio settings
        audio_frame = ttk.LabelFrame(self, text="Audio Settings")
        audio_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(audio_frame, text="Tone (Hz):").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=300, to=1000, increment=10, textvariable=self.tone, width=7).grid(row=0, column=1, padx=4, pady=4)

        ttk.Label(audio_frame, text="Jitter (±%):").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=0.3, increment=0.01, textvariable=self.jitter, width=6).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(audio_frame, text="WPM jitter (±):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=5.0, increment=0.5, textvariable=self.wpm_jitter, width=6).grid(row=0, column=5, padx=4, pady=4)

        ttk.Label(audio_frame, text="Tone jitter (±Hz):").grid(row=0, column=6, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=300.0, increment=10.0, textvariable=self.tone_jitter, width=7).grid(row=0, column=7, padx=4, pady=4)

        # Stereo separation settings (row 1)
        sep_row = 1
        sep_len = 4
        ttk.Label(audio_frame, text="Separation:").grid(row=sep_row, column=0, sticky="e", padx=4, pady=4)
        sep = ttk.Scale(audio_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        ttk.Label(audio_frame, text="mono").grid(row=sep_row, column=1, sticky="w", padx=4)
        sep.grid(row=sep_row, column=2, padx=4, pady=4, columnspan=sep_len, sticky="ew")
        ttk.Label(audio_frame, text="fully split").grid(row=sep_row, column=sep_len+2, sticky="w", padx=4)
        ttk.Checkbutton(audio_frame, text="Swap L/R ears", variable=self.swap_lr).grid(row=sep_row, column=sep_len+3, sticky="w", padx=8)

        # Snap separation slider to 0.25 steps
        def snap_sep(*_):
            v = self.sep_pct.get()
            snapped = round(v / 0.25) * 0.25
            self.sep_pct.set(min(1.0, max(0.0, snapped)))
        self.sep_pct.trace_add("write", snap_sep)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Contrast", command=lambda: self.start_callback(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.stop_callback, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # Status
        status_frame = ttk.LabelFrame(self, text="Status")
        status_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.status_label = ttk.Label(status_frame, text="Ready", anchor="w", justify="left")
        self.status_label.pack(fill="both", expand=True, padx=8, pady=8)

    def validate_inputs(self) -> Optional[str]:
        pair, err = validate_pair(self.pair)
        if err:
            return err

        wpm = self.wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        # Trust that validate_inputs() already validated the pair
        pair_str = self.pair.get().replace(" ", "")
        parts = pair_str.split(",")
        pair = (parts[0].strip().upper(), parts[1].strip().upper())

        return DrillSpec(
            mode="contrast",
            pair=pair,
            wpm=self.wpm.get(),
            tone_hz=self.tone.get(),
            jitter_pct=self.jitter.get(),
            wpm_jitter=self.wpm_jitter.get(),
            tone_jitter_hz=self.tone_jitter.get(),
            stereo=(self.sep_pct.get() > 0.0),
            pan_strength=self.sep_pct.get(),
            swap_channels=self.swap_lr.get()
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Session running... Copy the dense A/B lines on paper.")

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Session stopped.")

    def get_params(self) -> Dict[str, Any]:
        """Get current parameter values for persistence."""
        return {
            'wpm': self.wpm.get(),
            'tone': self.tone.get(),
            'jitter': self.jitter.get(),
            'wpm_jitter': self.wpm_jitter.get(),
            'tone_jitter': self.tone_jitter.get()
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        """Restore parameter values from saved config."""
        if 'wpm' in params:
            self.wpm.set(params['wpm'])
        if 'tone' in params:
            self.tone.set(params['tone'])
        if 'jitter' in params:
            self.jitter.set(params['jitter'])
        if 'wpm_jitter' in params:
            self.wpm_jitter.set(params['wpm_jitter'])
        if 'tone_jitter' in params:
            self.tone_jitter.set(params['tone_jitter'])


class ContextTab(ttk.Frame):
    """Context drill mode: Listening + text input for call-like strings."""

    def __init__(self, parent, start_callback, stop_callback, active_pair: tk.StringVar):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.mode_name = "context"

        # Variables
        self.pair = active_pair
        self.wpm = tk.DoubleVar(value=25.0)
        self.tone = tk.DoubleVar(value=650.0)

        self._build_ui()

    def _build_ui(self):
        # Instructions
        inst_frame = ttk.LabelFrame(self, text="Context Mode")
        inst_frame.pack(fill="x", padx=8, pady=8)
        ttk.Label(inst_frame, text="• Listen to call-like strings containing your pair\n"
                                   "• Type what you copy in the box below (A–Z, 0–9)\n"
                                   "• On Stop, accuracy is computed vs what was sent\n"
                                   "• Mono-only (stereo disabled)",
                  justify="left").pack(padx=8, pady=8, anchor="w")

        # Pair settings
        pair_frame = ttk.LabelFrame(self, text="Pair Settings")
        pair_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(pair_frame, text="Active pair (A,B):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(pair_frame, textvariable=self.pair, width=10).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(pair_frame, text="WPM:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(pair_frame, from_=8, to=50, increment=1, textvariable=self.wpm, width=6).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(pair_frame, text="Tone (Hz):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        ttk.Spinbox(pair_frame, from_=300, to=1000, increment=10, textvariable=self.tone, width=7).grid(row=0, column=5, padx=4, pady=4)

        # Copy input
        copy_frame = ttk.LabelFrame(self, text="Copy Input")
        copy_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.copy_text = tk.Text(copy_frame, height=10, wrap="word")
        self.copy_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.copy_text.insert("1.0", "Type what you copy here (A–Z, 0–9, spaces ignored in scoring).")

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Context", command=lambda: self.start_callback(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop & Score", command=self.stop_callback, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

    def validate_inputs(self) -> Optional[str]:
        pair, err = validate_pair(self.pair)
        if err:
            return err

        wpm = self.wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = validate_pair(self.pair)

        return DrillSpec(
            mode="context",
            pair=pair,
            wpm=self.wpm.get(),
            tone_hz=self.tone.get(),
            stereo=False  # Context is always mono
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.copy_text.delete("1.0", "end")
        self.copy_text.config(state="normal")
        # Focus on the input area so user can start typing immediately
        self.copy_text.focus_set()

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.copy_text.config(state="disabled")
        return self.copy_text.get("1.0", "end")

    def get_params(self) -> Dict[str, Any]:
        """Get current parameter values for persistence."""
        return {
            'wpm': self.wpm.get(),
            'tone': self.tone.get()
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        """Restore parameter values from saved config."""
        if 'wpm' in params:
            self.wpm.set(params['wpm'])
        if 'tone' in params:
            self.tone.set(params['tone'])


class OverspeedTab(ttk.Frame):
    """Overspeed drill mode: High-speed listening + text input."""

    def __init__(self, parent, start_callback, stop_callback, active_pair: tk.StringVar):
        super().__init__(parent)
        self.start_callback = start_callback
        self.stop_callback = stop_callback
        self.mode_name = "overspeed"

        # Variables
        self.pair = active_pair
        self.overspeed_wpm = tk.DoubleVar(value=30.0)
        self.tone = tk.DoubleVar(value=650.0)

        self._build_ui()

    def _build_ui(self):
        # Instructions
        inst_frame = ttk.LabelFrame(self, text="Overspeed Mode")
        inst_frame.pack(fill="x", padx=8, pady=8)
        ttk.Label(inst_frame, text="• Short high-WPM burst of pair-heavy lines\n"
                                   "• Type what you copy in the box below (A–Z, 0–9)\n"
                                   "• On Stop, accuracy is computed\n"
                                   "• Mono-only (stereo disabled)",
                  justify="left").pack(padx=8, pady=8, anchor="w")

        # Pair settings
        pair_frame = ttk.LabelFrame(self, text="Pair Settings")
        pair_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(pair_frame, text="Active pair (A,B):").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Entry(pair_frame, textvariable=self.pair, width=10).grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(pair_frame, text="Overspeed WPM:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(pair_frame, from_=24, to=45, increment=1, textvariable=self.overspeed_wpm, width=6).grid(row=0, column=3, padx=4, pady=4)

        ttk.Label(pair_frame, text="Tone (Hz):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        ttk.Spinbox(pair_frame, from_=300, to=1000, increment=10, textvariable=self.tone, width=7).grid(row=0, column=5, padx=4, pady=4)

        # Copy input
        copy_frame = ttk.LabelFrame(self, text="Copy Input")
        copy_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.copy_text = tk.Text(copy_frame, height=10, wrap="word")
        self.copy_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.copy_text.insert("1.0", "Type what you copy here (A–Z, 0–9, spaces ignored in scoring).")

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Overspeed", command=lambda: self.start_callback(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop & Score", command=self.stop_callback, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

    def validate_inputs(self) -> Optional[str]:
        pair, err = validate_pair(self.pair)
        if err:
            return err

        wpm = self.overspeed_wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = validate_pair(self.pair)

        return DrillSpec(
            mode="overspeed",
            pair=pair,
            wpm=self.overspeed_wpm.get(),
            tone_hz=self.tone.get(),
            stereo=False,  # Overspeed is always mono
            overspeed_wpm=self.overspeed_wpm.get()
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.copy_text.delete("1.0", "end")
        self.copy_text.config(state="normal")
        # Focus on the input area so user can start typing immediately
        self.copy_text.focus_set()

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.copy_text.config(state="disabled")
        return self.copy_text.get("1.0", "end")

    def get_params(self) -> Dict[str, Any]:
        """Get current parameter values for persistence."""
        return {
            'overspeed_wpm': self.overspeed_wpm.get(),
            'tone': self.tone.get()
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        """Restore parameter values from saved config."""
        if 'overspeed_wpm' in params:
            self.overspeed_wpm.set(params['overspeed_wpm'])
        if 'tone' in params:
            self.tone.set(params['tone'])
