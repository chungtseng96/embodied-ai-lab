import { useState, type MouseEvent } from "react";
import { Step } from "./api";

type TraceProps = {
  steps: Step[];
  cursorTime?: number;
  onSeek?: (timeSeconds: number) => void;
};

export default function Trace({ steps, cursorTime, onSeek }: TraceProps) {
  const [joint, setJoint] = useState(0);
  // Keep source order so invalid or out-of-order timestamps remain real gaps.
  const ordered = steps;
  const valid = ordered.filter(
    (step) =>
      Number.isFinite(step.timestamp_s) &&
      Number.isFinite(step.joint_positions?.[joint]),
  );
  if (!valid.length)
    return (
      <p className="empty-inline">
        No numeric joint traces recorded for this episode.
      </p>
    );
  const timedValues = ordered
    .filter((step) => Number.isFinite(step.timestamp_s))
    .flatMap((step) => [
      step.joint_positions?.[joint],
      step.joint_targets?.[joint],
    ])
    .filter((value): value is number => Number.isFinite(value));
  const timedSteps = ordered.filter(
    (step) =>
      Number.isFinite(step.timestamp_s) &&
      (Number.isFinite(step.joint_positions?.[joint]) ||
        Number.isFinite(step.joint_targets?.[joint])),
  );
  const min = timedValues.reduce((a, b) => Math.min(a, b), Infinity),
    max = timedValues.reduce((a, b) => Math.max(a, b), -Infinity),
    start = Math.min(...timedSteps.map((step) => step.timestamp_s)),
    end = Math.max(...timedSteps.map((step) => step.timestamp_s));
  const point = (step: Step, value: number) =>
    `${48 + ((step.timestamp_s - start) / (end - start || 1)) * 620},${155 - ((value - min) / (max - min || 1)) * 122}`;
  const path = (field: "joint_positions" | "joint_targets") => {
    let drawing = false;
    let previousTime: number | null = null;
    return ordered
      .map((step) => {
        const timestamp = step.timestamp_s;
        const value = step[field]?.[joint];
        if (!Number.isFinite(timestamp) || !Number.isFinite(value)) {
          drawing = false;
          previousTime = null;
          return "";
        }
        const time = timestamp as number;
        if (previousTime !== null && time <= previousTime) drawing = false;
        const command = drawing ? "L" : "M";
        drawing = true;
        previousTime = time;
        return `${command}${point(step, value as number)}`;
      })
      .join(" ");
  };
  const cursorInRange =
    cursorTime !== undefined &&
    Number.isFinite(cursorTime) &&
    cursorTime >= start &&
    cursorTime <= end;
  const cursorX = cursorInRange
    ? 48 + ((cursorTime - start) / (end - start || 1)) * 620
    : null;
  function seekFromPointer(event: MouseEvent<SVGSVGElement>) {
    if (!onSeek) return;
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    const x = ((event.clientX - rect.left) / rect.width) * 700;
    if (x < 48 || x > 668) return;
    onSeek(start + ((x - 48) / 620) * (end - start));
  }
  const sliderValue =
    cursorTime !== undefined && Number.isFinite(cursorTime)
      ? Math.min(end, Math.max(start, cursorTime))
      : start;
  const playbackOutsideTrace =
    cursorTime !== undefined &&
    Number.isFinite(cursorTime) &&
    (cursorTime < start || cursorTime > end);
  const sliderStep = Math.max((end - start) / 1000, 0.01);
  return (
    <>
      <div className="section-toolbar">
        <label>
          Joint{" "}
          <select
            aria-label="Trace joint"
            value={joint}
            onChange={(event) => setJoint(Number(event.target.value))}
          >
            {valid[0].joint_positions.map((_, index) => (
              <option value={index} key={index}>
                {valid[0].joint_names?.[index] || `Joint ${index + 1}`}
              </option>
            ))}
          </select>
        </label>
        <span className="legend">
          <i />
          Position <i className="target" />
          Target
        </span>
      </div>
      {playbackOutsideTrace && (
        <p className="trace-outside-note" role="status">
          Playback is outside the recorded trace interval.
        </p>
      )}
      {onSeek && end > start && (
        <label className="trace-seek-control">
          Seek video from trace
          <input
            type="range"
            aria-label="Seek video from trace"
            min={start}
            max={end}
            step={sliderStep}
            value={sliderValue}
            onChange={(event) => onSeek(Number(event.target.value))}
          />
        </label>
      )}
      <svg
        className={`trace ${onSeek ? "trace-interactive" : ""}`}
        viewBox="0 0 700 195"
        role="img"
        aria-label="Recorded joint position and target over elapsed time"
        onClick={onSeek ? seekFromPointer : undefined}
      >
        <line x1="48" y1="155" x2="668" y2="155" stroke="#cad8d7" />
        <line x1="48" y1="33" x2="48" y2="155" stroke="#cad8d7" />
        <text x="4" y="38">
          {max.toFixed(1)}
        </text>
        <text x="4" y="157">
          {min.toFixed(1)}
        </text>
        <text x="48" y="183">
          0 s
        </text>
        <text x="610" y="183">
          {(end - start).toFixed(2)} s
        </text>
        {cursorX !== null && (
          <line
            data-testid="trace-cursor"
            x1={cursorX}
            x2={cursorX}
            y1="33"
            y2="155"
            stroke="#c16646"
            strokeWidth="2"
          />
        )}
        <path
          fill="none"
          stroke="#087d80"
          strokeWidth="2.5"
          d={path("joint_positions")}
        />
        <path
          fill="none"
          stroke="#a87340"
          strokeWidth="2"
          strokeDasharray="5 4"
          d={path("joint_targets")}
        />
      </svg>
      <p className="muted small">
        {valid.length} recorded samples · units:{" "}
        {valid[0].joint_units || "not recorded"}. Lines connect observed
        samples; no interpolation model.
      </p>
    </>
  );
}
