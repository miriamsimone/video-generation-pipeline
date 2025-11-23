import React, { useEffect, useRef, useState, useMemo } from "react";
import { FaceMesh, type Results } from "@mediapipe/face_mesh";
import { Camera } from "@mediapipe/camera_utils";
import type { State, ExpressionId, PoseId } from "./transitionGraph.ts";
import { planRoute } from "./transitionGraph.ts";
import type { Timeline } from "./api.ts";
import type { Segment } from "./transitionGraph.ts";
import { fetchTimeline } from "./api.ts";

const API_BASE = "http://localhost:8000";

type ActiveSegment = {
  seg: Segment;
  timeline: Timeline;
  direction: "forward" | "reverse";
};

const FPS = 24;

/**
 * Calculate 3D head pose from MediaPipe face landmarks
 */
function calculateHeadPose(landmarks: any[]): { pitch: number; yaw: number; roll: number } {
  // Key landmarks for head pose estimation
  const noseTip = landmarks[1];
  const foreheadCenter = landmarks[10];
  const chinBottom = landmarks[152];
  const leftEye = landmarks[33];
  const rightEye = landmarks[263];
  // const leftMouth = landmarks[61];
  // const rightMouth = landmarks[291];

  // Calculate yaw (left/right turn) from nose position relative to face width
  const faceWidth = Math.abs(leftEye.x - rightEye.x);
  const noseOffset = noseTip.x - (leftEye.x + rightEye.x) / 2;
  const yaw = (noseOffset / faceWidth) * 60; // Scale to degrees

  // Calculate pitch (up/down) from vertical face positions
  const faceHeight = Math.abs(foreheadCenter.y - chinBottom.y);
  const noseVertical = noseTip.y - foreheadCenter.y;
  const pitch = (noseVertical / faceHeight - 0.5) * 60; // Scale to degrees

  // Calculate roll (tilt) from eye line angle
  const eyeDeltaY = rightEye.y - leftEye.y;
  const eyeDeltaX = rightEye.x - leftEye.x;
  const roll = Math.atan2(eyeDeltaY, eyeDeltaX) * (180 / Math.PI);

  return { pitch, yaw, roll };
}

/**
 * Calculate mouth openness from MediaPipe landmarks
 */
function calculateMouthOpen(landmarks: any[]): number {
  // Upper lip center and lower lip center
  const upperLip = landmarks[13];
  const lowerLip = landmarks[14];
  
  // Mouth corners
  const leftCorner = landmarks[61];
  const rightCorner = landmarks[291];
  
  // Calculate mouth height vs width ratio
  const mouthHeight = Math.abs(upperLip.y - lowerLip.y);
  const mouthWidth = Math.abs(leftCorner.x - rightCorner.x);
  
  // Normalize: bigger ratio = more open
  return mouthHeight / mouthWidth;
}

/**
 * Calculate mouth width (for smile detection)
 * Returns normalized width - higher = wider smile
 */
function calculateMouthWide(landmarks: any[]): number {
  // Mouth corners
  const leftCorner = landmarks[61];
  const rightCorner = landmarks[291];
  
  // Face width reference (distance between temples)
  const leftTemple = landmarks[127];
  const rightTemple = landmarks[356];
  const faceWidth = Math.abs(leftTemple.x - rightTemple.x);
  
  // Calculate mouth width relative to face width
  const mouthWidth = Math.abs(leftCorner.x - rightCorner.x);
  
  // Normalize: wider mouth = bigger smile
  return mouthWidth / faceWidth;
}

/**
 * Map MediaPipe face data to character state
 */
