"""
Stable Audio 3 text-to-audio generation worker.

Called as a subprocess by the GUI's "Generate" tab. Loads a Stable Audio 3 model
via stable-audio-tools and writes a .wav. Prints plain progress lines to stdout.

The models are gated: you must have a Hugging Face account, accept the Stability
AI Community License on the model page, and be logged in (`huggingface-cli login`)
before the first download will work.

Usage:
  python generate_worker.py --prompt "..." --model stabilityai/stable-audio-3-medium
      --duration 30 --steps 8 --cfg 1.0 --seed -1 --output out.wav
"""

from __future__ import annotations

import argparse
import sys


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--model", default="stabilityai/stable-audio-3-medium")
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--output", required=True)
    a = ap.parse_args()

    log("Loading libraries…")
    try:
        import torch
        import torchaudio
        from einops import rearrange
        from stable_audio_tools import get_pretrained_model
    except ImportError as e:
        log(f"ERROR: missing dependency: {e}")
        log("Install with:  pip install stable-audio-tools torchaudio einops")
        return 1

    # Plain conditional generation is the canonical text-to-audio path; the
    # inpaint variant is for continuing/filling existing audio. Prefer cond,
    # fall back to inpaint only if cond isn't present.
    gen = None
    try:
        from stable_audio_tools.inference.generation import (
            generate_diffusion_cond as gen,
        )
    except Exception:
        try:
            from stable_audio_tools.inference.generation import (
                generate_diffusion_cond_inpaint as gen,
            )
        except Exception as e:
            log(f"ERROR: no generation function available: {e}")
            return 1

    device = "cuda" if torch.cuda.is_available() else "cpu"
    log(f"Device: {device}")

    log(f"Loading model {a.model} (first run downloads the weights — gated)…")
    try:
        model, config = get_pretrained_model(a.model)
    except Exception as e:
        log(f"ERROR: could not load model: {e}")
        log("If this is an access error, accept the license on the model's HF page")
        log("and run `huggingface-cli login` with a token, then retry.")
        return 1

    sample_rate = config["sample_rate"]
    sample_size = config["sample_size"]
    model = model.to(device)

    log(f"Generating ~{a.duration:.0f}s of audio for: {a.prompt!r} …")
    conditioning = [{"prompt": a.prompt, "seconds_total": float(a.duration)}]
    try:
        output = gen(
            model,
            steps=a.steps,
            cfg_scale=a.cfg,
            conditioning=conditioning,
            sample_size=sample_size,
            seed=a.seed,          # -1 = random
            device=device,
        )
    except Exception as e:
        log(f"ERROR: generation failed: {e}")
        return 1

    log("Post-processing and saving…")
    output = rearrange(output, "b d n -> d (b n)")
    output = output.to(torch.float32)
    peak = torch.max(torch.abs(output))
    if peak > 0:
        output = output / peak
    output = output.clamp(-1, 1).mul(32767).to(torch.int16).cpu()

    # Trim to the requested length (the model generates within its native window).
    want = int(a.duration * sample_rate)
    if 0 < want < output.shape[-1]:
        output = output[:, :want]

    try:
        torchaudio.save(a.output, output, sample_rate)
    except Exception as e:
        log(f"ERROR: could not save wav: {e}")
        return 1

    log(f"Saved {a.output} ({sample_rate} Hz)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
