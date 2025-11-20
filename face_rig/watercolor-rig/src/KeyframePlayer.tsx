import React, { useState, useEffect, useRef } from "react";
import { planRoute } from "./transitionGraph.ts";
import { fetchTimeline } from "./api.ts";
import type { ExpressionId, PoseId, State, Segment } from "./transitionGraph.ts";

const API_BASE = "http://localhost:8000";

interface AnimationKeyframe {
  time_ms: number;
  target_expr: ExpressionId;
  target_pose: PoseId;
  transition_duration_ms: number;
}

interface AnimationTimeline {
  id: string;
  keyframes: AnimationKeyframe[];
}

interface ActiveSegment {
  seg: Segment;
  timeline: any;
  direction: "forward" | "reverse";
}

const DEFAULT_TIMELINE = `{
  "id": "greeting_123",
  "keyframes": [
    {
      "time_ms": 0,
      "target_expr": "neutral",
      "target_pose": "center",
      "transition_duration_ms": 0
    },
    {
      "time_ms": 500,
      "target_expr": "happy_soft",
      "target_pose": "center",
      "transition_duration_ms": 300
    },
    {
      "time_ms": 2000,
      "target_expr": "speaking_ah",
      "target_pose": "tilt_right_small",
      "transition_duration_ms": 400
    },
    {
      "time_ms": 5000,
      "target_expr": "neutral",
      "target_pose": "center",
      "transition_duration_ms": 500
    }
  ]
}`;

