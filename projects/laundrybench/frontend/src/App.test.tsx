import {
  act,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";
import {
  ComparisonResult,
  Detail,
  Episode,
  EpisodeMedia,
  ExperimentMetadata,
  MediaStream,
} from "./api";
const detail: Detail = {
  id: "exp-001-baseline",
  revision: 0,
  labelled_episodes: 0,
  manifest: { robot_implementation: "MockRobot", policy_name: "mock-policy" },
  summary: {
    episodes: 1,
    reviewed_episodes: 0,
    pending_episodes: 1,
    excluded_episodes: 0,
    metric_episodes: 0,
    successes: 0,
    success_rate: null,
    reviewed_rate: 0,
    success_rate_ci: null,
    median_completion_time_s: null,
    intervention_rate: null,
    failure_category_counts: {},
    outcome_schema_version: 2,
    label_revision: 0,
  },
  quality: null,
  episodes: [
    {
      episode_id: "exp-001-baseline-000",
      success: true,
      duration_s: 2,
      intervention: false,
      failure_category: null,
      review_status: "provisional",
      outcome_source: "recorded",
      effective_outcome: {
        success: true,
        intervention: false,
        failure_category: null,
      },
      original_outcome: {
        success: true,
        intervention: false,
        failure_category: null,
      },
      annotation: { status: "unlabelled" },
    },
  ],
};
function withEpisodes(...episodes: Episode[]): Detail {
  return {
    ...detail,
    episodes,
    summary: {
      ...detail.summary,
      episodes: episodes.length,
      pending_episodes: episodes.filter(
        (item) => item.review_status === "provisional",
      ).length,
      reviewed_episodes: episodes.filter(
        (item) => item.review_status === "reviewed",
      ).length,
      excluded_episodes: episodes.filter(
        (item) => item.review_status === "excluded",
      ).length,
    },
  };
}
function makeEpisode(
  id: string,
  status: Episode["review_status"] = "provisional",
): Episode {
  const base = detail.episodes[0];
  return {
    ...base,
    episode_id: id,
    review_status: status,
    annotation:
      status === "reviewed"
        ? { status: "labelled", notes: "" }
        : { status: "unlabelled" },
  };
}
function metadata(
  options: {
    taskVersion?: string;
    protocolVersion?: string;
    revision?: number;
  } = {},
): ExperimentMetadata {
  return {
    schema_version: 1,
    revision: options.revision ?? 0,
    name: "Laundry fold trial",
    hypothesis: "Changing the grasp pose improves success.",
    what_changed: "Raised the grasp start by 2 cm.",
    task: { id: "laundry_fold", version: options.taskVersion ?? "1" },
    protocol: { id: "paired-v1", version: options.protocolVersion ?? "1" },
    dataset: { id: "fold-set", revision: "r3" },
    checkpoint: { identity: "model-abc" },
    effective_overrides: { attempts: 10, camera: "front" },
    evidence_links: [
      { label: "Trial notes", url: "https://example.test/trial" },
    ],
  };
}
function api(
  putStatus = 200,
  runDetail: Detail = detail,
  runList: Detail[] = [runDetail],
  mediaStreams: MediaStream[] = [],
  mediaEvents: EpisodeMedia["events"] = [],
) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, options) => {
      const url = String(input);
      if (url.includes("/compare/")) {
        const parsed = new URL(url, "http://local.test");
        const parts = parsed.pathname.split("/").filter(Boolean);
        const candidateId = decodeURIComponent(parts[2]);
        const baselineId = decodeURIComponent(parts[4]);
        const candidate =
          runList.find((item) => item.id === candidateId) || runDetail;
        const baseline =
          runList.find((item) => item.id === baselineId) || runDetail;
        const required = [
          [
            "task.id",
            candidate.experiment?.task.id,
            baseline.experiment?.task.id,
          ],
          [
            "task.version",
            candidate.experiment?.task.version,
            baseline.experiment?.task.version,
          ],
          [
            "protocol.id",
            candidate.experiment?.protocol.id,
            baseline.experiment?.protocol.id,
          ],
          [
            "protocol.version",
            candidate.experiment?.protocol.version,
            baseline.experiment?.protocol.version,
          ],
        ] as const;
        const differences: ComparisonResult["compatibility"]["differences"] =
          {};
        const mismatches: string[] = [];
        const unknown: string[] = [];
        for (const [key, candidateValue, baselineValue] of required) {
          if (!candidateValue || !baselineValue)
            unknown.push(`${key} is missing`);
          else if (candidateValue !== baselineValue) {
            mismatches.push(`${key} differs`);
            differences[key] = {
              candidate: candidateValue,
              baseline: baselineValue,
            };
          }
        }
        const status = mismatches.length
          ? "mismatched"
          : unknown.length
            ? "unknown"
            : "matched";
        const acknowledged =
          parsed.searchParams.get("acknowledge_incompatible") === "1";
        const subtract = (a: number | null, b: number | null) =>
          a === null || b === null ? null : a - b;
        const failureKeys = new Set([
          ...Object.keys(candidate.summary.failure_category_counts),
          ...Object.keys(baseline.summary.failure_category_counts),
        ]);
        const result: ComparisonResult = {
          candidate_id: candidateId,
          baseline_id: baselineId,
          candidate_context: candidate.experiment || null,
          baseline_context: baseline.experiment || null,
          candidate_label_revision: candidate.revision,
          baseline_label_revision: baseline.revision,
          compatibility: {
            status,
            reasons: [...mismatches, ...unknown],
            differences,
            advisories: [],
          },
          candidate: candidate.summary,
          baseline: baseline.summary,
          delta:
            status === "matched" || acknowledged
              ? {
                  reviewed_episodes:
                    candidate.summary.reviewed_episodes -
                    baseline.summary.reviewed_episodes,
                  successes:
                    candidate.summary.successes - baseline.summary.successes,
                  success_rate: subtract(
                    candidate.summary.success_rate,
                    baseline.summary.success_rate,
                  ),
                  reviewed_rate: subtract(
                    candidate.summary.reviewed_rate,
                    baseline.summary.reviewed_rate,
                  ),
                  intervention_rate: subtract(
                    candidate.summary.intervention_rate,
                    baseline.summary.intervention_rate,
                  ),
                  failure_category_counts: Object.fromEntries(
                    [...failureKeys].map((key) => [
                      key,
                      (candidate.summary.failure_category_counts[key] || 0) -
                        (baseline.summary.failure_category_counts[key] || 0),
                    ]),
                  ),
                }
              : null,
        };
        return new Response(JSON.stringify(result));
      }
      if (options?.method === "PUT") {
        const payload = JSON.parse(String(options.body || "{}"));
        const excluded = payload.status === "excluded";
        const targetEpisodeId = decodeURIComponent(url.split("/").at(-2) || "");
        const originalEpisode =
          runDetail.episodes.find(
            (item) => item.episode_id === targetEpisodeId,
          ) || runDetail.episodes[0];
        const reviewedOutcome = {
          success: payload.success ?? originalEpisode.effective_outcome.success,
          intervention:
            payload.intervention ??
            originalEpisode.effective_outcome.intervention,
          failure_category:
            payload.failure_category ??
            (payload.success === true
              ? null
              : originalEpisode.effective_outcome.failure_category),
        };
        const updatedEpisode: Episode = excluded
          ? {
              ...originalEpisode,
              success: originalEpisode.original_outcome.success,
              intervention: originalEpisode.original_outcome.intervention,
              failure_category:
                originalEpisode.original_outcome.failure_category,
              review_status: "excluded",
              outcome_source: "recorded",
              effective_outcome: originalEpisode.original_outcome,
              annotation: {
                status: "excluded",
                exclusion_reason: payload.exclusion_reason,
              },
            }
          : {
              ...originalEpisode,
              ...reviewedOutcome,
              review_status: "reviewed",
              outcome_source: "label",
              effective_outcome: reviewedOutcome,
              annotation: { status: "labelled", notes: payload.notes || "" },
            };
        const episodes = runDetail.episodes.map((item) =>
          item.episode_id === originalEpisode.episode_id
            ? updatedEpisode
            : item,
        );
        const reviewedCount = episodes.filter(
          (item) => item.review_status === "reviewed",
        ).length;
        const excludedCount = episodes.filter(
          (item) => item.review_status === "excluded",
        ).length;
        const metricEpisodes = reviewedCount;
        const successes = episodes.filter(
          (item) =>
            item.review_status === "reviewed" && item.effective_outcome.success,
        ).length;
        const failureCounts = episodes.reduce<Record<string, number>>(
          (counts, item) => {
            if (
              item.review_status === "reviewed" &&
              !item.effective_outcome.success
            ) {
              const category =
                item.effective_outcome.failure_category || "unspecified";
              counts[category] = (counts[category] || 0) + 1;
            }
            return counts;
          },
          {},
        );
        return new Response(
          JSON.stringify(
            putStatus === 409
              ? { error: "Review revision changed" }
              : {
                  ...runDetail,
                  revision: runDetail.revision + 1,
                  labelled_episodes: reviewedCount + excludedCount,
                  summary: {
                    ...runDetail.summary,
                    reviewed_episodes: reviewedCount,
                    pending_episodes: Math.max(
                      0,
                      runDetail.summary.episodes -
                        reviewedCount -
                        excludedCount,
                    ),
                    excluded_episodes: excludedCount,
                    metric_episodes: metricEpisodes,
                    successes,
                    success_rate:
                      metricEpisodes > 0 ? successes / metricEpisodes : null,
                    reviewed_rate:
                      runDetail.summary.episodes > 0
                        ? reviewedCount / runDetail.summary.episodes
                        : null,
                    success_rate_ci: metricEpisodes > 0 ? [0, 0.8] : null,
                    median_completion_time_s: null,
                    intervention_rate:
                      metricEpisodes > 0
                        ? episodes.filter(
                            (item) =>
                              item.review_status === "reviewed" &&
                              item.effective_outcome.intervention,
                          ).length / metricEpisodes
                        : null,
                    failure_category_counts: failureCounts,
                    label_revision: runDetail.summary.label_revision + 1,
                  },
                  episodes,
                },
          ),
          { status: putStatus },
        );
      }
      if (url.endsWith("/trace"))
        return new Response(JSON.stringify({ steps: [] }));
      if (url.endsWith("/media")) {
        const episodeId = decodeURIComponent(url.split("/").at(-2) || "");
        return new Response(
          JSON.stringify({
            schema_version: 1,
            episode_id: episodeId,
            streams: mediaStreams,
            events: mediaEvents,
          }),
        );
      }
      if (url === "/api/runs")
        return new Response(JSON.stringify({ runs: runList }));
      const requestedRun = runList.find((candidate) =>
        url.includes(candidate.id),
      );
      return new Response(JSON.stringify(requestedRun || runDetail));
    });
}
afterEach(() => vi.restoreAllMocks());
it("saves a manual review with the current revision and preserves original evidence", async () => {
  const fetch = api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByLabelText("Failure"));
  await userEvent.selectOptions(
    screen.getByLabelText("Failure category"),
    "missed_grasp",
  );
  await userEvent.type(screen.getByLabelText("Review notes"), "Observed slip");
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await screen.findByText("Review saved. Metrics refreshed.");
  const call = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(call?.[1]?.body))).toEqual({
    success: false,
    intervention: false,
    failure_category: "missed_grasp",
    notes: "Observed slip",
    expected_revision: 0,
  });
  expect(
    screen.getByText("Reviewed", { selector: ".pill" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Recorded outcome").querySelector("b"),
  ).toHaveTextContent("Success");
});
it("keeps edits visible on a conflicting review and requires explicit reload", async () => {
  api(409);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.type(
    screen.getByLabelText("Review notes"),
    "Do not lose this",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await screen.findByText("Review revision changed");
  expect(screen.getByLabelText("Review notes")).toHaveValue("Do not lose this");
  expect(
    screen.getByRole("button", { name: "Reload latest review" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Review saved. Metrics refreshed."),
  ).not.toBeInTheDocument();
});
it("advances through the filtered pending queue after a confirmed save", async () => {
  const run = withEpisodes(
    makeEpisode("exp-001-baseline-000"),
    makeEpisode("exp-001-baseline-001"),
    makeEpisode("exp-001-baseline-002"),
  );
  api(200, run);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByRole("button", { name: "Needs review" }));
  await userEvent.click(
    screen.getByRole("button", {
      name: "Save & next: save review and go to next pending episode",
    }),
  );
  const nextHeading = await screen.findByRole("heading", {
    name: "exp-001-baseline-001",
  });
  expect(nextHeading).toHaveFocus();
  expect(
    screen.getByText("Review saved. Opened the next pending episode."),
  ).toBeInTheDocument();
});
it("clears the selection at the end of the filtered queue without wrapping to an earlier pending row", async () => {
  const run = withEpisodes(
    makeEpisode("exp-001-baseline-000"),
    makeEpisode("exp-001-baseline-001"),
    makeEpisode("exp-001-baseline-002", "reviewed"),
  );
  api(200, run);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(
    screen.getByRole("button", { name: /exp-001-baseline-001/ }),
  );
  await userEvent.click(
    screen.getByRole("button", {
      name: "Save & next: save review and go to next pending episode",
    }),
  );
  expect(
    await screen.findByText(
      "Review saved. No later pending episodes in this filtered queue.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Manual review" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "exp-001-baseline-000" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /exp-001-baseline-000/ }),
  ).toHaveTextContent("Pending review");
});
it("ignores decision shortcuts in editable fields and native video controls", async () => {
  api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  const notes = screen.getByLabelText("Review notes");
  fireEvent.keyDown(notes, { key: "2" });
  expect(screen.queryByLabelText("Failure category")).not.toBeInTheDocument();
  const video = document.createElement("video");
  video.controls = true;
  document.body.append(video);
  fireEvent.keyDown(video, { key: "3", bubbles: true });
  expect(
    screen.queryByLabelText("Reason for exclusion"),
  ).not.toBeInTheDocument();
  video.remove();
  fireEvent.keyDown(document.body, { key: "2" });
  expect(await screen.findByLabelText("Failure category")).toBeInTheDocument();
  fireEvent.keyDown(document.body, { key: "1" });
  expect(screen.queryByLabelText("Failure category")).not.toBeInTheDocument();
});
it("ignores shortcuts while a native button has focus", async () => {
  const fetch = api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  const saveNext = screen.getByRole("button", {
    name: "Save & next: save review and go to next pending episode",
  });
  saveNext.focus();
  fireEvent.keyDown(saveNext, { key: "2", bubbles: true });
  fireEvent.keyDown(saveNext, { key: "Enter", ctrlKey: true, bubbles: true });
  expect(screen.queryByLabelText("Failure category")).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
    false,
  );
});
it("uses j/k and Ctrl+Enter through the single save-and-next form path", async () => {
  const run = withEpisodes(
    makeEpisode("exp-001-baseline-000"),
    makeEpisode("exp-001-baseline-001"),
    makeEpisode("exp-001-baseline-002"),
  );
  const fetch = api(200, run);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  fireEvent.keyDown(document.body, { key: "j" });
  expect(
    await screen.findByRole("heading", { name: "exp-001-baseline-001" }),
  ).toHaveFocus();
  fireEvent.keyDown(document.body, { key: "k" });
  expect(
    await screen.findByRole("heading", { name: "exp-001-baseline-000" }),
  ).toHaveFocus();
  fireEvent.keyDown(document.body, { key: "Enter", ctrlKey: true });
  expect(
    await screen.findByRole("heading", { name: "exp-001-baseline-001" }),
  ).toHaveFocus();
  expect(
    fetch.mock.calls.filter(([, init]) => init?.method === "PUT"),
  ).toHaveLength(1);
});
it("does not let a delayed save response move the user after they navigate", async () => {
  const run = withEpisodes(
    makeEpisode("exp-001-baseline-000"),
    makeEpisode("exp-001-baseline-001"),
    makeEpisode("exp-001-baseline-002"),
  );
  const fetch = api(200, run);
  const implementation = fetch.getMockImplementation()!;
  let releasePut!: () => void;
  const pendingPut = new Promise<void>((resolve) => {
    releasePut = resolve;
  });
  fetch.mockImplementation(async (input, options) => {
    if (options?.method === "PUT") await pendingPut;
    return implementation(input, options);
  });
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(
    screen.getByRole("button", {
      name: "Save & next: save review and go to next pending episode",
    }),
  );
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
      true,
    ),
  );
  await userEvent.click(
    screen.getByRole("button", { name: /exp-001-baseline-001/ }),
  );
  expect(
    await screen.findByRole("heading", { name: "exp-001-baseline-001" }),
  ).toBeInTheDocument();
  await act(async () => {
    releasePut();
  });
  await screen.findByText("Review saved. Metrics refreshed.");
  expect(
    screen.getByRole("heading", { name: "exp-001-baseline-001" }),
  ).toBeInTheDocument();
});
it("keeps revision 2 when a delayed revision 1 save response arrives", async () => {
  const run = withEpisodes(
    makeEpisode("exp-001-baseline-000"),
    makeEpisode("exp-001-baseline-001"),
  );
  const revision2 = {
    ...run,
    revision: 2,
    summary: { ...run.summary, label_revision: 2 },
  };
  const fetch = api(200, run);
  const implementation = fetch.getMockImplementation()!;
  let releasePut!: () => void;
  let refreshed = false;
  const pendingPut = new Promise<void>((resolve) => {
    releasePut = resolve;
  });
  fetch.mockImplementation(async (input, options) => {
    const url = String(input);
    if (options?.method === "PUT") {
      await pendingPut;
      return implementation(input, options);
    }
    if (refreshed && url === "/api/runs") {
      return new Response(JSON.stringify({ runs: [revision2] }));
    }
    if (
      refreshed &&
      url.includes(run.id) &&
      !url.endsWith("/trace") &&
      !url.endsWith("/media")
    ) {
      return new Response(JSON.stringify(revision2));
    }
    return implementation(input, options);
  });
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(
    screen.getByRole("button", {
      name: "Save & next: save review and go to next pending episode",
    }),
  );
  await waitFor(() =>
    expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
      true,
    ),
  );
  refreshed = true;
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh experiments" }),
  );
  expect(await screen.findByText("Revision 2")).toBeInTheDocument();
  await act(async () => {
    releasePut();
  });
  await screen.findByText("Review saved. Metrics refreshed.");
  expect(screen.getByText("Revision 2")).toBeInTheDocument();
});
it("excludes an episode with the exact reason payload and restores it as a reviewed failure", async () => {
  const fetch = api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByLabelText("Exclude"));
  const reason = screen.getByLabelText("Reason for exclusion");
  expect(reason).toBeRequired();
  await userEvent.type(reason, "   ");
  await userEvent.click(screen.getByRole("button", { name: "Save exclusion" }));
  expect(
    screen.getByText("Enter a reason before excluding this episode."),
  ).toBeInTheDocument();
  expect(fetch.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
    false,
  );
  await userEvent.clear(reason);
  await userEvent.type(reason, "Camera view was fully occluded");
  await userEvent.click(screen.getByRole("button", { name: "Save exclusion" }));
  await screen.findByText("Review saved. Metrics refreshed.");
  expect(
    screen.getByText("Excluded", { selector: ".pill" }),
  ).toBeInTheDocument();
  const puts = fetch.mock.calls.filter(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(puts[0]?.[1]?.body))).toEqual({
    status: "excluded",
    exclusion_reason: "Camera view was fully occluded",
    expected_revision: 0,
  });
  expect(
    screen.getByText("0 reviewed · 0 pending · 1 excluded"),
  ).toBeInTheDocument();

  await userEvent.click(screen.getByLabelText("Failure"));
  await userEvent.selectOptions(
    screen.getByLabelText("Failure category"),
    "missed_grasp",
  );
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await screen.findByText("Review saved. Metrics refreshed.", { exact: true });
  const updatedPuts = fetch.mock.calls.filter(
    ([, init]) => init?.method === "PUT",
  );
  expect(JSON.parse(String(updatedPuts[1]?.[1]?.body))).toMatchObject({
    success: false,
    failure_category: "missed_grasp",
    expected_revision: 1,
  });
  expect(
    screen.getByText("Reviewed", { selector: ".pill" }),
  ).toBeInTheDocument();
});

