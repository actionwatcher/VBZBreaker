"""Tab classes for VBZBreaker drill modes."""
import tkinter as tk
from tkinter import ttk
from typing import Optional
from vbz_drill import DrillSpec
from vbz_utils import MORSE_MAP


class DrillTab(ttk.Frame):
    """Base class for drill mode tabs."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.mode_name = ""  # Override in subclasses

    def get_drill_spec(self) -> Optional[DrillSpec]:
        """Build and return DrillSpec from tab's controls. Override in subclasses."""
        raise NotImplementedError

    def on_session_start(self):
        """Called when session starts. Override to disable controls."""
        pass

    def on_session_stop(self, sent_lines=None):
        """Called when session stops. Override to re-enable controls and handle results."""
        pass

    def validate_inputs(self) -> Optional[str]:
        """Validate inputs and return error message if invalid, None if valid."""
        return None

    def _validate_pair(self, pair_var: tk.StringVar) -> Optional[tuple]:
        """Common pair validation. Returns (a, b) tuple or None if invalid."""
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

    def _validate_tone(self, tone_var: tk.DoubleVar) -> Optional[str]:
        """Common tone validation."""
        tone_hz = tone_var.get()
        if tone_hz < 100 or tone_hz > 2000:
            return "Tone frequency must be between 100 and 2000 Hz"
        return None


