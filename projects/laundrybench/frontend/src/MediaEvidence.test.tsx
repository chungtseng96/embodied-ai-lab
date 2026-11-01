import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import MediaEvidence from "./MediaEvidence";
import { EpisodeMedia, Step } from "./api";

const steps: Step[] = [
  {
    step: 0,
    timestamp_s: 1000.25,
    joint_positions: [0.2],
    joint_targets: [0.3],
    joint_names: ["shoulder"],
  },
  {
    step: 1,
    timestamp_s: 1000.75,
    joint_positions: [0.6],
    joint_targets: [0.7],
    joint_names: ["shoulder"],
  },
];
function manifest(
  episodeId = "episode-a",
  camera = "front",
  events: EpisodeMedia["events"] = [
    { name: "grasp", timestamp_s: 1000.65 },
    { name: "approach", timestamp_s: 1000.4 },
    { name: "before clip", timestamp_s: 1000.2 },
    { name: "after clip", timestamp_s: 1001.3 },
  ],
): EpisodeMedia {
  return {
    schema_version: 1,
    episode_id: episodeId,
    streams: [
      {
        camera,
        path: `media/${camera}.mp4`,
        mime_type: "video/mp4",
        duration_s: 1,
        trace_start_s: 1000.25,
        url: `/api/media/${episodeId}/${camera}`,
      },
    ],
    events,
  };
}
function apiFor(data: EpisodeMedia) {
  return vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(data)));
}
function stubCurrentTime(video: HTMLVideoElement) {
  let currentTime = 0;
  Object.defineProperty(video, "readyState", {
    configurable: true,
    value: HTMLMediaElement.HAVE_METADATA,
  });
  Object.defineProperty(video, "duration", { configurable: true, value: 1 });
  Object.defineProperty(video, "currentTime", {
    configurable: true,
    get: () => currentTime,
    set: (value: number) => {
      currentTime = value;
    },
  });
  return () => currentTime;
}
afterEach(() => vi.restoreAllMocks());

it("maps playback to trace time and trace/event seeks to video time using the manifest offset", async () => {
  apiFor(manifest());
  const { container } = render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={steps}
      traceError=""
    />,
  );
  const video = (await screen.findByLabelText(
    "Episode video",
  )) as HTMLVideoElement;
  const readCurrentTime = stubCurrentTime(video);
  fireEvent.loadedMetadata(video);
  const slider = screen.getByRole("slider", { name: "Seek video from trace" });
  expect(slider).toHaveValue("1000.25");
  expect(
    screen.getAllByRole("button", { name: /Seek to recorded event/ }),
  ).toHaveLength(2);
  expect(
    screen
      .getAllByRole("button", { name: /Seek to recorded event/ })
      .map((button) => button.getAttribute("aria-label")),
  ).toEqual([
    "Seek to recorded event approach at 0.15 seconds",
    "Seek to recorded event grasp at 0.40 seconds",
  ]);

  act(() => {
    (video as HTMLVideoElement).currentTime = 0.2;
    fireEvent.timeUpdate(video);
  });
  expect(slider).toHaveValue("1000.45");
  expect(
    Number(
      container
        .querySelector('[data-testid="trace-cursor"]')
        ?.getAttribute("x1"),
    ),
  ).toBeCloseTo(296);

  fireEvent.change(slider, { target: { value: "1000.55" } });
  expect(readCurrentTime()).toBeCloseTo(0.3);

  const svg = screen.getByRole("img", {
    name: "Recorded joint position and target over elapsed time",
  });
  vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 700,
    bottom: 195,
    width: 700,
    height: 195,
    toJSON: () => ({}),
  });
  fireEvent.click(svg, { clientX: 358, clientY: 90 });
  expect(readCurrentTime()).toBeCloseTo(0.25);

  await userEvent.click(
    screen.getByRole("button", {
      name: "Seek to recorded event grasp at 0.40 seconds",
    }),
  );
  expect(readCurrentTime()).toBeCloseTo(0.4);
});