it("keeps zero-denominator metrics null and suppresses baseline deltas", async () => {
  const baseline: Detail = { ...detail, id: "exp-002-baseline" };
  api(200, detail, [detail, baseline]);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByText("Run overview"));
  await userEvent.selectOptions(
    screen.getByLabelText("Baseline experiment"),
    baseline.id,
  );
  expect(screen.getByText("0 of 0 reviewed")).toBeInTheDocument();
  expect(
    screen.getByText("Success rate", { selector: "span" }),
  ).toBeInTheDocument();
  expect(screen.queryByText(/pp vs baseline/)).not.toBeInTheDocument();
  expect(screen.getAllByText("—", { selector: ".kpi strong" })).toHaveLength(3);
});

it("shows human context, provenance, matched comparison, and independently selected evidence", async () => {
  const candidate = {
    ...withEpisodes(makeEpisode("exp-101-candidate-000")),
    id: "exp-101-candidate",
    experiment: metadata(),
  };
  const baseline = {
    ...withEpisodes(makeEpisode("exp-100-baseline-000")),
    id: "exp-100-baseline",
    experiment: metadata(),
  };
  api(200, candidate, [candidate, baseline]);
  render(<App />);
  await screen.findByText("Laundry fold trial");
  expect(
    screen.getByText("Changing the grasp pose improves success."),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByText("Protocol, data, checkpoint, overrides, and links"),
  );
  expect(screen.getByText(/laundry_fold/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Trial notes" })).toHaveAttribute(
    "href",
    "https://example.test/trial",
  );
  await userEvent.click(screen.getByText("Run overview"));
  await userEvent.selectOptions(
    screen.getByLabelText("Baseline experiment"),
    baseline.id,
  );
  expect(
    await screen.findByRole("status", { name: "Compatibility: matched" }),
  ).toBeInTheDocument();
  const successRow = screen.getByRole("row", { name: /Success rate/ });
  expect(
    within(successRow).getAllByText(/0 reviewed episodes; no interval/),
  ).toHaveLength(2);
  expect(
    screen.getByText("No reviewed failure categories in either run."),
  ).toBeInTheDocument();
  await userEvent.selectOptions(
    screen.getByLabelText("Candidate representative episode"),
    "exp-101-candidate-000",
  );
  await waitFor(() =>
    expect(
      screen.getByLabelText("Baseline representative episode"),
    ).toBeEnabled(),
  );
  await userEvent.selectOptions(
    screen.getByLabelText("Baseline representative episode"),
    "exp-100-baseline-000",
  );
  expect(
    await screen.findByText(
      /Matching episode IDs do not indicate paired trials/,
    ),
  ).toBeInTheDocument();
  expect(screen.getAllByText("exp-101-candidate-000").length).toBeGreaterThan(
    1,
  );
  expect(screen.getByText("exp-100-baseline-000")).toBeInTheDocument();
});

it("requires a fresh acknowledgment when the baseline selection changes and returns", async () => {
  const candidate = {
    ...withEpisodes(makeEpisode("exp-101-candidate-000")),
    id: "exp-101-candidate",
    experiment: metadata(),
  };
  const baselineA = {
    ...withEpisodes(makeEpisode("exp-100-baseline-000")),
    id: "exp-100-baseline",
    experiment: metadata({ protocolVersion: "2" }),
  };
  const baselineB = {
    ...withEpisodes(makeEpisode("exp-099-baseline-000")),
    id: "exp-099-baseline",
    experiment: metadata({ taskVersion: "2" }),
  };
  const fetch = api(200, candidate, [candidate, baselineA, baselineB]);
  render(<App />);
  await screen.findByText("Laundry fold trial");
  await userEvent.click(screen.getByText("Run overview"));
  const picker = screen.getByLabelText("Baseline experiment");
  const ackName =
    "Acknowledge incompatible comparison and show descriptive delta";
  await userEvent.selectOptions(picker, baselineA.id);
  expect(
    await screen.findByRole("status", { name: "Compatibility: mismatched" }),
  ).toBeInTheDocument();
  const comparePanel = screen.getByRole("region", {
    name: "Baseline comparison",
  });
  expect(
    within(comparePanel).getAllByText(
      "0 reviewed · 1 pending · 0 excluded / 1 total",
    ),
  ).toHaveLength(2);
  expect(
    screen.getByRole("heading", { name: "Per-run outcome summaries" }),
  ).toBeInTheDocument();
  const preAckSuccessRate = screen.getByRole("row", { name: /Success rate/ });
  expect(
    within(preAckSuccessRate).getAllByText(
      "— (0 reviewed episodes; no interval)",
    ),
  ).toHaveLength(2);
  expect(
    within(preAckSuccessRate).getByText("Withheld until acknowledged"),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Descriptive outcome differences" }),
  ).not.toBeInTheDocument();
  await userEvent.click(await screen.findByRole("button", { name: ackName }));
  expect(
    await screen.findByRole("heading", {
      name: "Descriptive outcome differences",
    }),
  ).toBeInTheDocument();
  await userEvent.selectOptions(picker, baselineB.id);
  expect(
    await screen.findByRole("button", { name: ackName }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Descriptive outcome differences" }),
  ).not.toBeInTheDocument();
  await userEvent.selectOptions(picker, baselineA.id);
  expect(
    await screen.findByRole("button", { name: ackName }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Descriptive outcome differences" }),
  ).not.toBeInTheDocument();
  const acknowledgedRequests = fetch.mock.calls.filter(([input]) =>
    String(input).includes("acknowledge_incompatible=1"),
  );
  expect(acknowledgedRequests).toHaveLength(1);
});

it("retries an acknowledged comparison after a request failure", async () => {
  const candidate = {
    ...withEpisodes(makeEpisode("exp-101-candidate-000")),
    id: "exp-101-candidate",
    experiment: metadata(),
  };
  const baseline = {
    ...withEpisodes(makeEpisode("exp-100-baseline-000")),
    id: "exp-100-baseline",
    experiment: metadata({ protocolVersion: "2" }),
  };
  const fetch = api(200, candidate, [candidate, baseline]);
  const implementation = fetch.getMockImplementation()!;
  let acknowledgedCalls = 0;
  fetch.mockImplementation(async (input, options) => {
    const url = String(input);
    if (url.includes("acknowledge_incompatible=1")) {
      acknowledgedCalls += 1;
      if (acknowledgedCalls === 1) {
        return new Response(
          JSON.stringify({ error: "Compare temporarily unavailable" }),
          { status: 503 },
        );
      }
    }
    return implementation(input, options);
  });
  render(<App />);
  await screen.findByText("Laundry fold trial");
  await userEvent.click(screen.getByText("Run overview"));
  await userEvent.selectOptions(
    screen.getByLabelText("Baseline experiment"),
    baseline.id,
  );
  expect(
    await screen.findByRole("status", { name: "Compatibility: mismatched" }),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", {
      name: "Acknowledge incompatible comparison and show descriptive delta",
    }),
  );
  expect(
    await screen.findByText("Compare temporarily unavailable"),
  ).toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: "Retry comparison" }),
  );
  expect(
    await screen.findByRole("heading", {
      name: "Descriptive outcome differences",
    }),
  ).toBeInTheDocument();
  expect(acknowledgedCalls).toBe(2);
  expect(
    fetch.mock.calls.filter(([input]) =>
      String(input).includes("acknowledge_incompatible=1"),
    ),
  ).toHaveLength(2);
});

