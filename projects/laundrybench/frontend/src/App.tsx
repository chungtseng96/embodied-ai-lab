import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  categories,
  ComparisonResult,
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
import MediaEvidence from "./MediaEvidence";

function LabelForm({
  run,
  episode,
  onSaved,
  onReload,
  onDirty,
  navigationVersion,
  queueEpisodeIds,
}: {
  run: Detail;
  episode: Episode;
  onSaved: (
    run: Detail,
    context: {
      runId: string;
      episodeId: string;
      navigationVersion: number;
      saveNext: boolean;
      queueEpisodeIds: string[];
    },
  ) => void;
  onReload: () => void;
  onDirty: (dirty: boolean) => void;
  navigationVersion: number;
  queueEpisodeIds: string[];
}) {
  const [outcome, setOutcome] = useState<"success" | "failure" | "excluded">(
    episode.review_status === "excluded"
      ? "excluded"
      : episode.effective_outcome.success
        ? "success"
        : "failure",
  );
  const [category, setCategory] = useState(
    episode.effective_outcome.failure_category || "unspecified",
  );
  const [intervention, setIntervention] = useState(
    episode.effective_outcome.intervention,
  );
  const [notes, setNotes] = useState(episode.annotation.notes || "");
  const [exclusionReason, setExclusionReason] = useState(
    episode.annotation.exclusion_reason || "",
  );
  const [decisionTouched, setDecisionTouched] = useState(false);
  const [saving, setSaving] = useState(false),
    [error, setError] = useState(""),
    [conflict, setConflict] = useState(false);
  const isDirty =
    outcome === "excluded"
      ? episode.review_status !== "excluded" ||
        exclusionReason !== (episode.annotation.exclusion_reason || "")
      : episode.review_status === "excluded" ||
        (episode.review_status !== "reviewed" && decisionTouched) ||
        outcome !==
          (episode.effective_outcome.success ? "success" : "failure") ||
        (outcome === "failure" &&
          category !==
            (episode.effective_outcome.failure_category || "unspecified")) ||
        intervention !== episode.effective_outcome.intervention ||
        notes !== (episode.annotation.notes || "");
  useEffect(() => {
    onDirty(isDirty);
  }, [isDirty, onDirty]);
  useEffect(() => () => onDirty(false), [onDirty]);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter;
    const saveNext =
      submitter instanceof HTMLElement && submitter.dataset.saveNext === "true";
    if (outcome === "excluded" && !exclusionReason.trim()) {
      setError("Enter a reason before excluding this episode.");
      setConflict(false);
      return;
    }
    setSaving(true);
    setError("");
    setConflict(false);
    const label: Label =
      outcome === "excluded"
        ? {
            status: "excluded",
            exclusion_reason: exclusionReason,
            expected_revision: run.revision,
          }
        : {
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
      onSaved(updated, {
        runId: run.id,
        episodeId: episode.episode_id,
        navigationVersion,
        saveNext,
        queueEpisodeIds,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save label");
      setConflict(err instanceof ApiError && err.status === 409);
    } finally {
      setSaving(false);
    }
  }
  const statusLabel = isDirty
    ? "Unsaved changes"
    : episode.review_status === "reviewed"
      ? "Reviewed"
      : episode.review_status === "excluded"
        ? "Excluded"
        : "Needs review";
  return (
    <form onSubmit={save} className="label-form">
      <div className="section-heading">
        <h3>Manual review</h3>
        <span
          className={`pill ${isDirty ? "amber" : episode.review_status === "reviewed" ? "teal" : episode.review_status === "excluded" ? "excluded-pill" : ""}`}
          role="status"
        >
          {statusLabel}
        </span>
      </div>
      <p className="muted small">
        Review the recorded outcome or exclude unusable evidence with a reason.
        Only reviewed episodes contribute to outcome metrics. Assisted episodes
        count as failures; keep the actual failure reason when known.
      </p>
      <details className="keyboard-help">
        <summary>Keyboard shortcuts</summary>
        <p>
          <kbd>1</kbd> Success · <kbd>2</kbd> Failure · <kbd>3</kbd> Exclude
        </p>
        <p>
          <kbd>j</kbd>/<kbd>k</kbd> Next/previous episode · <kbd>Ctrl</kbd>/
          <kbd>⌘</kbd> + <kbd>Enter</kbd> Save &amp; next
        </p>
        <p className="muted">
          Shortcuts pause while you type or use video controls.
        </p>
      </details>
      <fieldset disabled={saving}>
        <legend>Review decision</legend>
        <div className="segmented decision-options">
          <label className={outcome === "success" ? "chosen" : ""}>
            <input
              type="radio"
              name="outcome"
              value="success"
              checked={outcome === "success"}
              onChange={() => {
                setDecisionTouched(true);
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
              onChange={() => {
                setDecisionTouched(true);
                setOutcome("failure");
              }}
            />
            Failure
          </label>
          <label className={outcome === "excluded" ? "chosen" : ""}>
            <input
              type="radio"
              name="outcome"
              value="excluded"
              checked={outcome === "excluded"}
              onChange={() => {
                setDecisionTouched(true);
                setOutcome("excluded");
              }}
            />
            Exclude
          </label>
        </div>
        {outcome === "excluded" ? (
          <label className="field">
            Reason for exclusion
            <textarea
              value={exclusionReason}
              onChange={(e) => setExclusionReason(e.target.value)}
              maxLength={4000}
              required
              rows={3}
              placeholder="Why is this episode unsuitable for outcome metrics?"
            />
          </label>
        ) : (
          <>
            {outcome === "failure" && (
              <label className="field">
                Failure category
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
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
          </>
        )}
        <div className="save-actions">
          <button className="primary" type="submit">
            {saving
              ? outcome === "excluded"
                ? "Saving exclusion…"
                : "Saving review…"
              : outcome === "excluded"
                ? "Save exclusion"
                : "Save review"}
          </button>
          <button
            className="save-next"
            type="submit"
            data-save-next="true"
            aria-label="Save & next: save review and go to next pending episode"
          >
            Save &amp; next
          </button>
        </div>
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
  headingRef,
}: {
  run: Detail;
  episode: Episode;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
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
          <h2 ref={headingRef} tabIndex={-1}>
            {episode.episode_id}
          </h2>
        </div>
        <span
          className={`status ${episode.review_status === "reviewed" ? (episode.success ? "success" : "failure") : episode.review_status === "excluded" ? "excluded" : "pending"}`}
        >
          {episode.review_status === "reviewed"
            ? episode.success
              ? "Reviewed success"
              : "Reviewed failure"
            : episode.review_status === "excluded"
              ? "Excluded"
              : "Pending review"}
        </span>
      </div>
      <div className="episode-facts">
        <span>
          <b>{episode.original_outcome.success ? "Success" : "Failure"}</b>
          Recorded outcome
        </span>
        <span>
          <b>
            {episode.review_status === "reviewed"
              ? episode.effective_outcome.success
                ? "Success"
                : "Failure"
              : episode.review_status === "excluded"
                ? "Excluded"
                : "Pending"}
          </b>
          {episode.review_status === "reviewed"
            ? "Reviewed outcome"
            : "Metric status"}
        </span>
        <span>
          <b>{episode.duration_s.toFixed(2)}s</b>Duration
        </span>
        <span>
          <b>
            {episode.review_status === "reviewed"
              ? episode.effective_outcome.intervention
                ? "Yes"
                : "No"
              : episode.original_outcome.intervention
                ? "Yes, recorded"
                : "No, recorded"}
          </b>
          Intervention
        </span>
      </div>
      <MediaEvidence
        key={`${run.id}/${episode.episode_id}`}
        runId={run.id}
        episodeId={episode.episode_id}
        steps={trace}
        traceError={error}
      />
    </section>
  );
}

function ReadOnlyReview({ episode }: { episode: Episode }) {
  return (
    <section className="readonly-review panel" aria-label="Review record">
      <div className="section-heading">
        <h3>Review record</h3>
        <span className="pill">Read only</span>
      </div>
      <p className="muted small">
        This exported snapshot preserves both the original outcome and any
        reviewer decision. No edits can be saved here.
      </p>
      <dl>
        <div>
          <dt>Review status</dt>
          <dd>{episode.review_status}</dd>
        </div>
        <div>
          <dt>Original recorded outcome</dt>
          <dd>
            {episode.original_outcome.success ? "Success" : "Failure"}
            {episode.original_outcome.failure_category
              ? ` · ${episode.original_outcome.failure_category.replaceAll("_", " ")}`
              : ""}
            {episode.original_outcome.intervention ? " · intervention" : ""}
          </dd>
        </div>
        <div>
          <dt>Current reviewed outcome</dt>
          <dd>
            {episode.review_status === "reviewed"
              ? `${episode.effective_outcome.success ? "Success" : "Failure"}${episode.effective_outcome.failure_category ? ` · ${episode.effective_outcome.failure_category.replaceAll("_", " ")}` : ""}${episode.effective_outcome.intervention ? " · intervention" : ""}`
              : episode.review_status === "excluded"
                ? "Excluded from metrics"
                : "Pending review"}
          </dd>
        </div>
        {episode.annotation.notes && (
          <div>
            <dt>Reviewer notes</dt>
            <dd>{episode.annotation.notes}</dd>
          </div>
        )}
        {episode.annotation.exclusion_reason && (
          <div>
            <dt>Exclusion reason</dt>
            <dd>{episode.annotation.exclusion_reason}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}

function contextValue(value: string | null | undefined) {
  return value?.trim() || "Not recorded";
}

function mergeRunSnapshot<T extends Run>(
  current: T | null | undefined,
  incoming: T,
): T {
  if (!current || current.id !== incoming.id) return incoming;
  const latestOutcome =
    current.revision > incoming.revision ? current : incoming;
  const currentContextRevision = current.experiment?.revision ?? -1;
  const incomingContextRevision = incoming.experiment?.revision ?? -1;
  const latestContext =
    incomingContextRevision >= currentContextRevision
      ? incoming.experiment
      : current.experiment;
  return { ...latestOutcome, experiment: latestContext ?? null } as T;
}

function ExperimentContext({
  run,
  baseline = false,
}: {
  run: Run;
  baseline?: boolean;
}) {
  const experiment = run.experiment;
  return (
    <section
      className="experiment-context panel"
      aria-label={`${baseline ? "Baseline" : "Current"} experiment context`}
    >
      <div className="section-heading">
        <h3>{baseline ? "Baseline context" : "Experiment context"}</h3>
        <span className="muted small">{run.id}</span>
      </div>
      {!experiment ? (
        <p className="legacy-context" role="status">
          No experiment context sidecar is recorded for this run. It may be a
          legacy run.
        </p>
      ) : (
        <>
          <dl className="human-context">
            <div>
              <dt>Name</dt>
              <dd>{contextValue(experiment.name)}</dd>
            </div>
            <div>
              <dt>Hypothesis</dt>
              <dd>{contextValue(experiment.hypothesis)}</dd>
            </div>
            <div>
              <dt>What changed</dt>
              <dd>{contextValue(experiment.what_changed)}</dd>
            </div>
          </dl>
          <details className="context-provenance">
            <summary>Protocol, data, checkpoint, overrides, and links</summary>
            <dl>
              <div>
                <dt>Task</dt>
                <dd>
                  {contextValue(experiment.task.id)} ·{" "}
                  {contextValue(experiment.task.version)}
                </dd>
              </div>
              <div>
                <dt>Protocol</dt>
                <dd>
                  {contextValue(experiment.protocol.id)} ·{" "}
                  {contextValue(experiment.protocol.version)}
                </dd>
              </div>
              <div>
                <dt>Dataset</dt>
                <dd>
                  {contextValue(experiment.dataset.id)} ·{" "}
                  {contextValue(experiment.dataset.revision)}
                </dd>
              </div>
              <div>
                <dt>Checkpoint</dt>
                <dd>{contextValue(experiment.checkpoint.identity)}</dd>
              </div>
              <div>
                <dt>Source config hash</dt>
                <dd className="mono">
                  {String(run.manifest.config_hash || "Not recorded")}
                </dd>
              </div>
            </dl>
            <div className="context-json">
              <strong>Effective overrides</strong>
              <pre>
                {JSON.stringify(experiment.effective_overrides, null, 2)}
              </pre>
            </div>
            <div className="context-links">
              <strong>Evidence links</strong>
              {experiment.evidence_links.length ? (
                <ul>
                  {experiment.evidence_links.map((link) => (
                    <li key={`${link.label}:${link.url}`}>
                      <a href={link.url} target="_blank" rel="noreferrer">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted small">No evidence links recorded.</p>
              )}
            </div>
          </details>
        </>
      )}
    </section>
  );
}

function differenceLabel(value: unknown) {
  if (value === null || value === undefined) return "Not recorded";
  return typeof value === "string" ? value : JSON.stringify(value);
}

function deltaRateText(value: number | null) {
  return value === null
    ? "— (no reviewed denominator)"
    : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(1)} pp`;
}

function FailureComparison({
  candidate,
  baseline,
  delta,
}: {
  candidate: ComparisonResult["candidate"];
  baseline: ComparisonResult["baseline"];
  delta: ComparisonResult["delta"];
}) {
  const categories = Array.from(
    new Set([
      ...Object.keys(candidate.failure_category_counts),
      ...Object.keys(baseline.failure_category_counts),
    ]),
  ).sort();
  const candidateFailures = Object.values(
    candidate.failure_category_counts,
  ).reduce((sum, count) => sum + count, 0);
  const baselineFailures = Object.values(
    baseline.failure_category_counts,
  ).reduce((sum, count) => sum + count, 0);
  return (
    <section
      className="failure-comparison"
      aria-label="Failure category distributions"
    >
      <h4>Reviewed failure distribution</h4>
      <p className="muted small">
        Candidate: {candidateFailures} reviewed failures among{" "}
        {candidate.reviewed_episodes} reviewed episodes. Baseline:{" "}
        {baselineFailures} among {baseline.reviewed_episodes}.
      </p>
      {!categories.length ? (
        <p className="muted small">
          No reviewed failure categories in either run.
        </p>
      ) : (
        <div
          className="comparison-table-wrap"
          role="region"
          aria-label="Failure distribution comparison table"
          tabIndex={0}
        >
          <table className="comparison-table">
            <thead>
              <tr>
                <th scope="col">Failure category</th>
                <th scope="col">Candidate</th>
                <th scope="col">Baseline</th>
                <th scope="col">Count difference</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((category) => {
                const candidateCount =
                  candidate.failure_category_counts[category] || 0;
                const baselineCount =
                  baseline.failure_category_counts[category] || 0;
                const difference = delta?.failure_category_counts[category];
                return (
                  <tr key={category}>
                    <th scope="row">{category.replaceAll("_", " ")}</th>
                    <td>
                      {candidateCount} / {candidateFailures} reviewed failures
                    </td>
                    <td>
                      {baselineCount} / {baselineFailures} reviewed failures
                    </td>
                    <td>
                      {difference === undefined
                        ? "Withheld"
                        : `${difference >= 0 ? "+" : ""}${difference}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RunComparison({
  candidate,
  baseline,
  selectionEpoch,
}: {
  candidate: Detail;
  baseline: Run | undefined;
  selectionEpoch: number;
}) {
  const [acknowledgedKey, setAcknowledgedKey] = useState("");
  const [stored, setStored] = useState<{
    key: string;
    result: ComparisonResult;
  }>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [requestGeneration, setRequestGeneration] = useState(0);
  const comparisonKey = baseline
    ? `${candidate.id}:${candidate.revision}:${candidate.experiment?.revision ?? "legacy"}/${baseline.id}:${baseline.revision}:${baseline.experiment?.revision ?? "legacy"}/${selectionEpoch}`
    : "";
  const acknowledged = Boolean(
    comparisonKey && acknowledgedKey === comparisonKey,
  );
  const current = stored?.key === comparisonKey ? stored.result : undefined;

  useEffect(() => {
    if (!baseline || !comparisonKey) {
      setStored(undefined);
      setError("");
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    setStored(undefined);
    const query = acknowledged ? "?acknowledge_incompatible=1" : "";
    request<ComparisonResult>(
      `${runPath(candidate.id)}/compare/${encodeURIComponent(baseline.id)}${query}`,
    )
      .then((result) => {
        if (!active) return;
        if (
          result.candidate_label_revision !== candidate.revision ||
          result.baseline_label_revision !== baseline.revision ||
          (result.candidate_context?.revision ?? null) !==
            (candidate.experiment?.revision ?? null) ||
          (result.baseline_context?.revision ?? null) !==
            (baseline.experiment?.revision ?? null)
        ) {
          setError(
            "Run labels or experiment context changed while the comparison was loading. Refresh the runs before comparing again.",
          );
          return;
        }
        setStored({ key: comparisonKey, result });
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error ? reason.message : "Could not compare runs",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [
    candidate.id,
    candidate.revision,
    baseline?.id,
    baseline?.revision,
    candidate.experiment?.revision,
    baseline?.experiment?.revision,
    comparisonKey,
    acknowledged,
    requestGeneration,
  ]);

  if (!baseline) return null;
  const formatRate = (
    summary: ComparisonResult["candidate"],
    key: "success_rate" | "reviewed_rate" | "intervention_rate",
  ) => {
    const denominator =
      key === "reviewed_rate" ? summary.episodes : summary.metric_episodes;
    const denominatorLabel =
      key === "reviewed_rate" ? "total episodes" : "reviewed episodes";
    if (summary[key] === null) return `— (0 ${denominatorLabel}; no interval)`;
    const interval = key === "success_rate" ? summary.success_rate_ci : null;
    const uncertainty =
      key !== "success_rate"
        ? ""
        : interval
          ? `; 95% CI ${interval.map(percent).join("–")}`
          : "; 95% CI unavailable";
    return `${percent(summary[key]!)} (n=${denominator})${uncertainty}`;
  };
  const delta = current?.delta;
  return (
    <section className="run-comparison panel" aria-label="Baseline comparison">
      <div className="section-heading">
        <h3>Baseline comparison</h3>
        <span className="muted small">
          Descriptive outcomes; not a significance test
        </span>
      </div>
      {loading && (
        <p role="status" className="muted">
          Loading comparison…
        </p>
      )}
      {error && (
        <div role="alert" className="error">
          <p>{error}</p>
          <button
            type="button"
            onClick={() => setRequestGeneration((value) => value + 1)}
          >
            Retry comparison
          </button>
        </div>
      )}
      {current && (
        <>
          <div
            className={`compatibility compatibility-${current.compatibility.status}`}
            role="status"
            aria-label={`Compatibility: ${current.compatibility.status}`}
          >
            Compatibility: <strong>{current.compatibility.status}</strong>
          </div>
          {!!current.compatibility.reasons.length && (
            <ul className="comparison-reasons">
              {current.compatibility.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          {!!current.compatibility.advisories.length && (
            <div className="comparison-advisories">
              <strong>Context advisories</strong>
              <ul>
                {current.compatibility.advisories.map((advisory) => (
                  <li key={advisory}>{advisory}</li>
                ))}
              </ul>
              <p className="muted small">
                Dataset, checkpoint, source configuration, and override
                differences are descriptive advisories. Record evaluation
                condition changes in the protocol version.
              </p>
            </div>
          )}
          {!!Object.keys(current.compatibility.differences).length && (
            <details className="comparison-differences">
              <summary>Context differences</summary>
              <dl>
                {Object.entries(current.compatibility.differences).map(
                  ([key, values]) => (
                    <div key={key}>
                      <dt>{key}</dt>
                      <dd>Candidate: {differenceLabel(values.candidate)}</dd>
                      <dd>Baseline: {differenceLabel(values.baseline)}</dd>
                    </div>
                  ),
                )}
              </dl>
            </details>
          )}
          <dl className="comparison-counts" aria-label="Run review counts">
            <div>
              <dt>Candidate episode counts</dt>
              <dd>
                {current.candidate.reviewed_episodes} reviewed ·{" "}
                {current.candidate.pending_episodes} pending ·{" "}
                {current.candidate.excluded_episodes} excluded /{" "}
                {current.candidate.episodes} total
              </dd>
            </div>
            <div>
              <dt>Baseline episode counts</dt>
              <dd>
                {current.baseline.reviewed_episodes} reviewed ·{" "}
                {current.baseline.pending_episodes} pending ·{" "}
                {current.baseline.excluded_episodes} excluded /{" "}
                {current.baseline.episodes} total
              </dd>
            </div>
          </dl>
          {current.compatibility.status !== "matched" && !acknowledged && (
            <div className="compatibility-ack">
              <p>
                Outcome differences are withheld because required task or
                protocol context is different or missing.
              </p>
              <button
                type="button"
                onClick={() => setAcknowledgedKey(comparisonKey)}
              >
                Acknowledge incompatible comparison and show descriptive delta
              </button>
            </div>
          )}
          {current && (
            <>
              <h4 className="comparison-delta-heading">
                {delta
                  ? "Descriptive outcome differences"
                  : "Per-run outcome summaries"}
              </h4>
              <div
                className="comparison-table-wrap"
                role="region"
                aria-label="Outcome comparison table"
                tabIndex={0}
              >
                <table className="comparison-table">
                  <thead>
                    <tr>
                      <th scope="col">Measure</th>
                      <th scope="col">Candidate</th>
                      <th scope="col">Baseline</th>
                      <th scope="col">
                        {delta ? "Candidate − baseline" : "Difference"}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <th scope="row">Successes</th>
                      <td>
                        {current.candidate.successes} /{" "}
                        {current.candidate.metric_episodes} reviewed
                      </td>
                      <td>
                        {current.baseline.successes} /{" "}
                        {current.baseline.metric_episodes} reviewed
                      </td>
                      <td>
                        {delta
                          ? `${delta.successes >= 0 ? "+" : ""}${delta.successes}`
                          : "Withheld until acknowledged"}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Success rate</th>
                      <td>{formatRate(current.candidate, "success_rate")}</td>
                      <td>{formatRate(current.baseline, "success_rate")}</td>
                      <td>
                        {delta
                          ? deltaRateText(delta.success_rate)
                          : "Withheld until acknowledged"}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Decision coverage</th>
                      <td>{formatRate(current.candidate, "reviewed_rate")}</td>
                      <td>{formatRate(current.baseline, "reviewed_rate")}</td>
                      <td>
                        {delta
                          ? deltaRateText(delta.reviewed_rate)
                          : "Withheld until acknowledged"}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Intervention rate</th>
                      <td>
                        {formatRate(current.candidate, "intervention_rate")}
                      </td>
                      <td>
                        {formatRate(current.baseline, "intervention_rate")}
                      </td>
                      <td>
                        {delta
                          ? deltaRateText(delta.intervention_rate)
                          : "Withheld until acknowledged"}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              {delta && (
                <p className="muted small">
                  Episodes are not paired by ID. Select representative evidence
                  independently for each run below.
                </p>
              )}
            </>
          )}
          <FailureComparison
            candidate={current.candidate}
            baseline={current.baseline}
            delta={delta || null}
          />
        </>
      )}
    </section>
  );
}

function RepresentativeEvidenceCard({
  run,
  episode,
}: {
  run: Detail;
  episode: Episode;
}) {
  const [steps, setSteps] = useState<Step[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setSteps(null);
    setError("");
    request<{ steps: Step[] }>(
      `${episodePath(run.id, episode.episode_id)}/trace`,
    )
      .then((data) => {
        if (active) setSteps(data.steps);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error ? reason.message : "Could not load trace",
          );
      });
    return () => {
      active = false;
    };
  }, [run.id, episode.episode_id]);
  return (
    <article className="representative-card">
      <div className="representative-summary">
        <strong>{episode.episode_id}</strong>
        <span>
          {episode.review_status === "reviewed"
            ? "Reviewed"
            : episode.review_status === "excluded"
              ? "Excluded"
              : "Pending review"}
        </span>
        <span>
          {episode.review_status === "reviewed"
            ? episode.effective_outcome.success
              ? "Reviewed success"
              : "Reviewed failure"
            : episode.original_outcome.success
              ? "Recorded success"
              : "Recorded failure"}
        </span>
      </div>
      <MediaEvidence
        key={`${run.id}/${episode.episode_id}`}
        runId={run.id}
        episodeId={episode.episode_id}
        steps={steps}
        traceError={error}
      />
    </article>
  );
}

function RepresentativeEvidenceComparison({
  candidate,
  baselineId,
  baselineRevision,
}: {
  candidate: Detail;
  baselineId: string;
  baselineRevision: number;
}) {
  const [loadedBaseline, setLoadedBaseline] = useState<Detail | null>(null);
  const [baselineError, setBaselineError] = useState("");
  const [candidateEpisodeId, setCandidateEpisodeId] = useState("");
  const [baselineEpisodeId, setBaselineEpisodeId] = useState("");
  useEffect(() => {
    setCandidateEpisodeId("");
  }, [candidate.id]);
  useEffect(() => {
    if (!baselineId) {
      setLoadedBaseline(null);
      setBaselineEpisodeId("");
      return;
    }
    let active = true;
    setLoadedBaseline(null);
    setBaselineError("");
    setBaselineEpisodeId("");
    request<Detail>(runPath(baselineId))
      .then((data) => {
        if (!active) return;
        if (data.id !== baselineId || data.revision !== baselineRevision) {
          setBaselineError(
            "Baseline evidence changed while loading. Refresh the runs before selecting an episode.",
          );
          return;
        }
        setLoadedBaseline(data);
      })
      .catch((reason) => {
        if (active)
          setBaselineError(
            reason instanceof Error
              ? reason.message
              : "Could not load baseline evidence",
          );
      });
    return () => {
      active = false;
    };
  }, [baselineId, baselineRevision]);
  const baseline =
    loadedBaseline?.id === baselineId &&
    loadedBaseline.revision === baselineRevision
      ? loadedBaseline
      : null;
  const candidateEpisode = candidate.episodes.find(
    (item) => item.episode_id === candidateEpisodeId,
  );
  const baselineEpisode = baseline?.episodes.find(
    (item) => item.episode_id === baselineEpisodeId,
  );
  if (!baselineId) return null;
  return (
    <section
      className="representative-evidence panel"
      aria-label="Representative episode evidence"
    >
      <div className="section-heading">
        <h3>Representative episode evidence</h3>
        <span className="muted small">Read only</span>
      </div>
      <p className="muted small">
        Choose an episode independently for each run. Matching episode IDs do
        not indicate paired trials.
      </p>
      <div className="representative-pickers">
        <label>
          Candidate representative episode
          <select
            aria-label="Candidate representative episode"
            value={candidateEpisodeId}
            onChange={(event) => setCandidateEpisodeId(event.target.value)}
          >
            <option value="">Choose a candidate episode</option>
            {candidate.episodes.map((item) => (
              <option key={item.episode_id} value={item.episode_id}>
                {item.episode_id} · {item.review_status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Baseline representative episode
          <select
            aria-label="Baseline representative episode"
            value={baselineEpisodeId}
            onChange={(event) => setBaselineEpisodeId(event.target.value)}
            disabled={!baseline}
          >
            <option value="">
              {baseline
                ? "Choose a baseline episode"
                : baselineError || "Loading baseline episodes…"}
            </option>
            {baseline?.episodes.map((item) => (
              <option key={item.episode_id} value={item.episode_id}>
                {item.episode_id} · {item.review_status}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="representative-cards">
        {candidateEpisode && (
          <RepresentativeEvidenceCard
            key={`candidate:${candidate.id}:${candidateEpisode.episode_id}`}
            run={candidate}
            episode={candidateEpisode}
          />
        )}
        {baseline && baselineEpisode && (
          <RepresentativeEvidenceCard
            key={`baseline:${baseline.id}:${baselineEpisode.episode_id}`}
            run={baseline}
            episode={baselineEpisode}
          />
        )}
      </div>
    </section>
  );
}

export default function App({
  initialRunId,
  initialBaselineId,
  readOnly = false,
}: {
  initialRunId?: string;
  initialBaselineId?: string;
  readOnly?: boolean;
}) {
  const selectedRef = useRef("");
  const dirtyRef = useRef(false);
  const navigationVersionRef = useRef(0);
  const episodeIdRef = useRef("");
  const focusEpisodeAfterNavigationRef = useRef(false);
  const updateDirty = useCallback((dirty: boolean) => {
    dirtyRef.current = dirty;
  }, []);
  function navigate(action: () => void) {
    if (
      dirtyRef.current &&
      !window.confirm("Discard the unsaved review changes?")
    )
      return;
    navigationVersionRef.current += 1;
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
    [selected, setSelected] = useState(initialRunId || ""),
    [run, setRun] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true),
    [detailLoading, setDetailLoading] = useState(false),
    [error, setError] = useState(""),
    [detailError, setDetailError] = useState("");
  const [search, setSearch] = useState(""),
    [episodeSearch, setEpisodeSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [episodeId, setEpisodeId] = useState(""),
    [baselineId, setBaselineId] = useState(initialBaselineId || ""),
    [comparisonSelectionEpoch, setComparisonSelectionEpoch] = useState(0),
    [reload, setReload] = useState(0),
    [notice, setNotice] = useState("");
  selectedRef.current = selected;
  episodeIdRef.current = episodeId;
  async function loadRuns() {
    setLoading(true);
    setError("");
    try {
      const data = await request<{ runs: Run[] }>("/api/runs");
      setRuns((current) =>
        data.runs.map((next) => {
          const previous = current.find((r) => r.id === next.id);
          return mergeRunSnapshot(previous, next);
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
    setEpisodeSearch("");
  }, [selected]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    setDetailLoading(true);
    setDetailError("");
    setRun((current) => (current?.id === selected ? current : null));
    setNotice("");
    setFilter("all");
    request<Detail>(runPath(selected))
      .then((data) => {
        if (active) {
          setRun((current) => mergeRunSnapshot(current, data));
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
  function saved(
    updated: Detail,
    context: {
      runId: string;
      episodeId: string;
      navigationVersion: number;
      saveNext: boolean;
      queueEpisodeIds: string[];
    },
  ) {
    setRuns((items) =>
      items.map((r) =>
        r.id === updated.id ? mergeRunSnapshot(r, updated) : r,
      ),
    );
    if (selectedRef.current === updated.id) {
      setRun((current) => mergeRunSnapshot(current, updated));
      const canAdvance =
        context.saveNext &&
        run?.id === updated.id &&
        run.revision <= updated.revision &&
        selectedRef.current === context.runId &&
        episodeIdRef.current === context.episodeId &&
        navigationVersionRef.current === context.navigationVersion;
      if (canAdvance) {
        const query = episodeSearch.trim().toLowerCase();
        const matchesSearch = (candidate: Episode) =>
          !query ||
          candidate.episode_id.toLowerCase().includes(query) ||
          (candidate.failure_category || "").toLowerCase().includes(query) ||
          (candidate.annotation.notes || "").toLowerCase().includes(query) ||
          (candidate.annotation.exclusion_reason || "")
            .toLowerCase()
            .includes(query);
        const matchesFilter = (candidate: Episode) =>
          filter === "all" ||
          (filter === "unlabelled" &&
            candidate.review_status === "provisional") ||
          (filter === "reviewed" && candidate.review_status === "reviewed") ||
          (filter === "excluded" && candidate.review_status === "excluded") ||
          (filter === "success" &&
            candidate.review_status === "reviewed" &&
            candidate.success) ||
          (filter === "failure" &&
            candidate.review_status === "reviewed" &&
            !candidate.success);
        const oldIndex = context.queueEpisodeIds.indexOf(context.episodeId);
        const candidates = updated.episodes.filter(
          (item) =>
            item.review_status === "provisional" &&
            matchesFilter(item) &&
            matchesSearch(item),
        );
        const next = candidates.find((item) => {
          const index = context.queueEpisodeIds.indexOf(item.episode_id);
          return oldIndex < 0 || index > oldIndex;
        });
        navigationVersionRef.current += 1;
        setNotice(
          next
            ? "Review saved. Opened the next pending episode."
            : "Review saved. No later pending episodes in this filtered queue.",
        );
        focusEpisodeAfterNavigationRef.current = Boolean(next);
        episodeIdRef.current = next?.episode_id || "";
        setEpisodeId(next?.episode_id || "");
      } else {
        setNotice("Review saved. Metrics refreshed.");
      }
    }
  }
  const baseline = runs.find((r) => r.id === baselineId && r.id !== selected);
  const visible =
    run?.episodes.filter(
      (e) =>
        filter === "all" ||
        (filter === "unlabelled" && e.review_status === "provisional") ||
        (filter === "reviewed" && e.review_status === "reviewed") ||
        (filter === "excluded" && e.review_status === "excluded") ||
        (filter === "success" && e.review_status === "reviewed" && e.success) ||
        (filter === "failure" && e.review_status === "reviewed" && !e.success),
    ) || [];
  const episode = episodeId
    ? visible.find((e) => e.episode_id === episodeId) || visible[0]
    : undefined;
  const queuedEpisodes = visible.filter((e) => {
    const query = episodeSearch.trim().toLowerCase();
    return (
      !query ||
      e.episode_id.toLowerCase().includes(query) ||
      (e.failure_category || "").toLowerCase().includes(query) ||
      (e.annotation.notes || "").toLowerCase().includes(query) ||
      (e.annotation.exclusion_reason || "").toLowerCase().includes(query)
    );
  });
  const evidenceHeadingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (episode && focusEpisodeAfterNavigationRef.current) {
      evidenceHeadingRef.current?.focus();
      focusEpisodeAfterNavigationRef.current = false;
    }
  }, [episode?.episode_id]);
  useEffect(() => {
    const isEditableOrMediaControl = (target: EventTarget | null) => {
      if (!(target instanceof HTMLElement)) return false;
      return Boolean(
        target.closest(
          "button, [role='button'], a[href], summary, input, textarea, select, [contenteditable]:not([contenteditable='false']), video, audio, [role='slider']",
        ),
      );
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (isEditableOrMediaControl(event.target)) return;
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        const form = document.querySelector<HTMLFormElement>(".label-form");
        const button = form?.querySelector<HTMLButtonElement>(
          "[data-save-next='true']",
        );
        if (form && button && !button.disabled) {
          event.preventDefault();
          form.requestSubmit(button);
        }
        return;
      }
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey)
        return;
      if (["1", "2", "3"].includes(event.key)) {
        const option = document.querySelector<HTMLInputElement>(
          `input[name='outcome'][value='${event.key === "1" ? "success" : event.key === "2" ? "failure" : "excluded"}']`,
        );
        if (option && !option.disabled) {
          event.preventDefault();
          option.click();
        }
        return;
      }
      if (event.key !== "j" && event.key !== "k") return;
      const currentIndex = queuedEpisodes.findIndex(
        (item) => item.episode_id === episode?.episode_id,
      );
      const nextIndex = currentIndex + (event.key === "j" ? 1 : -1);
      const target = queuedEpisodes[nextIndex];
      if (target && target.episode_id !== episode?.episode_id) {
        event.preventDefault();
        navigate(() => {
          focusEpisodeAfterNavigationRef.current = true;
          setEpisodeId(target.episode_id);
          setNotice("");
        });
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [queuedEpisodes, episode?.episode_id, navigate]);
  const MainContent = readOnly ? "div" : "main";
  return (
    <div className={`app ${readOnly ? "readonly-app" : ""}`}>
      <aside className="sidebar">
        <a className="brand" href="#">
          <span className="brand-mark">
            L<span>↗</span>
          </span>
          <span>
            LaundryBench<small>EMBODIED AI LAB</small>
          </span>
        </a>
        <div className="nav-label">{readOnly ? "SHOWCASE" : "WORKSPACE"}</div>
        <div className="nav-active">
          <span>◫</span>{readOnly ? "Evidence explorer" : "Experiment review"}
          <span className="count">{runs.length}</span>
        </div>
        {!readOnly && <>
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
                      setComparisonSelectionEpoch((epoch) => epoch + 1);
                      setNotice("");
                    });
                }}
              >
                <span className="run-dot" />
                <span>
                  <strong>{r.id}</strong>
                  <small>
                    {r.summary.episodes} episodes ·{" "}
                    {r.summary.reviewed_episodes} reviewed ·{" "}
                    {r.summary.pending_episodes} pending ·{" "}
                    {r.summary.excluded_episodes} excluded
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
        </>}
      </aside>
      <MainContent className={readOnly ? "showcase-app-main" : undefined}>
        <div className="topbar">
          <span>
            Workspace <span className="slash">/</span> Experiments
          </span>
          <span className="local-label">
            <span />
            {readOnly ? "STATIC SHOWCASE" : "LOCAL REVIEW"}
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
              <div className="run-context-grid">
                <ExperimentContext run={run} />
                {baseline && <ExperimentContext run={baseline} baseline />}
              </div>
              <details className="run-overview" open={readOnly}>
                <summary>
                  <span className="overview-title">Run overview</span>
                  <span className="overview-hint">
                    Metrics, comparison, and run evidence
                  </span>
                </summary>
                <div className="overview-heading">
                  <span className="muted small">
                    Outcome metrics and recorded configuration
                  </span>
                  {!readOnly && <label className="baseline-picker">
                    Compare to
                    <select
                      aria-label="Baseline experiment"
                      value={baselineId === selected ? "" : baselineId}
                      onChange={(e) => {
                        setBaselineId(e.target.value);
                        setComparisonSelectionEpoch((epoch) => epoch + 1);
                      }}
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
                  </label>}
                </div>
                <div className="kpis">
                  <div className="kpi">
                    <span>Success rate</span>
                    <strong>
                      {run.summary.metric_episodes > 0 &&
                      run.summary.success_rate !== null
                        ? percent(run.summary.success_rate)
                        : "—"}
                    </strong>
                    <small>
                      {run.summary.successes} of {run.summary.metric_episodes}{" "}
                      reviewed
                    </small>
                    {run.summary.metric_episodes > 0 &&
                      run.summary.success_rate_ci && (
                        <small>
                          95% CI{" "}
                          {run.summary.success_rate_ci.map(percent).join(" – ")}
                        </small>
                      )}
                  </div>
                  <div className="kpi">
                    <span>Median completion</span>
                    <strong>
                      {run.summary.median_completion_time_s !== null
                        ? run.summary.median_completion_time_s.toFixed(2)
                        : "—"}
                      {run.summary.median_completion_time_s !== null && (
                        <i>s</i>
                      )}
                    </strong>
                    <small>Successful episodes only</small>
                  </div>
                  <div className="kpi">
                    <span>Intervention rate</span>
                    <strong>
                      {run.summary.metric_episodes > 0 &&
                      run.summary.intervention_rate !== null
                        ? percent(run.summary.intervention_rate)
                        : "—"}
                    </strong>
                    <small>Reviewed episodes only</small>
                  </div>
                  <div className="kpi">
                    <span>Decision coverage</span>
                    <strong>
                      {run.labelled_episodes}
                      <i>/ {run.summary.episodes}</i>
                    </strong>
                    <small>
                      {run.summary.reviewed_episodes} reviewed ·{" "}
                      {run.summary.pending_episodes} pending ·{" "}
                      {run.summary.excluded_episodes} excluded
                    </small>
                    <div className="coverage">
                      <span
                        style={{
                          width: `${run.summary.episodes ? (100 * run.labelled_episodes) / run.summary.episodes : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
                <RunComparison
                  candidate={run}
                  baseline={baseline}
                  selectionEpoch={comparisonSelectionEpoch}
                />
                <div className="insights">
                  <section className="panel failures">
                    <div className="section-heading">
                      <h3>Failure distribution</h3>
                      <span className="muted small">
                        Reviewed failure counts
                      </span>
                    </div>
                    {Object.keys(run.summary.failure_category_counts).length ? (
                      Object.entries(run.summary.failure_category_counts).map(
                        ([category, count]) => (
                          <div className="failure-row" key={category}>
                            <span>{category.replaceAll("_", " ")}</span>
                            <div>
                              <i
                                style={{
                                  width: `${run.summary.metric_episodes ? (100 * count) / run.summary.metric_episodes : 0}%`,
                                }}
                              />
                            </div>
                            <b>{count}</b>
                          </div>
                        ),
                      )
                    ) : (
                      <p className="empty-inline">
                        {run.summary.metric_episodes
                          ? "No reviewed failures."
                          : run.summary.pending_episodes ||
                              run.summary.excluded_episodes
                            ? "No outcome metrics until at least one episode is reviewed."
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
              </details>
              {baseline && (
                <RepresentativeEvidenceComparison
                  candidate={run}
                  baselineId={baseline.id}
                  baselineRevision={baseline.revision}
                />
              )}
              <div className="episodes-heading">
                <div>
                  <h2>Episode workspace</h2>
                  <p className="muted">
                    {readOnly
                      ? "Browse the exported evidence and review record."
                      : "Inspect the evidence. Label what actually happened."}
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
                    ["reviewed", "Reviewed"],
                    ["excluded", "Excluded"],
                    ["failure", "Failures"],
                    ["success", "Successes"],
                  ].map(([value, label]) => (
                    <button
                      key={value}
                      className={filter === value ? "selected" : ""}
                      aria-pressed={filter === value}
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
                <section
                  className="episode-table panel"
                  aria-label="Episode queue"
                >
                  <div className="table-caption">
                    <strong>Episode queue</strong>
                    <span>
                      {queuedEpisodes.length} / {visible.length}
                    </span>
                  </div>
                  <label className="episode-search">
                    <span aria-hidden="true">⌕</span>
                    <input
                      aria-label="Search episodes"
                      placeholder="Find an episode…"
                      value={episodeSearch}
                      onChange={(e) => {
                        navigationVersionRef.current += 1;
                        setEpisodeSearch(e.target.value);
                      }}
                    />
                  </label>
                  {episode &&
                    episodeSearch.trim() &&
                    !queuedEpisodes.some(
                      (queued) => queued.episode_id === episode.episode_id,
                    ) && (
                      <p className="queue-search-note" role="status">
                        Current episode remains open while the queue is
                        filtered.
                      </p>
                    )}
                  <div className="episode-list">
                    {queuedEpisodes.map((e, index) => (
                      <button
                        className={`episode-row ${episode?.episode_id === e.episode_id ? "selected" : ""}`}
                        data-episode-id={e.episode_id}
                        key={e.episode_id}
                        aria-current={
                          episode?.episode_id === e.episode_id
                            ? "true"
                            : undefined
                        }
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
                        <span className="episode-row-copy">
                          <strong>{e.episode_id}</strong>
                          <small>
                            {e.review_status === "reviewed"
                              ? "Reviewed"
                              : e.review_status === "excluded"
                                ? "Excluded"
                                : "Pending review"}
                          </small>
                          <span className="episode-outcome">
                            <i
                              className={
                                e.review_status !== "reviewed"
                                  ? "pending-dot"
                                  : e.success
                                    ? "success-dot"
                                    : "failure-dot"
                              }
                            />
                            {e.review_status === "reviewed"
                              ? e.success
                                ? "Success"
                                : "Failure"
                              : e.review_status === "excluded"
                                ? "Excluded"
                                : e.original_outcome.success
                                  ? "Recorded success"
                                  : "Recorded failure"}{" "}
                            · {e.duration_s.toFixed(1)}s
                          </span>
                        </span>
                      </button>
                    ))}
                    {!queuedEpisodes.length && (
                      <p className="empty-inline">
                        {visible.length
                          ? "No episodes match your search."
                          : "No episodes match this filter."}
                      </p>
                    )}
                  </div>
                </section>
                {episode ? (
                  <EpisodeReview
                    run={run}
                    episode={episode}
                    headingRef={evidenceHeadingRef}
                  />
                ) : (
                  <div className="panel empty-inline evidence-empty">
                    Select an episode to inspect its evidence.
                  </div>
                )}
                {episode ? (
                  readOnly ? (
                    <ReadOnlyReview episode={episode} />
                  ) : (
                  <LabelForm
                    key={`${run.id}/${episode.episode_id}`}
                    run={run}
                    episode={episode}
                    onSaved={saved}
                    onReload={() => navigate(() => setReload((r) => r + 1))}
                    onDirty={updateDirty}
                    navigationVersion={navigationVersionRef.current}
                    queueEpisodeIds={queuedEpisodes.map(
                      (item) => item.episode_id,
                    )}
                  />
                  )
                ) : (
                  <div className="panel empty-inline form-empty">
                    {readOnly
                      ? "Select an episode to inspect its review record."
                      : "Select an episode to add a manual review."}
                  </div>
                )}
              </div>
              {!readOnly && <p className="save-notice" role="status">
                {notice}
              </p>}
              <details className="provenance">
                <summary>Full run manifest</summary>
                <pre>{JSON.stringify(run.manifest, null, 2)}</pre>
              </details>
              <footer>
                LAUNDRYBENCH{" "}
                <span>
                  {readOnly
                    ? "Synthetic demonstration data. No physical results."
                    : "Reproducible experiments. Inspectable evidence. Better robot behavior."}
                </span>
              </footer>
            </div>
          )
        )}
      </MainContent>
    </div>
  );
}
