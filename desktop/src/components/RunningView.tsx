// The processing screen. The timeline is the hero; below it, a compact readout
// of the chunk currently being worked, plus overall progress and ETA.

import type { JobState } from "../useJob";
import { overallPercent } from "../useJob";
import { Timeline } from "./Timeline";
import { clock, dur, basename } from "../format";

interface Props {
  state: JobState;
  onCancel: () => void;
}

export function RunningView({ state, onCancel }: Props) {
  const active =
    state.chunks.find((c) => c.stage === "transcribing" || c.stage === "translating") ??
    state.chunks.find((c) => c.stage !== "done");

  const stageLabel = active
    ? active.stage === "transcribing"
      ? "Transcribing"
      : active.stage === "translating"
        ? "Translating"
        : "Preparing"
    : "Working";

  const pct = overallPercent(state);

  // A model is downloading (first run). Show a DISTINCT download bar + location,
  // not the transcribe/translate progress — that's the whole point here.
  if (state.download) {
    const d = state.download;
    const mb = (b: number) => (b / 1048576).toFixed(0);
    return (
      <section className="running" data-testid="running">
        <header className="running__head">
          <div>
            <p className="running__file mono">{basename(state.video ?? "")}</p>
            <h2 className="running__stage" data-testid="running-stage">
              Downloading speech model
              <span className="running__chunkno mono"> · {d.model}</span>
            </h2>
          </div>
          <button className="btn btn--ghost" data-testid="cancel" onClick={onCancel}>
            Cancel
          </button>
        </header>
        <div className="overall">
          <div className="overall__bar">
            <span
              className="overall__fill"
              style={{ width: `${d.percent}%` }}
              data-testid="download-fill"
            />
          </div>
          <div className="overall__meta mono">
            <span data-testid="download-pct">{d.percent}%</span>
            {d.totalBytes > 0 && <span>{mb(d.completedBytes)} / {mb(d.totalBytes)} MB</span>}
          </div>
        </div>
        <p className="running__hint">
          First-time setup — downloading the speech model (one-time, cached after
          this). Saving to <code>{d.location}</code>
        </p>
      </section>
    );
  }

  // The run was requested but the CLI hasn't emitted its first event yet. On a
  // fresh install this stretch can be long (installing deps + downloading the
  // ~3 GB model), so make it explicit rather than showing a dead "0%".
  if (state.status === "starting") {
    return (
      <section className="running" data-testid="running">
        <header className="running__head">
          <div>
            <p className="running__file mono">{basename(state.video ?? "")}</p>
            <h2 className="running__stage" data-testid="running-stage">
              Starting…
            </h2>
          </div>
          <button className="btn btn--ghost" data-testid="cancel" onClick={onCancel}>
            Cancel
          </button>
        </header>
        <p className="running__hint">
          Preparing the engine. The first run can take a few minutes while it sets
          up and downloads the speech model (cached for next time).
        </p>
      </section>
    );
  }

  return (
    <section className="running" data-testid="running">
      <header className="running__head">
        <div>
          <p className="running__file mono">{basename(state.video ?? "")}</p>
          <h2 className="running__stage" data-testid="running-stage">
            {stageLabel}
            {active ? <span className="running__chunkno mono"> · chunk {active.index}/{state.total}</span> : null}
          </h2>
        </div>
        <button className="btn btn--ghost" data-testid="cancel" onClick={onCancel}>
          Cancel
        </button>
      </header>

      <div className="overall">
        <div className="overall__bar">
          <span
            className="overall__fill"
            style={{ width: `${pct}%` }}
            data-testid="overall-fill"
          />
        </div>
        <div className="overall__meta mono">
          <span data-testid="overall-pct">{pct}%</span>
          {state.etaSeconds > 0 && <span>{dur(state.etaSeconds)} left</span>}
        </div>
      </div>

      <Timeline
        chunks={state.chunks}
        duration={state.duration ?? 0}
        activeIndex={active?.index}
      />

      {active && (
        <dl className="ledger" data-testid="ledger">
          <div>
            <dt>Range</dt>
            <dd className="mono">
              {clock(active.start)}–{clock(active.end)}
            </dd>
          </div>
          <div>
            <dt>Transcribe</dt>
            <dd className="mono">
              {active.jaLines != null
                ? `${active.jaLines} lines · ${active.peakGb?.toFixed(1)} GB peak`
                : active.stage === "transcribing"
                  ? active.transcribeTotal
                    ? `${Math.round(((active.transcribeDone ?? 0) / active.transcribeTotal) * 100)}% listened`
                    : "listening…"
                  : "—"}
            </dd>
          </div>
          <div>
            <dt>Translate</dt>
            <dd className="mono">
              {active.translateTotal
                ? `${active.translateDone ?? 0}/${active.translateTotal} lines`
                : active.enLines != null
                  ? `${active.enLines} lines`
                  : "—"}
            </dd>
          </div>
        </dl>
      )}
    </section>
  );
}
