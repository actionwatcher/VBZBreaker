"""GUI front-end for VBZBreaker (Tkinter application).

This module defines the App class which builds the UI and maps controls to
the SessionRunner. The design intentionally keeps UI wiring separate from
audio/synth logic in vbz_session and vbz_synth.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, time, csv, sys
from typing import Optional

from vbz_drill import DrillSpec
from vbz_session import SessionRunner
from vbz_utils import MORSE_MAP, norm_text, levenshtein


def get_default_log_dir() -> str:
    """Get platform-appropriate default log directory.

    Returns:
        Path to the default log directory based on the platform.
    """
    if sys.platform == 'win32':
        # Windows: Use AppData\Local
        base = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'VBZBreaker', 'logs')
    elif sys.platform == 'darwin':
        # macOS: Use ~/Library/Application Support
        return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'VBZBreaker', 'logs')
    else:
        # Linux/Unix: Use XDG_DATA_HOME or ~/.local/share
        xdg_data = os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))
        return os.path.join(xdg_data, 'vbzbreaker', 'logs')


class App(tk.Tk):
    """Main application window and UI wiring.

    The App mirrors the original script's controls and delegates session
    execution to SessionRunner.
    """
    def __init__(self):
        super().__init__()
        self.title("VBZBreaker")
        self.geometry("1040x720")
        self.resizable(True, True)

        # Set up window close handler to clean up running sessions
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Bindable UI variables
        self.active_pair = tk.StringVar(value="H,5")
        self.mode = tk.StringVar(value="reanchor")
        self.wpm = tk.DoubleVar(value=25.0)
        self.tone = tk.DoubleVar(value=650.0)
        self.jitter = tk.DoubleVar(value=0.10)
        self.wpm_jitter = tk.DoubleVar(value=0.0)
        self.tone_jitter = tk.DoubleVar(value=0.0)
        self.stereo = tk.BooleanVar(value=True)
        self.sep_pct = tk.DoubleVar(value=1.0)
        self.low_wpm = tk.DoubleVar(value=12.0)
        self.high_wpm = tk.DoubleVar(value=36.0)
        self.block_seconds = tk.DoubleVar(value=12.0)
        self.overspeed_wpm = tk.DoubleVar(value=30.0)

        self.log_dir = tk.StringVar(value=get_default_log_dir())
        self.status = tk.StringVar(value="Welcome to VBZBreaker")
        self.runner: Optional[SessionRunner] = None

        self._build_ui()

    def _build_ui(self):
        """Construct the Tkinter layout and controls."""
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=8)

        # Top controls (session config)
        top = ttk.LabelFrame(frm, text="Session")
        top.pack(fill="x", padx=4, pady=4)
        ttk.Label(top, text="Active pair (A,B):").grid(row=0, column=0, sticky="w")
        self.pair_entry = ttk.Entry(top, textvariable=self.active_pair, width=10)
        self.pair_entry.grid(row=0, column=1, padx=6)

        ttk.Label(top, text="Mode:").grid(row=0, column=2, sticky="e")
        ttk.OptionMenu(top, self.mode, self.mode.get(), "reanchor","contrast","context","overspeed").grid(row=0,column=3,padx=6)

        ttk.Label(top, text="WPM:").grid(row=0, column=4, sticky="e")
        ttk.Spinbox(top, from_=8, to=50, increment=1, textvariable=self.wpm, width=6).grid(row=0, column=5, padx=6)

        ttk.Label(top, text="Tone (Hz):").grid(row=0, column=6, sticky="e")
        ttk.Spinbox(top, from_=300, to=1000, increment=10, textvariable=self.tone, width=7).grid(row=0, column=7, padx=6)

        ttk.Button(top, text="Start", command=self.start_session).grid(row=0, column=8, padx=8)
        ttk.Button(top, text="Stop", command=self.stop_session).grid(row=0, column=9, padx=4)

        # Options frame
        opt = ttk.LabelFrame(frm, text="Options")
        opt.pack(fill="x", padx=4, pady=4)
        ttk.Checkbutton(opt, text="Stereo L/R (reanchor/contrast only)", variable=self.stereo).grid(row=0,column=0,sticky="w",padx=6)

        ttk.Label(opt, text="Separation:").grid(row=0,column=1,sticky="e")
        sep = ttk.Scale(opt, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        sep.grid(row=0, column=2, padx=4, sticky="ew")
        opt.columnconfigure(2, weight=1)
        ttk.Label(opt, text="0=mono — 1=fully split (snap 0.25)").grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(opt, text="Jitter (±%):").grid(row=1, column=0, sticky="e")
        ttk.Spinbox(opt, from_=0.0, to=0.3, increment=0.01, textvariable=self.jitter, width=6).grid(row=1, column=1, padx=4, sticky="w")

        ttk.Label(opt, text="WPM jitter (±):").grid(row=1, column=2, sticky="e")
        ttk.Spinbox(opt, from_=0.0, to=5.0, increment=0.5, textvariable=self.wpm_jitter, width=6).grid(row=1, column=3, padx=4, sticky="w")

        ttk.Label(opt, text="Tone jitter (±Hz):").grid(row=1, column=4, sticky="e")
        ttk.Spinbox(opt, from_=0.0, to=300.0, increment=10.0, textvariable=self.tone_jitter, width=7).grid(row=1, column=5, padx=4, sticky="w")

        # Re-anchor & Overspeed settings
        ra = ttk.LabelFrame(frm, text="Re-anchor / Overspeed Settings")
        ra.pack(fill="x", padx=4, pady=4)

        ttk.Label(ra, text="Low WPM:").grid(row=0,column=0,sticky="e")
        ttk.Spinbox(ra, from_=6, to=30, increment=1, textvariable=self.low_wpm, width=6).grid(row=0,column=1,padx=4)
        ttk.Label(ra, text="High WPM:").grid(row=0,column=2,sticky="e")
        ttk.Spinbox(ra, from_=20, to=50, increment=1, textvariable=self.high_wpm, width=6).grid(row=0,column=3,padx=4)
        ttk.Label(ra, text="Block (s):").grid(row=0,column=4,sticky="e")
        ttk.Spinbox(ra, from_=6, to=30, increment=1, textvariable=self.block_seconds, width=6).grid(row=0,column=5,padx=4)

        ttk.Label(ra, text="Overspeed WPM:").grid(row=0,column=6,sticky="e")
        ttk.Spinbox(ra, from_=24, to=45, increment=1, textvariable=self.overspeed_wpm, width=6).grid(row=0,column=7,padx=4)

        # Copy input (Context & Overspeed)
        copyf = ttk.LabelFrame(frm, text="Copy Input (Context & Overspeed)")
        copyf.pack(fill="both", expand=False, padx=4, pady=4)
        self.copy_text = tk.Text(copyf, height=6, wrap="word")
        self.copy_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.copy_text.insert("1.0", "Type what you copy here (A–Z, 0–9, spaces ignored in scoring).")
        self.copy_text.config(state="disabled")

        # Status / instructions
        statusf = ttk.LabelFrame(frm, text="Status & Instructions")
        statusf.pack(fill="both", expand=True, padx=4, pady=4)
        self.status_lbl = ttk.Label(statusf, textvariable=self.status, anchor="w", justify="left")
        self.status_lbl.pack(fill="both", expand=True, padx=6, pady=6)

        def snap_sep(*_):
            v = self.sep_pct.get()
            snapped = round(v / 0.25) * 0.25
            self.sep_pct.set(min(1.0, max(0.0, snapped)))
        self.sep_pct.trace_add("write", snap_sep)

        self._set_instructions(self.mode.get())
        def on_mode_change(*_):
            self._set_instructions(self.mode.get())
        self.mode.trace_add("write", on_mode_change)

    def _set_instructions(self, mode: str):
        """Update instructions text and enable/disable copy input area."""
        ins = {
            "reanchor":
                "Re-anchor:\n• Alternate slow↔fast A/B blocks.\n• Focus on FEEL; do NOT copy.\n• Separation slider (if enabled) pans A left, B right.\n• Jitter/variation helps de-normalize timing.",
            "contrast":
                "Contrast:\n• Copy dense A/B minimal-pair strings at normal speed.\n• Accuracy matters; repeat short lines.\n• Separation slider (if enabled) pans A left, B right.",
            "context":
                "Context:\n• You will hear call-like strings containing your pair.\n• Type what you copy into the box below (A–Z, 0–9).\n• On Stop, VBZBreaker computes accuracy vs what was sent.\n• Mono-only (stereo disabled).",
            "overspeed":
                "Overspeed:\n• Short high-WPM burst of pair-heavy lines.\n• Type what you copy into the box below (A–Z, 0–9).\n• On Stop, VBZBreaker computes accuracy.\n• Mono-only (stereo disabled)."
        }
        self.status.set(ins.get(mode, "Ready"))
        if mode in ("context", "overspeed"):
            self.copy_text.config(state="normal")
        else:
            self.copy_text.delete("1.0", "end")
            self.copy_text.insert("1.0", "Type what you copy here (A–Z, 0–9, spaces ignored in scoring).")
            self.copy_text.config(state="disabled")

    def _choose_log_dir(self):
        d = filedialog.askdirectory(initialdir=self.log_dir.get(), title="Choose log directory")
        if d:
            self.log_dir.set(d)

    def update_status(self, msg: str):
        """Helper to update status line from SessionRunner callbacks."""
        self.status.set(msg)

    def start_session(self):
        """Gather UI options, create a DrillSpec and start a SessionRunner."""
        if self.runner is not None:
            messagebox.showinfo("Busy", "A session is already running. Press Stop first.")
            return

        # Validate pair input
        pair_str = self.active_pair.get().replace(" ", "")
        if "," not in pair_str:
            messagebox.showerror("Pair error", "Enter active pair as A,B (e.g., H,5)")
            return

        parts = pair_str.split(",")
        if len(parts) != 2:
            messagebox.showerror("Pair error", "Enter exactly two characters separated by comma (e.g., H,5)")
            return

        a, b = parts[0].strip().upper(), parts[1].strip().upper()
        if not a or not b:
            messagebox.showerror("Pair error", "Both characters must be non-empty")
            return

        if a not in MORSE_MAP:
            messagebox.showerror("Pair error", f"Character '{a}' is not valid. Use A-Z or 0-9.")
            return
        if b not in MORSE_MAP:
            messagebox.showerror("Pair error", f"Character '{b}' is not valid. Use A-Z or 0-9.")
            return

        # Validate audio parameters
        wpm = self.wpm.get()
        if wpm <= 0 or wpm > 100:
            messagebox.showerror("WPM error", "WPM must be between 1 and 100")
            return

        tone_hz = self.tone.get()
        if tone_hz < 100 or tone_hz > 2000:
            messagebox.showerror("Tone error", "Tone frequency must be between 100 and 2000 Hz")
            return

        spec = DrillSpec(
            mode=self.mode.get(),
            pair=(a, b),
            wpm=wpm,
            tone_hz=tone_hz,
            jitter_pct=self.jitter.get(),
            wpm_jitter=self.wpm_jitter.get(),
            tone_jitter_hz=self.tone_jitter.get(),
            stereo=(self.mode.get() in ("reanchor","contrast")) and self.stereo.get(),
            pan_strength=self.sep_pct.get(),
            low_wpm=self.low_wpm.get(),
            high_wpm=self.high_wpm.get(),
            block_seconds=self.block_seconds.get(),
            overspeed_wpm=self.overspeed_wpm.get()
        )

        os.makedirs(self.log_dir.get(), exist_ok=True)
        log_path = os.path.join(self.log_dir.get(), f"session_{int(time.time())}.csv")

        self.runner = SessionRunner(spec, log_path, self.update_status)
        self.runner.start()

        if spec.mode in ("reanchor", "contrast") and spec.stereo:
            self.update_status(f"Running {spec.mode} for pair {a}/{b} (stereo sep={spec.pan_strength:.2f}) ... logging to {log_path}")
        else:
            self.update_status(f"Running {spec.mode} for pair {a}/{b} (mono) ... logging to {log_path}")

    def stop_session(self):
        """Stop the runner and, when appropriate, compute and show metrics."""
        if self.runner:
            with self.runner._sent_lines_lock:
                sent_lines = list(self.runner.sent_lines)
            pair_str = self.runner.spec.pair  # Get the actual (a,b) tuple
            self.runner.stop()
            self.runner = None
            mode = self.mode.get()
            if mode in ("context","overspeed") and sent_lines:
                expected = norm_text(' '.join(sent_lines))
                try:
                    typed = self.copy_text.get("1.0","end")
                except Exception:
                    typed = ""
                typed_norm = norm_text(typed)
                total = len(expected)
                dist = levenshtein(expected, typed_norm) if total>0 else 0
                acc = (1.0 - dist/max(1,total)) * 100.0
                pair_normalized = f"{pair_str[0]}{pair_str[1]}"  # "H5" not "H,5"
                try:
                    files = sorted([f for f in os.listdir(self.log_dir.get()) if f.startswith("session_") and f.endswith(".csv")])
                    if files:
                        last = os.path.join(self.log_dir.get(), files[-1])
                        with open(last, "a", newline="") as f:
                            w = csv.writer(f)
                            w.writerow(["metrics", mode, pair_normalized, "chars_total", total])
                            w.writerow(["metrics", mode, pair_normalized, "levenshtein", dist])
                            w.writerow(["metrics", mode, pair_normalized, "accuracy_pct", f"{acc:.2f}"])
                except Exception:
                    pass
                messagebox.showinfo("VBZBreaker — Session Metrics",
                                    f"Mode: {mode}\n"
                                    f"Pair: {self.active_pair.get()}\n"
                                    f"Total chars (gt): {total}\n"
                                    f"Levenshtein distance: {dist}\n"
                                    f"Accuracy: {acc:.2f}%")
        self.update_status("Stopped.")

    def _on_closing(self):
        """Clean up and close the application gracefully."""
        if self.runner:
            self.runner.stop()
            self.runner = None
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