function mapFaceToState(
  results: Results,
  currentState: State,
  baseline: { pitch: number; yaw: number; roll: number } | null
): State {
  if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
    return currentState;
  }

  const landmarks = results.multiFaceLandmarks[0];
  
  // Calculate head pose
  const { pitch, yaw, roll } = calculateHeadPose(landmarks);
  let targetPose: PoseId = "center";
  let relativePitch = 0;

  // If we have a baseline, use relative angles
  if (baseline) {
    // Normalize angle differences
    const normalizeDelta = (angle: number) => {
      let delta = angle;
      while (delta > 180) delta -= 360;
      while (delta < -180) delta += 360;
      return delta;
    };

    relativePitch = normalizeDelta(pitch - baseline.pitch);
    const relativeYaw = normalizeDelta(yaw - baseline.yaw);
    const relativeRoll = normalizeDelta(roll - baseline.roll);

    // Thresholds with hysteresis (dead zone to prevent rapid toggling)
    // If already in a tilted/nodded state, require less movement to stay
    // If in center, require more movement to enter
    const isInCenter = currentState.pose === "center";
    const HORIZONTAL_ENTER = 15; // degrees to enter tilt from center
    const HORIZONTAL_EXIT = 8;   // degrees to exit tilt back to center
    const PITCH_ENTER = 12;      // degrees to enter nod from center
    const PITCH_EXIT = 6;        // degrees to exit nod back to center

    const horizontalThreshold = isInCenter ? HORIZONTAL_ENTER : HORIZONTAL_EXIT;
    const pitchThreshold = isInCenter ? PITCH_ENTER : PITCH_EXIT;

    const absYaw = Math.abs(relativeYaw);
    const absRoll = Math.abs(relativeRoll);
    const absPitch = Math.abs(relativePitch);

    // Horizontal movement (yaw or roll)
    const horizontalMovement = Math.max(absYaw, absRoll);

    if (horizontalMovement > absPitch && horizontalMovement > horizontalThreshold) {
      const direction = absYaw > absRoll ? relativeYaw : relativeRoll;
      targetPose = direction > 0 ? "tilt_right_small" : "tilt_left_small";
    } else if (absPitch > pitchThreshold) {
      targetPose = relativePitch > 0 ? "nod_down_small" : "nod_up_small";
    }
  }

  // Calculate mouth metrics
  const mouthOpen = calculateMouthOpen(landmarks);
  const mouthWide = calculateMouthWide(landmarks);
  let targetExpr: ExpressionId = "neutral";

  // Adjust thresholds based on head pitch (looking up/down affects mouth measurements)
  // Positive relativePitch = looking down, Negative = looking up
  const pitchAdjustmentDown = Math.max(0, relativePitch / 10); // For looking down
  const pitchAdjustmentUp = Math.max(0, -relativePitch / 10);  // For looking up
  
  // Hysteresis for expression transitions (dead zone to prevent rapid toggling)
  // const isNeutralExpr = currentState.expr === "neutral";
  const isSmiling = currentState.expr === "happy_soft" || currentState.expr === "happy_big";
  const isSpeaking = currentState.expr === "speaking_ah";

  // Base thresholds
  // MOUTH OPEN: Gets compressed when looking down, so lower threshold (but not too much)
  const MOUTH_OPEN_ENTER = Math.max(0.15, 0.70 - (pitchAdjustmentDown * 0.80));
  const MOUTH_OPEN_EXIT = Math.max(0.10, 0.50 - (pitchAdjustmentDown * 0.60));
  
  // SMILE: Mouth appears wider when head is tilted (up OR down), so INCREASE threshold
  const pitchAdjustmentTotal = pitchAdjustmentDown + pitchAdjustmentUp;
  const SMILE_SOFT_ENTER = 0.40 + (pitchAdjustmentTotal * 0.05); // Higher when tilted
  const SMILE_SOFT_EXIT = 0.38 + (pitchAdjustmentTotal * 0.04);  // Closer to enter (smaller hysteresis)
  const SMILE_BIG_ENTER = 0.46 + (pitchAdjustmentTotal * 0.06);
  const SMILE_BIG_EXIT = 0.42 + (pitchAdjustmentTotal * 0.05);   // Closer to enter (smaller hysteresis)

  // Apply hysteresis
  const mouthOpenThreshold = isSpeaking ? MOUTH_OPEN_EXIT : MOUTH_OPEN_ENTER;
  const smileSoftThreshold = isSmiling ? SMILE_SOFT_EXIT : SMILE_SOFT_ENTER;
  const smileBigThreshold = (currentState.expr === "happy_big") ? SMILE_BIG_EXIT : SMILE_BIG_ENTER;

  // Detect expressions based on mouth shape
  // Check mouth open FIRST - speaking takes priority over smiling
  if (mouthOpen > mouthOpenThreshold) {
    targetExpr = "speaking_ah";
  }
  // Wide smile (mouth stretched horizontally)
  else if (mouthWide > smileSoftThreshold) {
    targetExpr = mouthWide > smileBigThreshold ? "happy_big" : "happy_soft";
  }

  return { expr: targetExpr, pose: targetPose };
}

