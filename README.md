# Whisper Transcriber

A simple, black-and-minimalist desktop GUI for [OpenAI Whisper](https://github.com/openai/whisper) — pick an audio or video file, choose a model, and get a transcript. Cross-platform (Windows, macOS, Linux), with a built-in dependency installer and automatic GPU acceleration when available.

> Built with Python + Tkinter (standard library only). It shells out to the `whisper` CLI from the `openai-whisper` package.

## Features

- Transcribe or translate audio/video (mp3, wav, m4a, mp4, mkv, …)
- Model picker: `tiny` → `large`, plus `turbo`
- Language auto-detect or manual selection
- Output formats: txt, srt, vtt, tsv, json (or all)
- Live progress log, Cancel button, one-click "Open output folder"
- **GPU acceleration** (NVIDIA CUDA) used automatically when available; CPU fallback otherwise
- **Dependency installer GUI** that checks/installs ffmpeg, openai-whisper, and PyTorch
- Dark, minimalist UI with a single accent color

## Requirements

- Python 3.8+ (with Tkinter — included in the python.org installers)
- [ffmpeg](https://ffmpeg.org/) on PATH
- `openai-whisper` (pulls in PyTorch)

The included setup tool installs ffmpeg + openai-whisper for you.

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

- **NVIDIA:** install the CUDA build of PyTorch matching your GPU, e.g.
  ```bash
  pip install torch --index-url https://download.pytorch.org/whl/cu128
  ```
  (use the index that matches your GPU/driver; cu128+ is required for RTX 50-series / Blackwell). The app auto-detects CUDA and shows "GPU acceleration" in the header.
- **No GPU / CPU:** works out of the box; stick to `tiny`/`base`/`turbo` for reasonable speed.

## Project structure

| File | Purpose |
|---|---|
| `whisper_gui.py` | The transcription GUI |
| `setup_whisper.py` | Dependency checker / installer GUI |
| `Whisper Transcriber.bat` / `.command` | App launchers (Windows / macOS-Linux) |
| `Install Dependencies.bat` / `.command` | Setup launchers |

## Credits

Speech recognition by [OpenAI Whisper](https://github.com/openai/whisper) (MIT). This project is an independent GUI wrapper and is not affiliated with OpenAI.

## License

MIT — see [LICENSE](LICENSE).
