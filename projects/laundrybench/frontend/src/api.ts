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
export type Outcome = {
  success: boolean;
  intervention: boolean;
  failure_category: string | null;
};
export type ReviewStatus = "provisional" | "reviewed" | "excluded";
export type Label =
  | {
      success: boolean;
      intervention: boolean;
      failure_category: string | null;
      notes: string;
      expected_revision: number;
      status?: "reviewed";
    }
  | {
      status: "excluded";
      exclusion_reason: string;
      expected_revision: number;
    };
export type Episode = {
  episode_id: string;
  success: boolean;
  duration_s: number;
  intervention: boolean;
  failure_category: string | null;
  review_status: ReviewStatus;
  outcome_source: "recorded" | "label";
  effective_outcome: Outcome;
  original_outcome: Outcome;
  annotation: {
    status: "unlabelled" | "labelled" | "excluded";
    notes?: string;
    exclusion_reason?: string;
  };
};
export type Summary = {
  episodes: number;
  reviewed_episodes: number;
  pending_episodes: number;
  excluded_episodes: number;
  metric_episodes: number;
  successes: number;
  success_rate: number | null;
  reviewed_rate: number | null;
  success_rate_ci: number[] | null;
  median_completion_time_s: number | null;
  intervention_rate: number | null;
  failure_category_counts: Record<string, number>;
  outcome_schema_version: number;
  label_revision: number;
};
export type ExperimentMetadata = {
  schema_version: number;
  revision: number;
  name: string | null;
  hypothesis: string | null;
  what_changed: string | null;
  task: { id: string | null; version: string | null };
  protocol: { id: string | null; version: string | null };
  dataset: { id: string | null; revision: string | null };
  checkpoint: { identity: string | null };
  effective_overrides: Record<string, unknown>;
  evidence_links: { label: string; url: string }[];
};
export type Compatibility = {
  status: "matched" | "mismatched" | "unknown";
  reasons: string[];
  differences: Record<string, { candidate: unknown; baseline: unknown }>;
  advisories: string[];
};
export type ComparisonResult = {
  candidate_id: string;
  baseline_id: string;
  candidate_context: ExperimentMetadata | null;
  baseline_context: ExperimentMetadata | null;
  candidate_label_revision: number;
  baseline_label_revision: number;
  compatibility: Compatibility;
  candidate: Summary;
  baseline: Summary;
  delta: {
    reviewed_episodes: number;
    successes: number;
    success_rate: number | null;
    reviewed_rate: number | null;
    intervention_rate: number | null;
    failure_category_counts: Record<string, number>;
  } | null;
};
export type Run = {
  id: string;
  summary: Summary;
  manifest: Record<string, unknown>;
  experiment?: ExperimentMetadata | null;
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
export type MediaStream = {
  camera: string;
  path: string;
  mime_type: string;
  duration_s: number;
  trace_start_s: number;
  url: string;
};
export type MediaEvent = {
  name: string;
  timestamp_s: number;
};
export type EpisodeMedia = {
  schema_version: 1;
  episode_id: string;
  streams: MediaStream[];
  events: MediaEvent[];
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
export function mapShowcaseRequest(
  path: string,
  options?: RequestInit,
): string {
  const method = (options?.method || "GET").toUpperCase();
  if (method !== "GET") {
    throw new ApiError(
      "This showcase is read only. Write requests are disabled.",
      405,
    );
  }
  if (!path.startsWith("/api/") || path.startsWith("//")) {
    throw new ApiError("Unsupported request in the static showcase.", 400);
  }
  const queryIndex = path.indexOf("?");
  const pathname = queryIndex < 0 ? path : path.slice(0, queryIndex);
  const query = queryIndex < 0 ? "" : path.slice(queryIndex + 1);
  const pathSegments = pathname.split("/");
  let decodedSegments: string[];
  try {
    decodedSegments = pathSegments.map((segment) =>
      decodeURIComponent(segment),
    );
  } catch {
    throw new ApiError("Malformed request path in the static showcase.", 400);
  }
  if (
    pathname.includes("//") ||
    decodedSegments.some(
      (segment) =>
        segment.includes("/") ||
        segment.includes("\\") ||
        segment === "." ||
        segment === "..",
    )
  ) {
    throw new ApiError("Unsupported request path in the static showcase.", 400);
  }
  const isKnownRoute =
    /^\/api\/runs$/.test(pathname) ||
    /^\/api\/runs\/[^/]+$/.test(pathname) ||
    /^\/api\/runs\/[^/]+\/compare\/[^/]+$/.test(pathname) ||
    /^\/api\/runs\/[^/]+\/episodes\/[^/]+\/(trace|media)$/.test(pathname);
  if (!isKnownRoute) {
    throw new ApiError("Unsupported request path in the static showcase.", 400);
  }
  let suffix = ".json";
  if (queryIndex >= 0) {
    if (
      !pathname.match(/^\/api\/runs\/[^/]+\/compare\/[^/]+$/) ||
      query !== "acknowledge_incompatible=1"
    ) {
      throw new ApiError(
        "Unsupported query parameters in the static showcase.",
        400,
      );
    }
    suffix = ".acknowledged.json";
  }
  return `/data${pathname.slice(4)}${suffix}`;
}

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const showcase =
    (import.meta as ImportMeta & { env?: { VITE_SHOWCASE?: string } }).env
      ?.VITE_SHOWCASE === "1";
  const response = await fetch(
    showcase ? mapShowcaseRequest(path, options) : path,
    showcase ? { method: "GET", headers: options?.headers } : options,
  );
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