class ReanchorTab(DrillTab):
    """Re-anchor drill mode: Listening only, alternating slow/fast blocks."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.mode_name = "reanchor"

        # Variables
        self.pair = tk.StringVar(value="H,5")
        self.tone = tk.DoubleVar(value=650.0)
        self.jitter = tk.DoubleVar(value=0.10)
        self.tone_jitter = tk.DoubleVar(value=0.0)
        self.stereo = tk.BooleanVar(value=True)
        self.sep_pct = tk.DoubleVar(value=1.0)
        self.low_wpm = tk.DoubleVar(value=12.0)
        self.high_wpm = tk.DoubleVar(value=36.0)
        self.timing_balance = tk.DoubleVar(value=0.0)  # 0=equal chars, 1=equal time

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
        stereo_frame = ttk.LabelFrame(self, text="Stereo Settings")
        stereo_frame.pack(fill="x", padx=8, pady=4)

        ttk.Checkbutton(stereo_frame, text="Enable Stereo L/R", variable=self.stereo).grid(row=0, column=0, sticky="w", padx=4, pady=4)

        ttk.Label(stereo_frame, text="Separation:").grid(row=0, column=1, sticky="e", padx=4)
        sep = ttk.Scale(stereo_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        sep.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        stereo_frame.columnconfigure(2, weight=1)
        ttk.Label(stereo_frame, text="0=mono — 1=fully split (snap 0.25)").grid(row=0, column=3, sticky="w", padx=4)

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

        # Timing balance control
        timing_frame = ttk.LabelFrame(self, text="Timing Balance")
        timing_frame.pack(fill="x", padx=8, pady=4)

        ttk.Label(timing_frame, text="Balance:").grid(row=0, column=0, sticky="w", padx=4, pady=4)

        timing_slider = ttk.Scale(timing_frame, from_=0.0, to=1.0, orient="horizontal",
                                   variable=self.timing_balance, length=300)
        timing_slider.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        timing_frame.columnconfigure(1, weight=1)

        # Add labels for the slider positions
        labels_frame = ttk.Frame(timing_frame)
        labels_frame.grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(labels_frame, text="Equal Characters", font=('', 8)).pack(side="left")
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

        # Explanation label
        explain_frame = ttk.Frame(timing_frame)
        explain_frame.grid(row=2, column=1, sticky="ew", padx=4, pady=(0, 4))
        ttk.Label(explain_frame, text="← Same character count at each speed | Same duration at each speed →",
                  font=('', 8), foreground='gray').pack()

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Re-anchor", command=lambda: self.app.start_session_from_tab(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.app.stop_session, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # Status
        status_frame = ttk.LabelFrame(self, text="Status")
        status_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.status_label = ttk.Label(status_frame, text="Ready", anchor="w", justify="left")
        self.status_label.pack(fill="both", expand=True, padx=8, pady=8)

    def validate_inputs(self) -> Optional[str]:
        pair, err = self._validate_pair(self.pair)
        if err:
            return err

        err = self._validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = self._validate_pair(self.pair)

        return DrillSpec(
            mode="reanchor",
            pair=pair,
            wpm=self.low_wpm.get(),
            tone_hz=self.tone.get(),
            jitter_pct=self.jitter.get(),
            tone_jitter_hz=self.tone_jitter.get(),
            stereo=self.stereo.get(),
            pan_strength=self.sep_pct.get(),
            low_wpm=self.low_wpm.get(),
            high_wpm=self.high_wpm.get(),
            timing_balance=self.timing_balance.get()
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Session running... Listen to alternating slow/fast blocks.")

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Session stopped.")


class ContrastTab(DrillTab):
    """Contrast drill mode: Listening only, copy dense A/B lines."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.mode_name = "contrast"

        # Variables
        self.pair = tk.StringVar(value="H,5")
        self.wpm = tk.DoubleVar(value=25.0)
        self.tone = tk.DoubleVar(value=650.0)
        self.jitter = tk.DoubleVar(value=0.10)
        self.wpm_jitter = tk.DoubleVar(value=0.0)
        self.tone_jitter = tk.DoubleVar(value=0.0)
        self.stereo = tk.BooleanVar(value=True)
        self.sep_pct = tk.DoubleVar(value=1.0)

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

        ttk.Label(audio_frame, text="WPM jitter (±):").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=5.0, increment=0.5, textvariable=self.wpm_jitter, width=6).grid(row=1, column=1, padx=4, pady=4)

        ttk.Label(audio_frame, text="Tone jitter (±Hz):").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(audio_frame, from_=0.0, to=300.0, increment=10.0, textvariable=self.tone_jitter, width=7).grid(row=1, column=3, padx=4, pady=4)

        # Stereo settings
        stereo_frame = ttk.LabelFrame(self, text="Stereo Settings")
        stereo_frame.pack(fill="x", padx=8, pady=4)

        ttk.Checkbutton(stereo_frame, text="Enable Stereo L/R", variable=self.stereo).grid(row=0, column=0, sticky="w", padx=4, pady=4)

        ttk.Label(stereo_frame, text="Separation:").grid(row=0, column=1, sticky="e", padx=4)
        sep = ttk.Scale(stereo_frame, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        sep.grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        stereo_frame.columnconfigure(2, weight=1)
        ttk.Label(stereo_frame, text="0=mono — 1=fully split (snap 0.25)").grid(row=0, column=3, sticky="w", padx=4)

        # Snap separation slider to 0.25 steps
        def snap_sep(*_):
            v = self.sep_pct.get()
            snapped = round(v / 0.25) * 0.25
            self.sep_pct.set(min(1.0, max(0.0, snapped)))
        self.sep_pct.trace_add("write", snap_sep)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=8)
        self.start_btn = ttk.Button(btn_frame, text="Start Contrast", command=lambda: self.app.start_session_from_tab(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop", command=self.app.stop_session, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        # Status
        status_frame = ttk.LabelFrame(self, text="Status")
        status_frame.pack(fill="both", expand=True, padx=8, pady=4)
        self.status_label = ttk.Label(status_frame, text="Ready", anchor="w", justify="left")
        self.status_label.pack(fill="both", expand=True, padx=8, pady=8)

    def validate_inputs(self) -> Optional[str]:
        pair, err = self._validate_pair(self.pair)
        if err:
            return err

        wpm = self.wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = self._validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = self._validate_pair(self.pair)

        return DrillSpec(
            mode="contrast",
            pair=pair,
            wpm=self.wpm.get(),
            tone_hz=self.tone.get(),
            jitter_pct=self.jitter.get(),
            wpm_jitter=self.wpm_jitter.get(),
            tone_jitter_hz=self.tone_jitter.get(),
            stereo=self.stereo.get(),
            pan_strength=self.sep_pct.get()
        )

    def on_session_start(self):
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_label.config(text="Session running... Copy the dense A/B lines on paper.")

    def on_session_stop(self, sent_lines=None):
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_label.config(text="Session stopped.")


class ContextTab(DrillTab):
    """Context drill mode: Listening + text input for call-like strings."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.mode_name = "context"

        # Variables
        self.pair = tk.StringVar(value="H,5")
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
        self.start_btn = ttk.Button(btn_frame, text="Start Context", command=lambda: self.app.start_session_from_tab(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop & Score", command=self.app.stop_session, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

    def validate_inputs(self) -> Optional[str]:
        pair, err = self._validate_pair(self.pair)
        if err:
            return err

        wpm = self.wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = self._validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = self._validate_pair(self.pair)

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


class OverspeedTab(DrillTab):
    """Overspeed drill mode: High-speed listening + text input."""

    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.mode_name = "overspeed"

        # Variables
        self.pair = tk.StringVar(value="H,5")
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
        self.start_btn = ttk.Button(btn_frame, text="Start Overspeed", command=lambda: self.app.start_session_from_tab(self))
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(btn_frame, text="Stop & Score", command=self.app.stop_session, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

    def validate_inputs(self) -> Optional[str]:
        pair, err = self._validate_pair(self.pair)
        if err:
            return err

        wpm = self.overspeed_wpm.get()
        if wpm <= 0 or wpm > 100:
            return "WPM must be between 1 and 100"

        err = self._validate_tone(self.tone)
        if err:
            return err

        return None

    def get_drill_spec(self) -> Optional[DrillSpec]:
        pair, _ = self._validate_pair(self.pair)

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
