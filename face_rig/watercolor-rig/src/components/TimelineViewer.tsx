import React, { useEffect, useMemo, useState } from "react";
import { API_BASE, fetchTimeline, regenerateFrame } from "../api.ts";
import type { FrameInfo, Timeline } from "../api.ts";

type Props = {
  pathId: string | null;
};

type RegenTask = {
  frame: FrameInfo;
  index: number;
  anchorStartT: number;
  anchorEndT: number;
};

/**
 * Build a recursive regen schedule:
 * - Global anchors are the first and last frame (t ~ 0 and t ~ 1).
 * - Only frames whose t is within the user-selected [selStartT, selEndT]
 *   are included.
 * - Order is: mid of whole segment first, then recursively mid of
 *   left and right subsegments, etc.
 */
function buildRecursiveRegenTasks(
  frames: FrameInfo[],
  selStartIndex: number,
  selEndIndex: number
): RegenTask[] {
  if (!frames.length) return [];

  const tasks: RegenTask[] = [];

  const a = Math.min(selStartIndex, selEndIndex);
  const b = Math.max(selStartIndex, selEndIndex);
  const selStartT = frames[a].t;
  const selEndT = frames[b].t;

  const EPS = 1e-6;

  function inSelectedRange(t: number) {
    return t >= selStartT - EPS && t <= selEndT + EPS;
  }

  function schedule(leftIdx: number, rightIdx: number) {
    if (rightIdx <= leftIdx + 1) return; // no interior frames in this segment

    const left = frames[leftIdx];
    const right = frames[rightIdx];
    const leftT = left.t;
    const rightT = right.t;
    const midT = (leftT + rightT) / 2;

    // Find the frame between leftIdx and rightIdx whose t is in the
    // selected range and closest to midT.
    let bestIdx = -1;
    let bestDist = Infinity;

    for (let i = leftIdx + 1; i < rightIdx; i++) {
      const t = frames[i].t;

      // only regen frames inside the selected range
      if (!inSelectedRange(t)) continue;

      // never regen the global endpoints (should only be i=0 or i=last)
      if (t <= 0 + EPS || t >= 1 - EPS) continue;

      const dist = Math.abs(t - midT);
      if (dist < bestDist) {
        bestDist = dist;
        bestIdx = i;
      }
    }

    if (bestIdx === -1) {
      // nothing to regen in this segment within the selected range
      return;
    }

    const bestFrame = frames[bestIdx];
    tasks.push({
      frame: bestFrame,
      index: bestIdx,
      anchorStartT: leftT,
      anchorEndT: rightT,
    });

    // Recurse into left and right halves, using the newly regenerated
    // mid frame as an anchor for its subsegments.
    schedule(leftIdx, bestIdx);
    schedule(bestIdx, rightIdx);
  }

  // Start recursion from the global endpoints (0 and last frame),
  // even if the user selected an inner subrange like [0.25, 0.75].
  schedule(0, frames.length - 1);

  return tasks;
}

