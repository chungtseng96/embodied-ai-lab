import { expect, it } from "vitest";
import {
  formatJointPosition,
  leLabWebSocketUrl,
  parseTelemetryMessage,
  resolveLeLabOrigin,
} from "./operatorTelemetry";

it("parses finite joint updates and ignores unknown joints", () => {
  const frame = parseTelemetryMessage(
    JSON.stringify({
      type: "joint_update",
      joints: { Rotation: 1.25, Pitch: Number.NaN, Extra: 4 },
      timestamp: 123,
    }),
  );
  expect(frame).toEqual({
    type: "joint_update",
    joints: { Rotation: 1.25 },
    timestamp: 123,
  });
});

it("rejects malformed or non-telemetry messages", () => {
  expect(parseTelemetryMessage("not json")).toBeNull();
  expect(parseTelemetryMessage(JSON.stringify({ type: "status" }))).toBeNull();
  expect(
    parseTelemetryMessage(JSON.stringify({ type: "joint_update", joints: { Rotation: null } })),
  ).toBeNull();
});

it("resolves the local LeLab endpoint and websocket path", () => {
  expect(resolveLeLabOrigin("")).toBe("http://127.0.0.1:8000");
  expect(resolveLeLabOrigin("?lelab=http%3A%2F%2Flocalhost%3A8000%2F")).toBe(
    "http://localhost:8000",
  );
  expect(leLabWebSocketUrl("https://localhost:8000")).toBe(
    "wss://localhost:8000/ws/joint-data",
  );
});

it("formats positions without hiding the sign or missing state", () => {
  expect(formatJointPosition(1.23456)).toBe("+1.235");
  expect(formatJointPosition(-0.25)).toBe("-0.250");
  expect(formatJointPosition(undefined)).toBe("—");
});
