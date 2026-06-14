"""Local Japanese speech-to-text using Apple-Silicon-native MLX Whisper."""

from __future__ import annotations

from pathlib import Path

from .srt import Segment

# Friendly name -> mlx-community HF repo.
# large-v3 = best Japanese accuracy. turbo = ~4x faster, slightly less accurate.
MODELS = {
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
    "medium": "mlx-community/whisper-medium-mlx",
    "small": "mlx-community/whisper-small-mlx",
}


def transcribe(
    audio_path: Path,
    model: str = "large-v3",
    initial_prompt: str | None = None,
    verbose: bool | None = None,
    refine: bool = True,
    split_gap: float = 0.8,
) -> list[Segment]:
    """Transcribe Japanese audio to time-stamped Japanese segments.

    The model weights download once from Hugging Face and are then cached.

    verbose=None  -> live tqdm progress bar over the audio (with ETA)
    verbose=True  -> progress bar AND each decoded segment printed
    verbose=False -> silent

    refine=True snaps each cue to its actual spoken word boundaries and splits
    a cue wherever speech pauses for more than `split_gap` seconds, which fixes
    most off-by-a-beat sync and over-long-block issues.
    """
    import mlx_whisper  # imported lazily so `--help` etc. stay fast

    repo = MODELS.get(model, model)  # allow passing a raw repo id too
    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo=repo,
        language="ja",
        task="transcribe",
        word_timestamps=True,
        initial_prompt=initial_prompt,
        condition_on_previous_text=True,
        verbose=verbose,
    )

    raw = result.get("segments", [])
    segments = _refine(raw, split_gap) if refine else _plain(raw)
    # renumber 1..N after any splitting/merging
    for i, seg in enumerate(segments, start=1):
        seg.index = i
    return segments


def _plain(raw: list[dict]) -> list[Segment]:
    """Fallback: use Whisper's coarse segment-level timestamps as-is."""
    out: list[Segment] = []
    for seg in raw:
        text = (seg.get("text") or "").strip()
        if text:
            out.append(Segment(0, float(seg["start"]), float(seg["end"]), text))
    return out


def _refine(raw: list[dict], split_gap: float) -> list[Segment]:
    """Rebuild cues from word-level timestamps for tighter sync.

    - Each cue starts/ends on a real spoken word (no silence padding).
    - A long internal pause (> split_gap) starts a new cue, so two utterances
      separated by silence don't share one timestamp.
    """
    out: list[Segment] = []
    for seg in raw:
        words = [w for w in (seg.get("words") or []) if w.get("word", "").strip()]
        if not words:
            # No word timings (e.g. music/non-speech) — fall back to segment span.
            text = (seg.get("text") or "").strip()
            if text:
                out.append(Segment(0, float(seg["start"]), float(seg["end"]), text))
            continue

        cue_words: list[dict] = []
        prev_end: float | None = None
        for w in words:
            if prev_end is not None and float(w["start"]) - prev_end > split_gap:
                out.append(_cue_from_words(cue_words))
                cue_words = []
            cue_words.append(w)
            prev_end = float(w["end"])
        if cue_words:
            out.append(_cue_from_words(cue_words))
    return out


def _cue_from_words(words: list[dict]) -> Segment:
    text = "".join(w["word"] for w in words).strip()
    start = float(words[0]["start"])
    end = float(words[-1]["end"])
    if end <= start:  # guard against zero/negative-length cues
        end = start + 0.3
    return Segment(0, start, end, text)
