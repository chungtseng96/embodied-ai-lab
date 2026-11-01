import { useEffect, useRef, useState } from "react";
import { EpisodeMedia, episodePath, MediaEvent, request, Step } from "./api";
import Trace from "./Trace";

type MediaEvidenceProps = {
  runId: string;
  episodeId: string;
  steps: Step[] | null;
  traceError: string;
};

function isValidManifest(value: EpisodeMedia, episodeId: string) {
  return (
    value?.schema_version === 1 &&
    value.episode_id === episodeId &&
    Array.isArray(value.streams) &&
    Array.isArray(value.events) &&
    value.streams.every(
      (stream) =>
        !!stream &&
        typeof stream === "object" &&
        typeof stream.camera === "string" &&
        typeof stream.path === "string" &&
        typeof stream.mime_type === "string" &&
        typeof stream.url === "string" &&
        Number.isFinite(stream.duration_s) &&
        stream.duration_s > 0 &&
        Number.isFinite(stream.trace_start_s),
    ) &&
    value.events.every(
      (event) =>
        !!event &&
        typeof event === "object" &&
        typeof event.name === "string" &&
        Number.isFinite(event.timestamp_s),
    )
  );
}

export default function MediaEvidence({
  runId,
  episodeId,
  steps,
  traceError,
}: MediaEvidenceProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [manifest, setManifest] = useState<EpisodeMedia | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [videoError, setVideoError] = useState("");
  const [seekError, setSeekError] = useState("");
  const [selectedCamera, setSelectedCamera] = useState("");
  const [cursorTime, setCursorTime] = useState<number>();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setManifest(null);
    setError("");
    setVideoError("");
    setSeekError("");
    setSelectedCamera("");
    setCursorTime(undefined);
    request<EpisodeMedia>(`${episodePath(runId, episodeId)}/media`)
      .then((data) => {
        if (!active) return;
        if (!isValidManifest(data, episodeId)) {
          setError("Media manifest is invalid or belongs to another episode.");
          return;
        }
        setManifest(data);
        setSelectedCamera(data.streams[0]?.camera || "");
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof Error
              ? err.message
              : "Could not load media manifest",
          );
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [runId, episodeId]);

  const stream = manifest?.streams.find(
    (candidate) => candidate.camera === selectedCamera,
  );
  const events = (manifest?.events || [])
    .filter(
      (event) =>
        stream &&
        Number.isFinite(event.timestamp_s) &&
        event.timestamp_s >= stream.trace_start_s &&
        event.timestamp_s <= stream.trace_start_s + stream.duration_s,
    )
    .sort((a, b) => a.timestamp_s - b.timestamp_s);

  function seekVideo(videoTime: number, traceTime: number) {
    if (!stream || !Number.isFinite(videoTime) || !Number.isFinite(traceTime))
      return;
    const video = videoRef.current;
    if (!video) return;
    if (
      video.readyState < HTMLMediaElement.HAVE_METADATA ||
      !Number.isFinite(video.duration)
    ) {
      setSeekError(
        "Video metadata has not loaded; wait and try this seek again.",
      );
      return;
    }
    const playableDuration = Math.min(stream.duration_s, video.duration);
    if (videoTime < 0 || videoTime > playableDuration) {
      setSeekError("That timestamp falls outside the playable video duration.");
      return;
    }
    try {
      video.currentTime = videoTime;
      setSeekError("");
      setCursorTime(traceTime);
    } catch {
      setSeekError("The browser is not ready to seek this video yet.");
    }
  }

  function seekVideoToTraceTime(traceTime: number) {
    if (!stream || !Number.isFinite(traceTime)) return;
    const videoTime = traceTime - stream.trace_start_s;
    if (videoTime < 0 || videoTime > stream.duration_s) return;
    seekVideo(videoTime, traceTime);
  }

  function seekVideoToEvent(event: MediaEvent) {
    if (!stream) return;
    const videoTime = event.timestamp_s - stream.trace_start_s;
    if (videoTime < 0 || videoTime > stream.duration_s) return;
    seekVideo(videoTime, event.timestamp_s);
  }

  function updateCursorFromVideo() {
    const video = videoRef.current;
    if (!video || !stream || !Number.isFinite(video.currentTime)) return;
    setCursorTime(video.currentTime + stream.trace_start_s);
  }

  const traceContent = traceError ? (
    <p className="error" role="alert">
      Trace unavailable: {traceError}
    </p>
  ) : steps === null ? (
    <p className="muted">Loading recorded trace…</p>
  ) : (
    <Trace
      steps={steps}
      cursorTime={cursorTime}
      onSeek={stream ? seekVideoToTraceTime : undefined}
    />
  );

  return (
    <div className="media-evidence">
      {loading ? (
        <p className="muted media-load-state">Loading episode media…</p>
      ) : error ? (
        <div className="media-error" role="alert">
          <strong>Episode media unavailable</strong>
          <p>{error}</p>
        </div>
      ) : !manifest?.streams.length ? (
        <div className="media-empty">
          <span aria-hidden="true">▧</span>
          <div>
            <strong>No media linked to this episode</strong>
            <p>Review the recorded joint trajectory below.</p>
          </div>
        </div>
      ) : stream ? (
        <section className="media-player" aria-label="Episode video evidence">
          <div className="media-player-toolbar">
            <div>
              <strong>Recorded video</strong>
              <p className="media-meta">
                {stream.camera} · {stream.mime_type} ·{" "}
                {stream.duration_s.toFixed(2)}s
              </p>
            </div>
            {manifest.streams.length > 1 && (
              <label className="camera-picker">
                Camera
                <select
                  aria-label="Media camera"
                  value={selectedCamera}
                  onChange={(event) => {
                    setSelectedCamera(event.target.value);
                    setVideoError("");
                    setSeekError("");
                    setCursorTime(undefined);
                  }}
                >
                  {manifest.streams.map((camera) => (
                    <option key={camera.camera} value={camera.camera}>
                      {camera.camera}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
          <video
            key={`${episodeId}/${stream.camera}/${stream.url}`}
            ref={videoRef}
            aria-label="Episode video"
            controls
            preload="metadata"
            onLoadedMetadata={() => {
              setVideoError("");
              setSeekError("");
              setCursorTime(stream.trace_start_s);
            }}
            onTimeUpdate={updateCursorFromVideo}
            onError={(event) => {
              const code = event.currentTarget.error?.code;
              setVideoError(
                code === 3 || code === 4
                  ? `The browser could not decode this ${stream.mime_type} stream. Try a media format supported by this browser.`
                  : `The browser could not load this ${stream.mime_type} stream.`,
              );
            }}
            src={stream.url}
          />
          {videoError && (
            <p className="media-error" role="alert">
              {videoError}
            </p>
          )}
          {seekError && (
            <p className="media-seek-error" role="status">
              {seekError}
            </p>
          )}
          <p className="media-sync-note">
            Trace alignment uses the recorded host clock offset; timing has not
            been independently verified against robot motion.
          </p>
          {events.length > 0 ? (
            <div className="event-timeline">
              <p className="event-heading">Recorded events within this clip</p>
              <div
                className="event-track"
                role="group"
                aria-label="Recorded event markers"
              >
                <span className="event-track-line" aria-hidden="true" />
                {events.map((event, index) => {
                  const offset = event.timestamp_s - stream.trace_start_s;
                  return (
                    <button
                      className="event-marker"
                      key={`${event.name}/${event.timestamp_s}/${index}`}
                      style={{ left: `${(100 * offset) / stream.duration_s}%` }}
                      title={`${event.name} at ${offset.toFixed(2)}s`}
                      aria-label={`Seek to recorded event ${event.name} at ${offset.toFixed(2)} seconds`}
                      onClick={() => seekVideoToEvent(event)}
                    >
                      <span aria-hidden="true" />
                    </button>
                  );
                })}
              </div>
              <ul className="event-list">
                {events.map((event, index) => {
                  const offset = event.timestamp_s - stream.trace_start_s;
                  return (
                    <li key={`${event.name}/${event.timestamp_s}/${index}`}>
                      <button
                        type="button"
                        onClick={() => seekVideoToEvent(event)}
                      >
                        {event.name} <time>{offset.toFixed(2)}s</time>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <p className="muted small event-empty">
              No recorded event markers fall within this clip.
            </p>
          )}
        </section>
      ) : null}
      <section className="trace-panel">
        <h3>Joint trajectory</h3>
        {traceContent}
      </section>
    </div>
  );
}
