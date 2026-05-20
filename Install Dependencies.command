#!/bin/bash
# Whisper Transcriber dependency setup for macOS / Linux.
# First-time setup (once): open Terminal in this folder and run
#   chmod +x "Install Dependencies.command" "Whisper Transcriber.command"
# Then double-click this file (macOS) or run: ./"Install Dependencies.command"
cd "$(dirname "$0")" || exit 1

if command -v python3 >/dev/null 2>&1; then
    exec python3 setup_whisper.py "$@"
elif command -v python >/dev/null 2>&1; then
    exec python setup_whisper.py "$@"
else
    echo
    echo "Python 3 is not installed -- it's needed to run the setup tool."
    echo "  macOS:  https://www.python.org/downloads/   (or: brew install python python-tk)"
    echo "  Linux:  sudo apt install python3 python3-tk"
    echo
    read -n 1 -s -r -p "Press any key to close..."
    echo
fi