it("ignores a delayed comparison after the baseline selection changes", async () => {
  const candidate = {
    ...withEpisodes(makeEpisode("exp-101-candidate-000")),
    id: "exp-101-candidate",
    experiment: metadata(),
  };
  const baselineA = {
    ...withEpisodes(makeEpisode("exp-100-baseline-000")),
    id: "exp-100-baseline",
    experiment: metadata({ protocolVersion: "2" }),
  };
  const baselineB = {
    ...withEpisodes(makeEpisode("exp-099-baseline-000")),
    id: "exp-099-baseline",
    experiment: metadata(),
  };
  const fetch = api(200, candidate, [candidate, baselineA, baselineB]);
  const implementation = fetch.getMockImplementation()!;
  let releaseA!: () => void;
  let oldRequestSettled = false;
  const pausedA = new Promise<void>((resolve) => {
    releaseA = resolve;
  });
  fetch.mockImplementation(async (input, options) => {
    const url = String(input);
    if (url.includes(`/compare/${baselineA.id}`)) {
      await pausedA;
      const response = await implementation(input, options);
      oldRequestSettled = true;
      return response;
    }
    return implementation(input, options);
  });
  render(<App />);
  await screen.findByText("Laundry fold trial");
  await userEvent.click(screen.getByText("Run overview"));
  const picker = screen.getByLabelText("Baseline experiment");
  await userEvent.selectOptions(picker, baselineA.id);
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(([input]) =>
        String(input).includes(`/compare/${baselineA.id}`),
      ),
    ).toBe(true),
  );
  await userEvent.selectOptions(picker, baselineB.id);
  expect(
    await screen.findByRole("status", { name: "Compatibility: matched" }),
  ).toBeInTheDocument();
  await act(async () => {
    releaseA();
  });
  await waitFor(() => expect(oldRequestSettled).toBe(true));
  expect(
    screen.getByRole("status", { name: "Compatibility: matched" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("status", { name: "Compatibility: mismatched" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", {
      name: "Acknowledge incompatible comparison and show descriptive delta",
    }),
  ).not.toBeInTheDocument();
});

