import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import Trace from "./Trace";
import { Step } from "./api";
it("shows missing trace data explicitly", () => {
  render(<Trace steps={[]} />);
  expect(
    screen.getByText("No numeric joint traces recorded for this episode."),
  ).toBeInTheDocument();
});
it("breaks SVG paths across invalid recorded samples instead of fabricating continuity", () => {
  const steps = [
    { step: 0, timestamp_s: 0, joint_positions: [1], joint_targets: [2] },
    { step: 1, timestamp_s: 1, joint_positions: [null], joint_targets: [null] },
    { step: 2, timestamp_s: 2, joint_positions: [3], joint_targets: [4] },
  ] as unknown as Step[];
  const { container } = render(<Trace steps={steps} />);
  const paths = container.querySelectorAll("path");
  expect(paths).toHaveLength(2);
  expect(paths[0].getAttribute("d")?.match(/M/g)).toHaveLength(2);
  expect(paths[0].getAttribute("d")).not.toContain("NaN");
  expect(screen.getByRole("img")).toBeInTheDocument();
});

it("preserves missing and nonmonotonic timestamp gaps and includes target-only times in the domain", () => {
  const steps = [
    { step: 0, timestamp_s: 10, joint_positions: [1], joint_targets: [2] },
    { step: 1, timestamp_s: null, joint_positions: [2], joint_targets: [3] },
    { step: 2, timestamp_s: 12, joint_positions: [3], joint_targets: [4] },
    { step: 3, timestamp_s: 11, joint_positions: [4], joint_targets: [5] },
    { step: 4, timestamp_s: 14, joint_positions: [null], joint_targets: [6] },
  ] as unknown as Step[];
  const { container } = render(<Trace steps={steps} onSeek={() => {}} />);
  const paths = container.querySelectorAll("path");
  expect(paths[0].getAttribute("d")?.match(/M/g)).toHaveLength(3);
  expect(paths[0].getAttribute("d")).not.toContain("NaN");
  expect(
    screen.getByRole("slider", { name: "Seek video from trace" }),
  ).toHaveAttribute("max", "14");
  expect(paths[1].getAttribute("d")?.match(/M/g)).toHaveLength(3);
});

it("clamps the video slider to trace bounds without extrapolating the cursor", () => {
  const steps = [
    { step: 0, timestamp_s: 10, joint_positions: [1], joint_targets: [2] },
    { step: 1, timestamp_s: 12, joint_positions: [3], joint_targets: [4] },
  ];
  const { rerender, container } = render(
    <Trace steps={steps} cursorTime={15} onSeek={() => {}} />,
  );
  const slider = screen.getByRole("slider", { name: "Seek video from trace" });
  expect(slider).toHaveValue("12");
  expect(container.querySelector('[data-testid="trace-cursor"]')).toBeNull();
  expect(
    screen.getByText("Playback is outside the recorded trace interval."),
  ).toBeInTheDocument();

  rerender(<Trace steps={steps} cursorTime={9} onSeek={() => {}} />);
  expect(slider).toHaveValue("10");
  expect(container.querySelector('[data-testid="trace-cursor"]')).toBeNull();
  expect(
    screen.getByText("Playback is outside the recorded trace interval."),
  ).toBeInTheDocument();
});