it("guards event seeks until the native video metadata and duration are available", async () => {
  apiFor(
    manifest("episode-a", "front", [{ name: "grasp", timestamp_s: 1000.65 }]),
  );
  render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={steps}
      traceError=""
    />,
  );
  const video = (await screen.findByLabelText(
    "Episode video",
  )) as HTMLVideoElement;
  let currentTime = 0;
  Object.defineProperty(video, "currentTime", {
    configurable: true,
    get: () => currentTime,
    set: (value: number) => {
      currentTime = value;
    },
  });
  await userEvent.click(
    screen.getByRole("button", {
      name: "Seek to recorded event grasp at 0.40 seconds",
    }),
  );
  expect(currentTime).toBe(0);
  expect(
    screen.getByText(
      "Video metadata has not loaded; wait and try this seek again.",
    ),
  ).toBeInTheDocument();

  Object.defineProperty(video, "readyState", {
    configurable: true,
    value: HTMLMediaElement.HAVE_METADATA,
  });
  Object.defineProperty(video, "duration", { configurable: true, value: 1 });
  await userEvent.click(
    screen.getByRole("button", {
      name: "Seek to recorded event grasp at 0.40 seconds",
    }),
  );
  expect(currentTime).toBeCloseTo(0.4);
});

it("offers a camera selector when more than one stream is present", async () => {
  const multiCamera = manifest("episode-a", "front", []);
  multiCamera.streams.push({
    ...multiCamera.streams[0],
    camera: "side",
    path: "media/side.mp4",
    url: "/api/media/episode-a/side",
  });
  apiFor(multiCamera);
  render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={steps}
      traceError=""
    />,
  );
  const cameraSelect = await screen.findByLabelText("Media camera");
  expect(screen.getByLabelText("Episode video")).toHaveAttribute(
    "src",
    "/api/media/episode-a/front",
  );
  await userEvent.selectOptions(cameraSelect, "side");
  expect(screen.getByLabelText("Episode video")).toHaveAttribute(
    "src",
    "/api/media/episode-a/side",
  );
  expect(screen.getByText(/side · video\/mp4/)).toBeInTheDocument();
});

it("states when media is missing and reports manifest and codec errors", async () => {
  apiFor({
    schema_version: 1,
    episode_id: "episode-a",
    streams: [],
    events: [],
  });
  const { unmount: unmountMissing } = render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={[]}
      traceError=""
    />,
  );
  expect(
    await screen.findByText("No media linked to this episode"),
  ).toBeInTheDocument();
  expect(screen.queryByLabelText("Episode video")).not.toBeInTheDocument();

  unmountMissing();
  vi.restoreAllMocks();
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ error: "Media manifest is corrupt" }), {
      status: 422,
    }),
  );
  const { unmount } = render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-b"
      steps={[]}
      traceError=""
    />,
  );
  expect(
    await screen.findByText("Media manifest is corrupt"),
  ).toBeInTheDocument();
  unmount();

  apiFor(manifest());
  const media = render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={steps}
      traceError=""
    />,
  );
  const video = await screen.findByLabelText("Episode video");
  Object.defineProperty(video, "error", {
    configurable: true,
    value: { code: 4 },
  });
  fireEvent.error(video);
  expect(
    await screen.findByText(/could not decode this video\/mp4 stream/),
  ).toBeInTheDocument();
  media.unmount();
});

it("ignores a late media manifest after switching episodes", async () => {
  let resolveA: (response: Response) => void = () => {};
  let resolveB: (response: Response) => void = () => {};
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = String(input);
    return new Promise((resolve) => {
      if (url.includes("episode-a")) resolveA = resolve;
      else resolveB = resolve;
    });
  });
  const { rerender } = render(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-a"
      steps={steps}
      traceError=""
    />,
  );
  rerender(
    <MediaEvidence
      runId="run-a"
      episodeId="episode-b"
      steps={steps}
      traceError=""
    />,
  );
  await act(async () => {
    resolveB(new Response(JSON.stringify(manifest("episode-b", "rear", []))));
  });
  expect(await screen.findByText(/rear · video\/mp4/)).toBeInTheDocument();
  await act(async () => {
    resolveA(new Response(JSON.stringify(manifest("episode-a", "stale", []))));
  });
  await waitFor(() =>
    expect(screen.getByText(/rear · video\/mp4/)).toBeInTheDocument(),
  );
  expect(screen.queryByText(/stale · video\/mp4/)).not.toBeInTheDocument();
});
