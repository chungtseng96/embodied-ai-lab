import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import OperatorDashboard from "./OperatorDashboard";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  readyState = 0;
  constructor(public readonly url: string) {
    FakeWebSocket.instances.push(this);
  }
  close() {
    this.readyState = 3;
  }
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  message(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent);
  }
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  FakeWebSocket.instances = [];
});

it("shows the six live follower joint positions and stream state", async () => {
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify({ teleoperation_active: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );

  render(<OperatorDashboard />);
  const socket = FakeWebSocket.instances[0];
  expect(socket.url).toBe("ws://127.0.0.1:8000/ws/joint-data");
  act(() => socket.open());
  act(() =>
    socket.message({
      type: "joint_update",
      joints: {
        Rotation: 0.1,
        Pitch: -1.2,
        Elbow: 1.4,
        Wrist_Pitch: 0.3,
        Wrist_Roll: -0.2,
        Jaw: 0.5,
      },
    }),
  );

  await waitFor(() => expect(screen.getByText("LIVE")).toBeInTheDocument());
  expect(screen.getByText("+0.100")).toBeInTheDocument();
  expect(screen.getByText("-1.200")).toBeInTheDocument();
  expect(screen.getByText("+1.400")).toBeInTheDocument();
  expect(screen.getByText("Wrist flex")).toBeInTheDocument();
  expect(screen.getAllByText("Teleoperation active")).toHaveLength(2);
  expect(screen.getByText("READ ONLY")).toBeInTheDocument();
});

it("makes the no-server state explicit", async () => {
  vi.stubGlobal("WebSocket", FakeWebSocket);
  vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));

  render(<OperatorDashboard />);
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("offline"));
  expect(screen.getByText("WAITING")).toBeInTheDocument();
  expect(screen.getAllByText("—")).toHaveLength(6);
});
