export const categories = [
  "missed_grasp",
  "grasp_lost",
  "wrong_object",
  "dropped",
  "missed_basket",
  "timeout",
  "intervention",
  "hardware_fault",
  "frozen_camera",
  "unspecified",
] as const;
export type Label = {
  success: boolean;
  intervention: boolean;
  failure_category: string | null;
  notes: string;
  expected_revision: number;
};
export type Episode = {
  episode_id: string;
  success: boolean;
  duration_s: number;
  intervention: boolean;
  failure_category: string | null;
  original_outcome: {
    success: boolean;
    intervention: boolean;
    failure_category: string | null;
  };
  annotation: { status: "unlabelled" | "labelled"; notes?: string };
};
export type Summary = {
  episodes: number;
  successes: number;
  success_rate: number;
  success_rate_ci?: number[];
  median_completion_time_s: number;
  intervention_rate: number;
  failure_category_counts: Record<string, number>;
};
export type Run = {
  id: string;
  summary: Summary;
  manifest: Record<string, unknown>;
  revision: number;
  labelled_episodes: number;
};
export type Detail = Run & {
  episodes: Episode[];
  quality: {
    flagged?: number;
    episodes?: number;
    flags?: { episode_id: string; check: string; detail: string }[];
  } | null;
};
export type Step = {
  step: number;
  timestamp_s: number;
  joint_positions: number[];
  joint_targets: number[];
  joint_names?: string[];
  joint_units?: string;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.error?.message || body.error || body.message || message;
    } catch {
      /* keep HTTP error */
    }
    throw new ApiError(String(message), response.status);
  }
  return response.json() as Promise<T>;
}
export const runPath = (id: string) => `/api/runs/${encodeURIComponent(id)}`;
export const episodePath = (id: string, episode: string) =>
  `${runPath(id)}/episodes/${encodeURIComponent(episode)}`;
export const provenance = (run: Run) =>
  ["mock", "MockRobot"].includes(String(run.manifest.robot_implementation))
    ? "MOCK DATA"
    : "EXECUTION UNVERIFIED";
export const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
