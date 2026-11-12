export const JOINT_DEFINITIONS = [
  { key: "Rotation", label: "Shoulder pan", shortLabel: "PAN" },
  { key: "Pitch", label: "Shoulder lift", shortLabel: "LIFT" },
  { key: "Elbow", label: "Elbow flex", shortLabel: "ELBOW" },
  { key: "Wrist_Pitch", label: "Wrist flex", shortLabel: "W-FLEX" },
  { key: "Wrist_Roll", label: "Wrist roll", shortLabel: "W-ROLL" },
  { key: "Jaw", label: "Gripper", shortLabel: "GRIP" },
] as const;

export type JointKey = (typeof JOINT_DEFINITIONS)[number]["key"];
export type JointValues = Partial<Record<JointKey, number>>;

export type TelemetryFrame = {
  type: "joint_update";
  joints: JointValues;
  timestamp?: number;
};

export const DEFAULT_LELAB_ORIGIN = "http://127.0.0.1:8000";

export function resolveLeLabOrigin(search = ""): string {
  const candidate = new URLSearchParams(search).get("lelab");
  if (!candidate) return DEFAULT_LELAB_ORIGIN;
  try {
    const url = new URL(candidate);
    if (url.protocol !== "http:" && url.protocol !== "https:") return DEFAULT_LELAB_ORIGIN;
    return url.origin;
  } catch {
    return DEFAULT_LELAB_ORIGIN;
  }
}

export function leLabWebSocketUrl(origin: string): string {
  const url = new URL(origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws/joint-data";
  url.search = "";
  return url.toString();
}

export function parseTelemetryMessage(raw: string): TelemetryFrame | null {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!value || typeof value !== "object") return null;
  const data = value as {
    type?: unknown;
    joints?: unknown;
    timestamp?: unknown;
  };
  if (data.type !== "joint_update" || !data.joints || typeof data.joints !== "object") {
    return null;
  }

  const joints: JointValues = {};
  for (const { key } of JOINT_DEFINITIONS) {
    const position = (data.joints as Record<string, unknown>)[key];
    if (typeof position === "number" && Number.isFinite(position)) {
      joints[key] = position;
    }
  }
  if (!Object.keys(joints).length) return null;

  return {
    type: "joint_update",
    joints,
    ...(typeof data.timestamp === "number" && Number.isFinite(data.timestamp)
      ? { timestamp: data.timestamp }
      : {}),
  };
}

export function formatJointPosition(position: number | undefined): string {
  if (position === undefined) return "—";
  return `${position >= 0 ? "+" : ""}${position.toFixed(3)}`;
}
