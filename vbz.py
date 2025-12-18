"""GUI front-end for VBZBreaker (Tkinter application).

This module defines the App class which builds the UI and maps controls to
the SessionRunner. The design intentionally keeps UI wiring separate from
audio/synth logic in vbz_session and vbz_synth.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os, time, csv, sys
from typing import TYPE_CHECKING

from vbz_session import SessionRunner
from vbz_utils import norm_text, levenshtein
from vbz_tabs import ReanchorTab, ContrastTab, ContextTab, OverspeedTab
from vbz_config import load_config, save_config

if TYPE_CHECKING:
    from vbz_tabs import DrillTabProtocol


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
    """Main application window with tabbed drill mode interface."""

    def __init__(self):
        super().__init__()
        self.title("VBZBreaker")
        self.geometry("1040x760")
        self.resizable(True, True)

        # Set up window close handler to clean up running sessions
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Application state
        self.log_dir = tk.StringVar(value=get_default_log_dir())
        self.runner: SessionRunner | None = None
        self.active_tab: DrillTabProtocol | None = None
        self.active_pair = tk.StringVar(value="H,5")  # Global active pair shared across all tabs
        self.swap_lr = tk.BooleanVar(value=False)  # Global L/R swap shared across stereo tabs
        self.sep_pct = tk.DoubleVar(value=1.0)  # Global stereo separation shared across stereo tabs

        self._build_ui()

    def _build_ui(self):
        """Construct the tabbed UI interface."""
        # Create notebook (tab container)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=4, pady=4)

        # Create tabs with shared active_pair, swap_lr, and sep_pct
        self.reanchor_tab = ReanchorTab(self.notebook, self.start_session_from_tab, self.stop_session, self.active_pair, self.swap_lr, self.sep_pct)
        self.contrast_tab = ContrastTab(self.notebook, self.start_session_from_tab, self.stop_session, self.active_pair, self.swap_lr, self.sep_pct)
        self.context_tab = ContextTab(self.notebook, self.start_session_from_tab, self.stop_session, self.active_pair)
        self.overspeed_tab = OverspeedTab(self.notebook, self.start_session_from_tab, self.stop_session, self.active_pair)

        # Add tabs to notebook
        self.notebook.add(self.reanchor_tab, text="Re-anchor")
        self.notebook.add(self.contrast_tab, text="Contrast")
        self.notebook.add(self.context_tab, text="Context")
        self.notebook.add(self.overspeed_tab, text="Overspeed")

        # Store tab references for easy access
        self.tabs = [self.reanchor_tab, self.contrast_tab, self.context_tab, self.overspeed_tab]

        # Load saved parameters
        self._load_params()

    def update_status(self, msg: str):
        """Helper to update status line from SessionRunner callbacks."""
        # Check if this is a session completion notification
        if msg == "SESSION_COMPLETE":
            # Auto-stop the session
            self.after(100, self.stop_session)  # Schedule on main thread
            return

        if self.active_tab:
            if hasattr(self.active_tab, 'status_label'):
                self.active_tab.status_label.config(text=msg)

    def start_session_from_tab(self, tab):
        """Start a session from a specific tab."""
        if self.runner is not None:
            messagebox.showinfo("Busy", "A session is already running. Press Stop first.")
            return

        # Save current tab parameters before starting
        self._save_params()

        # Validate inputs
        error = tab.validate_inputs()
        if error:
            messagebox.showerror("Validation Error", error)
            return

        # Get drill spec from tab
        spec = tab.get_drill_spec()
        if not spec:
            messagebox.showerror("Error", "Failed to create drill specification")
            return

        # Create log directory and file
        os.makedirs(self.log_dir.get(), exist_ok=True)
        log_path = os.path.join(self.log_dir.get(), f"session_{int(time.time())}.csv")

        # Start session
        self.runner = SessionRunner(spec, log_path, self.update_status)
        self.runner.start()

        # Update UI state
        self.active_tab = tab
        tab.on_session_start()

        # Disable other tabs
        for i, other_tab in enumerate(self.tabs):
            if other_tab != tab:
                self.notebook.tab(i, state="disabled")

        # Log info
        pair_str = f"{spec.pair[0]}/{spec.pair[1]}"
        if spec.mode in ("reanchor", "contrast") and spec.stereo:
            self.update_status(f"Running {spec.mode} for pair {pair_str} (stereo sep={spec.pan_strength:.2f})")
        else:
            self.update_status(f"Running {spec.mode} for pair {pair_str} (mono)")

    def stop_session(self):
        """Stop the runner and, when appropriate, compute and show metrics."""
        if not self.runner or not self.active_tab:
            return

        # Get sent lines for scoring modes
        with self.runner._sent_lines_lock:
            sent_lines = list(self.runner.sent_lines)

        mode = self.runner.spec.mode
        pair_str = self.runner.spec.pair

        # Stop the runner
        self.runner.stop()
        self.runner = None

        # Get typed input from tab if applicable
        typed_text = self.active_tab.on_session_stop(sent_lines)

        # Re-enable all tabs
        for i in range(len(self.tabs)):
            self.notebook.tab(i, state="normal")

        # Compute metrics for context/overspeed modes
        if mode in ("context", "overspeed") and sent_lines and typed_text:
            expected = norm_text(' '.join(sent_lines))
            typed_norm = norm_text(typed_text)
            total = len(expected)
            dist = levenshtein(expected, typed_norm) if total > 0 else 0
            acc = (1.0 - dist / max(1, total)) * 100.0
            pair_normalized = f"{pair_str[0]}{pair_str[1]}"

            # Log metrics to CSV
            try:
                files = sorted([f for f in os.listdir(self.log_dir.get())
                               if f.startswith("session_") and f.endswith(".csv")])
                if files:
                    last = os.path.join(self.log_dir.get(), files[-1])
                    with open(last, "a", newline="") as f:
                        w = csv.writer(f)
                        w.writerow(["metrics", mode, pair_normalized, "chars_total", total])
                        w.writerow(["metrics", mode, pair_normalized, "levenshtein", dist])
                        w.writerow(["metrics", mode, pair_normalized, "accuracy_pct", f"{acc:.2f}"])
            except Exception:
                pass

            # Show metrics dialog
            messagebox.showinfo("VBZBreaker — Session Metrics",
                               f"Mode: {mode}\n"
                               f"Pair: {pair_str[0]},{pair_str[1]}\n"
                               f"Total chars (gt): {total}\n"
                               f"Levenshtein distance: {dist}\n"
                               f"Accuracy: {acc:.2f}%")

        self.active_tab = None
        self.update_status("Session stopped.")

    def _load_params(self):
        """Load saved parameters from config file and restore to tabs."""
        config = load_config()

        # Load global settings
        if 'active_pair' in config:
            self.active_pair.set(config['active_pair'])
        if 'swap_lr' in config:
            self.swap_lr.set(config['swap_lr'])
        if 'sep_pct' in config:
            self.sep_pct.set(config['sep_pct'])

        # Load tab-specific parameters
        if 'reanchor' in config:
            self.reanchor_tab.set_params(config['reanchor'])
        if 'contrast' in config:
            self.contrast_tab.set_params(config['contrast'])
        if 'context' in config:
            self.context_tab.set_params(config['context'])
        if 'overspeed' in config:
            self.overspeed_tab.set_params(config['overspeed'])

    def _save_params(self):
        """Save current parameters from all tabs to config file."""
        config = {
            'active_pair': self.active_pair.get(),
            'swap_lr': self.swap_lr.get(),
            'sep_pct': self.sep_pct.get(),
            'reanchor': self.reanchor_tab.get_params(),
            'contrast': self.contrast_tab.get_params(),
            'context': self.context_tab.get_params(),
            'overspeed': self.overspeed_tab.get_params()
        }
        save_config(config)

    def _on_closing(self):
        """Clean up and close the application gracefully."""
        # Save parameters before closing
        self._save_params()

        if self.runner:
            self.runner.stop()
            self.runner = None
        self.destroy()


def main():
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