it("does not show an older baseline detail after a newer label revision loads", async () => {
  const candidate = {
    ...withEpisodes(makeEpisode("exp-101-candidate-000")),
    id: "exp-101-candidate",
    experiment: metadata(),
  };
  const oldEpisode = makeEpisode("exp-100-baseline-old");
  const baselineV0 = {
    ...withEpisodes(oldEpisode),
    id: "exp-100-baseline",
    experiment: metadata(),
  };
  const baselineV1 = {
    ...baselineV0,
    revision: 1,
    summary: { ...baselineV0.summary, label_revision: 1 },
    episodes: [makeEpisode("exp-100-baseline-new")],
  };
  const fetch = api(200, candidate, [candidate, baselineV0]);
  const implementation = fetch.getMockImplementation()!;
  let refreshComplete = false;
  let releaseOldDetail!: () => void;
  let oldDetailSettled = false;
  const pausedOldDetail = new Promise<void>((resolve) => {
    releaseOldDetail = resolve;
  });
  fetch.mockImplementation(async (input, options) => {
    const url = String(input);
    if (url === "/api/runs" && refreshComplete) {
      return new Response(JSON.stringify({ runs: [candidate, baselineV1] }));
    }
    if (url === `/api/runs/${baselineV0.id}`) {
      if (!refreshComplete) {
        await pausedOldDetail;
        oldDetailSettled = true;
        return new Response(JSON.stringify(baselineV0));
      }
      return new Response(JSON.stringify(baselineV1));
    }
    return implementation(input, options);
  });
  render(<App />);
  await screen.findByText("Laundry fold trial");
  await userEvent.click(screen.getByText("Run overview"));
  await userEvent.selectOptions(
    screen.getByLabelText("Baseline experiment"),
    baselineV0.id,
  );
  await waitFor(() =>
    expect(
      fetch.mock.calls.some(
        ([input]) => String(input) === `/api/runs/${baselineV0.id}`,
      ),
    ).toBe(true),
  );
  refreshComplete = true;
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh experiments" }),
  );
  const baselineEpisodePicker = screen.getByLabelText(
    "Baseline representative episode",
  );
  await waitFor(() => expect(baselineEpisodePicker).toBeEnabled());
  await userEvent.selectOptions(baselineEpisodePicker, "exp-100-baseline-new");
  expect(screen.getByText("exp-100-baseline-new")).toBeInTheDocument();
  expect(screen.queryByText("exp-100-baseline-old")).not.toBeInTheDocument();
  await act(async () => {
    releaseOldDetail();
  });
  await waitFor(() => expect(oldDetailSettled).toBe(true));
  expect(screen.getByText("exp-100-baseline-new")).toBeInTheDocument();
  expect(screen.queryByText("exp-100-baseline-old")).not.toBeInTheDocument();
});

