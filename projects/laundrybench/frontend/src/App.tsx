import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  categories,
  Detail,
  Episode,
  episodePath,
  Label,
  percent,
  provenance,
  request,
  Run,
  runPath,
  Step,
} from "./api";
import Trace from "./Trace";

function LabelForm({
  run,
  episode,
  onSaved,
  onReload,
  onDirty,
}: {
  run: Detail;
  episode: Episode;
  onSaved: (run: Detail) => void;
  onReload: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [outcome, setOutcome] = useState(
    episode.success ? "success" : "failure",
  );
  const [category, setCategory] = useState(
    episode.failure_category || "unspecified",
  );
  const [intervention, setIntervention] = useState(episode.intervention);
  const [notes, setNotes] = useState(episode.annotation.notes || "");
  const [saving, setSaving] = useState(false),
    [error, setError] = useState(""),
    [conflict, setConflict] = useState(false);
  useEffect(() => {
    onDirty(
      outcome !== (episode.success ? "success" : "failure") ||
        (outcome === "failure" &&
          category !== (episode.failure_category || "unspecified")) ||
        intervention !== episode.intervention ||
        notes !== (episode.annotation.notes || ""),
    );
  }, [outcome, category, intervention, notes, episode, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  async function save(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setConflict(false);
    const label: Label = {
      success: outcome === "success",
      intervention,
      failure_category: outcome === "success" ? null : category,
      notes,
      expected_revision: run.revision,
    };
    try {
      const updated = await request<Detail>(
        `${episodePath(run.id, episode.episode_id)}/label`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(label),
        },
      );
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save label");
      setConflict(err instanceof ApiError && err.status === 409);
    } finally {
      setSaving(false);
    }
  }
  return (
    <form onSubmit={save} className="label-form">
      <div className="section-heading">
        <h3>Manual review</h3>
        <span
          className={`pill ${episode.annotation.status === "labelled" ? "teal" : ""}`}
        >
          {episode.annotation.status === "labelled"
            ? "Reviewed"
            : "Needs review"}
        </span>
      </div>
      <p className="muted small">
        Your review is saved separately from the original run. Metrics update
        after saving. This task defines success as autonomous: assisted episodes
        are failures; keep the actual failure reason when known.
      </p>
      <fieldset disabled={saving}>
        <legend>Episode outcome</legend>
        <div className="segmented">
          <label className={outcome === "success" ? "chosen" : ""}>
            <input
              type="radio"
              name="outcome"
              value="success"
              checked={outcome === "success"}
              onChange={() => {
                setOutcome("success");
                setIntervention(false);
              }}
            />
            Success
          </label>
          <label className={outcome === "failure" ? "chosen" : ""}>
            <input
              type="radio"
              name="outcome"
              value="failure"
              checked={outcome === "failure"}
              onChange={() => setOutcome("failure")}
            />
            Failure
          </label>
        </div>
        {outcome === "failure" && (
          <label className="field">
            Failure category
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
              }}
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="check">
          <input
            type="checkbox"
            checked={intervention}
            onChange={(e) => {
              setIntervention(e.target.checked);
              if (e.target.checked) {
                setOutcome("failure");
                if (outcome === "success") setCategory("intervention");
              } else if (category === "intervention") {
                setCategory("unspecified");
              }
            }}
          />
          Human intervention required
        </label>
        <label className="field">
          Review notes
          <textarea
            value={notes}
            maxLength={4000}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="What happened? What should change next?"
          />
        </label>
        <button className="primary" type="submit">
          {saving ? "Saving review…" : "Save review"}
        </button>
      </fieldset>
      {error && (
        <div className="error" role="alert">
          {error}
          {conflict && (
            <>
              <p>A newer review exists. Your edits have not been saved.</p>
              <button type="button" onClick={onReload}>
                Reload latest review
              </button>
            </>
          )}
        </div>
      )}
    </form>
  );
}
function EpisodeReview({
  run,
  episode,
  onSaved,
  onReload,
  onDirty,
}: {
  run: Detail;
  episode: Episode;
  onSaved: (run: Detail) => void;
  onReload: () => void;
  onDirty: (dirty: boolean) => void;
}) {
  const [trace, setTrace] = useState<Step[] | null>(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setTrace(null);
    setError("");
    request<{ steps: Step[] }>(
      `${episodePath(run.id, episode.episode_id)}/trace`,
    )
      .then((data) => {
        if (active) setTrace(data.steps);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [run.id, episode.episode_id]);
  return (
    <section className="review-panel">
      <div className="review-title">
        <div>
          <div className="eyebrow">EPISODE EVIDENCE</div>
          <h2>{episode.episode_id}</h2>
        </div>
        <span className={`status ${episode.success ? "success" : "failure"}`}>
          {episode.success ? "Success" : "Failure"}
        </span>
      </div>
      <div className="episode-facts">
        <span>
          <b>{episode.duration_s.toFixed(2)}s</b>Duration
        </span>
        <span>
          <b>{episode.intervention ? "Yes" : "No"}</b>Intervention
        </span>
        <span>
          <b>{episode.original_outcome.success ? "Success" : "Failure"}</b>
          Original outcome
        </span>
      </div>
      <div className="media-empty">
        <span aria-hidden="true">▧</span>
        <div>
          <strong>Video unavailable</strong>
          <p>
            This run has no supported media attachment. Review the recorded
            trajectory below.
          </p>
        </div>
      </div>
      <div className="trace-panel">
        <h3>Joint trajectory</h3>
        {error ? (
          <p className="error" role="alert">
            Trace unavailable: {error}
          </p>
        ) : trace === null ? (
          <p className="muted">Loading recorded trace…</p>
        ) : (
          <Trace steps={trace} />
        )}
      </div>
      <LabelForm
        key={`${run.id}/${episode.episode_id}`}
        run={run}
        episode={episode}
        onSaved={onSaved}
        onReload={onReload}
        onDirty={onDirty}
      />
    </section>
  );
}
export default function App() {
  const selectedRef = useRef("");
  const dirtyRef = useRef(false);
  const updateDirty = useCallback((dirty: boolean) => {
    dirtyRef.current = dirty;
  }, []);
  function navigate(action: () => void) {
    if (
      dirtyRef.current &&
      !window.confirm("Discard the unsaved review changes?")
    )
      return;
    action();
  }
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);
  const [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState(""),
    [run, setRun] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true),
    [detailLoading, setDetailLoading] = useState(false),
    [error, setError] = useState(""),
    [detailError, setDetailError] = useState("");
  const [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [episodeId, setEpisodeId] = useState(""),
    [baselineId, setBaselineId] = useState(""),
    [reload, setReload] = useState(0),
    [notice, setNotice] = useState("");
  selectedRef.current = selected;
  async function loadRuns() {
    setLoading(true);
    setError("");
    try {
      const data = await request<{ runs: Run[] }>("/api/runs");
      setRuns((current) =>
        data.runs.map((next) => {
          const previous = current.find((r) => r.id === next.id);
          return previous && previous.revision > next.revision
            ? previous
            : next;
        }),
      );
      setSelected((value) =>
        value && data.runs.some((r) => r.id === value)
          ? value
          : data.runs[0]?.id || "",
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not load experiments",
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void loadRuns();
  }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetailLoading(true);
    setDetailError("");
    setRun(null);
    setNotice("");
    setFilter("all");
    request<Detail>(runPath(selected))
      .then((data) => {
        if (active) {
          setRun((current) =>
            current &&
            current.id === data.id &&
            current.revision > data.revision
              ? current
              : data,
          );
          setEpisodeId(data.episodes[0]?.episode_id || "");
        }
      })
      .catch((err) => {
        if (active) setDetailError(err.message);
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selected, reload]);
  function saved(updated: Detail) {
    setRuns((items) =>
      items.map((r) =>
        r.id === updated.id && r.revision <= updated.revision ? updated : r,
      ),
    );
    if (selectedRef.current === updated.id) {
      setRun((current) =>
        current &&
        current.id === updated.id &&
        current.revision > updated.revision
          ? current
          : updated,
      );
      setNotice("Review saved. Metrics refreshed.");
    }
  }
  const baseline = runs.find((r) => r.id === baselineId && r.id !== selected);
  const visible =
    run?.episodes.filter(
      (e) =>
        filter === "all" ||
        (filter === "unlabelled" && e.annotation.status === "unlabelled") ||
        (filter === "success" && e.success) ||
        (filter === "failure" && !e.success),
    ) || [];
  const episode = visible.find((e) => e.episode_id === episodeId) || visible[0];
  return (
    <div className="app">
      <aside className="sidebar">
        <a className="brand" href="#">
          <span className="brand-mark">
            L<span>↗</span>
          </span>
          <span>
            LaundryBench<small>ROBOT LEARNING LAB</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <div className="nav-active">
          <span>◫</span>Experiment review
          <span className="count">{runs.length}</span>
        </div>
        <div className="sidebar-heading">
          <span>EXPERIMENTS</span>
          <button
            aria-label="Refresh experiments"
            onClick={() => {
              navigate(() => {
                void loadRuns();
                setReload((r) => r + 1);
              });
            }}
          >
            ↻
          </button>
        </div>
        <label className="search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="Search experiments"
            placeholder="Find an experiment…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <nav aria-label="Experiment runs">
          {runs
            .filter((r) => r.id.toLowerCase().includes(search.toLowerCase()))
            .map((r) => (
              <button
                className={`run-link ${selected === r.id ? "active" : ""}`}
                key={r.id}
                onClick={() => {
                  if (selected !== r.id)
                    navigate(() => {
                      setSelected(r.id);
                      setNotice("");
                    });
                }}
              >
                <span className="run-dot" />
                <span>
                  <strong>{r.id}</strong>
                  <small>
                    {r.summary.episodes} episodes · {r.labelled_episodes}{" "}
                    reviewed
                  </small>
                </span>
                <span className="run-arrow">↗</span>
              </button>
            ))}
          {!loading && !error && !runs.length && (
            <p className="sidebar-empty">No experiments yet.</p>
          )}
          {runs.length > 0 &&
            !runs.some((r) =>
              r.id.toLowerCase().includes(search.toLowerCase()),
            ) && <p className="sidebar-empty">No matching experiments.</p>}
        </nav>
        <div className="sidebar-footer">
          <span className="connection-dot" />
          Local evidence workspace
          <p>
            Review outcomes. Preserve originals.
            <br />
            No robot motion controls.
          </p>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <span>
            Workspace <span className="slash">/</span> Experiments
          </span>
          <span className="local-label">
            <span />
            LOCAL REVIEW
          </span>
        </div>
        {loading ? (
          <div className="state">
            <div className="spinner" />
            Loading experiment artifacts…
          </div>
        ) : error ? (
          <div className="state error" role="alert">
            <h1>Experiments unavailable</h1>
            <p>{error}</p>
            <button onClick={() => void loadRuns()}>Try again</button>
            <p className="muted">
              Start the local review server and check its configured outputs
              directory.
            </p>
          </div>
        ) : !runs.length ? (
          <div className="state">
            <div className="eyebrow">START WITH EVIDENCE</div>
            <h1>Your first experiment starts here.</h1>
            <p>
              Run a LaundryBench evaluation, then refresh to inspect its
              results.
            </p>
            <code>make demo</code>
            <button onClick={() => void loadRuns()}>Refresh experiments</button>
          </div>
        ) : detailLoading ? (
          <div className="state">
            <div className="spinner" />
            Loading run evidence…
          </div>
        ) : detailError ? (
          <div className="state error" role="alert">
            <h1>Run unavailable</h1>
            <p>{detailError}</p>
            <button onClick={() => setReload((r) => r + 1)}>Retry run</button>
          </div>
        ) : (
          run && (
            <div className="content">
              <header className="page-header">
                <div>
                  <div className="eyebrow">EXPERIMENT REVIEW</div>
                  <h1>
                    {run.id.replace(/^exp-\d+-/, "").replaceAll("-", " ")}
                  </h1>
                  <p className="run-code">{run.id}</p>
                </div>
                <div className="header-badges">
                  <span className="pill amber">{provenance(run)}</span>
                  <span className="muted small">Revision {run.revision}</span>
                </div>
              </header>
              <div className="evidence-banner">
                <strong>
                  {provenance(run) === "MOCK DATA"
                    ? "Software validation run"
                    : "Execution evidence unverified"}
                </strong>
                <span>
                  {provenance(run) === "MOCK DATA"
                    ? "Synthetic outcomes exercise the evaluation system. They are not physical robot performance."
                    : "The manifest does not establish physical execution. Interpret outcomes in that context."}
                </span>
              </div>
              <div className="overview-heading">
                <h2>Run overview</h2>
                <label className="baseline-picker">
                  Compare to
                  <select
                    aria-label="Baseline experiment"
                    value={baselineId === selected ? "" : baselineId}
                    onChange={(e) => setBaselineId(e.target.value)}
                  >
                    <option value="">No baseline</option>
                    {runs
                      .filter((r) => r.id !== selected)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.id}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <div className="kpis">
                <div className="kpi">
                  <span>Success rate</span>
                  <strong>
                    {run.summary.episodes
                      ? percent(run.summary.success_rate)
                      : "—"}
                  </strong>
                  <small>
                    {run.summary.successes} of {run.summary.episodes} episodes
                  </small>
                  {run.summary.episodes > 0 && run.summary.success_rate_ci && (
                    <small>
                      95% CI{" "}
                      {run.summary.success_rate_ci.map(percent).join(" – ")}
                    </small>
                  )}
                  {baseline &&
                    run.summary.episodes > 0 &&
                    baseline.summary.episodes > 0 && (
                      <em>
                        {(
                          (run.summary.success_rate -
                            baseline.summary.success_rate) *
                          100
                        ).toFixed(1)}{" "}
                        pp vs baseline
                      </em>
                    )}
                </div>
                <div className="kpi">
                  <span>Median completion</span>
                  <strong>
                    {run.summary.successes
                      ? `${run.summary.median_completion_time_s.toFixed(2)}`
                      : "—"}
                    {run.summary.successes > 0 && <i>s</i>}
                  </strong>
                  <small>Successful episodes only</small>
                </div>
                <div className="kpi">
                  <span>Intervention rate</span>
                  <strong>
                    {run.summary.episodes
                      ? percent(run.summary.intervention_rate)
                      : "—"}
                  </strong>
                  <small>Human-assisted episodes</small>
                </div>
                <div className="kpi">
                  <span>Review coverage</span>
                  <strong>
                    {run.labelled_episodes}
                    <i>/ {run.summary.episodes}</i>
                  </strong>
                  <small>Manual labels saved</small>
                  <div className="coverage">
                    <span
                      style={{
                        width: `${run.summary.episodes ? (100 * run.labelled_episodes) / run.summary.episodes : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
              {baseline && (
                <div className="comparison">
                  <div>
                    <div className="eyebrow">BASELINE COMPARISON</div>
                    <h3>{baseline.id}</h3>
                    <span className="pill amber">{provenance(baseline)}</span>
                  </div>
                  <dl>
                    <div>
                      <dt>Success rate</dt>
                      <dd>
                        {baseline.summary.episodes
                          ? percent(baseline.summary.success_rate)
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Completion</dt>
                      <dd>
                        {baseline.summary.successes
                          ? `${baseline.summary.median_completion_time_s.toFixed(2)}s`
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Interventions</dt>
                      <dd>
                        {baseline.summary.episodes
                          ? percent(baseline.summary.intervention_rate)
                          : "—"}
                      </dd>
                    </div>
                  </dl>
                  <p className="muted small">
                    Descriptive comparison only. Confirm the same task and
                    protocol before interpreting differences.
                  </p>
                </div>
              )}
              <div className="insights">
                <section className="panel failures">
                  <div className="section-heading">
                    <h3>Failure distribution</h3>
                    <span className="muted small">Episode counts</span>
                  </div>
                  {Object.keys(run.summary.failure_category_counts).length ? (
                    Object.entries(run.summary.failure_category_counts).map(
                      ([category, count]) => (
                        <div className="failure-row" key={category}>
                          <span>{category.replaceAll("_", " ")}</span>
                          <div>
                            <i
                              style={{
                                width: `${run.summary.episodes ? (100 * count) / run.summary.episodes : 0}%`,
                              }}
                            />
                          </div>
                          <b>{count}</b>
                        </div>
                      ),
                    )
                  ) : (
                    <p className="empty-inline">
                      {run.summary.episodes
                        ? "No failed episodes recorded."
                        : "No episodes recorded."}
                    </p>
                  )}
                </section>
                <section className="panel evidence">
                  <div className="section-heading">
                    <h3>Recorded evidence</h3>
                    <span className="pill">
                      {run.quality
                        ? `${run.quality.flagged ?? 0} recorded flags`
                        : "Quality unavailable"}
                    </span>
                  </div>
                  <dl>
                    <div>
                      <dt>Policy</dt>
                      <dd>
                        {String(run.manifest.policy_name || "Not recorded")}
                      </dd>
                    </div>
                    <div>
                      <dt>Robot</dt>
                      <dd>
                        {String(
                          run.manifest.robot_implementation || "Not recorded",
                        )}
                      </dd>
                    </div>
                    <div>
                      <dt>Seed</dt>
                      <dd>{String(run.manifest.seed ?? "Not recorded")}</dd>
                    </div>
                    <div>
                      <dt>Revision</dt>
                      <dd className="mono">
                        {String(
                          run.manifest.git_revision || "Not recorded",
                        ).slice(0, 12)}
                      </dd>
                    </div>
                  </dl>
                  <p className="muted small quality-note">
                    Quality flags describe the original recorded evidence.
                    Manual labels update outcomes, not these checks.
                  </p>
                </section>
              </div>
              <div className="episodes-heading">
                <div>
                  <h2>Episode workspace</h2>
                  <p className="muted">
                    Inspect the evidence. Label what actually happened.
                  </p>
                </div>
                <div
                  className="filters"
                  role="group"
                  aria-label="Filter episodes"
                >
                  {[
                    ["all", "All"],
                    ["unlabelled", "Needs review"],
                    ["failure", "Failures"],
                    ["success", "Successes"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      className={filter === value ? "selected" : ""}
                      onClick={() => {
                        if (filter !== value) navigate(() => setFilter(value));
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="review-layout">
                <section className="episode-table panel">
                  <div className="table-caption">
                    {visible.length} episodes <span>OUTCOME / DURATION</span>
                  </div>
                  <div className="episode-list">
                    {visible.map((e, index) => (
                      <button
                        className={`episode-row ${episode?.episode_id === e.episode_id ? "selected" : ""}`}
                        key={e.episode_id}
                        onClick={() => {
                          if (episode?.episode_id !== e.episode_id)
                            navigate(() => {
                              setEpisodeId(e.episode_id);
                              setNotice("");
                            });
                        }}
                      >
                        <span className="episode-number">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span>
                          <strong>{e.episode_id}</strong>
                          <small>
                            {e.annotation.status === "labelled"
                              ? "Reviewed"
                              : e.failure_category?.replaceAll("_", " ") ||
                                "Needs review"}
                          </small>
                        </span>
                        <span className="episode-outcome">
                          <i
                            className={
                              e.success ? "success-dot" : "failure-dot"
                            }
                          />
                          {e.duration_s.toFixed(1)}s
                        </span>
                      </button>
                    ))}
                    {!visible.length && (
                      <p className="empty-inline">
                        No episodes match this filter.
                      </p>
                    )}
                  </div>
                </section>
                {episode ? (
                  <EpisodeReview
                    run={run}
                    episode={episode}
                    onSaved={saved}
                    onReload={() => navigate(() => setReload((r) => r + 1))}
                    onDirty={updateDirty}
                  />
                ) : (
                  <div className="panel empty-inline">
                    Select an episode to inspect its evidence.
                  </div>
                )}
              </div>
              <p className="save-notice" role="status">
                {notice}
              </p>
              <details className="provenance">
                <summary>Full run manifest</summary>
                <pre>{JSON.stringify(run.manifest, null, 2)}</pre>
              </details>
              <footer>
                LAUNDRYBENCH{" "}
                <span>
                  Reproducible experiments. Inspectable evidence. Better robot
                  behavior.
                </span>
              </footer>
            </div>
          )
        )}
      </main>
    </div>
  );
}
