import { expect, it } from "vitest";
import { ApiError, mapShowcaseRequest } from "./api";

it("maps API GETs to exported JSON snapshots", () => {
  expect(mapShowcaseRequest("/api/runs")).toBe("/data/runs.json");
  expect(
    mapShowcaseRequest("/api/runs/exp-candidate/episodes/episode-1/trace"),
  ).toBe("/data/runs/exp-candidate/episodes/episode-1/trace.json");
});

it("uses the explicit acknowledged comparison snapshot", () => {
  expect(
    mapShowcaseRequest(
      "/api/runs/candidate/compare/baseline?acknowledge_incompatible=1",
    ),
  ).toBe("/data/runs/candidate/compare/baseline.acknowledged.json");
});

it("rejects writes and unsupported query parameters locally", () => {
  expect(() => mapShowcaseRequest("/api/runs", { method: "PUT" })).toThrowError(
    ApiError,
  );
  expect(() => mapShowcaseRequest("/api/runs?include=private")).toThrowError(
    ApiError,
  );
  expect(() =>
    mapShowcaseRequest(
      "/api/runs/candidate/compare/baseline?acknowledge_incompatible=1&other=yes",
    ),
  ).toThrowError(ApiError);
  expect(() =>
    mapShowcaseRequest(
      "/api/runs/candidate/compare/baseline?acknowledge_incompatible=1&",
    ),
  ).toThrowError(ApiError);
  expect(() => mapShowcaseRequest("/api/runs?")).toThrowError(ApiError);
  expect(() => mapShowcaseRequest("/api/secret")).toThrowError(ApiError);
  expect(() => mapShowcaseRequest("/api/runs/%2e%2e/secret")).toThrowError(
    ApiError,
  );
  expect(() => mapShowcaseRequest("/api/runs/run%2fprivate")).toThrowError(
    ApiError,
  );
  expect(() =>
    mapShowcaseRequest("/api/runs/run/episodes/ep%2fprivate/trace"),
  ).toThrowError(ApiError);
});