it("labels legacy run context as missing", async () => {
  api();
  render(<App />);
  expect(
    await screen.findByText(
      "No experiment context sidecar is recorded for this run. It may be a legacy run.",
    ),
  ).toBeInTheDocument();
});

it("merges a newer sidecar context without replacing newer outcome revisions", async () => {
  const current = {
    ...detail,
    revision: 2,
    experiment: { ...metadata({ revision: 0 }), name: "Older context" },
  };
  const incoming = {
    ...detail,
    revision: 1,
    experiment: { ...metadata({ revision: 1 }), name: "Newer context" },
  };
  const fetch = api(200, current, [current]);
  const implementation = fetch.getMockImplementation()!;
  let refreshed = false;
  fetch.mockImplementation(async (input, options) => {
    const url = String(input);
    if (refreshed && url === "/api/runs") {
      return new Response(JSON.stringify({ runs: [incoming] }));
    }
    if (refreshed && url === `/api/runs/${current.id}`) {
      return new Response(JSON.stringify(incoming));
    }
    return implementation(input, options);
  });
  render(<App />);
  expect(await screen.findByText("Older context")).toBeInTheDocument();
  refreshed = true;
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh experiments" }),
  );
  expect(await screen.findByText("Newer context")).toBeInTheDocument();
  expect(screen.getByText("Revision 2")).toBeInTheDocument();
});

