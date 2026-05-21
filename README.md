# Whisper Transcriber

A black-and-minimalist desktop audio toolkit:

- **Transcribe** — pick an audio/video file and get a transcript (OpenAI Whisper / faster-whisper).
- **Generate** — type a prompt and create music or sound effects (Stable Audio 3).

Cross-platform (Windows, macOS, Linux), with a built-in dependency installer and automatic GPU acceleration when available.

> Built with Python + Tkinter (standard library only). It uses **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** (via the `whisper-ctranslate2` CLI) — smaller and ~4× faster than the reference implementation, with no PyTorch dependency — and falls back to [openai-whisper](https://github.com/openai/whisper) if that's what's installed.

## Features

- Transcribe or translate audio/video (mp3, wav, m4a, mp4, mkv, …)
- Model picker: `tiny` → `large`, plus `turbo`
- Language auto-detect or manual selection
- Output formats: txt, srt, vtt, tsv, json (or all)
- **Progress bar** (with ETA from the media duration) plus a live log
- **Transcript preview** tab — read the result in-app without opening the file
- Remembers your last model / language / folders between runs
- Cancel button and one-click "Open output folder"
- **GPU acceleration** (NVIDIA CUDA) used automatically when available; CPU fallback otherwise
- **Dependency installer GUI** that checks/installs ffmpeg, openai-whisper, and PyTorch — and **auto-detects an NVIDIA GPU** to install the matching CUDA build
- **Generate tab** — text-to-audio with [Stable Audio 3](https://huggingface.co/collections/stabilityai/stable-audio-3) (music / SFX)
- Dark, minimalist UI with a single accent color

## Requirements

- Python 3.8+ (with Tkinter — included in the python.org installers)
- [ffmpeg](https://ffmpeg.org/) on PATH
- `whisper-ctranslate2` (the faster-whisper engine; no PyTorch needed)

The included setup tool installs ffmpeg + the engine for you.

## Install & run

### Windows
1. Double-click **`Install Dependencies.bat`** → click **Install all missing**.
2. Double-click **`Whisper Transcriber.bat`**.

### macOS / Linux
1. In a terminal in this folder, make the launchers executable (once):
   ```bash
   chmod +x "Install Dependencies.command" "Whisper Transcriber.command"
   ```
2. Run **`Install Dependencies.command`**, then **`Whisper Transcriber.command`**.
   - macOS Tkinter: use the python.org installer, or `brew install python python-tk`.
   - macOS first launch: right-click → Open to clear Gatekeeper.

Or run directly anywhere:
```bash
python3 setup_whisper.py     # dependency installer
python3 whisper_gui.py       # the app
```

## GPU acceleration

- **NVIDIA:** the faster-whisper engine uses CUDA via CTranslate2. If CUDA isn't
  picked up, install the CUDA 12 libraries:
  ```bash
  pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
  ```
  (the setup tool does this automatically when it detects an NVIDIA GPU.) The app
  auto-detects CUDA and shows "GPU acceleration" in the header.
- **No GPU / CPU:** works out of the box — and faster-whisper is already several
  times faster than the reference engine on CPU.

## "Windows protected your PC" / "Unknown Publisher" warning

When you run a `.bat` you downloaded from the internet, Windows shows a
**security warning** ("The publisher could not be verified", *Unknown Publisher*).
This is **normal and expected** for any unsigned script downloaded from the web —
it does not mean the file is unsafe. You have two options:

- Click **Run** (and, if you like, untick "Always ask before opening this file").
- Or clear the "downloaded from the internet" flag for the whole folder once —
  in PowerShell:
  ```powershell
  Get-ChildItem "<path to Whisper Transcriber folder>" -Recurse | Unblock-File
  ```
  (or right-click a file → Properties → tick **Unblock** → OK).

If SmartScreen shows a blue "Windows protected your PC" box, click
**More info → Run anyway**. Removing the warning entirely requires a paid
code-signing certificate, which this free project doesn't use.

## Generate audio (Stable Audio 3)

The **Generate** tab turns a text prompt into a `.wav` using
[Stable Audio 3](https://huggingface.co/collections/stabilityai/stable-audio-3)
(text-to-audio — music and sound effects).

One-time setup:
1. In the setup tool, install **Stable Audio (generation)** — or:
   `pip install stable-audio-tools einops torchaudio`
2. The models are **gated**. On the model page
   (e.g. `stabilityai/stable-audio-3-medium`), sign in and **accept the
   Stability AI Community License**, then authorize your machine:
   `huggingface-cli login` (paste a token from huggingface.co/settings/tokens).
3. Open the **Generate** tab, type a prompt (e.g. *"lo-fi hip hop beat, 80 BPM"*),
   pick a model + length, and click **Generate**. The first run downloads the model.

Notes:
- A GPU is strongly recommended (the 2B `medium` model is slow on CPU).
- The Stability AI Community License is free for non-commercial / small use;
  commercial use above their threshold needs a separate license. The model
  weights are not redistributed by this project.

## Storage & OneDrive

- **Model files download once** the first time you use each model — to
  `~/.cache/huggingface` (faster-whisper) or `~/.cache/whisper` (openai-whisper),
  **not** into the app folder. So they won't bloat a OneDrive-synced folder.
  Sizes range from ~75 MB (`tiny`) to ~1.5 GB (`large`).
- Running the app from a **OneDrive** folder works fine. Transcripts you save into
  a OneDrive folder will sync like any other file.
- If OneDrive "Files On-Demand" has made the scripts cloud-only (cloud icon),
  double-clicking downloads them automatically before running.

## Project structure

| File | Purpose |
|---|---|
| `whisper_gui.py` | The GUI (Transcribe + Generate tabs) |
| `generate_worker.py` | Stable Audio 3 text-to-audio worker (called by the Generate tab) |
| `setup_whisper.py` | Dependency checker / installer GUI |
| `Whisper Transcriber.bat` / `.command` | App launchers (Windows / macOS-Linux) |
| `Install Dependencies.bat` / `.command` | Setup launchers |

## Cost & privacy

**100% free and local — no paid services, no API keys, no subscriptions.** Everything
runs offline on your own machine; nothing is uploaded to a cloud service. The only
"costs" are your own electricity, GPU time, and disk space for the downloaded models.

- **Whisper / faster-whisper** (Transcribe): free and open-source, no restrictions.
- **Stable Audio 3** (Generate): free to download and run; a free Hugging Face account
  is needed only to fetch the gated weights. The Stability AI Community License allows
  free non-commercial / small-business use — large-scale **commercial** use of the
  model needs a separate license from Stability (a licensing term, not a usage fee).

## Credits

Speech recognition by [OpenAI Whisper](https://github.com/openai/whisper) (MIT). This project is an independent GUI wrapper and is not affiliated with OpenAI.

## License

MIT — see [LICENSE](LICENSE).
