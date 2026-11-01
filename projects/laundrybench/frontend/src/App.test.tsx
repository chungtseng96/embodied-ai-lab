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
    successes: 1,
    success_rate: 1,
    median_completion_time_s: 2,
    intervention_rate: 0,
    failure_category_counts: {},
  },
  quality: null,
  episodes: [
    {
      episode_id: "exp-001-baseline-000",
      success: true,
      duration_s: 2,
      intervention: false,
      failure_category: null,
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
      if (options?.method === "PUT")
        return new Response(
          JSON.stringify(
            putStatus === 409
              ? { error: "Review revision changed" }
              : {
                  ...runDetail,
                  revision: 1,
                  labelled_episodes: 1,
                  episodes: [
                    {
                      ...runDetail.episodes[0],
                      success: false,
                      failure_category: "missed_grasp",
                      annotation: {
                        status: "labelled",
                        notes: "Observed slip",
                      },
                    },
                  ],
                },
          ),
          { status: putStatus },
        );
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
    screen.getByText("Original outcome").querySelector("b"),
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
    original_outcome: {
      success: false,
      intervention: false,
      failure_category: null,
    },
    annotation: { status: "labelled", notes: "towel snag" },
  };
  const multi: Detail = {
    ...detail,
    id: "exp-001-multi",
    summary: { ...detail.summary, episodes: 3 },
    episodes: [detail.episodes[0], categoryEpisode, notesEpisode],
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