it("shows network errors without inventing runs", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Server offline"));
  render(<App />);
  await screen.findByRole("heading", { name: "Experiments unavailable" });
  expect(screen.getByText("Server offline")).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Run overview" }),
  ).not.toBeInTheDocument();
});
it("shows explicit empty state for an empty artifacts directory", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ runs: [] })),
  );
  render(<App />);
  await waitFor(() =>
    expect(
      screen.getByRole("heading", {
        name: "Your first experiment starts here.",
      }),
    ).toBeInTheDocument(),
  );
});
it("saves interventions using the backend failure contract", async () => {
  const fetch = api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByLabelText("Human intervention required"));
  expect(screen.getByLabelText("Failure")).toBeChecked();
  expect(screen.getByLabelText("Failure category")).toHaveValue("intervention");
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await screen.findByText("Review saved. Metrics refreshed.");
  const call = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
    success: false,
    intervention: true,
    failure_category: "intervention",
  });
});
it("keeps an unsaved label draft mounted while video playback updates the trace cursor", async () => {
  const streams: MediaStream[] = [
    {
      camera: "front",
      path: "media/front.mp4",
      mime_type: "video/mp4",
      duration_s: 1,
      trace_start_s: 1000,
      url: "/api/media/front",
    },
  ];
  api(200, detail, [detail], streams, []);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  const notes = screen.getByLabelText("Review notes");
  await userEvent.type(notes, "Keep my review draft during playback");
  const video = await screen.findByLabelText("Episode video");
  let currentTime = 0;
  Object.defineProperty(video, "currentTime", {
    configurable: true,
    get: () => currentTime,
    set: (value: number) => {
      currentTime = value;
    },
  });
  currentTime = 0.25;
  fireEvent.timeUpdate(video);
  expect(screen.getByLabelText("Review notes")).toHaveValue(
    "Keep my review draft during playback",
  );
  expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
});

