import React, { useEffect, useState } from "react";
import TimelineViewer from "./components/TimelineViewer.tsx";
import { MediaPipeFaceTrackedPlayer } from "./MediaPipeFaceTrackedPlayer.tsx";
import { KeyframePlayer } from "./KeyframePlayer.tsx";
import { TimelineDirector } from "./TimelineDirector.tsx";
import { fetchTimelines } from "./api.ts";

type Mode = "viewer" | "face-tracked" | "keyframe" | "director";

const App: React.FC = () => {
  const [mode, setMode] = useState<Mode>("viewer");
  const [pathIds, setPathIds] = useState<string[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [manualInput, setManualInput] = useState("");

  useEffect(() => {
    fetchTimelines().then((ids) => {
      setPathIds(ids);
      if (ids.length > 0) {
        setSelectedPath(ids[0]);
        setManualInput(ids[0]);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleManualLoad = () => {
    const trimmed = manualInput.trim();
    if (!trimmed) return;
    setSelectedPath(trimmed);
  };

  if (mode === "face-tracked") {
    return (
      <div>
        <div style={{ position: "absolute", top: 10, left: 10, zIndex: 100 }}>
          <button
            onClick={() => setMode("viewer")}
            style={{
              padding: "8px 16px",
              background: "#334155",
              color: "#e2e8f0",
              border: "1px solid #475569",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            ← Back to Viewer
          </button>
        </div>
        <MediaPipeFaceTrackedPlayer />
      </div>
    );
  }

  if (mode === "keyframe") {
    return (
      <div>
        <div style={{ position: "absolute", top: 10, left: 10, zIndex: 100 }}>
          <button
            onClick={() => setMode("viewer")}
            style={{
              padding: "8px 16px",
              background: "#334155",
              color: "#e2e8f0",
              border: "1px solid #475569",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            ← Back to Viewer
          </button>
        </div>
        <KeyframePlayer />
      </div>
    );
  }

  if (mode === "director") {
    return (
      <div>
        <div style={{ position: "absolute", top: 10, left: 10, zIndex: 100 }}>
          <button
            onClick={() => setMode("viewer")}
            style={{
              padding: "8px 16px",
              background: "#334155",
              color: "#e2e8f0",
              border: "1px solid #475569",
              borderRadius: "6px",
              cursor: "pointer",
            }}
          >
            ← Back to Viewer
          </button>
        </div>
        <TimelineDirector />
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h1 className="logo">Watercolor Rig</h1>

        <div className="field">
          <button
            className="btn"
            onClick={() => setMode("director")}
            style={{ marginBottom: "0.5rem", width: "100%", background: "#9C27B0" }}
          >
            🎞️ Timeline Director
          </button>
          <button
            className="btn"
            onClick={() => setMode("keyframe")}
            style={{ marginBottom: "0.5rem", width: "100%" }}
          >
            🎬 Keyframe Player
          </button>
          <button
            className="btn"
            onClick={() => setMode("face-tracked")}
            style={{ marginBottom: "1rem", width: "100%" }}
          >
            🎥 Face Tracking Mode
          </button>
        </div>

        <div className="field">
          <label>Path ID</label>
          <input
            type="text"
            value={manualInput}
            placeholder="neutral_to_speaking_ah__center"
            onChange={(e) => setManualInput(e.target.value)}
          />
          <button className="btn" onClick={handleManualLoad}>
            Load path
          </button>
        </div>

        {pathIds.length > 0 && (
          <div className="field">
            <label>Known timelines</label>
            <div className="path-list">
              {pathIds.map((id) => (
                <button
                  key={id}
                  className={`path-item ${
                    selectedPath === id ? "active" : ""
                  }`}
                  onClick={() => {
                    setSelectedPath(id);
                    setManualInput(id);
                  }}
                >
                  {id}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="footer-note">
          Endpoints are generated offline with <code>generate_sequence.py</code>.
          This UI just previews and regenerates individual frames.
        </div>
      </aside>

      <main className="main">
        <TimelineViewer pathId={selectedPath} />
      </main>
    </div>
  );
};

export default App;
