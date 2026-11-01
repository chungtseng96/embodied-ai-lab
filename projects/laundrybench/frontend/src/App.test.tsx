import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";
import { Detail, Episode } from "./api";
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
function api(
  putStatus = 200,
  runDetail: Detail = detail,
  runList: Detail[] = [runDetail],
) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input, options) => {
      const url = String(input);
      if (options?.method === "PUT") {
        const payload = JSON.parse(String(options.body || "{}"));
        const excluded = payload.status === "excluded";
        const originalEpisode = runDetail.episodes[0];
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
        const reviewedCount = excluded
          ? runDetail.summary.reviewed_episodes
          : Math.max(1, runDetail.summary.reviewed_episodes);
        const excludedCount = excluded
          ? Math.max(1, runDetail.summary.excluded_episodes)
          : runDetail.summary.excluded_episodes;
        const metricEpisodes = reviewedCount;
        const successes = excluded
          ? runDetail.summary.successes
          : Number(reviewedOutcome.success);
        return new Response(
          JSON.stringify(
            putStatus === 409
              ? { error: "Review revision changed" }
              : {
                  ...runDetail,
                  revision: 1,
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
                        ? Number(reviewedOutcome.intervention)
                        : null,
                    failure_category_counts:
                      metricEpisodes > 0 && !reviewedOutcome.success
                        ? {
                            [reviewedOutcome.failure_category || "unspecified"]:
                              1,
                          }
                        : {},
                    label_revision: 1,
                  },
                  episodes: [updatedEpisode],
                },
          ),
          { status: putStatus },
        );
      }
      if (url.endsWith("/trace"))
        return new Response(JSON.stringify({ steps: [] }));
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
