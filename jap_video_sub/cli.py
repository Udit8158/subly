"""Command-line interface for jap_video_sub.

Pipeline:  video --(ffmpeg)--> audio.wav --(mlx-whisper)--> ja.srt --(openai)--> en.srt

Intermediate files live in `<video>.jvs/` next to the input, so re-running
resumes where it left off. Use --force to redo a step.
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

from . import audio as audio_mod
from . import srt as srt_mod
from . import transcribe as transcribe_mod
from . import translate as translate_mod

app = typer.Typer(
    add_completion=False,
    help="Turn a Japanese-audio video into time-synced English subtitles.",
)
console = Console()


def _workdir(video: Path) -> Path:
    d = video.parent / f"{video.stem}.jvs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _step(msg: str) -> None:
    console.print(f"[bold cyan]›[/] {msg}")


def _done(msg: str) -> None:
    console.print(f"  [green]✓[/] {msg}")


def _get_audio(video: Path, work: Path, force: bool) -> Path:
    wav = work / "audio.wav"
    if wav.exists() and not force:
        _done(f"audio cached → {wav.name}")
        return wav
    _step("Extracting 16kHz mono audio (ffmpeg)…")
    with console.status("[cyan]extracting audio…", spinner="dots"):
        audio_mod.extract_audio(video, wav)
    _done(f"audio → {wav.name}")
    return wav


def _get_japanese(
    wav: Path, work: Path, model: str, notes: str, force: bool, verbose: bool
) -> list[srt_mod.Segment]:
    ja_path = work / "ja.srt"
    if ja_path.exists() and not force:
        _done(f"transcript cached → {ja_path.name}")
        return srt_mod.read(ja_path)
    _step(f"Transcribing Japanese with Whisper '{model}' (local, first run downloads the model)…")
    console.print("  [dim]a live progress bar with ETA appears below as the audio is decoded[/]")
    # verbose=None -> progress bar only; True -> bar + per-segment text
    segments = transcribe_mod.transcribe(
        wav, model=model, initial_prompt=notes or None, verbose=(True if verbose else None)
    )
    srt_mod.write(ja_path, segments)
    _done(f"{len(segments)} segments → {ja_path.name}")
    return segments


def _translate(
    segments: list[srt_mod.Segment],
    work: Path,
    out: Path,
    model: str | None,
    notes: str,
    force: bool,
) -> Path:
    if out.exists() and not force:
        _done(f"translation cached → {out}")
        return out
    _step(f"Translating {len(segments)} segments JA→EN (OpenAI)…")
    with console.status("[cyan]translating…", spinner="dots") as status:

        def progress(done: int, total: int) -> None:
            status.update(f"[cyan]translating… {done}/{total} segments")

        english = translate_mod.translate_segments(
            segments, model=model, notes=notes, progress=progress
        )
    srt_mod.write(out, english)
    _done(f"English subtitles → {out}")
    return out


@app.command()
def run(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Japanese-audio video/audio file."),
    output: Path = typer.Option(None, "--output", "-o", help="Output .srt path (default: <video>.en.srt)."),
    whisper_model: str = typer.Option("large-v3", "--whisper-model", "-w", help="large-v3 | turbo | medium | small."),
    openai_model: str = typer.Option(None, "--openai-model", "-m", help="OpenAI model (default: gpt-4o or $JVS_OPENAI_MODEL)."),
    notes: str = typer.Option("", "--notes", "-n", help="Context about the video (topic, character names) to improve accuracy."),
    force: bool = typer.Option(False, "--force", "-f", help="Redo every step, ignoring cached files."),
    keep_japanese: bool = typer.Option(False, "--keep-japanese", help="Also copy the Japanese .srt next to the output."),
    verbose: bool = typer.Option(False, "--verbose", help="Stream Whisper decoding output."),
) -> None:
    """Full pipeline: video → English .srt."""
    out = output or video.with_suffix(".en.srt")
    work = _workdir(video)
    console.print(f"[bold]jap-video-sub[/] · {video.name}")

    wav = _get_audio(video, work, force)
    segments = _get_japanese(wav, work, whisper_model, notes, force, verbose)
    if not segments:
        console.print("[red]No speech detected — nothing to translate.[/]")
        raise typer.Exit(1)
    _translate(segments, work, out, openai_model, notes, force)

    if keep_japanese:
        ja_out = out.with_suffix("")
        ja_out = ja_out.parent / f"{ja_out.name}.ja.srt"
        srt_mod.write(ja_out, segments)
        _done(f"Japanese subtitles → {ja_out}")

    console.print(f"\n[bold green]Done.[/] → [bold]{out}[/]")


@app.command()
def transcribe(
    video: Path = typer.Argument(..., exists=True, dir_okay=False, help="Japanese-audio video/audio file."),
    whisper_model: str = typer.Option("large-v3", "--whisper-model", "-w"),
    notes: str = typer.Option("", "--notes", "-n"),
    force: bool = typer.Option(False, "--force", "-f"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Only transcribe: produce the Japanese .srt (no translation)."""
    work = _workdir(video)
    console.print(f"[bold]jap-video-sub transcribe[/] · {video.name}")
    wav = _get_audio(video, work, force)
    _get_japanese(wav, work, whisper_model, notes, force, verbose)
    console.print(f"\n[bold green]Done.[/] → [bold]{work / 'ja.srt'}[/]")


@app.command()
def translate(
    japanese_srt: Path = typer.Argument(..., exists=True, dir_okay=False, help="Existing Japanese .srt to translate."),
    output: Path = typer.Option(None, "--output", "-o", help="Output .srt path (default: <input>.en.srt)."),
    openai_model: str = typer.Option(None, "--openai-model", "-m"),
    notes: str = typer.Option("", "--notes", "-n"),
    force: bool = typer.Option(False, "--force", "-f"),
) -> None:
    """Only translate an existing Japanese .srt → English .srt."""
    out = output or japanese_srt.with_suffix(".en.srt")
    segments = srt_mod.read(japanese_srt)
    console.print(f"[bold]jap-video-sub translate[/] · {japanese_srt.name} ({len(segments)} segments)")
    _translate(segments, japanese_srt.parent, out, openai_model, notes, force)
    console.print(f"\n[bold green]Done.[/] → [bold]{out}[/]")


def main() -> None:
    load_dotenv()
    app()


if __name__ == "__main__":
    main()
