/**
 * Face-tracked character player using OpenSeeFace + audio energy.
 * Drives expression + pose state from real-time tracking data.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, fetchTimeline } from "./api.ts";
import type { FrameInfo, Timeline } from "./api.ts";
import type {
  ExpressionId,
  PoseId,
  State,
  Segment,
} from "./transitionGraph.ts";
import { planRoute } from "./transitionGraph.ts";

const OSF_WS_URL = "ws://localhost:9000/ws/tracking";

type TrackingMessage = {
  face: {
    timestamp: number;
    face_id: number;
    success: boolean;
    eye_blink: { left: number; right: number };
    rotation: {
      euler: { pitch: number; yaw: number; roll: number };
    };
    features: {
      mouth_open: number;
      mouth_wide: number;
      eye_l: number;
      eye_r: number;
      [key: string]: number;
    };
  };
  audio: {
    energy: number;
    phoneme: string;
  };
};

type ActiveSegment = {
  seg: Segment;
  timeline: Timeline;
  direction: "forward" | "reverse";
};

const FPS = 24;  // Maximum speed for instant response testing

/**
 * Map OSF tracking data to character state.
 */
function mapTrackingToState(
  msg: TrackingMessage, 
  currentState: State,
  baseline: { pitch: number; yaw: number; roll: number } | null,
  _mouthOpen: boolean
): State {
  const { face } = msg;
  
  if (!face || !face.success) {
    return currentState; // no face detected, keep current
  }
  
  // --- Pose from head rotation ---
  const { pitch, yaw, roll } = face.rotation.euler;
  let targetPose: PoseId = "center";
  
  // If we have a baseline, use relative angles
  if (baseline) {
    // Normalize angle differences to -180 to +180 range
    const normalizeDelta = (angle: number) => {
      let delta = angle;
      while (delta > 180) delta -= 360;
      while (delta < -180) delta += 360;
      return delta;
    };
    
    const relativePitch = normalizeDelta(pitch - baseline.pitch);
    const relativeYaw = normalizeDelta(yaw - baseline.yaw);
    const relativeRoll = normalizeDelta(roll - baseline.roll);
    
    // Thresholds for detecting intentional pose changes
    const HORIZONTAL_THRESHOLD = 10;  // degrees - for yaw (turn) or roll (tilt)
    const PITCH_THRESHOLD = 6;  // degrees - for nod up/down (lower = more sensitive)
    
    // Combine yaw (turning) and roll (tilting) for horizontal movement
    const absYaw = Math.abs(relativeYaw);
    const absRoll = Math.abs(relativeRoll);
    const absPitch = Math.abs(relativePitch);
    
    // Use largest horizontal component (yaw OR roll)
    const horizontalMovement = Math.max(absYaw, absRoll);
    
    if (horizontalMovement > absPitch && horizontalMovement > HORIZONTAL_THRESHOLD) {
      // Horizontal movement dominates (either turning or tilting)
      // Determine direction from whichever is larger
      const direction = absYaw > absRoll ? relativeYaw : relativeRoll;
      
      if (direction > 0) {
        targetPose = "tilt_right_small";
      } else {
        targetPose = "tilt_left_small";
      }
    } else if (absPitch > PITCH_THRESHOLD) {
      // Pitch dominates (positive pitch = nod down, negative = nod up)
      if (relativePitch > 0) {
        targetPose = "nod_down_small";
      } else {
        targetPose = "nod_up_small";
      }
    }
  }
  
  // --- Expression from features + audio ---
  // Mouth tracking doesn't work reliably with OSF
  // For now, keep neutral - can be triggered manually with spacebar
  let targetExpr: ExpressionId = "neutral";
  
  return { expr: targetExpr, pose: targetPose };
}