export const MediaPipeFaceTrackedPlayer: React.FC = () => {
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

  const [debugInfo, setDebugInfo] = useState<string>("");
  const [faceDetected, setFaceDetected] = useState(false);

  // Calibration baseline
  const baselineRef = useRef<{ pitch: number; yaw: number; roll: number } | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const faceMeshRef = useRef<FaceMesh | null>(null);
  const cameraRef = useRef<Camera | null>(null);

  const currentStateRef = useRef<State>(currentState);
  const isPlayingRef = useRef<boolean>(isPlaying);
  const targetStateRef = useRef<State>(targetState);
  const lastTargetRef = useRef<State>(currentState);
  
  // Keep refs in sync
  useEffect(() => {
    currentStateRef.current = currentState;
    isPlayingRef.current = isPlaying;
    targetStateRef.current = targetState;
  }, [currentState, isPlaying, targetState]);

  // --- Idle frame display ---
  const [idleFrame, setIdleFrame] = useState<string | null>(null);
  const [loadedIdleKey, setLoadedIdleKey] = useState<string>("");

  useEffect(() => {
    const key = `${currentState.expr}__${currentState.pose}`;
    if (key === loadedIdleKey) return;

    if (currentState.expr === "neutral") {
      const neutralPath = `neutral_to_speaking_ah__${currentState.pose}`;
      fetchTimeline(neutralPath)
        .then((tl) => {
          if (tl.frames.length > 0) {
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

    // For most expressions, use the last frame of the neutral_to_expr transition
    const expressionIdleMap: Record<string, string> = {
      "speaking_ah": "neutral_to_speaking_ah",
      "happy_soft": "neutral_to_happy_soft",
      "happy_big": "happy_soft_to_happy_big",
      "surprised_ah": "speaking_ah_to_surprised",
      "speaking_ee": "neutral_to_speaking_ee",
      "speaking_uw": "neutral_to_speaking_uw",
      "oh_round": "neutral_to_oh_round",
      "concerned": "neutral_to_concerned",
      "blink_closed": "neutral_to_blink",
    };

    const transitionPath = expressionIdleMap[currentState.expr];
    if (transitionPath) {
      const fullPath = `${transitionPath}__${currentState.pose}`;
      fetchTimeline(fullPath)
        .then((tl) => {
          if (tl.frames.length > 0) {
            const lastFrame = tl.frames[tl.frames.length - 1];
            const url = `${API_BASE}/frames/${tl.path_id}/${lastFrame.file}`;
            setIdleFrame(url);
            setLoadedIdleKey(key);
          }
        })
        .catch((err) => {
          console.error(`Failed to load idle frame for ${currentState.expr}:`, err);
          setLoadedIdleKey(key);
        });
    }
  }, [currentState, loadedIdleKey]);

  // --- Initialize MediaPipe Face Mesh ---
  useEffect(() => {
    let faceMesh: FaceMesh | null = null;
    let camera: Camera | null = null;
    
    const initializeMediaPipe = async () => {
      try {
        faceMesh = new FaceMesh({
          locateFile: (file) => {
            return `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`;
          },
        });
      } catch (err) {
        console.error("[MediaPipe] Initialization error:", err);
        setDebugInfo("MediaPipe failed to initialize - refresh page");
        return;
      }

    faceMesh.setOptions({
      maxNumFaces: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.5,
      minTrackingConfidence: 0.5,
    });

    faceMesh.onResults((results: Results) => {
      const detected = results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0;
      setFaceDetected(detected);

      if (!detected) {
        setDebugInfo("No face detected - move into frame");
        return;
      }

      const landmarks = results.multiFaceLandmarks[0];
      const { pitch, yaw, roll } = calculateHeadPose(landmarks);

      // Auto-calibrate on first detection
      if (!baselineRef.current) {
        baselineRef.current = { pitch, yaw, roll };
        console.log("[MediaPipe] Auto-calibrated:", { pitch, yaw, roll });
      }

      const mouthOpen = calculateMouthOpen(landmarks);
      const mouthWide = calculateMouthWide(landmarks);
      const newTarget = mapFaceToState(results, currentStateRef.current, baselineRef.current);

      // Debug info
      let debugStr = `Face: ${detected ? "✓" : "✗"} | `;
      debugStr += `Yaw: ${yaw.toFixed(1)}° Pitch: ${pitch.toFixed(1)}° Roll: ${roll.toFixed(1)}°\n`;
      debugStr += `Mouth Open: ${mouthOpen.toFixed(3)} | Mouth Wide: ${mouthWide.toFixed(3)}`;

      if (baselineRef.current) {
        const normalizeDelta = (angle: number) => {
          let delta = angle;
          while (delta > 180) delta -= 360;
          while (delta < -180) delta += 360;
          return delta;
        };
        const relPitch = normalizeDelta(pitch - baselineRef.current.pitch);
        const relYaw = normalizeDelta(yaw - baselineRef.current.yaw);
        const relRoll = normalizeDelta(roll - baselineRef.current.roll);
        debugStr += `\n📍 Relative: Yaw: ${relYaw.toFixed(1)}° Pitch: ${relPitch.toFixed(1)}° Roll: ${relRoll.toFixed(1)}°`;
        
        // Show adjusted thresholds
        const pitchAdjDown = Math.max(0, relPitch / 10);
        const pitchAdjUp = Math.max(0, -relPitch / 10);
        const pitchAdjTotal = pitchAdjDown + pitchAdjUp;
        const openThresh = Math.max(0.15, 0.70 - (pitchAdjDown * 0.80)); // Balanced
        const smileThresh = 0.40 + (pitchAdjTotal * 0.05); // Increases when tilted up or down
        debugStr += `\n🎯 Thresholds: Open>${openThresh.toFixed(2)} Smile>${smileThresh.toFixed(2)}`;
      }

      setDebugInfo(debugStr);

      // Trigger animation if target changed from what we're currently animating to
      const targetChanged =
        newTarget.expr !== targetStateRef.current.expr ||
        newTarget.pose !== targetStateRef.current.pose;

      if (targetChanged) {
        console.log(
          `[State Change] ${targetStateRef.current.expr}__${targetStateRef.current.pose} → ${newTarget.expr}__${newTarget.pose}`
        );
        setTargetState(newTarget);
        playRouteTo(newTarget);
      }
    });

      faceMeshRef.current = faceMesh;

      // Initialize camera
      if (videoRef.current) {
        camera = new Camera(videoRef.current, {
          onFrame: async () => {
            if (videoRef.current && faceMeshRef.current) {
              await faceMeshRef.current.send({ image: videoRef.current });
            }
          },
          width: 640,
          height: 480,
        });
        camera.start();
        cameraRef.current = camera;
      }
    };

    initializeMediaPipe().catch(err => {
      console.error("[MediaPipe] Failed to start:", err);
    });

    return () => {
      if (cameraRef.current) {
        cameraRef.current.stop();
      }
      if (faceMeshRef.current) {
        faceMeshRef.current.close();
      }
    };
  }, []); // Empty deps - only initialize ONCE, never re-initialize

  // --- Animation playback ---
  const playRouteTo = async (target: State) => {
    // If we're currently animating to a target, route from that target instead of currentState
    // This handles cases like: tilting head (animating) -> open mouth (should route from tilted pose)
    const wasPlaying = isPlayingRef.current;
    const startState = wasPlaying ? targetStateRef.current : currentStateRef.current;
    
    // Stop any current animation
    setIsPlaying(false);
    
    const route = planRoute(startState, target);
    if (!route || route.length === 0) {
      setCurrentState(target);
      return;
    }

    const segments: ActiveSegment[] = [];
    for (const seg of route) {
      try {
        const tl = await fetchTimeline(seg.pathId);
        segments.push({ seg, timeline: tl, direction: seg.direction });
      } catch (err) {
        console.error(`Failed to fetch timeline ${seg.pathId}:`, err);
      }
    }

    if (segments.length === 0) {
      setCurrentState(target);
      return;
    }

    setActiveSegments(segments);
    setSegmentIndex(0);
    setFrameIndex(0);
    setIsPlaying(true);
  };

  useEffect(() => {
    if (!isPlaying || activeSegments.length === 0) return;

    const interval = setInterval(() => {
      setFrameIndex((prev) => {
        // Bounds check to prevent crash
        if (segmentIndex >= activeSegments.length) {
          setIsPlaying(false);
          return 0;
        }

        const currentSeg = activeSegments[segmentIndex];
        if (!currentSeg || !currentSeg.timeline) {
          setIsPlaying(false);
          return 0;
        }

        const maxFrames = currentSeg.timeline.frames.length;
        const next = prev + 1;

        if (next >= maxFrames) {
          // Move to next segment
          if (segmentIndex + 1 < activeSegments.length) {
            setSegmentIndex((s) => s + 1);
            return 0;
          } else {
            // Animation complete
            setIsPlaying(false);
            setCurrentState(targetState);
            return 0;
          }
        }

        return next;
      });
    }, 1000 / FPS);

    return () => clearInterval(interval);
  }, [isPlaying, activeSegments, segmentIndex, targetState]);

  const currentTimeline = activeSegments[segmentIndex]?.timeline;
  const currentFrame = currentTimeline?.frames[frameIndex];

  const currentImageUrl = useMemo(() => {
    if (isPlaying && currentTimeline && currentFrame) {
      return `${API_BASE}/frames/${currentTimeline.path_id}/${currentFrame.file}`;
    }
    return idleFrame;
  }, [isPlaying, currentTimeline, currentFrame, idleFrame]);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center p-6 gap-4">
      <h1 className="text-2xl font-bold mb-2">
        Face-Tracked Character (MediaPipe)
      </h1>

      {/* Hidden video element for camera */}
      <video
        ref={videoRef}
        style={{ display: "none" }}
        autoPlay
        playsInline
      />

      {/* Hidden canvas for MediaPipe */}
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {/* Status */}
      <div className="flex gap-4 text-sm">
        <div className={faceDetected ? "text-green-400" : "text-red-400"}>
          ● {faceDetected ? "Face Detected" : "No Face"}
        </div>
        <div className="text-slate-400">
          State: {currentState.expr}__{currentState.pose}
        </div>
        {isPlaying && (
          <div className="text-blue-400">
            ▶ Playing ({segmentIndex + 1}/{activeSegments.length})
          </div>
        )}
      </div>

      {/* Debug info */}
      <div className="w-full max-w-3xl bg-slate-800 rounded p-3 text-xs font-mono text-slate-300 whitespace-pre-line">
        <div className="font-semibold mb-1 text-slate-400">Tracking Data:</div>
        <div>{debugInfo || "Initializing MediaPipe..."}</div>
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
          Reset to Neutral
        </button>

        <button
          onClick={() => {
            baselineRef.current = null;
            console.log("[Recalibrate] Baseline cleared");
          }}
          className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded font-semibold"
        >
          Recalibrate
        </button>
      </div>

      {/* Character preview */}
      <div className="flex flex-col items-center gap-2">
        <div
          className="bg-slate-800 rounded-xl flex items-center justify-center overflow-hidden"
          style={{
            width: "320px",
            height: "480px",
            position: "relative",
          }}
        >
          {currentImageUrl ? (
            <img
              src={currentImageUrl}
              alt="current"
              style={{
                width: "320px",
                height: "480px",
                objectFit: "contain",
                display: "block",
              }}
            />
          ) : (
            <span className="text-slate-500 text-sm">Loading...</span>
          )}
        </div>
      </div>

      {/* Instructions */}
      <div className="w-full max-w-3xl bg-slate-800 rounded p-4 text-sm text-slate-300">
        <h3 className="font-semibold mb-2 text-slate-100">MediaPipe Face Tracking:</h3>
        <ul className="list-disc list-inside space-y-1">
          <li>✅ Runs directly in browser (no Python server needed!)</li>
          <li>✅ Auto-calibrates on first frame</li>
          <li>✅ Turn/tilt left/right (&gt;12°) to trigger animations</li>
          <li>✅ Nod up/down (&gt;8°) to trigger animations</li>
          <li>✅ <strong>Open mouth to speak</strong> - ACTUALLY WORKS! 🎉</li>
          <li>Use "Recalibrate" if you change position</li>
        </ul>
        <p className="mt-2 text-xs text-slate-400">
          💡 MediaPipe provides 468 facial landmarks with reliable mouth tracking!
        </p>
      </div>
    </div>
  );
};