it("searches episode IDs, failure categories, and notes without losing edits, and resets on run change", async () => {
  const categoryEpisode: Episode = {
    ...detail.episodes[0],
    episode_id: "exp-001-multi-001",
    success: false,
    failure_category: "missed_grasp",
    review_status: "provisional",
    outcome_source: "recorded",
    effective_outcome: {
      success: false,
      intervention: false,
      failure_category: "missed_grasp",
    },
    original_outcome: {
      success: false,
      intervention: false,
      failure_category: "missed_grasp",
    },
  };
  const notesEpisode: Episode = {
    ...detail.episodes[0],
    episode_id: "exp-001-multi-002",
    success: false,
    failure_category: "unspecified",
    original_outcome: {
      success: false,
      intervention: false,
      failure_category: null,
    },
    review_status: "reviewed",
    outcome_source: "label",
    effective_outcome: {
      success: false,
      intervention: false,
      failure_category: "unspecified",
    },
    annotation: { status: "labelled", notes: "towel snag" },
  };
  const excludedEpisode: Episode = {
    ...detail.episodes[0],
    episode_id: "exp-001-multi-003",
    review_status: "excluded",
    outcome_source: "recorded",
    annotation: { status: "excluded", exclusion_reason: "blurred clip" },
  };
  const multi: Detail = {
    ...detail,
    id: "exp-001-multi",
    labelled_episodes: 2,
    summary: {
      ...detail.summary,
      episodes: 4,
      reviewed_episodes: 1,
      pending_episodes: 2,
      excluded_episodes: 1,
      metric_episodes: 1,
      successes: 0,
      success_rate: 0,
      reviewed_rate: 1 / 4,
      success_rate_ci: [0, 0.79],
      median_completion_time_s: null,
      intervention_rate: 0,
      failure_category_counts: { unspecified: 1 },
    },
    episodes: [
      detail.episodes[0],
      categoryEpisode,
      notesEpisode,
      excludedEpisode,
    ],
  };
  const other: Detail = {
    ...detail,
    id: "exp-002-candidate",
    episodes: [{ ...detail.episodes[0], episode_id: "exp-002-candidate-000" }],
  };
  vi.spyOn(window, "confirm").mockReturnValue(true);
  api(200, multi, [multi, other]);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  const search = screen.getByRole("textbox", { name: "Search episodes" });
  await userEvent.type(search, "baseline-000");
  expect(
    screen.getByRole("button", { name: /exp-001-baseline-000/ }),
  ).toBeInTheDocument();
  await userEvent.clear(search);
  await userEvent.type(search, "missed_grasp");
  expect(
    screen.getByRole("button", { name: /exp-001-multi-001/ }),
  ).toBeInTheDocument();
  await userEvent.clear(search);
  await userEvent.type(search, "towel snag");
  expect(
    screen.getByRole("button", { name: /exp-001-multi-002/ }),
  ).toBeInTheDocument();
  await userEvent.clear(search);
  await userEvent.type(search, "blurred clip");
  expect(
    screen.getByRole("button", { name: /exp-001-multi-003/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("1 reviewed · 2 pending · 1 excluded"),
  ).toBeInTheDocument();

  await userEvent.clear(search);
  await userEvent.type(
    screen.getByLabelText("Review notes"),
    "Keep this unsaved draft",
  );
  await userEvent.type(search, "no-match");
  expect(
    screen.getByText("No episodes match your search."),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Current episode remains open while the queue is filtered.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Review notes")).toHaveValue(
    "Keep this unsaved draft",
  );

  await userEvent.clear(search);
  await userEvent.click(screen.getByRole("button", { name: "Reviewed" }));
  expect(
    screen.getByRole("button", { name: /exp-001-multi-002/ }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /exp-001-multi-001/ }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Failures" }));
  expect(
    screen.getByRole("button", { name: /exp-001-multi-002/ }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Successes" }));
  expect(
    screen.getByText("No episodes match this filter."),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Excluded" }));
  expect(
    screen.getByRole("button", { name: /exp-001-multi-003/ }),
  ).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Needs review" }));
  expect(
    screen.getByRole("button", { name: /exp-001-baseline-000/ }),
  ).toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: /exp-002-candidate 1 episodes/ }),
  );
  await screen.findByRole("heading", { name: "exp-002-candidate-000" });
  expect(screen.getByRole("textbox", { name: "Search episodes" })).toHaveValue(
    "",
  );
});

it("filters the episode workspace and clears excluded episode details", async () => {
  api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByRole("button", { name: "Failures" }));
  expect(
    screen.getByText("No episodes match this filter."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Manual review" }),
  ).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Needs review" }));
  expect(
    screen.getByRole("heading", { name: "Manual review" }),
  ).toBeInTheDocument();
});

it("preserves a specific failure reason when intervention is selected", async () => {
  const fetch = api();
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.click(screen.getByLabelText("Failure"));
  await userEvent.selectOptions(
    screen.getByLabelText("Failure category"),
    "missed_grasp",
  );
  await userEvent.click(screen.getByLabelText("Human intervention required"));
  expect(screen.getByLabelText("Failure category")).toHaveValue("missed_grasp");
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await screen.findByText("Review saved. Metrics refreshed.");
  const call = fetch.mock.calls.find(([, init]) => init?.method === "PUT");
  expect(JSON.parse(String(call?.[1]?.body))).toMatchObject({
    success: false,
    intervention: true,
    failure_category: "missed_grasp",
  });
});

it("keeps unsaved edits when navigation discard is declined", async () => {
  api();
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.type(
    screen.getByLabelText("Review notes"),
    "Keep my evidence notes",
  );
  await userEvent.click(screen.getByRole("button", { name: "Failures" }));
  expect(confirm).toHaveBeenCalled();
  expect(screen.getByLabelText("Review notes")).toHaveValue(
    "Keep my evidence notes",
  );
  expect(
    screen.getByRole("heading", { name: "Manual review" }),
  ).toBeInTheDocument();
});

it("does not replace the selected run when an earlier run save finishes late", async () => {
  const second: Detail = {
    ...detail,
    id: "exp-002-candidate",
    episodes: [{ ...detail.episodes[0], episode_id: "exp-002-candidate-000" }],
  };
  let finishSave: (response: Response) => void = () => {};
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const url = String(input);
    if (options?.method === "PUT")
      return new Promise<Response>((resolve) => {
        finishSave = resolve;
      });
    if (url === "/api/runs")
      return new Response(JSON.stringify({ runs: [detail, second] }));
    if (url.endsWith("/trace"))
      return new Response(JSON.stringify({ steps: [] }));
    return new Response(
      JSON.stringify(url.includes(second.id) ? second : detail),
    );
  });
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.type(screen.getByLabelText("Review notes"), "Old run review");
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await userEvent.click(
    screen.getByRole("button", { name: /exp-002-candidate 1 episodes/ }),
  );
  await screen.findByRole("heading", { name: "exp-002-candidate-000" });
  await act(async () => {
    finishSave(
      new Response(
        JSON.stringify({ ...detail, revision: 1, labelled_episodes: 1 }),
      ),
    );
  });
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "exp-002-candidate-000" }),
    ).toBeInTheDocument(),
  );
  expect(
    screen.getByRole("heading", { name: "candidate" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "exp-001-baseline-000" }),
  ).not.toBeInTheDocument();
});

