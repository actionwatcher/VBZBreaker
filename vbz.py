"""GUI front-end for VBZBreaker (Tkinter application).

This module defines the App class which builds the UI and maps controls to
the SessionRunner. The design intentionally keeps UI wiring separate from
audio/synth logic in vbz_session and vbz_synth.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, time, csv
from typing import Optional

from vbz_drill import DrillSpec
from vbz_session import SessionRunner
from vbz_utils import MORSE_MAP, norm_text, levenshtein


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

        self.log_dir = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "cwpb_logs"))
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

        # Options frame (abbreviated; rest follows original layout)
        opt = ttk.LabelFrame(frm, text="Options")
        opt.pack(fill="x", padx=4, pady=4)
        ttk.Checkbutton(opt, text="Stereo L/R (reanchor/contrast only)", variable=self.stereo).grid(row=0,column=0,sticky="w",padx=6)

        ttk.Label(opt, text="Separation:").grid(row=0,column=1,sticky="e")
        sep = ttk.Scale(opt, from_=0.0, to=1.0, orient="horizontal", variable=self.sep_pct)
        sep.grid(row=0, column=2, padx=4, sticky="ew")
        opt.columnconfigure(2, weight=1)
        ttk.Label(opt, text="0=mono — 1=fully split (snap 0.25)").grid(row=0, column=3, sticky="w", padx=6)

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
        pair_str = self.active_pair.get().replace(" ", "")
        try:
            a, b = pair_str.split(",")
            a, b = a.strip().upper(), b.strip().upper()
            assert a in MORSE_MAP and b in MORSE_MAP
        except Exception:
            messagebox.showerror("Pair error", "Enter active pair as A,B (e.g., H,5)")
            return

        spec = DrillSpec(
            mode=self.mode.get(),
            pair=(a, b),
            wpm=self.wpm.get(),
            tone_hz=self.tone.get(),
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
            sent_lines = list(self.runner.sent_lines)
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
                try:
                    files = sorted([f for f in os.listdir(self.log_dir.get()) if f.startswith("session_") and f.endswith(".csv")])
                    if files:
                        last = os.path.join(self.log_dir.get(), files[-1])
                        with open(last, "a", newline="") as f:
                            w = csv.writer(f)
                            w.writerow(["metrics", mode, ''.join(self.active_pair.get()), "chars_total", total])
                            w.writerow(["metrics", mode, ''.join(self.active_pair.get()), "levenshtein", dist])
                            w.writerow(["metrics", mode, ''.join(self.active_pair.get()), "accuracy_pct", f"{acc:.2f}"])
                except Exception:
                    pass
                messagebox.showinfo("VBZBreaker — Session Metrics",
                                    f"Mode: {mode}\n"
                                    f"Pair: {self.active_pair.get()}\n"
                                    f"Total chars (gt): {total}\n"
                                    f"Levenshtein distance: {dist}\n"
                                    f"Accuracy: {acc:.2f}%")
        self.update_status("Stopped.")


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
