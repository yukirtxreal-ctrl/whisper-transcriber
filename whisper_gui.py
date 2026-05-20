"""
Whisper Transcriber GUI  -  black / minimalist theme

A tkinter front-end for OpenAI Whisper (https://github.com/openai/whisper).
Pick an audio/video file, choose a model and options, and get a transcript.
Shells out to the `whisper` CLI from the `openai-whisper` pip package.
Requires ffmpeg on PATH.

Run:  py -3 whisper_gui.py   (or double-click "Whisper Transcriber.bat")
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

__version__ = "1.2.0"
SETTINGS_FILE = Path.home() / ".whisper_transcriber.json"
# Matches the end time in Whisper's "[mm:ss.fff --> mm:ss.fff]" verbose output.
_TS_RE = re.compile(r"-->\s*([0-9:]+\.[0-9]+)\]")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Platform-appropriate fonts (Tk substitutes if missing, but these look native).
if sys.platform == "darwin":
    UI_FAMILY, MONO_FAMILY = "Helvetica Neue", "Menlo"
elif sys.platform == "win32":
    UI_FAMILY, MONO_FAMILY = "Segoe UI", "Consolas"
else:
    UI_FAMILY, MONO_FAMILY = "DejaVu Sans", "DejaVu Sans Mono"

# --- Palette: near-black, minimalist, one restrained accent -----------------
BG = "#0d0d0d"        # window background
PANEL = "#161616"     # raised surfaces (log, secondary buttons)
FIELD = "#1a1a1a"     # entry / combobox fields
BORDER = "#272727"
TEXT = "#ededed"
MUTED = "#7c7c7c"
FAINT = "#555555"
ACCENT = "#5b8cff"        # soft blue accent
ACCENT_FG = "#ffffff"
ACCENT_HOVER = "#6f9bff"
ACCENT_DIM = "#243049"    # accent-tinted field highlight
HOVER = "#222222"

MODELS = [
    "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "medium", "medium.en", "large", "turbo",
]
LANGUAGES = [
    ("auto", "Auto-detect"), ("en", "English"), ("es", "Spanish"),
    ("fr", "French"), ("de", "German"), ("it", "Italian"),
    ("pt", "Portuguese"), ("nl", "Dutch"), ("ru", "Russian"),
    ("ja", "Japanese"), ("ko", "Korean"), ("zh", "Chinese"),
    ("ar", "Arabic"), ("hi", "Hindi"), ("id", "Indonesian"),
    ("tr", "Turkish"), ("vi", "Vietnamese"), ("th", "Thai"),
]
FORMATS = ["txt", "srt", "vtt", "tsv", "json", "all"]
AUDIO_EXTS = ["*.mp3", "*.wav", "*.m4a", "*.flac", "*.ogg", "*.aac",
              "*.wma", "*.mp4", "*.mkv", "*.mov", "*.avi", "*.webm"]


# Engines in preference order. whisper-ctranslate2 (faster-whisper / CTranslate2)
# is smaller and ~4x faster with the same CLI flags; plain openai-whisper is the
# fallback. Both auto-detect the GPU (--device defaults to auto).
ENGINES = ["whisper-ctranslate2", "whisper"]


def find_whisper_cmd() -> list[str] | None:
    bindir = Path(sys.executable).parent
    for engine in ENGINES:
        exe = shutil.which(engine)
        if exe:
            return [exe]
        nm = engine + (".exe" if os.name == "nt" else "")
        # Windows puts console scripts in Scripts/; Unix in the same bin/.
        for cand in (bindir / "Scripts" / nm, bindir / nm):
            if cand.exists():
                return [str(cand)]
    try:
        import whisper  # noqa: F401
        return [sys.executable, "-m", "whisper"]
    except ImportError:
        return None


def _add_to_path(dirs: list[str]) -> None:
    current = os.environ.get("PATH", "")
    seen = {p.lower() for p in current.split(os.pathsep) if p}
    add = []
    for d in dirs:
        d = (d or "").strip()
        if d and d.lower() not in seen:
            add.append(d)
            seen.add(d.lower())
    if add:
        os.environ["PATH"] = current + os.pathsep + os.pathsep.join(add)


def ensure_tool_paths() -> None:
    """Make freshly-installed tools (ffmpeg, whisper) findable even when the GUI
    was launched from a process with a stale/minimal PATH.

    Windows: reload PATH from the registry (winget updates it there).
    macOS/Linux: Finder/desktop launches don't inherit the shell PATH, so add
    the usual locations (Homebrew, /usr/local, ~/.local/bin)."""
    if sys.platform == "win32":
        try:
            import winreg
        except ImportError:
            return
        found = []
        for root, sub in (
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            (winreg.HKEY_CURRENT_USER, "Environment"),
        ):
            try:
                with winreg.OpenKey(root, sub) as key:
                    val, _ = winreg.QueryValueEx(key, "Path")
                    if val:
                        found.append(os.path.expandvars(val))
            except OSError:
                pass
        dirs = []
        for chunk in found:
            dirs.extend(chunk.split(os.pathsep))
        _add_to_path(dirs)
    else:
        home = str(Path.home())
        candidates = [
            "/opt/homebrew/bin", "/opt/homebrew/sbin",   # Apple Silicon brew
            "/usr/local/bin", "/usr/local/sbin",         # Intel brew / common
            "/usr/bin", "/bin", "/snap/bin",
            f"{home}/.local/bin", f"{home}/bin",
        ]
        _add_to_path([d for d in candidates if os.path.isdir(d)])


def ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def probe_duration(path: str) -> float | None:
    """Total media length in seconds via ffprobe, or None if unavailable."""
    ff = shutil.which("ffprobe")
    if not ff:
        return None
    try:
        r = subprocess.run(
            [ff, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW,
        )
        return float(r.stdout.strip())
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def parse_end_seconds(line: str) -> float | None:
    """Extract the segment end time (seconds) from a Whisper verbose line."""
    m = _TS_RE.search(line)
    if not m:
        return None
    sec = 0.0
    try:
        for part in m.group(1).split(":"):
            sec = sec * 60 + float(part)
    except ValueError:
        return None
    return sec


def apply_theme(root: tk.Tk) -> None:
    root.configure(bg=BG)
    st = ttk.Style(root)
    st.theme_use("clam")

    st.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD,
                 bordercolor=BORDER, focuscolor=BG, font=(UI_FAMILY,10),
                 lightcolor=BORDER, darkcolor=BORDER)
    st.configure("TFrame", background=BG)
    st.configure("TLabel", background=BG, foreground=TEXT)
    st.configure("Muted.TLabel", background=BG, foreground=MUTED, font=(UI_FAMILY,9))
    st.configure("Section.TLabel", background=BG, foreground=MUTED,
                 font=(UI_FAMILY,8, "bold"))
    st.configure("Title.TLabel", background=BG, foreground=TEXT,
                 font=(UI_FAMILY, 17, "bold"))
    st.configure("Status.TLabel", background=BG, foreground=MUTED, font=(UI_FAMILY,9))

    # Entry
    st.configure("TEntry", fieldbackground=FIELD, foreground=TEXT, bordercolor=BORDER,
                 insertcolor=ACCENT, relief="flat", padding=9)
    st.map("TEntry", bordercolor=[("focus", ACCENT)],
           lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)],
           fieldbackground=[("disabled", PANEL)])

    # Combobox
    st.configure("TCombobox", fieldbackground=FIELD, background=FIELD, foreground=TEXT,
                 arrowcolor=MUTED, bordercolor=BORDER, relief="flat", padding=8)
    st.map("TCombobox",
           fieldbackground=[("readonly", FIELD), ("disabled", PANEL)],
           foreground=[("readonly", TEXT)],
           selectbackground=[("readonly", FIELD)],
           selectforeground=[("readonly", TEXT)],
           bordercolor=[("focus", ACCENT), ("active", "#3a3a3a")],
           lightcolor=[("focus", ACCENT)], darkcolor=[("focus", ACCENT)],
           arrowcolor=[("active", TEXT)])

    # Secondary (ghost) button
    st.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER,
                 relief="flat", padding=(16, 10), anchor="center")
    st.map("TButton",
           background=[("active", HOVER), ("disabled", "#131313")],
           foreground=[("disabled", FAINT)],
           bordercolor=[("active", "#3a3a3a")])

    # Kicker / accent labels
    st.configure("Kicker.TLabel", background=BG, foreground=ACCENT,
                 font=(UI_FAMILY, 9, "bold"))

    # Primary (accent) button
    st.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_FG,
                 relief="flat", padding=(26, 12), font=(UI_FAMILY, 10, "bold"))
    st.map("Accent.TButton",
           background=[("active", ACCENT_HOVER), ("disabled", "#2a2a2a")],
           foreground=[("disabled", "#666666")])

    st.configure("TSeparator", background=BORDER)

    # Scrollbar (slim, flat)
    st.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                 bordercolor=BG, arrowcolor=MUTED, relief="flat", width=12)
    st.map("Vertical.TScrollbar", background=[("active", "#333333")])

    # Notebook (Log / Transcript tabs)
    st.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", background=BG, foreground=MUTED,
                 padding=(14, 7), borderwidth=0, font=(UI_FAMILY, 9, "bold"))
    st.map("TNotebook.Tab",
           background=[("selected", BG)],
           foreground=[("selected", ACCENT), ("active", TEXT)])

    # Progress bar
    st.configure("Accent.Horizontal.TProgressbar", troughcolor=FIELD,
                 background=ACCENT, bordercolor=BORDER, lightcolor=ACCENT,
                 darkcolor=ACCENT, thickness=6)

    # Combobox popup list
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    root.option_add("*TCombobox*Listbox.borderWidth", "0")
    root.option_add("*TCombobox*Listbox.font", "{%s} 10" % UI_FAMILY)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Whisper Transcriber")
        root.geometry("900x700")
        root.minsize(760, 600)

        s = load_settings()
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.model = tk.StringVar(value=s.get("model", "base"))
        self.language = tk.StringVar(value=s.get("language", "Auto-detect"))
        self.task = tk.StringVar(value=s.get("task", "transcribe"))
        self.fmt = tk.StringVar(value=s.get("fmt", "txt"))
        self.status = tk.StringVar(value="Pick an audio or video file to begin.")
        self._last_input_dir = s.get("last_input_dir", "")

        self._busy = False
        self._proc: subprocess.Popen | None = None
        self._last_out_dir: Path | None = None
        self._last_output_file: Path | None = None
        self._duration: float | None = None

        self._build()
        self._check_device()

    def _persist(self):
        save_settings({
            "model": self.model.get(),
            "language": self.language.get(),
            "task": self.task.get(),
            "fmt": self.fmt.get(),
            "last_input_dir": self._last_input_dir,
            "last_output_dir": self.output_dir.get().strip(),
        })

    def _check_device(self):
        def work():
            cuda, name = False, ""
            probe = (
                "cuda=0\nname=''\n"
                "try:\n import ctranslate2\n cuda=1 if ctranslate2.get_cuda_device_count()>0 else 0\n"
                "except Exception: pass\n"
                "try:\n import torch\n"
                " if torch.cuda.is_available():\n  cuda=1\n  name=torch.cuda.get_device_name(0)\n"
                "except Exception: pass\n"
                "print(cuda)\nprint(name)\n"
            )
            try:
                r = subprocess.run(
                    [sys.executable, "-c", probe],
                    capture_output=True, text=True, timeout=40, creationflags=NO_WINDOW,
                )
                lines = (r.stdout or "").strip().splitlines()
                cuda = bool(lines) and lines[0].strip() == "1"
                name = lines[1].strip() if len(lines) > 1 else ""
            except Exception:
                pass
            if cuda and not name:
                name = "NVIDIA GPU"
            self.root.after(0, self._set_device, cuda, name)
        threading.Thread(target=work, daemon=True).start()

    def _set_device(self, cuda: bool, name: str):
        if cuda:
            self.device_var.set(f"●  GPU acceleration  —  {name}")
            self.device_lbl.configure(foreground=ACCENT)
        else:
            self.device_var.set("●  CPU mode  —  no CUDA GPU detected")
            self.device_lbl.configure(foreground=MUTED)

    def _build(self):
        outer = ttk.Frame(self.root, padding=(36, 30, 36, 24))
        outer.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(outer, text="AUDIO  →  TEXT", style="Kicker.TLabel").pack(anchor=tk.W)
        ttk.Label(outer, text="Whisper Transcriber", style="Title.TLabel").pack(
            anchor=tk.W, pady=(2, 0))
        ttk.Label(outer, text="Offline speech-to-text, powered by OpenAI Whisper.",
                  style="Muted.TLabel").pack(anchor=tk.W, pady=(3, 0))
        # device (GPU/CPU) indicator
        self.device_var = tk.StringVar(value="checking compute device…")
        self.device_lbl = ttk.Label(outer, textvariable=self.device_var, style="Muted.TLabel")
        self.device_lbl.pack(anchor=tk.W, pady=(6, 0))
        # thin accent rule
        tk.Frame(outer, bg=ACCENT, height=2, width=46).pack(anchor=tk.W, pady=(12, 20))

        # Input
        ttk.Label(outer, text="INPUT FILE", style="Section.TLabel").pack(anchor=tk.W)
        r = ttk.Frame(outer)
        r.pack(fill=tk.X, pady=(4, 14))
        ttk.Entry(r, textvariable=self.input_path).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        ttk.Button(r, text="Browse", command=self.pick_input).pack(side=tk.LEFT, padx=(8, 0))

        # Output
        ttk.Label(outer, text="OUTPUT FOLDER", style="Section.TLabel").pack(anchor=tk.W)
        r = ttk.Frame(outer)
        r.pack(fill=tk.X, pady=(4, 18))
        ttk.Entry(r, textvariable=self.output_dir).pack(
            side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        ttk.Button(r, text="Choose", command=self.pick_output).pack(side=tk.LEFT, padx=(8, 0))

        # Options grid
        opts = ttk.Frame(outer)
        opts.pack(fill=tk.X, pady=(0, 6))
        for i in range(4):
            opts.columnconfigure(i, weight=1, uniform="opt")
        self._opt(opts, 0, "MODEL", self.model, MODELS)
        self._opt(opts, 1, "LANGUAGE", self.language, [l for _, l in LANGUAGES])
        self._opt(opts, 2, "TASK", self.task, ["transcribe", "translate"])
        self._opt(opts, 3, "FORMAT", self.fmt, FORMATS)

        ttk.Label(
            outer,
            text="Bigger model = more accurate, slower, larger download.  "
                 "'turbo' is a fast, accurate default.  'translate' outputs English.",
            style="Muted.TLabel",
        ).pack(anchor=tk.W, pady=(10, 16))

        # Actions
        act = ttk.Frame(outer)
        act.pack(fill=tk.X)
        self.run_btn = ttk.Button(act, text="Transcribe", style="Accent.TButton",
                                  command=self.transcribe)
        self.run_btn.pack(side=tk.LEFT)
        self.cancel_btn = ttk.Button(act, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_btn.pack(side=tk.LEFT, padx=(10, 14))
        ttk.Label(act, textvariable=self.status, style="Status.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        # Progress bar
        self.progress = ttk.Progressbar(outer, style="Accent.Horizontal.TProgressbar",
                                        mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(12, 0))

        ttk.Separator(outer).pack(fill=tk.X, pady=14)

        # Log / Transcript tabs
        nb = ttk.Notebook(outer)
        nb.pack(fill=tk.BOTH, expand=True)
        self.notebook = nb
        self.log, log_tab = self._make_text_panel(nb)
        self.transcript, tr_tab = self._make_text_panel(nb)
        nb.add(log_tab, text="LOG")
        nb.add(tr_tab, text="TRANSCRIPT")

        # Footer
        foot = ttk.Frame(outer)
        foot.pack(fill=tk.X, pady=(12, 0))
        self.open_btn = ttk.Button(foot, text="Open output folder",
                                   command=self._open_output, state="disabled")
        self.open_btn.pack(side=tk.LEFT)

    def _make_text_panel(self, parent):
        wrap = ttk.Frame(parent)
        txt = tk.Text(
            wrap, height=13, wrap=tk.WORD, relief="flat", borderwidth=0,
            bg=PANEL, fg="#c8c8c8", insertbackground=TEXT,
            font=(MONO_FAMILY, 10), padx=12, pady=10, state="disabled",
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER,
        )
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=txt.yview,
                           style="Vertical.TScrollbar")
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        txt.configure(yscrollcommand=sb.set)
        return txt, wrap

    def _opt(self, parent, col, label, var, values):
        cell = ttk.Frame(parent)
        cell.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
        ttk.Label(cell, text=label, style="Section.TLabel").pack(anchor=tk.W, pady=(0, 4))
        ttk.Combobox(cell, textvariable=var, values=values, state="readonly").pack(
            fill=tk.X, ipady=2)

    # --- pickers ---

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="Pick audio or video file",
            filetypes=[("Audio/Video", " ".join(AUDIO_EXTS)), ("All files", "*.*")],
            initialdir=self._last_input_dir or None,
        )
        if not path:
            return
        self.input_path.set(path)
        self._last_input_dir = str(Path(path).parent)
        if not self.output_dir.get():
            self.output_dir.set(str(Path(path).parent))

    def pick_output(self):
        path = filedialog.askdirectory(
            title="Pick output folder",
            initialdir=self.output_dir.get() or self._last_input_dir or None,
        )
        if path:
            self.output_dir.set(path)

    def _open_output(self):
        if self._last_out_dir and self._last_out_dir.exists():
            try:
                if sys.platform == "win32":
                    os.startfile(str(self._last_out_dir))  # noqa: S606
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(self._last_out_dir)], check=False)
                else:
                    subprocess.run(["xdg-open", str(self._last_out_dir)], check=False)
            except OSError:
                pass

    # --- logging ---

    def log_line(self, text: str):
        self.root.after(0, self._append, text)

    def _append(self, text: str):
        self.log.configure(state="normal")
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    # --- run ---

    def transcribe(self):
        if self._busy:
            return
        inp = self.input_path.get().strip()
        if not inp:
            messagebox.showwarning("Whisper Transcriber", "Pick an input file first.")
            return
        if not os.path.isfile(inp):
            messagebox.showerror("Whisper Transcriber", f"File not found:\n{inp}")
            return
        if not ffmpeg_present():
            ensure_tool_paths()  # in case it was installed while we were open
        if not ffmpeg_present():
            messagebox.showerror(
                "Whisper Transcriber",
                "ffmpeg is not installed or not on PATH.\n\n"
                "Whisper needs ffmpeg to read audio. Run "
                "\"Install Dependencies.bat\" first.",
            )
            return
        cmd_prefix = find_whisper_cmd()
        if cmd_prefix is None:
            messagebox.showerror(
                "Whisper Transcriber",
                "The 'whisper' tool isn't installed.\n\n"
                "Run \"Install Dependencies.bat\" first.",
            )
            return

        out_dir = self.output_dir.get().strip() or str(Path(inp).parent)
        os.makedirs(out_dir, exist_ok=True)
        lang = next((c for c, lbl in LANGUAGES if lbl == self.language.get()), "auto")

        cmd = cmd_prefix + [
            inp, "--model", self.model.get(), "--output_dir", out_dir,
            "--output_format", self.fmt.get(), "--task", self.task.get(),
            "--verbose", "True",
        ]
        if lang != "auto":
            cmd += ["--language", lang]

        self._last_out_dir = Path(out_dir)
        self._last_output_file = Path(out_dir) / (Path(inp).stem + ".txt")
        self._persist()
        self._busy = True
        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")
        self._clear(self.transcript)
        self.notebook.select(0)  # show the Log tab while it runs
        self.status.set("Transcribing… (first run downloads the model)")
        self._append(f"$ {' '.join(cmd)}\n")
        threading.Thread(target=self._run, args=(cmd, inp), daemon=True).start()

    def _clear(self, widget: tk.Text):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.configure(state="disabled")

    def _set_progress(self, pct: float):
        self.progress.configure(value=max(0.0, min(100.0, pct)))

    def _run(self, cmd: list[str], inp: str):
        self._duration = probe_duration(inp)
        self._switched = False
        # Animate immediately; switch to a real % only if the engine emits
        # segment timestamps (openai-whisper does; faster-whisper shows its own
        # bar, so we keep the animation going for it).
        self.root.after(0, self._start_indeterminate)
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
                creationflags=NO_WINDOW, env=env,
            )
        except OSError as e:
            self.root.after(0, self._done, False, f"Failed to launch: {e}")
            return
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            line = line.rstrip()
            self.log_line(line)
            if self._duration:
                end = parse_end_seconds(line)
                if end is not None:
                    if not self._switched:
                        self._switched = True
                        self.root.after(0, self._to_determinate)
                    self.root.after(0, self._set_progress, end / self._duration * 100.0)
        code = self._proc.wait()
        self._proc = None
        ok = code == 0
        self.root.after(0, self._done, ok, "Done." if ok else f"engine exited with code {code}")

    def _start_indeterminate(self):
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)

    def _to_determinate(self):
        try:
            self.progress.stop()
        except tk.TclError:
            pass
        self.progress.configure(mode="determinate", value=0)

    def cancel(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self.log_line("\n[cancelled]")
            except OSError:
                pass

    def _done(self, ok: bool, msg: str):
        self._busy = False
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        # finalize progress bar
        if str(self.progress["mode"]) == "indeterminate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        self.progress.configure(value=100 if ok else 0)
        self.status.set(msg)
        if ok and self._last_out_dir and self._last_out_dir.exists():
            self.open_btn.configure(state="normal")
            self._load_transcript()

    def _load_transcript(self):
        """Show the produced transcript in the Transcript tab and switch to it."""
        path = self._last_output_file
        text = None
        if path and path.exists():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = None
        if text is None and self._last_out_dir and self._last_output_file:
            # Fallback: any sibling file with the same stem (srt/vtt/json…).
            for alt in sorted(self._last_out_dir.glob(self._last_output_file.stem + ".*")):
                if alt.suffix.lower() != ".txt":
                    try:
                        text = alt.read_text(encoding="utf-8", errors="replace")
                        break
                    except OSError:
                        continue
        if not text:
            return
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", tk.END)
        self.transcript.insert(tk.END, text)
        self.transcript.configure(state="disabled")
        self.notebook.select(1)  # switch to the Transcript tab


def main():
    ensure_tool_paths()  # pick up ffmpeg etc. installed since the shell started
    root = tk.Tk()
    apply_theme(root)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        messagebox.showerror("Whisper Transcriber", f"Fatal error:\n{e}")
        sys.exit(1)
