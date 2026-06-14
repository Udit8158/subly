"""Extract a Whisper-friendly audio track from any video/audio file via ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install it with: brew install ffmpeg"
        )


def extract_audio(src: Path, dst: Path) -> Path:
    """Convert `src` to 16kHz mono 16-bit PCM WAV at `dst`.

    16kHz mono is exactly what Whisper expects, so this avoids any
    resampling inside the model and keeps the file tiny.
    """
    ensure_ffmpeg()
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",                 # overwrite
        "-i", str(src),
        "-vn",                # drop video
        "-ac", "1",           # mono
        "-ar", "16000",       # 16 kHz
        "-c:a", "pcm_s16le",  # 16-bit PCM
        "-loglevel", "error",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{proc.stderr.strip()}")
    if not dst.exists() or dst.stat().st_size == 0:
        raise RuntimeError("ffmpeg produced no audio output.")
    return dst
