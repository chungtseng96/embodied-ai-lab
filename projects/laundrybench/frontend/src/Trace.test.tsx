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
