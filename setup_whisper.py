"""
Whisper Transcriber - Setup

Checks and installs everything the Whisper GUI needs:
  - Python 3 + pip
  - ffmpeg (audio decoding; installed via winget on Windows)
  - openai-whisper pip package (pulls in PyTorch -- large download)
  - reports whether a CUDA GPU is available (optional, speeds things up)

Run:  py -3 setup_whisper.py   (or double-click "Install Dependencies.bat")
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk
from typing import Callable, Optional

IS_WINDOWS = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

if IS_MAC:
    UI_FAMILY, MONO_FAMILY = "Helvetica Neue", "Menlo"
elif IS_WINDOWS:
    UI_FAMILY, MONO_FAMILY = "Segoe UI", "Consolas"
else:
    UI_FAMILY, MONO_FAMILY = "DejaVu Sans", "DejaVu Sans Mono"

# Black / minimalist palette (matches the main GUI).
BG = "#0d0d0d"
PANEL = "#161616"
FIELD = "#1a1a1a"
BORDER = "#272727"
TEXT = "#ededed"
MUTED = "#7c7c7c"
FAINT = "#555555"
HOVER = "#222222"
ACCENT = "#5b8cff"
ACCENT_FG = "#ffffff"
ACCENT_HOVER = "#6f9bff"
OK_GREEN = "#5ad17a"
BAD_RED = "#ff6b6b"

CheckResult = tuple[bool, str]


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
    """Make just-installed tools (ffmpeg) visible to this process without a
    restart. Windows: reload PATH from the registry. macOS/Linux: add the usual
    Homebrew / local-bin locations (desktop launches don't inherit shell PATH)."""
    if IS_WINDOWS:
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
            "/opt/homebrew/bin", "/opt/homebrew/sbin",
            "/usr/local/bin", "/usr/local/sbin",
            "/usr/bin", "/bin", "/snap/bin",
            f"{home}/.local/bin", f"{home}/bin",
        ]
        _add_to_path([d for d in candidates if os.path.isdir(d)])


def run(cmd: list[str], timeout: float = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW
    )


def _stream(cmd: list[str], log) -> bool:
    log(f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, creationflags=NO_WINDOW,
        )
    except FileNotFoundError as e:
        log(f"ERROR: {e}")
        return False
    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    return proc.wait() == 0


# --- checks ---

def check_python() -> CheckResult:
    v = sys.version_info
    ok = v >= (3, 8)
    return ok, f"Python {v.major}.{v.minor}.{v.micro}" + ("" if ok else " (need >= 3.8)")


