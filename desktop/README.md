# Subly · desktop app

A Mac desktop wrapper around the `subly` CLI. Drop a Japanese-audio
video, watch it get transcribed and translated chunk-by-chunk on a live
timeline, and grab the English `.srt`.

> Status: **experimental.** You can run it in dev, or build a clickable
> `Subly.app` / `.dmg` (see [Build a Mac app](#build-a-mac-app-dmg)). The packaged
> app bundles the `subly` CLI **source** and runs it with the user's `uv`, so it
> needs `uv` + `ffmpeg` installed on the machine (full Python bundling +
> signing/notarization is still future work — see [the ship-to-others path](#whats-left-the-ship-to-others-path)).

## Run it (dev)

The sibling `cli/` package must work first:

```bash
cd ../cli && uv sync     # installs the Python CLI (see ../cli/README.md)
```

Then the app:

```bash
cd ../desktop
npm install
npm run dev:electron     # Vite + Electron, with the real CLI behind it
```

To work on just the UI in a browser with fixture data (no Electron, no backend):

```bash
npm run dev              # then open http://localhost:5173/?mock
```

URL flags for browser mode:
- `?mock` — replay the captured event fixture instead of the real CLI.
- `?needkey` — force the API-key onboarding screen (in-memory stub).

## Build a Mac app (.dmg)

Produces a double-clickable `Subly.app` plus a `.dmg`/`.zip` in `release/`:

```bash
cd desktop
npm install
npm run icon      # (re)generate build/icon.icns from the 字 logo — optional
npm run dist      # vite build + electron-builder → release/
```

Output:
- `release/Subly-<version>-arm64.dmg` — the installer to share
- `release/Subly-<version>-arm64-mac.zip` — same app, zipped
- `release/mac-arm64/Subly.app` — the raw app

### What users need

This is an **Apple-Silicon-only** build, and it runs the bundled CLI with the
user's own toolchain, so a recipient needs:

- an **Apple-Silicon (M-series) Mac**
- **`uv`** and **`ffmpeg`**: `brew install uv ffmpeg`
- an **OpenAI API key** (entered on first launch, stored in the Keychain)
- a network connection the first time (downloads the ~3 GB Whisper model;
  cached afterwards in `~/.cache/huggingface`)

On first run, `uv` auto-installs the CLI's Python deps into a writable venv under
the app's data dir (`~/Library/Application Support/Subly/cli-venv`) — no manual
Python setup.

### Opening an unsigned app

The build is **not code-signed/notarized**, so Gatekeeper will warn on first
open. Either:

- **right-click the app → Open → Open**, or
- clear the quarantine flag: `xattr -cr /Applications/Subly.app`

(To ship without this friction you need an Apple Developer ID — see
[the ship-to-others path](#whats-left-the-ship-to-others-path).)

## API key

Translation uses OpenAI. On first launch the app asks for your key and stores it
in the **macOS Keychain** (service `subly`, account `openai-api-key`) —
you can inspect or revoke it in Keychain Access. The key is injected into the
CLI's environment at run time; in dev it also falls back to a `.env` in the
`cli/` package.

## Tests

```bash
npm test                 # typecheck + node tests + Playwright e2e
```

What's covered:

| Test | What it proves |
|---|---|
| `tests/buildArgs.test.mjs` | UI settings map to the correct CLI flags |
| `tests/keychain.test.mjs` | Keychain store → read → update → delete round-trip |
| `tests/bridge.test.mjs` | Spawns the **real CLI** (`--json --simulate`) and parses its event stream — the exact main-process bridge logic |
| `tests/e2e/bridge.spec.ts` | Full setup → running → done flow + the timeline (Playwright, mock source) |
| `tests/e2e/gate.spec.ts` | API-key onboarding gate blocks until a valid key is entered |

The Python side has its own event-contract tests: `uv run --with pytest pytest`
in `../cli` (`cli/tests/test_events.py`).

## Architecture

The UI talks to the pipeline through exactly **one seam**: a subprocess that
emits JSON-lines events (`subly run --json`). Everything else is built on
that contract.

```
┌────────────────────────┐  spawn   ┌──────────────────────────┐
│ Electron + React (UI)   │ ───────▶ │ subly run --json │
│ reducer → timeline/views│ ◀─────── │ 1 JSON event per line     │
└────────────────────────┘  stdout  └──────────────────────────┘
        │ EventSource seam
        ├── ElectronEventSource → real CLI via IPC (production)
        └── MockEventSource     → replays a captured fixture (browser + tests)
```

Key files:

- `electron/main.js` — spawns the CLI, line-buffers stdout, forwards parsed
  events to the renderer over IPC. The **only** place that knows how the
  pipeline is launched: `uv run` from the repo `cli/` in dev, or from the bundled
  `Contents/Resources/cli` when packaged (with a writable `UV_PROJECT_ENVIRONMENT`
  and a PATH augmented to find `uv`/`ffmpeg`). The renderer never changes.
- `electron/buildArgs.js` — RunOptions → CLI argv (unit-tested).
- `electron/keychain.js` — OpenAI key in the Keychain via the `security` CLI.
- `electron/preload.js` — the `contextBridge` exposing a small `window.subly` API.
- `src/eventsource/` — the `EventSource` seam: `types.ts` (the contract, mirrors
  Python `events.py`), `electron.ts`, `mock.ts`.
- `src/useJob.ts` — reducer that turns the event stream into `JobState`. Every
  view reads from this, never from raw events.
- `src/components/Timeline.tsx` — the signature two-stage chunk timeline.
- `src/fixtures/simulate.jsonl` — captured real `--simulate` output; the mock and
  browser dev replay it, so they stay faithful to the contract.

The event contract itself is defined and documented in the CLI:
`../cli/subly/events.py`.

## What's left (the "ship to others" path)

The packaged `.dmg` already bundles the CLI source and auto-provisions its Python
deps via the user's `uv`. To reach **zero-prerequisite**, non-developer
distribution, what remains is:

- bundle Python + `mlx-whisper` so `uv` isn't required (PyInstaller / relocatable uv env)
- bundle a static `ffmpeg` binary so `brew install ffmpeg` isn't required
- a first-run model-download progress screen
- code signing + notarization (needs a paid Apple Developer ID) so Gatekeeper
  doesn't warn
