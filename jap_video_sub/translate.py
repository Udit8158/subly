"""Context-aware JA->EN translation via OpenAI, preserving segment alignment.

Segments are translated in batches. Each batch is sent as JSON keyed by the
segment id, and the model must return the same ids — so timestamps are never
lost or shifted. A rolling tail of previously translated lines is passed as
context so names, tone, and terminology stay consistent across the whole video.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable

from .srt import Segment, with_text

DEFAULT_MODEL = os.environ.get("JVS_OPENAI_MODEL", "gpt-4o")

SYSTEM_PROMPT = """\
You are a professional Japanese-to-English subtitle translator.
Translate each Japanese subtitle line into natural, fluent, concise English
suitable for on-screen subtitles. Rules:
- Preserve meaning and tone; do not add or omit information.
- Keep it idiomatic English, not word-for-word.
- One translation per input line; never merge or split lines.
- Keep proper nouns/names consistent across lines.
- Return ONLY valid JSON of the form: {"lines": [{"id": <int>, "en": "<text>"}]}.
- Include every id you were given, exactly once."""


class TranslationError(RuntimeError):
    pass


def _client():
    from openai import OpenAI

    if not os.environ.get("OPENAI_API_KEY"):
        raise TranslationError(
            "OPENAI_API_KEY is not set. Put it in a .env file or export it."
        )
    return OpenAI()


def _call(client, model: str, system: str, user: str, retries: int = 4) -> str:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as e:  # network / rate-limit / transient API errors
            last_err = e
            time.sleep(min(2 ** attempt, 30))
    raise TranslationError(f"OpenAI request failed after {retries} tries: {last_err}")


def _translate_batch(
    client,
    model: str,
    batch: list[Segment],
    notes: str,
    context_tail: list[str],
) -> dict[int, str]:
    payload = {"lines": [{"id": seg.index, "ja": seg.text} for seg in batch]}
    context_parts = []
    if notes:
        context_parts.append(f"About this video (use for terminology/names):\n{notes}")
    if context_tail:
        joined = "\n".join(context_tail[-6:])
        context_parts.append(f"Preceding English lines (for continuity):\n{joined}")
    context = "\n\n".join(context_parts)
    user = (
        (context + "\n\n" if context else "")
        + "Translate these lines to English:\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    raw = _call(client, model, SYSTEM_PROMPT, user)
    try:
        data = json.loads(raw)
        out = {int(item["id"]): str(item["en"]).strip() for item in data["lines"]}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise TranslationError(f"Could not parse model output as JSON: {e}\n{raw[:500]}")
    return out


def translate_segments(
    segments: list[Segment],
    model: str | None = None,
    batch_size: int = 40,
    notes: str = "",
    progress: Callable[[int, int], None] | None = None,
) -> list[Segment]:
    """Return new segments with English text, timestamps unchanged."""
    if not segments:
        return []
    model = model or DEFAULT_MODEL
    client = _client()

    translated: list[Segment] = []
    context_tail: list[str] = []
    total = len(segments)

    for start in range(0, total, batch_size):
        batch = segments[start : start + batch_size]
        out = _translate_batch(client, model, batch, notes, context_tail)

        # Repair any ids the model dropped by translating them one-by-one.
        missing = [seg for seg in batch if seg.index not in out]
        for seg in missing:
            one = _translate_batch(client, model, [seg], notes, context_tail)
            out.update(one)

        for seg in batch:
            en = out.get(seg.index, seg.text)  # last-resort: keep original
            translated.append(with_text(seg, en))
            context_tail.append(en)

        if progress:
            progress(min(start + batch_size, total), total)

    return translated