export const KeyframePlayer: React.FC = () => {
  const [timelineJson, setTimelineJson] = useState(DEFAULT_TIMELINE);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  
  const [currentState, setCurrentState] = useState<State>({
    expr: "neutral",
    pose: "center",
  });
  
  const [activeSegments, setActiveSegments] = useState<ActiveSegment[]>([]);
  const [segmentIndex, setSegmentIndex] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  
  const [idleFrame, setIdleFrame] = useState<string | null>(null);
  const [loadedIdleKey, setLoadedIdleKey] = useState<string>("");
  
  // Double-buffer for crossfade
  const [displayImageA, setDisplayImageA] = useState<string | null>(null);
  const [displayImageB, setDisplayImageB] = useState<string | null>(null);
  const [showA, setShowA] = useState(true);
  
  const startTimeRef = useRef<number>(0);
  const timelineRef = useRef<AnimationTimeline | null>(null);
  const nextKeyframeIndexRef = useRef(0);
  const lastDisplayedUrl = useRef<string | null>(null);
  
  const FPS = 24;

  // Parse and validate timeline
  const parseTimeline = (json: string): AnimationTimeline | null => {
    try {
      const parsed = JSON.parse(json);
      if (!parsed.keyframes || !Array.isArray(parsed.keyframes)) {
        setError("Timeline must have 'keyframes' array");
        return null;
      }
      setError(null);
      return parsed;
    } catch (e) {
      setError(`Invalid JSON: ${e}`);
      return null;
    }
  };

  // Execute a transition to a target state
  const executeTransition = async (target: State) => {
    const route = planRoute(currentState, target);
    if (!route || route.length === 0) {
      setCurrentState(target);
      setIsAnimating(false);
      return;
    }

    const segments: ActiveSegment[] = [];
    for (const seg of route) {
      try {
        const tl = await fetchTimeline(seg.pathId);
        segments.push({ seg, timeline: tl, direction: seg.direction });
        console.log(`[Transition] Loaded segment: ${seg.pathId} (${tl.frames.length} frames)`);
      } catch (err) {
        console.error(`Failed to fetch timeline ${seg.pathId}:`, err);
      }
    }

    if (segments.length === 0) {
      console.log("[Transition] No segments to play, jumping to target state");
      setCurrentState(target);
      setIsAnimating(false);
      return;
    }

    console.log(`[Transition] Starting animation with ${segments.length} segment(s)`);
    setActiveSegments(segments);
    setSegmentIndex(0);
    setFrameIndex(0);
    setIsAnimating(true);
  };

  // Animation playback loop (plays through activeSegments)
  useEffect(() => {
    if (!isAnimating || activeSegments.length === 0) return;

    const interval = setInterval(() => {
      setFrameIndex((prev) => {
        if (segmentIndex >= activeSegments.length) {
          setIsAnimating(false);
          return 0;
        }

        const currentSeg = activeSegments[segmentIndex];
        if (!currentSeg || !currentSeg.timeline) {
          setIsAnimating(false);
          return 0;
        }

        const maxFrames = currentSeg.timeline.frames.length;
        const next = prev + 1;

        if (next >= maxFrames) {
          // Move to next segment
          if (segmentIndex + 1 < activeSegments.length) {
            console.log(`[Animation] Segment ${segmentIndex} complete, moving to segment ${segmentIndex + 1}`);
            setSegmentIndex((s) => s + 1);
            return 0;
          } else {
            // Animation complete
            console.log(`[Animation] All segments complete`);
            setIsAnimating(false);
            return 0;
          }
        }

        return next;
      });
    }, 1000 / FPS);

    return () => clearInterval(interval);
  }, [isAnimating, activeSegments, segmentIndex]);

  // When animation completes, update current state
  useEffect(() => {
    if (!isAnimating && activeSegments.length > 0) {
      // Extract target state from the last segment
      const lastSeg = activeSegments[activeSegments.length - 1];
      if (lastSeg && lastSeg.seg) {
        console.log(`[State] Animation complete, setting state to ${lastSeg.seg.to.expr}__${lastSeg.seg.to.pose}`);
        setCurrentState(lastSeg.seg.to);
      }
    }
  }, [isAnimating, activeSegments]);

  // Load idle frame for current state when not animating
  useEffect(() => {
    if (isAnimating) return; // Don't load idle frame while animating

    const key = `${currentState.expr}__${currentState.pose}`;
    if (key === loadedIdleKey) return; // Already loaded

    console.log(`[Idle] Loading idle frame for ${key}`);

    // For neutral, use first frame of neutral_to_speaking_ah
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
  }, [currentState, loadedIdleKey, isAnimating]);

  // Timeline playback loop (triggers keyframes at the right time)
  useEffect(() => {
    if (!isPlaying) return;

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      setCurrentTime(elapsed);

      // Check if we should trigger the next keyframe
      const timeline = timelineRef.current;
      if (!timeline) return;

      const nextIdx = nextKeyframeIndexRef.current;
      if (nextIdx >= timeline.keyframes.length) {
        // Timeline complete
        setIsPlaying(false);
        return;
      }

      const nextKeyframe = timeline.keyframes[nextIdx];
      if (elapsed >= nextKeyframe.time_ms) {
        console.log(`[Keyframe ${nextIdx}] Triggering at ${elapsed}ms:`, nextKeyframe);
        
        const target: State = {
          expr: nextKeyframe.target_expr,
          pose: nextKeyframe.target_pose,
        };
        
        executeTransition(target);
        nextKeyframeIndexRef.current = nextIdx + 1;
      }
    }, 16); // ~60fps for timing precision

    return () => clearInterval(interval);
  }, [isPlaying, currentState]);

  const handlePlay = () => {
    const timeline = parseTimeline(timelineJson);
    if (!timeline) return;

    console.log("[Timeline] Starting playback:", timeline);
    timelineRef.current = timeline;
    nextKeyframeIndexRef.current = 0;
    startTimeRef.current = Date.now();
    setCurrentTime(0);
    setIsPlaying(true);
  };

  const handleStop = () => {
    setIsPlaying(false);
    setIsAnimating(false);
    setCurrentTime(0);
    nextKeyframeIndexRef.current = 0;
    setCurrentState({ expr: "neutral", pose: "center" });
    setLoadedIdleKey(""); // Force reload idle frame
  };

  // Get current frame for display
  // If animating, show the current animation frame
  // If not animating, show the idle frame for current state
  const currentTimeline = activeSegments[segmentIndex]?.timeline;
  const currentFrame = currentTimeline?.frames[frameIndex];
  const animatingImageUrl = currentFrame
    ? `${API_BASE}/frames/${activeSegments[segmentIndex].timeline.path_id}/${currentFrame.file}`
    : null;
  
  const currentImageUrl = isAnimating ? animatingImageUrl : idleFrame;

  // Crossfade effect when image changes
  useEffect(() => {
    if (!currentImageUrl) return;
    
    // First image - just set it immediately
    if (!lastDisplayedUrl.current) {
      setDisplayImageA(currentImageUrl);
      setShowA(true);
      lastDisplayedUrl.current = currentImageUrl;
      return;
    }
    
    // Same image - no need to crossfade
    if (currentImageUrl === lastDisplayedUrl.current) return;
    
    // Update the buffer that's currently hidden
    if (showA) {
      setDisplayImageB(currentImageUrl);
    } else {
      setDisplayImageA(currentImageUrl);
    }
    
    // Small delay to ensure image is loaded, then crossfade
    const timer = setTimeout(() => {
      setShowA(!showA);
      lastDisplayedUrl.current = currentImageUrl;
    }, 10);
    
    return () => clearTimeout(timer);
  }, [currentImageUrl, showA]);

  return (
    <div style={{ padding: "20px", maxWidth: "1200px", margin: "0 auto" }}>
      <h1>🎬 Keyframe Animation Player</h1>
      
      <div style={{ display: "flex", gap: "20px", marginTop: "20px" }}>
        {/* Left: Timeline Input */}
        <div style={{ flex: 1 }}>
          <h2>Timeline JSON</h2>
          <textarea
            value={timelineJson}
            onChange={(e) => setTimelineJson(e.target.value)}
            style={{
              width: "100%",
              height: "400px",
              fontFamily: "monospace",
              fontSize: "12px",
              padding: "10px",
              border: "1px solid #ccc",
              borderRadius: "4px",
            }}
          />
          
          {error && (
            <div style={{ color: "red", marginTop: "10px", fontSize: "14px" }}>
              ❌ {error}
            </div>
          )}
          
          <div style={{ marginTop: "10px", display: "flex", gap: "10px" }}>
            <button
              onClick={handlePlay}
              disabled={isPlaying}
              style={{
                padding: "10px 20px",
                fontSize: "16px",
                backgroundColor: isPlaying ? "#ccc" : "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: isPlaying ? "not-allowed" : "pointer",
              }}
            >
              ▶️ Play
            </button>
            
            <button
              onClick={handleStop}
              disabled={!isPlaying && !isAnimating}
              style={{
                padding: "10px 20px",
                fontSize: "16px",
                backgroundColor: (!isPlaying && !isAnimating) ? "#ccc" : "#f44336",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: (!isPlaying && !isAnimating) ? "not-allowed" : "pointer",
              }}
            >
              ⏹️ Stop
            </button>
          </div>
          
          <div style={{ marginTop: "20px", fontSize: "14px" }}>
            <div>⏱️ <strong>Time:</strong> {(currentTime / 1000).toFixed(2)}s</div>
            <div>🎭 <strong>State:</strong> {currentState.expr}__{currentState.pose}</div>
            <div>🎬 <strong>Status:</strong> {isAnimating ? "Animating" : "Holding"}</div>
          </div>
        </div>
        
        {/* Right: Character Display */}
        <div style={{ flex: 1 }}>
          <h2>Character</h2>
          <div
            style={{
              width: "100%",
              height: "600px",
              border: "2px solid #333",
              borderRadius: "8px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: "#f9f9f9",
              overflow: "hidden",
              position: "relative",
            }}
          >
            {displayImageA || displayImageB ? (
              <>
                <img
                  src={displayImageA || ""}
                  alt="character layer A"
                  style={{
                    position: "absolute",
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                    opacity: showA ? 1 : 0,
                    transition: "opacity 0.08s ease-in-out",
                  }}
                />
                <img
                  src={displayImageB || ""}
                  alt="character layer B"
                  style={{
                    position: "absolute",
                    maxWidth: "100%",
                    maxHeight: "100%",
                    objectFit: "contain",
                    opacity: showA ? 0 : 1,
                    transition: "opacity 0.08s ease-in-out",
                  }}
                />
              </>
            ) : (
              <div style={{ color: "#999", fontSize: "18px" }}>
                Press Play to start
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

