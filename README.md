# jap-video-sub

Turn a **Japanese-audio video** (1–2 hr lectures, talks, anime, etc.) into a
**time-synced English `.srt`** — offline-first, on Apple Silicon.

```
video.mp4
   │  ① ffmpeg        16kHz mono WAV          (local, fast)
   ▼
audio.wav
   │  ② mlx-whisper   Japanese SRT + timing   (local, M1-native, large-v3)
   ▼
ja.srt
   │  ③ OpenAI        context-aware JA→EN      (only tiny text leaves the Mac)
   ▼
video.en.srt   ← final English subtitles
```

**The big media file never leaves your machine.** Transcription is 100% local.
Only the small text transcript (a few KB) is sent to OpenAI for translation,
and every timestamp from Whisper is preserved exactly.

## Setup

```bash
cd jap_video_sub
uv sync
cp .env.example .env        # then add your OPENAI_API_KEY
```

Requires `ffmpeg` (`brew install ffmpeg`). The Whisper model (~1.5 GB for
`large-v3`) downloads once on first run and is cached.

## Usage

Full pipeline:

```bash
uv run jap-video-sub run lecture.mp4
# → lecture.en.srt
```

Useful options:

```bash
uv run jap-video-sub run lecture.mp4 \
  -o subs.srt \                    # output path
  -w turbo \                       # faster Whisper model (large-v3 | turbo | medium | small)
  -m gpt-4o \                      # OpenAI model
  -n "University physics lecture; lecturer is Dr. Tanaka" \  # context → better accuracy
  --keep-japanese                  # also write the Japanese .srt
```

Run the stages separately (e.g. verify the Japanese before paying for translation):

```bash
uv run jap-video-sub transcribe lecture.mp4          # → lecture.jvs/ja.srt
uv run jap-video-sub translate lecture.jvs/ja.srt    # → ...en.srt
```

## Resume / caching

Intermediate files live in `<video>.jvs/` (`audio.wav`, `ja.srt`). Re-running
skips finished steps automatically. Use `--force` to redo everything.

## Tips for accuracy

- **`--notes` matters.** A one-line description of the topic and any proper
  nouns/character names keeps Whisper and the translator consistent.
- `large-v3` is the most accurate for Japanese; `turbo` is ~4× faster with a
  small accuracy hit — good for a first pass.
- Translation runs in batches with rolling context, so names and tone stay
  consistent across the whole video.

## Performance (Apple M1, 16 GB)

A 90-minute video transcribes in roughly **5–15 min** with `large-v3`
(faster with `turbo`). Translation of the text takes a minute or two and costs
a few cents.