def check_pip() -> CheckResult:
    try:
        r = run([sys.executable, "-m", "pip", "--version"], timeout=20)
        if r.returncode == 0:
            return True, (r.stdout.strip().splitlines() or ["pip"])[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False, "pip not available"


def check_ffmpeg() -> CheckResult:
    exe = shutil.which("ffmpeg")
    if not exe:
        return False, "not on PATH (Whisper needs it to read audio)"
    try:
        r = run([exe, "-version"], timeout=15)
        first = (r.stdout.splitlines() or ["ffmpeg"])[0]
        return True, first
    except (OSError, subprocess.TimeoutExpired):
        return True, exe


def check_whisper() -> CheckResult:
    try:
        import whisper
        ver = getattr(whisper, "__version__", "installed")
        return True, f"openai-whisper {ver}"
    except ImportError:
        return False, "openai-whisper not installed"


def check_torch() -> CheckResult:
    try:
        import torch
        cuda = torch.cuda.is_available()
        dev = "CUDA GPU available" if cuda else "CPU only (slower, still works)"
        return True, f"torch {torch.__version__} - {dev}"
    except ImportError:
        return False, "PyTorch not installed (comes with openai-whisper)"


def check_whisper_cli() -> CheckResult:
    if shutil.which("whisper"):
        return True, "whisper command on PATH"
    bindir = Path(sys.executable).parent
    name = "whisper.exe" if IS_WINDOWS else "whisper"
    for cand in (bindir / "Scripts" / name, bindir / name):
        if cand.exists():
            return True, str(cand)
    try:
        import whisper  # noqa: F401
        return True, "module form (python -m whisper)"
    except ImportError:
        return False, "whisper CLI not found"


# --- fixes ---

def fix_ffmpeg(log) -> bool:
    if IS_WINDOWS:
        if shutil.which("winget") is None:
            log("winget not found. Install ffmpeg manually from https://ffmpeg.org/download.html")
            log("then add its bin folder to PATH.")
            webbrowser.open("https://www.gyan.dev/ffmpeg/builds/")
            return False
        ok = _stream(
            ["winget", "install", "--id", "Gyan.FFmpeg", "-e",
             "--accept-package-agreements", "--accept-source-agreements"],
            log,
        )
        log("")
        log("NOTE: you may need to CLOSE and REOPEN this tool (and the main app)")
        log("for the new PATH entry to take effect, then click Recheck.")
        return ok
    if IS_MAC:
        if shutil.which("brew") is None:
            log("Homebrew not found. Install from https://brew.sh then run: brew install ffmpeg")
            webbrowser.open("https://brew.sh")
            return False
        return _stream(["brew", "install", "ffmpeg"], log)
    return _stream(["sudo", "apt-get", "install", "-y", "ffmpeg"], log)


def fix_whisper(log) -> bool:
    log("Installing openai-whisper (this also installs PyTorch -- large, be patient)...")
    return _stream(
        [sys.executable, "-m", "pip", "install", "-U", "openai-whisper"], log
    )


# CUDA wheel index. cu128 supports modern NVIDIA GPUs (RTX 20-series .. 50-series
# / Blackwell). Very old GPUs may need cu121 or cu118 instead.
NVIDIA_CUDA_INDEX = "https://download.pytorch.org/whl/cu128"


def has_nvidia_gpu() -> bool:
    if shutil.which("nvidia-smi"):
        return True
    if IS_WINDOWS and os.path.exists(r"C:\Windows\System32\nvidia-smi.exe"):
        return True
    return False


def check_gpu() -> CheckResult:
    """Reports GPU status and, on NVIDIA machines, whether the CUDA PyTorch
    build is installed (the plain `pip install openai-whisper` pulls CPU torch)."""
    nvidia = has_nvidia_gpu()
    try:
        import torch
        if torch.cuda.is_available():
            return True, f"CUDA enabled - {torch.cuda.get_device_name(0)}"
        if nvidia:
            return False, ("NVIDIA GPU found, but CPU-only PyTorch is installed -- "
                           "click to install the CUDA build")
        return True, "no NVIDIA GPU - using CPU (works fine)"
    except ImportError:
        if nvidia:
            return False, "NVIDIA GPU found -- install whisper, then the CUDA build"
        return True, "no NVIDIA GPU - using CPU (works fine)"


def fix_cuda_torch(log) -> bool:
    if not has_nvidia_gpu():
        log("No NVIDIA GPU detected -- CPU PyTorch is correct here. Nothing to do.")
        return True
    log("NVIDIA GPU detected. Installing the CUDA build of PyTorch (cu128).")
    log("This replaces the CPU build; large download (~2-3 GB), be patient.")
    _stream([sys.executable, "-m", "pip", "uninstall", "-y", "torch"], log)
    ok = _stream(
        [sys.executable, "-m", "pip", "install", "torch", "--index-url", NVIDIA_CUDA_INDEX],
        log,
    )
    if ok:
        log("")
        log("Installed. If CUDA still isn't available on a very old GPU, try a")
        log("different index (cu121 or cu118) at download.pytorch.org/whl.")
    return ok


# --- registry ---

@dataclass
class Check:
    key: str
    label: str
    desc: str
    fn: Callable[[], CheckResult]
    fix_label: Optional[str] = None
    fix_fn: Optional[Callable[[Callable[[str], None]], bool]] = None
    required: bool = True
    ok: Optional[bool] = field(default=None, init=False)
    detail: str = field(default="", init=False)


CHECKS: list[Check] = [
    Check("python", "Python 3", "Runs the app.", check_python),
    Check("pip", "pip", "Installs Python packages.", check_pip),
    Check("ffmpeg", "ffmpeg", "Decodes audio/video for Whisper.",
          check_ffmpeg, "Install", fix_ffmpeg),
    Check("whisper", "openai-whisper", "The speech-recognition package.",
          check_whisper, "Install (pip)", fix_whisper),
    Check("torch", "PyTorch", "Deep-learning backend (installed with whisper).",
          check_torch, "Install (pip)", fix_whisper),
    Check("cli", "whisper command", "CLI the GUI calls to transcribe.",
          check_whisper_cli, "Install (pip)", fix_whisper),
    Check("cuda", "GPU acceleration",
          "NVIDIA CUDA makes transcription much faster (optional; CPU works too).",
          check_gpu, "Install CUDA PyTorch", fix_cuda_torch, required=False),
]


class SetupApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Setup - Whisper Transcriber")
        root.geometry("800x620")
        root.minsize(680, 520)
        self._busy = False
        self._rows: dict[str, dict] = {}
        self._build()
        self.recheck()

    def _build(self):
        head = ttk.Frame(self.root)
        head.pack(fill=tk.X, padx=12, pady=(12, 6))
        ttk.Label(head, text="Dependency check", font=(UI_FAMILY,14, "bold")).pack(anchor=tk.W)
        ttk.Label(
            head,
            text="Install anything red. The openai-whisper download is large "
                 "(PyTorch); ffmpeg installs via winget.",
            foreground=MUTED,
        ).pack(anchor=tk.W, pady=(2, 0))

        rows = ttk.Frame(self.root)
        rows.pack(fill=tk.X, padx=12, pady=(8, 0))
        for c in CHECKS:
            r = ttk.Frame(rows)
            r.pack(fill=tk.X, pady=2)
            st = ttk.Label(r, text="...", width=2, font=(UI_FAMILY,12, "bold"))
            st.pack(side=tk.LEFT, padx=(0, 6))
            tf = ttk.Frame(r)
            tf.pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Label(tf, text=c.label, font=(UI_FAMILY,10, "bold")).pack(anchor=tk.W)
            dl = ttk.Label(tf, text=c.desc, foreground=MUTED)
            dl.pack(anchor=tk.W)
            btn = None
            if c.fix_label and c.fix_fn:
                btn = ttk.Button(r, text=c.fix_label, width=14,
                                 command=lambda x=c: self.run_fix(x))
                btn.pack(side=tk.RIGHT)
            self._rows[c.key] = {"status": st, "detail": dl, "fix": btn}

        ctl = ttk.Frame(self.root)
        ctl.pack(fill=tk.X, padx=12, pady=(8, 4))
        self.summary = tk.StringVar(value="Checking...")
        ttk.Label(ctl, textvariable=self.summary, font=(UI_FAMILY,10, "bold")).pack(side=tk.LEFT)
        ttk.Button(ctl, text="Close", command=self.root.destroy).pack(side=tk.RIGHT)
        self.install_btn = ttk.Button(ctl, text="Install all missing",
                                      style="Accent.TButton", command=self.install_all)
        self.install_btn.pack(side=tk.RIGHT, padx=(4, 8))
        self.recheck_btn = ttk.Button(ctl, text="Recheck", command=self.recheck)
        self.recheck_btn.pack(side=tk.RIGHT, padx=4)

        lf = ttk.Frame(self.root)
        lf.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))
        ttk.Label(lf, text="LOG", foreground=MUTED,
                  font=(UI_FAMILY,8, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.logw = scrolledtext.ScrolledText(
            lf, height=14, font=(MONO_FAMILY, 9), state="disabled", wrap=tk.WORD,
            relief="flat", borderwidth=0, bg=PANEL, fg="#c8c8c8",
            insertbackground=TEXT, highlightthickness=1,
            highlightbackground=BORDER, highlightcolor=BORDER,
        )
        self.logw.pack(fill=tk.BOTH, expand=True)

    def log(self, line: str):
        self.root.after(0, self._append, line)

    def _append(self, line: str):
        self.logw.configure(state="normal")
        self.logw.insert(tk.END, line + "\n")
        self.logw.see(tk.END)
        self.logw.configure(state="disabled")

    def _set_busy(self, b: bool):
        self._busy = b
        s = "disabled" if b else "normal"
        self.recheck_btn.configure(state=s)
        self.install_btn.configure(state=s)
        for row in self._rows.values():
            if row["fix"] is not None:
                row["fix"].configure(state=s)

    def recheck(self):
        if self._busy:
            return
        self._set_busy(True)
        self.summary.set("Checking...")
        threading.Thread(target=self._recheck_worker, daemon=True).start()

    def _recheck_worker(self):
        ensure_tool_paths()
        for c in CHECKS:
            try:
                c.ok, c.detail = c.fn()
            except Exception as e:
                c.ok, c.detail = False, f"check failed: {e}"
            self.root.after(0, self._update_row, c)
        self.root.after(0, self._update_summary)
        self.root.after(0, self._set_busy, False)

    def _update_row(self, c: Check):
        row = self._rows[c.key]
        row["status"].configure(text="OK" if c.ok else "X",
                                foreground=OK_GREEN if c.ok else BAD_RED)
        row["detail"].configure(text=f"{c.desc}   -   {c.detail}")
        if row["fix"] is not None:
            row["fix"].state(["disabled"] if c.ok else ["!disabled"])

    def _update_summary(self):
        req = [c for c in CHECKS if c.required]
        ready = sum(1 for c in req if c.ok)
        if ready == len(req):
            self.summary.set(f"All set - {ready}/{len(req)} required ready. Launch the app!")
        else:
            miss = [c.label for c in req if not c.ok]
            self.summary.set(f"{ready}/{len(req)} ready. Missing: " + ", ".join(miss))

    def run_fix(self, c: Check):
        if self._busy or not c.fix_fn:
            return
        self._set_busy(True)
        self.log("")
        self.log(f"--- Installing: {c.label} ---")
        threading.Thread(target=self._fix_worker, args=(c,), daemon=True).start()

    def _fix_worker(self, c: Check):
        try:
            ok = bool(c.fix_fn(self.log))
        except Exception as e:
            self.log(f"ERROR: {e}")
            ok = False
        self.log(f"--- {'OK' if ok else 'did not complete'}: {c.label} ---")
        ensure_tool_paths()
        for c2 in CHECKS:
            try:
                c2.ok, c2.detail = c2.fn()
            except Exception:
                pass
            self.root.after(0, self._update_row, c2)
        self.root.after(0, self._update_summary)
        self.root.after(0, self._set_busy, False)

    def install_all(self):
        if self._busy:
            return
        missing = [c for c in CHECKS if c.ok is False and c.fix_fn is not None]
        if not missing:
            messagebox.showinfo("Setup", "Nothing to install - all set.")
            return
        # de-dup fixes that share a function (whisper/torch/cli all = pip install)
        seen = set()
        plan = []
        for c in missing:
            key = c.fix_fn
            if key not in seen:
                seen.add(key)
                plan.append(c)
        self._set_busy(True)
        threading.Thread(target=self._install_worker, args=(plan,), daemon=True).start()

    def _install_worker(self, plan: list[Check]):
        for c in plan:
            self.log("")
            self.log(f"--- Installing: {c.label} ---")
            try:
                ok = bool(c.fix_fn(self.log))
            except Exception as e:
                self.log(f"ERROR: {e}")
                ok = False
            self.log(f"--- {'OK' if ok else 'did not complete'}: {c.label} ---")
        ensure_tool_paths()
        for c2 in CHECKS:
            try:
                c2.ok, c2.detail = c2.fn()
            except Exception:
                pass
            self.root.after(0, self._update_row, c2)
        self.root.after(0, self._update_summary)
        self.root.after(0, self._set_busy, False)


def _theme(root):
    root.configure(bg=BG)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=BG, foreground=TEXT, fieldbackground=FIELD,
                bordercolor=BORDER, focuscolor=BG, font=(UI_FAMILY,10),
                lightcolor=BORDER, darkcolor=BORDER)
    s.configure("TFrame", background=BG)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("TButton", background=PANEL, foreground=TEXT, bordercolor=BORDER,
                relief="flat", padding=(14, 8))
    s.map("TButton", background=[("active", HOVER), ("disabled", "#131313")],
          foreground=[("disabled", FAINT)], bordercolor=[("active", "#3a3a3a")])
    s.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_FG,
                relief="flat", padding=(16, 8), font=(UI_FAMILY, 10, "bold"))
    s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#2a2a2a")],
          foreground=[("disabled", "#666666")])
    s.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                bordercolor=BG, arrowcolor=MUTED, relief="flat", width=12)
    s.map("Vertical.TScrollbar", background=[("active", "#333333")])


def main():
    root = tk.Tk()
    _theme(root)
    SetupApp(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        messagebox.showerror("Setup", f"Fatal error:\n{e}")
        sys.exit(1)