it("retains dirty protection when a filter change keeps the same episode mounted", async () => {
  api();
  const confirm = vi
    .spyOn(window, "confirm")
    .mockReturnValueOnce(true)
    .mockReturnValueOnce(false);
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.type(
    screen.getByLabelText("Review notes"),
    "Keep dirty protection",
  );
  await userEvent.click(screen.getByRole("button", { name: "Needs review" }));
  await userEvent.click(screen.getByRole("button", { name: "Failures" }));
  expect(confirm).toHaveBeenCalledTimes(2);
  expect(screen.getByLabelText("Review notes")).toHaveValue(
    "Keep dirty protection",
  );
});

it("retains a newer same-run revision when an older save response arrives late", async () => {
  let finishSave: (response: Response) => void = () => {};
  let refreshed = false;
  const newer: Detail = {
    ...detail,
    revision: 2,
    labelled_episodes: 1,
    episodes: [
      {
        ...detail.episodes[0],
        annotation: { status: "labelled", notes: "Latest reviewer notes" },
      },
    ],
  };
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const url = String(input);
    if (options?.method === "PUT")
      return new Promise<Response>((resolve) => {
        finishSave = resolve;
        refreshed = true;
      });
    if (url.endsWith("/trace"))
      return new Response(JSON.stringify({ steps: [] }));
    const current = refreshed ? newer : detail;
    return new Response(
      JSON.stringify(url === "/api/runs" ? { runs: [current] } : current),
    );
  });
  render(<App />);
  await screen.findByRole("heading", { name: "Manual review" });
  await userEvent.type(screen.getByLabelText("Review notes"), "Old form notes");
  await userEvent.click(screen.getByRole("button", { name: "Save review" }));
  await userEvent.click(
    screen.getByRole("button", { name: "Refresh experiments" }),
  );
  await screen.findByText("Revision 2");
  await act(async () => {
    finishSave(
      new Response(
        JSON.stringify({ ...detail, revision: 1, labelled_episodes: 1 }),
      ),
    );
  });
  expect(screen.getByText("Revision 2")).toBeInTheDocument();
  expect(screen.getByLabelText("Review notes")).toHaveValue(
    "Latest reviewer notes",
  );
});
