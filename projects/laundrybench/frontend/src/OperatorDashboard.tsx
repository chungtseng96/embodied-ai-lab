import { useEffect, useMemo, useState } from "react";
import {
  formatJointPosition,
  JOINT_DEFINITIONS,
  leLabWebSocketUrl,
  parseTelemetryMessage,
  resolveLeLabOrigin,
  JointKey,
  JointValues,
} from "./operatorTelemetry";

type SocketState = "connecting" | "connected" | "disconnected" | "error";

type TeleoperationStatus = {
  teleoperation_active?: boolean;
};

const STALE_AFTER_MS = 1_000;

function connectionLabel(state: SocketState): string {
  switch (state) {
    case "connected":
      return "LeLab connected";
    case "error":
      return "Connection error";
    case "disconnected":
      return "LeLab disconnected";
    default:
      return "Connecting to LeLab";
  }
}

function relativeMeter(position: number | undefined): number {
  if (position === undefined) return 0;
  return Math.min(100, Math.max(0, 50 + (position / Math.PI) * 45));
}

function JointCard({ joint, position }: { joint: (typeof JOINT_DEFINITIONS)[number]; position: number | undefined }) {
  const value = formatJointPosition(position);
  return (
    <article className={`operator-joint-card ${position === undefined ? "missing" : ""}`}>
      <div className="operator-joint-card-heading">
        <span className="operator-joint-index">{joint.shortLabel}</span>
        <span className="operator-joint-name">{joint.label}</span>
      </div>
      <strong className="operator-joint-value">{value}</strong>
      <span className="operator-joint-unit">LeLab position · rad</span>
      <div className="operator-joint-meter" aria-hidden="true">
        <span style={{ width: `${relativeMeter(position)}%` }} />
        <i style={{ left: `${relativeMeter(position)}%` }} />
      </div>
    </article>
  );
}

export default function OperatorDashboard() {
  const lelabOrigin = useMemo(
    () => resolveLeLabOrigin(window.location.search),
    [],
  );
  const [socketState, setSocketState] = useState<SocketState>("connecting");
  const [teleoperationActive, setTeleoperationActive] = useState<boolean | null>(null);
  const [joints, setJoints] = useState<JointValues>({});
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [frameCount, setFrameCount] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState("");

  useEffect(() => {
    const socket = new WebSocket(leLabWebSocketUrl(lelabOrigin));
    socket.onopen = () => setSocketState("connected");
    socket.onmessage = (event) => {
      const frame = parseTelemetryMessage(event.data);
      if (!frame) return;
      setJoints(frame.joints);
      setLastMessageAt(Date.now());
      setFrameCount((count) => count + 1);
    };
    socket.onerror = () => {
      setSocketState("error");
      setError("The LeLab telemetry socket could not be opened.");
    };
    socket.onclose = () => setSocketState("disconnected");
    return () => socket.close();
  }, [lelabOrigin]);

  useEffect(() => {
    let active = true;
    async function readStatus() {
      try {
        const response = await fetch(`${lelabOrigin}/teleoperation-status`, {
          cache: "no-store",
        });
        if (!response.ok) throw new Error(`LeLab status returned ${response.status}`);
        const status = (await response.json()) as TeleoperationStatus;
        if (active) {
          setTeleoperationActive(status.teleoperation_active === true);
          setError("");
        }
      } catch (reason) {
        if (active) {
          setTeleoperationActive(null);
          setError(reason instanceof Error ? reason.message : "LeLab status unavailable.");
        }
      }
    }
    void readStatus();
    const interval = window.setInterval(() => void readStatus(), 1_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [lelabOrigin]);

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(interval);
  }, []);

  const ageMs = lastMessageAt === null ? null : Math.max(0, now - lastMessageAt);
  const streamLive = socketState === "connected" && ageMs !== null && ageMs < STALE_AFTER_MS;
  const streamLabel = streamLive ? "LIVE" : ageMs === null ? "WAITING" : "STALE";
  const lastUpdate = ageMs === null ? "No frames yet" : `${ageMs} ms ago`;

  return (
    <div className="operator-page">
      <header className="operator-header">
        <a className="operator-brand" href="/">
          <span className="brand-mark" aria-hidden="true">L<span>↗</span></span>
          <span>LaundryBench<small>EMBODIED AI LAB</small></span>
        </a>
        <div className="operator-header-actions">
          <a href="/" className="operator-back-link">Evidence review ↗</a>
          <span className={`operator-connection ${socketState}`}>
            <i aria-hidden="true" /> {connectionLabel(socketState)}
          </span>
        </div>
      </header>

      <main className="operator-main">
        <section className="operator-hero">
          <div>
            <p className="operator-kicker"><span /> LIVE HARDWARE TELEMETRY</p>
            <h1>SO-101 operator view</h1>
            <p className="operator-lede">
              Watch the follower arm’s six joint positions update in real time while LeLab owns the control loop.
            </p>
          </div>
          <div className={`operator-mode-badge ${teleoperationActive ? "active" : ""}`}>
            <span className="operator-mode-dot" />
            {teleoperationActive ? "Teleoperation active" : "Waiting for teleoperation"}
          </div>
        </section>

        <section className="operator-summary-grid" aria-label="Telemetry summary">
          <div className={`operator-summary-card ${streamLive ? "good" : "warning"}`}>
            <span>Telemetry stream</span>
            <strong>{streamLabel}</strong>
            <small>{lastUpdate}</small>
          </div>
          <div className="operator-summary-card">
            <span>Frames received</span>
            <strong>{frameCount.toLocaleString()}</strong>
            <small>Latest-wins WebSocket feed</small>
          </div>
          <div className="operator-summary-card">
            <span>LeLab endpoint</span>
            <strong className="operator-endpoint">{lelabOrigin}</strong>
            <small>Read-only dashboard connection</small>
          </div>
        </section>

        {error && <p className="operator-error" role="alert">{error}</p>}

        <section className="operator-joint-panel" aria-labelledby="joint-panel-title">
          <div className="operator-section-heading">
            <div>
              <p className="operator-kicker">FOLLOWER ARM</p>
              <h2 id="joint-panel-title">Joint positions</h2>
            </div>
            <span className="operator-readonly-pill">READ ONLY</span>
          </div>
          <div className="operator-joint-grid">
            {JOINT_DEFINITIONS.map((joint) => (
              <JointCard
                key={joint.key}
                joint={joint}
                position={joints[joint.key as JointKey]}
              />
            ))}
          </div>
          <div className="operator-panel-footnote">
            <span className="operator-footnote-mark">i</span>
            Values are the follower pose broadcast by LeLab in radians. This view never sends motion commands.
          </div>
        </section>

        <section className="operator-checklist" aria-label="Bring-up checks">
          <div>
            <p className="operator-kicker">OPERATOR CHECK</p>
            <h2>What to look for before recording</h2>
          </div>
          <div className="operator-check-items">
            <span><i className={socketState === "connected" ? "checked" : ""} /> LeLab connected</span>
            <span><i className={teleoperationActive ? "checked" : ""} /> Teleoperation active</span>
            <span><i className={streamLive ? "checked" : ""} /> Fresh joint frames</span>
          </div>
        </section>
      </main>
    </div>
  );
}