const TimelineViewer: React.FC<Props> = ({ pathId }) => {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // range selection
  const [rangeStartIndex, setRangeStartIndex] = useState<number | null>(null);
  const [rangeEndIndex, setRangeEndIndex] = useState<number | null>(null);

  // playback
  const [isPlaying, setIsPlaying] = useState(false);
  const [fps, setFps] = useState(8);

  // regen state
  const [regenPending, setRegenPending] = useState<number | null>(null); // single frame t
  const [rangeRegenProgress, setRangeRegenProgress] = useState<
    { current: number; total: number } | null
  >(null);

  // Track last update time for cache busting
  const [lastUpdate, setLastUpdate] = useState<number>(Date.now());

  // load timeline whenever pathId changes
  useEffect(() => {
    if (!pathId) {
      setTimeline(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    setTimeline(null);
    setSelectedIndex(0);
    setRangeStartIndex(null);
    setRangeEndIndex(null);
    setRangeRegenProgress(null);

    fetchTimeline(pathId)
      .then((tl) => {
        tl.frames.sort((a, b) => a.t - b.t);
        setTimeline(tl);
        if (tl.frames.length > 0) {
          setRangeStartIndex(0);
          setRangeEndIndex(0);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [pathId]);

  // playback loop
  useEffect(() => {
    if (!isPlaying || !timeline) return;
    if (timeline.frames.length === 0) return;

    const intervalMs = 1000 / Math.max(fps, 1);
    const id = window.setInterval(() => {
      setSelectedIndex((prev) => (prev + 1) % timeline.frames.length);
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [isPlaying, fps, timeline]);

  const currentFrame: FrameInfo | null = useMemo(() => {
    if (!timeline || timeline.frames.length === 0) return null;
    return timeline.frames[Math.min(selectedIndex, timeline.frames.length - 1)];
  }, [timeline, selectedIndex]);

  const handleRegenerateSingle = async (frame: FrameInfo, index: number) => {
    if (!timeline || !pathId) return;
    if (frame.t <= 0 || frame.t >= 1) return; // don't regen endpoints

    try {
      setRegenPending(frame.t);
      await regenerateFrame(pathId, frame.t); // uses full-path endpoints as anchors
      const tl = await fetchTimeline(pathId);
      tl.frames.sort((a, b) => a.t - b.t);
      setTimeline(tl);
      setSelectedIndex(index);
      setLastUpdate(Date.now()); // Bust image cache
    } catch (err: any) {
      alert(err?.message ?? "Regenerate failed");
    } finally {
      setRegenPending(null);
    }
  };

  const handleRegenerateRange = async () => {
    if (!timeline || !pathId) return;
    if (
      rangeStartIndex == null ||
      rangeEndIndex == null ||
      timeline.frames.length === 0
    )
      return;

    const tasks = buildRecursiveRegenTasks(
      timeline.frames,
      rangeStartIndex,
      rangeEndIndex
    );

    if (tasks.length === 0) return;

    try {
      setRangeRegenProgress({ current: 0, total: tasks.length });
      setIsPlaying(false);

      for (let i = 0; i < tasks.length; i++) {
        const task = tasks[i];
        await regenerateFrame(
          pathId,
          task.frame.t,
          task.anchorStartT,
          task.anchorEndT
        );
        setRangeRegenProgress({ current: i + 1, total: tasks.length });
      }

      // One reload at the end, so we get all updated frames
      const tl = await fetchTimeline(pathId);
      tl.frames.sort((a, b) => a.t - b.t);
      setTimeline(tl);
      setLastUpdate(Date.now()); // Bust image cache
    } catch (err: any) {
      alert(err?.message ?? "Range regenerate failed");
    } finally {
      setRangeRegenProgress(null);
    }
  };

  const onFrameClick = (e: React.MouseEvent, idx: number) => {
    setSelectedIndex(idx);
    setIsPlaying(false);

    // Shift-click → extend range; normal click → reset range
    if (e.shiftKey && rangeStartIndex != null) {
      setRangeEndIndex(idx);
    } else {
      setRangeStartIndex(idx);
      setRangeEndIndex(idx);
    }
  };

  if (!pathId) {
    return <div className="panel">Select or enter a path id to view frames.</div>;
  }

  if (loading) {
    return <div className="panel">Loading timeline...</div>;
  }

  if (error) {
    return (
      <div className="panel error">
        <div>Failed to load: {error}</div>
      </div>
    );
  }

  if (!timeline) {
    return null;
  }

  const inRange = (idx: number) => {
    if (rangeStartIndex == null || rangeEndIndex == null) return false;
    const a = Math.min(rangeStartIndex, rangeEndIndex);
    const b = Math.max(rangeStartIndex, rangeEndIndex);
    return idx >= a && idx <= b;
  };

  const rangeButtonDisabled =
    !timeline.frames.length ||
    rangeStartIndex == null ||
    rangeEndIndex == null ||
    rangeRegenProgress !== null;

  return (
    <div className="panel timeline-root">
      <header className="timeline-header">
        <div>
          <div className="tag">{timeline.pose}</div>
          <h2>{timeline.path_id}</h2>
          <div className="subtitle">
            {timeline.expr_start} → {timeline.expr_end}
          </div>
        </div>

        <div className="controls">
          <button
            className="btn"
            onClick={() => setIsPlaying((p) => !p)}
            disabled={timeline.frames.length === 0}
          >
            {isPlaying ? "Pause" : "Play"}
          </button>

          <label className="fps-control">
            <span>FPS</span>
            <input
              type="range"
              min={2}
              max={24}
              value={fps}
              onChange={(e) => setFps(Number(e.target.value))}
            />
            <span>{fps}</span>
          </label>

          <button
            className="btn"
            onClick={handleRegenerateRange}
            disabled={rangeButtonDisabled}
          >
            {rangeRegenProgress
              ? `Recursive ${rangeRegenProgress.current}/${rangeRegenProgress.total}`
              : "Regenerate range (recursive)"}
          </button>
        </div>
      </header>

      <div className="preview">
        {currentFrame ? (
          <div className="preview-inner">
            <img
              key={currentFrame.file}
              src={`${API_BASE}/frames/${timeline.path_id}/${currentFrame.file}?v=${lastUpdate}`}
              alt={`t=${currentFrame.t.toFixed(2)}`}
            />
            <div className="preview-caption">
              t = {currentFrame.t.toFixed(3)} · {currentFrame.file}
            </div>
          </div>
        ) : (
          <div>No frames found.</div>
        )}
      </div>

      <div className="strip-label">
        Frames{" "}
        <span style={{ marginLeft: 8, fontSize: 11, color: "#9ca3af" }}>
          Click to select, <kbd>Shift</kbd>+click to extend range.
        </span>
      </div>

      <div className="frame-strip">
        {timeline.frames.map((frame, idx) => {
          const isSelected = idx === selectedIndex;
          const isEndpoint = frame.t <= 0 || frame.t >= 1;
          const isBusy = regenPending === frame.t;
          const isInRange = inRange(idx);

          return (
            <div
              key={`${frame.t}-${frame.file}`}
              className={`frame-card ${isSelected ? "selected" : ""} ${
                isInRange ? "in-range" : ""
              }`}
              onClick={(e) => onFrameClick(e, idx)}
            >
              <img
                src={`${API_BASE}/frames/${timeline.path_id}/${frame.file}?v=${lastUpdate}`}
                alt={`t=${frame.t.toFixed(2)}`}
              />
              <div className="frame-meta">
                <span className="t">t={frame.t.toFixed(2)}</span>
              </div>
              {!isEndpoint && (
                <button
                  className="btn btn-small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRegenerateSingle(frame, idx);
                  }}
                  disabled={isBusy || !!rangeRegenProgress}
                >
                  {isBusy ? "Regenerating..." : "Regenerate"}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TimelineViewer;