export const FaceTrackedPlayer: React.FC = () => {
  const [currentState, setCurrentState] = useState<State>({
    expr: "neutral",
    pose: "center",
  });
  const [targetState, setTargetState] = useState<State>({
    expr: "neutral",
    pose: "center",
  });
  
  const [activeSegments, setActiveSegments] = useState<ActiveSegment[]>([]);
  const [segmentIndex, setSegmentIndex] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  
  const [wsConnected, setWsConnected] = useState(false);
  const [debugInfo, setDebugInfo] = useState<string>("");
  
  // Calibration baseline - auto-set on first frame (use ref for immediate access)
  const baselineRef = useRef<{ pitch: number; yaw: number; roll: number } | null>(null);
  const [, setBaselineDisplay] = useState<{ pitch: number; yaw: number; roll: number } | null>(null);
  
  // Track previous pitch for jaw movement detection
  const wsRef = useRef<WebSocket | null>(null);
  const lastTargetRef = useRef<State>(currentState);
  const lastValidDataTime = useRef<number>(Date.now());
  
  // --- WebSocket connection ---
  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    
    const connect = () => {
      if (ws && ws.readyState !== WebSocket.CLOSED) {
        return; // Already connected or connecting
      }
      
      ws = new WebSocket(OSF_WS_URL);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log("[WS] Connected to OSF server");
        setWsConnected(true);
      };
      
      ws.onclose = () => {
        console.log("[WS] Disconnected");
        setWsConnected(false);
        
        // Auto-reconnect after 2 seconds
        reconnectTimer = setTimeout(() => {
          console.log("[WS] Attempting to reconnect...");
          connect();
        }, 2000);
      };
      
      ws.onerror = (err) => {
        console.error("[WS] Error:", err);
      };
      
      ws.onmessage = (event) => {
      try {
        const msg: TrackingMessage = JSON.parse(event.data);
        
        // Check if we have face data
        if (!msg.face) {
          // Only show "waiting" message if we haven't had valid data for 2+ seconds
          const now = Date.now();
          if (now - lastValidDataTime.current > 2000) {
            setDebugInfo("Waiting for face tracking data... (check lighting and position)");
          }
          return;
        }
        
        // Update last valid data time
        lastValidDataTime.current = Date.now();
        
        // Get current angles
        const { pitch, yaw, roll } = msg.face.rotation.euler;
        
        // Auto-calibrate on first frame
        if (!baselineRef.current) {
          const newBaseline = { pitch, yaw, roll };
          baselineRef.current = newBaseline;
          setBaselineDisplay(newBaseline);
          console.log('[Auto-calibrate] Baseline set:', newBaseline);
        }
        
        // Map to new state
        const newTarget = mapTrackingToState(msg, currentState, baselineRef.current, false);
        
        // Update debug info
        let debugStr = `Face: ${msg.face.success ? "✓" : "✗"} | ` +
          `Yaw: ${yaw.toFixed(2)} Pitch: ${pitch.toFixed(2)} Roll: ${roll.toFixed(2)} | ` +
          `Eyes: L=${msg.face.eye_blink.left.toFixed(2)} R=${msg.face.eye_blink.right.toFixed(2)} | ` +
          `Mouth Open: ${msg.face.features.mouth_open.toFixed(2)} Wide: ${msg.face.features.mouth_wide.toFixed(2)} | ` +
          `Audio: ${msg.audio.energy.toFixed(3)} (${msg.audio.phoneme})`;
        
        if (baselineRef.current) {
          const relPitch = pitch - baselineRef.current.pitch;
          const relYaw = yaw - baselineRef.current.yaw;
          const relRoll = roll - baselineRef.current.roll;
          debugStr += `\n📍 Relative: Yaw: ${relYaw.toFixed(1)}° Pitch: ${relPitch.toFixed(1)}° Roll: ${relRoll.toFixed(1)}°`;
        }
        
        setDebugInfo(debugStr);
          
        // INSTANT MODE: No debouncing or stability checks
        // Trigger animation immediately on every state change
        if (!isPlaying) {
          const changed =
            newTarget.expr !== lastTargetRef.current.expr ||
            newTarget.pose !== lastTargetRef.current.pose;
          
          if (changed) {
            console.log(`[State Change] ${lastTargetRef.current.expr}__${lastTargetRef.current.pose} → ${newTarget.expr}__${newTarget.pose}`);
            lastTargetRef.current = newTarget;
            setTargetState(newTarget);
            playRouteTo(newTarget);
          }
        }
        } catch (err) {
          console.error("[WS] Parse error:", err);
        }
      };
    };
    
    connect();
    
    return () => {
      clearTimeout(reconnectTimer);
      if (ws) {
        ws.close();
      }
    };
  }, []); // Only on mount
  
  // --- Animation player ---
  const [currentTimeline, currentFrame]: [Timeline | null, FrameInfo | null] =
    useMemo(() => {
      if (!activeSegments.length || !isPlaying) return [null, null];
      const seg = activeSegments[segmentIndex];
      if (!seg) return [null, null];
      const frames =
        seg.direction === "forward"
          ? seg.timeline.frames
          : [...seg.timeline.frames].slice().reverse();
      const idx = Math.min(frameIndex, frames.length - 1);
      return [seg.timeline, frames[idx] ?? null];
    }, [activeSegments, segmentIndex, frameIndex, isPlaying]);
  
  useEffect(() => {
    if (!isPlaying || !activeSegments.length) return;
    
    const seg = activeSegments[segmentIndex];
    if (!seg) return;
    
    const frames =
      seg.direction === "forward"
        ? seg.timeline.frames
        : [...seg.timeline.frames].slice().reverse();
    
    if (!frames.length) return;
    
    const intervalMs = 1000 / FPS;
    const id = window.setInterval(() => {
      setFrameIndex((prev) => {
        const next = prev + 1;
        if (next < frames.length) {
          return next;
        } else {
          // Move to next segment
          setSegmentIndex((s) => {
            const nextSeg = s + 1;
            if (nextSeg < activeSegments.length) {
              return nextSeg;
            } else {
              // Route done
              const lastSeg = activeSegments[activeSegments.length - 1];
              setCurrentState(lastSeg.seg.to);
              setActiveSegments([]);
              setSegmentIndex(0);
              setFrameIndex(0);
              setIsPlaying(false);
              return 0;
            }
          });
          return 0;
        }
      });
    }, intervalMs);
    
    return () => window.clearInterval(id);
  }, [activeSegments, segmentIndex, isPlaying]);
  
  // --- Route planning and playback ---
  const playRouteTo = useCallback(
    async (next: State) => {
      const route = planRoute(currentState, next);
      if (!route.length) {
        setCurrentState(next);
        setTargetState(next);
        return;
      }
      
      try {
        const segs: ActiveSegment[] = [];
        for (const seg of route) {
          const timeline = await fetchTimeline(seg.pathId);
          segs.push({ seg, timeline, direction: seg.direction });
        }
        setTargetState(next);
        setActiveSegments(segs);
        setSegmentIndex(0);
        setFrameIndex(0);
        setIsPlaying(true);
      } catch (err) {
        console.error("Failed to play route:", err);
      }
    },
    [currentState]
  );
  
  // --- Idle frame display ---
  const [idleFrame, setIdleFrame] = useState<string | null>(null);
  const [loadedIdleKey, setLoadedIdleKey] = useState<string>("");
  
  useEffect(() => {
    const key = `${currentState.expr}__${currentState.pose}`;
    if (key === loadedIdleKey) return;
    
    // For neutral expression, load the first frame of neutral_to_speaking_ah
    // as a placeholder idle frame
    if (currentState.expr === "neutral") {
      const neutralPath = `neutral_to_speaking_ah__${currentState.pose}`;
      fetchTimeline(neutralPath)
        .then((tl) => {
          if (tl.frames.length > 0) {
            // Use the FIRST frame (neutral state)
            const firstFrame = tl.frames[0];
            const url = `${API_BASE}/frames/${tl.path_id}/${firstFrame.file}`;
            setIdleFrame(url);
            setLoadedIdleKey(key);
          }
        })
        .catch((err) => {
          console.error("Failed to load neutral idle frame:", err);
          setLoadedIdleKey(key);
        });
      return;
    }
    
    let exprForIdle = currentState.expr;
    if (currentState.expr === "surprised_ah") {
      exprForIdle = "speaking_ah";
    } else if (currentState.expr === "happy_big") {
      exprForIdle = "happy_soft";
    } else if (currentState.expr === "blink_closed") {
      exprForIdle = "speaking_ah"; // fallback to speaking_ah instead of neutral
    }
    
    const idlePath = `neutral_to_${exprForIdle}__${currentState.pose}`;
    
    fetchTimeline(idlePath)
      .then((tl) => {
        if (tl.frames.length > 0) {
          const lastFrame = tl.frames[tl.frames.length - 1];
          const url = `${API_BASE}/frames/${tl.path_id}/${lastFrame.file}`;
          setIdleFrame(url);
          setLoadedIdleKey(key);
        }
      })
      .catch((err) => {
        console.error("Failed to load idle frame:", err);
        setLoadedIdleKey(key); // Mark as loaded even if failed, to avoid retry loop
      });
  }, [currentState, loadedIdleKey]);
  
  // Always prefer animation frame if playing, otherwise show idle frame
  const currentImageUrl = useMemo(() => {
    if (isPlaying && currentTimeline && currentFrame) {
      return `${API_BASE}/frames/${currentTimeline.path_id}/${currentFrame.file}`;
    }
    return idleFrame;
  }, [isPlaying, currentTimeline, currentFrame, idleFrame]);
  
  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center p-6 gap-4">
      <h1 className="text-2xl font-bold mb-2">
        Face-Tracked Character (OpenSeeFace)
      </h1>
      
      {/* Connection status */}
      <div className="text-xs">
        <span
          className={
            wsConnected
              ? "text-emerald-400"
              : "text-red-400"
          }
        >
          {wsConnected ? "● Connected" : "● Disconnected"}
        </span>
        {!wsConnected && (
          <span className="ml-2 text-slate-400">
            (Run: uvicorn osf_server:app --port 9000)
          </span>
        )}
      </div>
      
      {/* Preview */}
      <div className="flex flex-col items-center gap-2">
        <div 
          className="bg-slate-800 rounded-xl flex items-center justify-center overflow-hidden"
          style={{
            width: '320px',
            height: '480px',
            position: 'relative'
          }}
        >
          {currentImageUrl ? (
            <img
              src={currentImageUrl}
              alt="current"
              style={{ 
                width: '320px',
                height: '480px',
                objectFit: 'contain',
                display: 'block'
              }}
            />
          ) : (
            <span className="text-slate-500 text-sm">Loading...</span>
          )}
        </div>
        
        <div className="text-xs text-slate-300 font-mono">
          Current: {currentState.expr} @ {currentState.pose}
          {isPlaying && ` → ${targetState.expr} @ ${targetState.pose}`}
        </div>
      </div>
      
      {/* Debug info */}
      <div className="w-full max-w-3xl bg-slate-800 rounded p-3 text-xs font-mono text-slate-300">
        <div className="font-semibold mb-1 text-slate-400">Tracking Data:</div>
        <div>{debugInfo || "Waiting for tracking data..."}</div>
      </div>
      
      {/* Manual Controls */}
      <div className="w-full max-w-3xl bg-slate-800 rounded p-4 flex gap-3">
        <button
          onClick={() => {
            const neutralState: State = { expr: "neutral", pose: "center" };
            setCurrentState(neutralState);
            setTargetState(neutralState);
            lastTargetRef.current = neutralState;
            setActiveSegments([]);
            setIsPlaying(false);
          }}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-semibold"
        >
          Reset to Neutral (Center)
        </button>
        
        <button
          onClick={() => {
            baselineRef.current = null;
            setBaselineDisplay(null);
            console.log('[Recalibrate] Baseline cleared - will auto-calibrate on next frame');
          }}
          className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded font-semibold"
        >
          Recalibrate
        </button>
      </div>
      
      {/* Instructions */}
      <div className="w-full max-w-3xl bg-slate-800 rounded p-4 text-sm text-slate-300">
        <h3 className="font-semibold mb-2 text-slate-100">How to use:</h3>
        <ol className="list-decimal list-inside space-y-1">
          <li>Start the OSF server: <code className="bg-slate-900 px-1 rounded">./start_osf_server.sh</code></li>
          <li><strong>Sit in your normal position</strong> - the first frame auto-calibrates!</li>
          <li>Wait for "📍 Relative" to appear - shows angles from your neutral</li>
          <li>Tilt left/right (&gt;10°) or nod up/down (&gt;10°) to trigger animations</li>
          <li>Click "Recalibrate" if you change position</li>
          <li>Use "Reset to Neutral" if the character gets stuck</li>
        </ol>
        <p className="mt-2 text-xs text-slate-400">
          💡 Auto-calibrates your neutral pose on first frame, then tracks absolute angles relative to that baseline.
        </p>
      </div>
    </div>
  );
};

