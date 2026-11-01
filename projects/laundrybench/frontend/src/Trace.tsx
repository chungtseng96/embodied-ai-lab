import { useState } from "react";
import { Step } from "./api";
export default function Trace({ steps }: { steps: Step[] }) {
  const [joint, setJoint] = useState(0);
  const valid = steps.filter(
    (s) =>
      Number.isFinite(s.timestamp_s) &&
      Number.isFinite(s.joint_positions[joint]),
  );
  if (!valid.length)
    return (
      <p className="empty-inline">
        No numeric joint traces recorded for this episode.
      </p>
    );
  const values = steps
    .flatMap((s) => [s.joint_positions[joint], s.joint_targets[joint]])
    .filter(Number.isFinite);
  const min = values.reduce((a, b) => Math.min(a, b), Infinity),
    max = values.reduce((a, b) => Math.max(a, b), -Infinity),
    start = valid[0].timestamp_s,
    end = valid[valid.length - 1].timestamp_s;
  const point = (s: Step, v: number) =>
    `${48 + ((s.timestamp_s - start) / (end - start || 1)) * 620},${155 - ((v - min) / (max - min || 1)) * 122}`;
  const path = (field: "joint_positions" | "joint_targets") => {
    let drawing = false;
    return steps
      .map((s) => {
        if (
          !Number.isFinite(s.timestamp_s) ||
          !Number.isFinite(s[field][joint])
        ) {
          drawing = false;
          return "";
        }
        const command = drawing ? "L" : "M";
        drawing = true;
        return `${command}${point(s, s[field][joint])}`;
      })
      .join(" ");
  };
  return (
    <>
      <div className="section-toolbar">
        <label>
          Joint{" "}
          <select
            aria-label="Trace joint"
            value={joint}
            onChange={(e) => setJoint(Number(e.target.value))}
          >
            {valid[0].joint_positions.map((_, i) => (
              <option value={i} key={i}>
                {valid[0].joint_names?.[i] || `Joint ${i + 1}`}
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
      <svg
        className="trace"
        viewBox="0 0 700 195"
        role="img"
        aria-label="Recorded joint position and target over elapsed time"
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
