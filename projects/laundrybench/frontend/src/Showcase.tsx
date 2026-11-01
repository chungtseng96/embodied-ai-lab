import { useEffect, useRef, useState } from "react";
import App from "./App";

type ShowcaseManifest = {
  schema_version: 1;
  source_commit: string;
  source_repository: string;
  candidate_id: string;
  baseline_id: string;
  evidence_kind: "synthetic";
  limitations: string[];
  walkthrough_video_url: string | null;
};

const SOURCE_REPOSITORY = "https://github.com/chungtseng96/embodied-ai-lab";

function isSafeWalkthroughUrl(value: unknown): value is string | null {
  if (value === null) return true;
  if (
    typeof value !== "string" ||
    !/^\/[A-Za-z0-9._/-]+\.(mp4|webm)$/i.test(value)
  ) {
    return false;
  }
  return (
    !value.includes("//") &&
    !value.split("/").some((segment) => segment === "." || segment === "..")
  );
}

function isManifest(value: unknown): value is ShowcaseManifest {
  if (!value || typeof value !== "object") return false;
  const data = value as Partial<ShowcaseManifest>;
  return (
    data.schema_version === 1 &&
    typeof data.source_commit === "string" &&
    /^[0-9a-f]{40}$/i.test(data.source_commit) &&
    data.source_repository === SOURCE_REPOSITORY &&
    typeof data.candidate_id === "string" &&
    data.candidate_id.trim().length > 0 &&
    typeof data.baseline_id === "string" &&
    data.baseline_id.trim().length > 0 &&
    data.baseline_id !== data.candidate_id &&
    data.evidence_kind === "synthetic" &&
    Array.isArray(data.limitations) &&
    data.limitations.every((item) => typeof item === "string") &&
    isSafeWalkthroughUrl(data.walkthrough_video_url)
  );
}

export default function Showcase() {
  const [manifest, setManifest] = useState<ShowcaseManifest | null>(null);
  const [manifestError, setManifestError] = useState("");
  const [started, setStarted] = useState(false);
  const explorerRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let active = true;
    fetch("/showcase.json")
      .then(async (response) => {
        if (!response.ok)
          throw new Error(`Showcase manifest unavailable (${response.status})`);
        const value: unknown = await response.json();
        if (!isManifest(value))
          throw new Error(
            "Showcase manifest does not match the required schema.",
          );
        return value;
      })
      .then((value) => {
        if (active) setManifest(value);
      })
      .catch((error: unknown) => {
        if (active)
          setManifestError(
            error instanceof Error
              ? error.message
              : "Could not load showcase manifest.",
          );
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (started)
      explorerRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
  }, [started]);

  const repositoryUrl = manifest ? SOURCE_REPOSITORY : undefined;
  const commitUrl =
    repositoryUrl && manifest
      ? `${repositoryUrl}/commit/${manifest.source_commit}`
      : undefined;

  return (
    <div className="showcase-page">
      <header className="showcase-header">
        <a
          className="showcase-brand"
          href="#top"
        >
          <span className="brand-mark" aria-hidden="true">
            L<span>↗</span>
          </span>
          <span>
            LaundryBench<small>ROBOT LEARNING LAB</small>
          </span>
        </a>
        <a className="showcase-header-link" href="#explorer">
          Evidence explorer <span aria-hidden="true">↓</span>
        </a>
      </header>

      <main className="showcase-main" id="top">
        <section className="showcase-hero" aria-labelledby="showcase-title">
          <div className="showcase-hero-copy">
            <p className="showcase-kicker">
              <span /> A small robot learning system, built to be inspected
            </p>
            <h1 id="showcase-title">
              Can a robot sort socks from the rest of the laundry?
            </h1>
            <p className="showcase-lede">
              LaundryBench is an evaluation system for laundry sorting with an
              SO-101 arm. It makes each experiment traceable from task and
              policy through episode evidence, human review, and outcome
              metrics. Physical validation is pending.
            </p>
            <div className="showcase-actions">
              <button
                className="primary showcase-cta"
                type="button"
                onClick={() => setStarted(true)}
                disabled={!manifest}
              >
                {manifest
                  ? "Open the evidence explorer"
                  : "Loading showcase data…"}
                <span aria-hidden="true">→</span>
              </button>
              {manifestError && (
                <p className="showcase-error" role="alert">
                  {manifestError}
                </p>
              )}
            </div>
            <div className="showcase-hero-meta">
              <span>
                <i className="showcase-dot" /> Synthetic experiment snapshot
              </span>
              <span>Read-only · no robot controls</span>
            </div>
          </div>
          <div
            className="showcase-visual"
            role="img"
            aria-label="Illustration of an SO-101 arm sorting socks beside other laundry."
          >
            <div className="visual-window-bar">
              <span />
              <span />
              <span />
              <b>laundrybench / evaluation</b>
            </div>
            <div className="visual-scene">
              <div className="visual-label">TASK · SOCK SORTING</div>
              <div className="laundry-bin laundry-left">
                <span className="fabric sock-a" />
                <span className="fabric sock-b" />
                <b>socks</b>
              </div>
              <div className="robot-arm" aria-hidden="true">
                <span className="arm-segment arm-base" />
                <span className="arm-joint joint-one" />
                <span className="arm-segment arm-upper" />
                <span className="arm-joint joint-two" />
                <span className="arm-segment arm-wrist" />
                <span className="arm-gripper" />
              </div>
              <div className="laundry-bin laundry-right">
                <span className="fabric sock-c" />
                <span className="fabric sock-d" />
                <b>other laundry</b>
              </div>
              <div className="visual-camera">
                <span />
                <i />
              </div>
              <div className="visual-caption">
                <span className="visual-caption-pulse" /> Episode evidence ·
                synchronized video + trace
              </div>
            </div>
            <div className="visual-foot">
              <span>SO-101 arm</span>
              <span>Camera</span>
              <span>Episode record</span>
            </div>
          </div>
        </section>

        <div className="synthetic-ribbon" role="note">
          <span className="synthetic-icon" aria-hidden="true">
            !
          </span>
          <div>
            <strong>All experiment outcomes shown here are synthetic.</strong>
            <span>
              The walkthrough is software demonstration footage. Physical
              validation is pending.
            </span>
          </div>
        </div>

        {manifest?.walkthrough_video_url && (
          <section
            className="showcase-video"
            aria-labelledby="showcase-video-title"
          >
            <div>
              <p className="showcase-overline">SOFTWARE WALKTHROUGH</p>
              <h2 id="showcase-video-title">See the review loop in motion.</h2>
              <p>
                This recording shows the interface and evidence navigation. It
                is not physical robot validation.
              </p>
            </div>
            <video
              controls
              preload="metadata"
              src={manifest.walkthrough_video_url}
              aria-label="LaundryBench software walkthrough recording"
            />
          </section>
        )}

        <section
          className="showcase-section contributions"
          aria-labelledby="contribution-title"
        >
          <div className="section-intro">
            <p className="showcase-overline">WHAT I OWNED</p>
            <h2 id="contribution-title">The work is in the evaluation loop.</h2>
            <p>
              I built the software that makes small robot experiments easier to
              run, compare, audit, and learn from.
            </p>
          </div>
          <div className="contribution-grid">
            <article>
              <span className="contribution-icon">01</span>
              <h3>Evaluation design</h3>
              <p>
                Task and protocol contracts turn a laundry pick-and-sort attempt
                into comparable, reviewable episodes.
              </p>
            </article>
            <article>
              <span className="contribution-icon">02</span>
              <h3>Observability</h3>
              <p>
                Recorded outcomes stay linked to video, synchronized action
                traces, run context, and data quality checks.
              </p>
            </article>
            <article>
              <span className="contribution-icon">03</span>
              <h3>Human review</h3>
              <p>
                Reviewers can correct outcomes while preserving the original
                record and seeing exactly what feeds the metrics.
              </p>
            </article>
            <article>
              <span className="contribution-icon">04</span>
              <h3>Robot adapters</h3>
              <p>
                Stable LaundryBench boundaries connect task and evaluation logic
                to robot and policy implementations.
              </p>
            </article>
          </div>
        </section>

        <section
          className="showcase-section architecture"
          aria-labelledby="architecture-title"
        >
          <div className="section-intro">
            <p className="showcase-overline">SYSTEM SHAPE</p>
            <h2 id="architecture-title">
              From an attempt to evidence you can trust.
            </h2>
            <p>
              Each boundary keeps the experiment reproducible and makes
              disagreements visible.
            </p>
          </div>
          <div
            className="architecture-flow"
            role="img"
            aria-label="Task and protocol flow through robot and policy adapters into episode evidence, review, and metrics"
          >
            <div className="architecture-node">
              <small>01 · DEFINE</small>
              <strong>Task + protocol</strong>
              <span>What counts as a trial?</span>
            </div>
            <span className="architecture-arrow" aria-hidden="true">
              →
            </span>
            <div className="architecture-node">
              <small>02 · EXECUTE</small>
              <strong>Robot + policy adapters</strong>
              <span>LeRobot owns mechanics</span>
            </div>
            <span className="architecture-arrow" aria-hidden="true">
              →
            </span>
            <div className="architecture-node">
              <small>03 · CAPTURE</small>
              <strong>Episode evidence</strong>
              <span>Video · trace · outcomes</span>
            </div>
            <span className="architecture-arrow" aria-hidden="true">
              →
            </span>
            <div className="architecture-node architecture-node-accent">
              <small>04 · LEARN</small>
              <strong>Review + metrics</strong>
              <span>Compare with context</span>
            </div>
          </div>
          <p className="architecture-note">
            <span>↳</span> The system keeps original observations intact while
            review decisions and descriptive comparisons remain explicit.
          </p>
        </section>

        <section
          className="walkthrough-section"
          aria-labelledby="walkthrough-title"
        >
          <div className="walkthrough-heading">
            <div>
              <p className="showcase-overline">A THREE-STEP TOUR</p>
              <h2 id="walkthrough-title">Follow one experiment through.</h2>
            </div>
            <button
              type="button"
              className="walkthrough-cta"
              onClick={() => setStarted(true)}
              disabled={!manifest}
            >
              Start the walkthrough <span aria-hidden="true">↓</span>
            </button>
          </div>
          <ol className="walkthrough-steps">
            <li>
              <span>1</span>
              <div>
                <strong>Compare two runs</strong>
                <p>
                  See the candidate and baseline context, review coverage, and
                  compatibility before reading a delta.
                </p>
              </div>
            </li>
            <li>
              <span>2</span>
              <div>
                <strong>Choose an episode</strong>
                <p>
                  Browse the queue and inspect what was originally recorded and
                  what a reviewer decided.
                </p>
              </div>
            </li>
            <li>
              <span>3</span>
              <div>
                <strong>Inspect the evidence</strong>
                <p>
                  Play the clip, seek the joint trace, and connect actions to
                  the outcome on screen.
                </p>
              </div>
            </li>
          </ol>
        </section>

        <section
          className="showcase-section source-section"
          aria-labelledby="source-title"
        >
          <div className="source-copy">
            <p className="showcase-overline">REPRODUCIBLE SNAPSHOT</p>
            <h2 id="source-title">
              Code, experiments, and limits in the open.
            </h2>
            <p>
              This portfolio view is an exported snapshot of one source commit.
              Inspect the source or open the exact experiment records below.
            </p>
          </div>
          <div className="source-card">
            {manifest ? (
              <>
                <div className="source-links">
                  <a
                    href={manifest.source_repository}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Source repository <span aria-hidden="true">↗</span>
                  </a>
                  <a href={commitUrl} target="_blank" rel="noreferrer">
                    Snapshot commit <span aria-hidden="true">↗</span>
                  </a>
                </div>
                <code className="source-commit">{manifest.source_commit}</code>
                <div className="experiment-links">
                  <span>Experiment records</span>
                  <a
                    href={`/data/runs/${encodeURIComponent(manifest.candidate_id)}.json`}
                  >
                    Candidate · {manifest.candidate_id}{" "}
                    <b aria-hidden="true">↗</b>
                  </a>
                  <a
                    href={`/data/runs/${encodeURIComponent(manifest.baseline_id)}.json`}
                  >
                    Baseline · {manifest.baseline_id}{" "}
                    <b aria-hidden="true">↗</b>
                  </a>
                </div>
                <div className="limitations">
                  <strong>Limitations</strong>
                  <ul>
                    {manifest.limitations.map((limitation) => (
                      <li key={limitation}>{limitation}</li>
                    ))}
                  </ul>
                </div>
              </>
            ) : manifestError ? (
              <p className="showcase-error" role="alert">
                {manifestError}
              </p>
            ) : (
              <p className="muted">Loading source and experiment metadata…</p>
            )}
          </div>
        </section>

        {started && manifest && (
          <section
            className="showcase-explorer"
            id="explorer"
            ref={explorerRef}
            aria-labelledby="explorer-title"
          >
            <div className="explorer-intro">
              <div>
                <p className="showcase-overline">READ-ONLY EXPLORER</p>
                <h2 id="explorer-title">The real experiment workspace</h2>
                <p>
                  Use the fixed candidate and baseline to browse exported
                  evidence. The review record, video, and trace are available;
                  saving is disabled.
                </p>
              </div>
              <span className="readonly-stamp">
                SYNTHETIC SNAPSHOT
                <br />
                NO PHYSICAL RESULTS
              </span>
            </div>
            <App
              initialRunId={manifest.candidate_id}
              initialBaselineId={manifest.baseline_id}
              readOnly
            />
          </section>
        )}
      </main>
      <footer className="showcase-footer">
        <span>LAUNDRYBENCH</span>
        <p>Inspectable robot learning experiments.</p>
        <a href="#top">Back to top ↑</a>
      </footer>
    </div>
  );
}
