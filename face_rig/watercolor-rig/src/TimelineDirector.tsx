import React, { useState, useRef, useEffect, useMemo } from "react";
import { planRoute, type State, type ExpressionId, type PoseId, type Segment } from "./transitionGraph.ts";
import { fetchTimeline, type Timeline } from "./api.ts";

const API_BASE = "http://localhost:8000";

// Timeline data structures
interface PoseKeyframe {
  id: string;
  time_ms: number;
  target_pose: PoseId;
  transition_duration_ms: number;
}

interface ExpressionKeyframe {
  id: string;
  time_ms: number;
  target_expr: ExpressionId;
  transition_duration_ms: number;
}

interface PhonemeKeyframe {
  id: string;
  time_ms: number;
  target_expr: ExpressionId;
  transition_duration_ms: number;
  phoneme: string;
}

interface CombinedKeyframe {
  time_ms: number;
  target_expr: ExpressionId;
  target_pose: PoseId;
  transition_duration_ms: number;
}

export const TimelineDirector: React.FC = () => {
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioDuration, setAudioDuration] = useState<number>(5000); // Default 5s
  
  const [poseTimeline, setPoseTimeline] = useState<PoseKeyframe[]>([
    { id: "p0", time_ms: 0, target_pose: "center", transition_duration_ms: 0 }
  ]);
  
  const [expressionTimeline, setExpressionTimeline] = useState<ExpressionKeyframe[]>([
    { id: "e0", time_ms: 0, target_expr: "neutral", transition_duration_ms: 0 }
  ]);
  
  const [phonemeTimeline, setPhonemeTimeline] = useState<PhonemeKeyframe[]>([]);
  
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [selectedKeyframe, setSelectedKeyframe] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<string>("");
  const [isGeneratingEmotions, setIsGeneratingEmotions] = useState(false);
  const [isGeneratingAlignment, setIsGeneratingAlignment] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportFormat, setExportFormat] = useState<"mp4" | "webm">("mp4");
  const [exportFps, setExportFps] = useState(24);
  
  // Animation state
  const [currentState, setCurrentState] = useState<State>({ expr: "neutral", pose: "center" });
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  
  // Keep ref in sync with state
  useEffect(() => {
    currentStateRef.current = currentState;
  }, [currentState]);
  
  // Animation playback state (for crossfade transitions)
  const [activeSegments, setActiveSegments] = useState<Array<{ seg: Segment, timeline: Timeline, direction: "forward" | "reverse" }>>([]);
  const [segmentIndex, setSegmentIndex] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);
  const [bufferA, setBufferA] = useState<string>("");
  const [bufferB, setBufferB] = useState<string>("");
  const [activeBuffer, setActiveBuffer] = useState<"A" | "B">("A");
  const animationIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  const audioRef = useRef<HTMLAudioElement>(null);
  const animationFrameRef = useRef<number>();
  const lastUpdateTime = useRef<number>(0);
  const transcriptFileInputRef = useRef<HTMLInputElement>(null);
  const currentStateRef = useRef<State>({ expr: "neutral", pose: "center" });
  
  // Available options
  const POSES: PoseId[] = ["center", "tilt_left_small", "tilt_right_small", "nod_down_small", "nod_up_small"];
  const EXPRESSIONS: ExpressionId[] = [
    "neutral", "happy_soft", "happy_big", "speaking_ah", "speaking_ee", 
    "speaking_uw", "oh_round", "concerned", "surprised_ah"
  ];
  
  // Handle audio file upload
  const handleAudioUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Stop and clean up old audio first
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setIsPlaying(false);
    
    // Revoke old URL to prevent memory leaks
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }
    
    setAudioFile(file);
    const url = URL.createObjectURL(file);
    setAudioUrl(url);
  };
  
  // Use effect to get duration from the main audio element (not a temporary one)
  useEffect(() => {
    if (audioRef.current && audioUrl) {
      const handleLoadedMetadata = () => {
        if (audioRef.current) {
          setAudioDuration(audioRef.current.duration * 1000);
        }
      };
      
      audioRef.current.addEventListener('loadedmetadata', handleLoadedMetadata);
      
      return () => {
        if (audioRef.current) {
          audioRef.current.removeEventListener('loadedmetadata', handleLoadedMetadata);
        }
      };
    }
  }, [audioUrl]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Stop audio
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      }
      // Cancel any pending animation frames
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      // Cleanup animation interval
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
      }
      // Revoke audio URL
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, []);
  
  // Parse TextGrid file
  const parseTextGrid = (content: string): PhonemeKeyframe[] => {
    // Find phones tier
    const phonesTierMatch = content.match(/name = "phones"[\s\S]*?intervals: size = (\d+)([\s\S]*?)(?=item \[|$)/);
    if (!phonesTierMatch) {
      throw new Error("Could not find 'phones' tier in TextGrid");
    }
    
    const tierContent = phonesTierMatch[2];
    const intervalRegex = /intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"/g;
    
    const phonemes: Array<{ start: number; end: number; text: string }> = [];
    let match;
    while ((match = intervalRegex.exec(tierContent)) !== null) {
      const text = match[3].trim();
      if (text) {
        phonemes.push({
          start: parseFloat(match[1]) * 1000, // Convert to ms
          end: parseFloat(match[2]) * 1000,
          text
        });
      }
    }
    
    // Map phonemes to expressions with conjoining
    const PHONEME_TO_EXPR: Record<string, ExpressionId> = {
      // AH sounds
      "AH0": "speaking_ah", "AH1": "speaking_ah", "AH2": "speaking_ah",
      "AA0": "speaking_ah", "AA1": "speaking_ah", "AA2": "speaking_ah",
      "AO0": "speaking_ah", "AO1": "speaking_ah", "AO2": "speaking_ah",
      // EE sounds
      "IY0": "speaking_ee", "IY1": "speaking_ee", "IY2": "speaking_ee",
      "IH0": "speaking_ee", "IH1": "speaking_ee", "IH2": "speaking_ee",
      "EH0": "speaking_ee", "EH1": "speaking_ee", "EH2": "speaking_ee",
      "EY0": "speaking_ee", "EY1": "speaking_ee", "EY2": "speaking_ee",
      "AE0": "speaking_ee", "AE1": "speaking_ee", "AE2": "speaking_ee",
      "AY0": "speaking_ee", "AY1": "speaking_ee", "AY2": "speaking_ee",
      // OO/UW sounds
      "UW0": "speaking_uw", "UW1": "speaking_uw", "UW2": "speaking_uw",
      "UH0": "speaking_uw", "UH1": "speaking_uw", "UH2": "speaking_uw",
      "OW0": "oh_round", "OW1": "oh_round", "OW2": "oh_round",
      "OY0": "oh_round", "OY1": "oh_round", "OY2": "oh_round",
      "AW0": "oh_round", "AW1": "oh_round", "AW2": "oh_round",
      // ER sounds
      "ER0": "speaking_ah", "ER1": "speaking_ah", "ER2": "speaking_ah",
    };
    
    const keyframes: PhonemeKeyframe[] = [];
    let lastExpr: ExpressionId = "neutral";
    let lastKeyframeArrivalMs = -175; // Allow first keyframe immediately
    let i = 0;
    const TRANSITION_MS = 500; // Long smooth transitions for lip-sync
    const COOLDOWN_MS = 175; // Minimum time between transitions (175ms)
    
    while (i < phonemes.length) {
      const phoneme = phonemes[i];
      const expr = PHONEME_TO_EXPR[phoneme.text] || "neutral";
      
      // If consonant, look ahead for vowel
      if (expr === "neutral" && i + 1 < phonemes.length) {
        const nextPhoneme = phonemes[i + 1];
        const nextExpr = PHONEME_TO_EXPR[nextPhoneme.text];
        
        if (nextExpr && nextExpr !== "neutral") {
          // Conjoin consonant with vowel
          if (nextExpr !== lastExpr) {
            // Check cooldown: has enough time passed since last keyframe?
            const timeSinceLastArrival = phoneme.start - lastKeyframeArrivalMs;
            if (timeSinceLastArrival < COOLDOWN_MS) {
              // Skip this transition - too soon after last one
              i += 2;
              continue;
            }
            
            // Use fixed transition duration
            const adaptiveDuration = TRANSITION_MS;
            
            // Start transition AT phoneme start for audio sync
            keyframes.push({
              id: `ph${keyframes.length}`,
              time_ms: Math.round(phoneme.start),
              target_expr: nextExpr,
              transition_duration_ms: adaptiveDuration,
              phoneme: `${phoneme.text}→${nextPhoneme.text}`
            });
            lastExpr = nextExpr;
            lastKeyframeArrivalMs = phoneme.start; // Update cooldown timer
          }
          i += 2; // Skip vowel
          continue;
        }
      }
      
      // Vowel or standalone consonant
      if (expr !== lastExpr) {
        // Check cooldown: has enough time passed since last keyframe?
        const timeSinceLastArrival = phoneme.start - lastKeyframeArrivalMs;
        if (timeSinceLastArrival < COOLDOWN_MS) {
          // Skip this transition - too soon after last one
          i++;
          continue;
        }
        
        // Use fixed transition duration
        const adaptiveDuration = TRANSITION_MS;
        
        // Start transition AT phoneme start for audio sync
        keyframes.push({
          id: `ph${keyframes.length}`,
          time_ms: Math.round(phoneme.start),
          target_expr: expr,
          transition_duration_ms: adaptiveDuration,
          phoneme: phoneme.text
        });
        lastExpr = expr;
        lastKeyframeArrivalMs = phoneme.start; // Update cooldown timer
      }
      
      i++;
    }
    
    // Add final keyframe to return to neutral (if not already neutral)
    if (phonemes.length > 0 && lastExpr !== "neutral") {
      const finalTimeMs = phonemes[phonemes.length - 1].end;
      // Start transition at end of speech
      keyframes.push({
        id: `ph${keyframes.length}`,
        time_ms: Math.round(finalTimeMs),
        target_expr: "neutral",
        transition_duration_ms: 300,
        phoneme: ""
      });
    }
    
    return keyframes;
  };
  
  // Load phoneme timeline from JSON or TextGrid
  const handleLoadPhonemeTimeline = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        
        // Detect file type
        if (file.name.endsWith('.TextGrid') || content.includes('ooTextFile')) {
          // Parse TextGrid
          const keyframes = parseTextGrid(content);
          setPhonemeTimeline(keyframes);
          console.log(`Loaded ${keyframes.length} phoneme keyframes from TextGrid`);
        } else {
          // Parse JSON
          const data = JSON.parse(content);
          const keyframes: PhonemeKeyframe[] = data.keyframes.map((kf: any, i: number) => ({
            id: `ph${i}`,
            time_ms: kf.time_ms,
            target_expr: kf.target_expr,
            transition_duration_ms: kf.transition_duration_ms,
            phoneme: kf.phoneme || "",
          }));
          setPhonemeTimeline(keyframes);
          console.log(`Loaded ${keyframes.length} phoneme keyframes from JSON`);
        }
      } catch (err) {
        alert(`Failed to load timeline: ${err}`);
        console.error(err);
      }
    };
    reader.readAsText(file);
  };
  
  // Add pose keyframe
  const addPoseKeyframe = (pose: PoseId) => {
    const newKf: PoseKeyframe = {
      id: `p${Date.now()}`,
      time_ms: Math.round(currentTime),
      target_pose: pose,
      transition_duration_ms: 300
    };
    setPoseTimeline([...poseTimeline, newKf].sort((a, b) => a.time_ms - b.time_ms));
    console.log(`Added pose keyframe: ${pose} at ${newKf.time_ms}ms`);
  };
  
  // Add expression keyframe
  const addExpressionKeyframe = (expr: ExpressionId) => {
    const newKf: ExpressionKeyframe = {
      id: `e${Date.now()}`,
      time_ms: Math.round(currentTime),
      target_expr: expr,
      transition_duration_ms: 300
    };
    setExpressionTimeline([...expressionTimeline, newKf].sort((a, b) => a.time_ms - b.time_ms));
    console.log(`Added expression keyframe: ${expr} at ${newKf.time_ms}ms`);
  };
  
  // Delete keyframe
  const deleteKeyframe = (id: string) => {
    setPoseTimeline(poseTimeline.filter(kf => kf.id !== id));
    setExpressionTimeline(expressionTimeline.filter(kf => kf.id !== id));
    setPhonemeTimeline(phonemeTimeline.filter(kf => kf.id !== id));
    setSelectedKeyframe(null);
  };
  
  // Handle transcript upload
  const handleTranscriptUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = (event.target?.result as string).trim();
      setTranscript(text);
      console.log(`Loaded transcript (${file.name}): ${text.length} characters`);
    };
    reader.readAsText(file);
  };
  
  // Generate phoneme alignment from audio + transcript
  const generateAlignment = async () => {
    if (!audioFile || !transcript) {
      alert("Please upload both audio and transcript first");
      return;
    }
    
    setIsGeneratingAlignment(true);
    
    try {
      const formData = new FormData();
      formData.append("audio", audioFile);
      formData.append("transcript", transcript);
      
      console.log("🎵 Generating alignment with MFA...");
      
      const response = await fetch(`${API_BASE}/generate-alignment`, {
        method: "POST",
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Alignment failed: ${response.status} ${errorText}`);
      }
      
      const timelineData = await response.json();
      
      // Load the phoneme timeline
      const keyframes: PhonemeKeyframe[] = timelineData.keyframes.map((kf: any, i: number) => ({
        id: `ph${i}`,
        time_ms: kf.time_ms,
        target_expr: kf.target_expr,
        transition_duration_ms: kf.transition_duration_ms,
        phoneme: kf.phoneme || "",
      }));
      
      setPhonemeTimeline(keyframes);
      console.log(`✅ Loaded ${keyframes.length} phoneme keyframes from alignment`);
      alert(`Successfully generated ${keyframes.length} phoneme keyframes!`);
      
    } catch (err) {
      console.error("Failed to generate alignment:", err);
      alert(`Failed to generate alignment: ${err}`);
    } finally {
      setIsGeneratingAlignment(false);
    }
  };
  
  // Generate emotion keyframes using OpenAI (via backend)
  const generateEmotions = async () => {
    if (!transcript || phonemeTimeline.length === 0) {
      alert("Please upload both a transcript and load a TextGrid/phoneme timeline first");
      return;
    }
    
    setIsGeneratingEmotions(true);
    
    try {
      const response = await fetch(`${API_BASE}/generate-emotions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          transcript: transcript,
          phoneme_timeline: phonemeTimeline.map(kf => ({
            time_ms: kf.time_ms,
            phoneme: kf.phoneme,
            target_expr: kf.target_expr,
            transition_duration_ms: kf.transition_duration_ms
          })),
          total_duration_ms: phonemeTimeline[phonemeTimeline.length - 1]?.time_ms || 3000
        })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Backend error: ${response.status} ${errorText}`);
      }
      
      const data = await response.json();
      const emotionKeyframes = data.keyframes;
      
      // Add keyframes to expression timeline
      const newKeyframes: ExpressionKeyframe[] = emotionKeyframes.map((kf: any, i: number) => ({
        id: `ai_emotion_${Date.now()}_${i}`,
        time_ms: kf.time_ms,
        target_expr: kf.target_expr as ExpressionId,
        transition_duration_ms: 300
      }));
      
      setExpressionTimeline([...expressionTimeline, ...newKeyframes].sort((a, b) => a.time_ms - b.time_ms));
      
      console.log(`✨ Added ${newKeyframes.length} AI-generated emotion keyframes:`, emotionKeyframes);
      alert(`Added ${newKeyframes.length} emotion keyframes to timeline!`);
      
    } catch (err) {
      console.error("Failed to generate emotions:", err);
      alert(`Failed to generate emotions: ${err}`);
    } finally {
      setIsGeneratingEmotions(false);
    }
  };
  
  // Combine timelines
  const combinedTimeline = useMemo((): CombinedKeyframe[] => {
    const combined: CombinedKeyframe[] = [];
    
    // Get all unique times
    const allTimes = new Set<number>();
    poseTimeline.forEach(kf => allTimes.add(kf.time_ms));
    expressionTimeline.forEach(kf => allTimes.add(kf.time_ms));
    phonemeTimeline.forEach(kf => allTimes.add(kf.time_ms));
    
    const sortedTimes = Array.from(allTimes).sort((a, b) => a - b);
    
    let lastPose: PoseId = "center";
    let lastExpr: ExpressionId = "neutral";
    
    for (const time of sortedTimes) {
      // Check for pose change
      const poseKf = poseTimeline.find(kf => kf.time_ms === time);
      if (poseKf) {
        lastPose = poseKf.target_pose;
      }
      
      // Check for expression change (phoneme takes precedence)
      const phonemeKf = phonemeTimeline.find(kf => kf.time_ms === time);
      const exprKf = expressionTimeline.find(kf => kf.time_ms === time);
      
      if (phonemeKf) {
        lastExpr = phonemeKf.target_expr;
        combined.push({
          time_ms: time,
          target_expr: lastExpr,
          target_pose: lastPose,
          transition_duration_ms: phonemeKf.transition_duration_ms
        });
      } else if (exprKf) {
        lastExpr = exprKf.target_expr;
        combined.push({
          time_ms: time,
          target_expr: lastExpr,
          target_pose: lastPose,
          transition_duration_ms: exprKf.transition_duration_ms
        });
      } else if (poseKf) {
        // Pose-only change
        combined.push({
          time_ms: time,
          target_expr: lastExpr,
          target_pose: lastPose,
          transition_duration_ms: poseKf.transition_duration_ms
        });
      }
    }
    
    return combined;
  }, [poseTimeline, expressionTimeline, phonemeTimeline]);
  
  // Get current state from timeline
  const getCurrentStateFromTimeline = (time: number): State => {
    let expr: ExpressionId = "neutral";
    let pose: PoseId = "center";
    
    // Find active pose
    for (let i = poseTimeline.length - 1; i >= 0; i--) {
      if (poseTimeline[i].time_ms <= time) {
        pose = poseTimeline[i].target_pose;
        break;
      }
    }
    
    // Find active expression (phoneme takes precedence, but only while active)
    let phonemeExpr: ExpressionId | null = null;
    let phonemeTime = -Infinity;
    for (let i = phonemeTimeline.length - 1; i >= 0; i--) {
      if (phonemeTimeline[i].time_ms <= time) {
        const transitionEnd = phonemeTimeline[i].time_ms + phonemeTimeline[i].transition_duration_ms;
        // Only use phoneme if we're still within its transition duration
        if (time < transitionEnd) {
          phonemeExpr = phonemeTimeline[i].target_expr;
          phonemeTime = phonemeTimeline[i].time_ms;
        }
        break;
      }
    }
    
    // Find most recent expression keyframe
    let exprExpr: ExpressionId | null = null;
    let exprTime = -Infinity;
    for (let i = expressionTimeline.length - 1; i >= 0; i--) {
      if (expressionTimeline[i].time_ms <= time) {
        exprExpr = expressionTimeline[i].target_expr;
        exprTime = expressionTimeline[i].time_ms;
        break;
      }
    }
    
    // Use whichever is more recent (phoneme takes precedence when times are equal)
    if (phonemeExpr !== null && phonemeTime >= exprTime) {
      expr = phonemeExpr;
    } else if (exprExpr !== null) {
      expr = exprExpr;
    }
    
    return { expr, pose };
  };
  
  // Execute a transition to a target state
  const executeTransition = async (target: State) => {
    // Check if we're already at or transitioning to this state
    if (currentState.expr === target.expr && currentState.pose === target.pose) {
      return;
    }
    
    console.log(`🎭 ${currentState.expr}__${currentState.pose} → ${target.expr}__${target.pose}`);
    
    const route = planRoute(currentState, target);
    if (!route || route.length === 0) {
      setCurrentState(target);
      setIsAnimating(false);
      return;
    }

    const segments: Array<{ seg: Segment, timeline: Timeline, direction: "forward" | "reverse" }> = [];
    for (const seg of route) {
      try {
        const tl = await fetchTimeline(seg.pathId);
        segments.push({ seg, timeline: tl, direction: seg.direction });
      } catch (err) {
        console.error(`❌ Failed to fetch ${seg.pathId}:`, err);
      }
    }

    if (segments.length === 0) {
      setCurrentState(target);
      setIsAnimating(false);
      return;
    }

    setActiveSegments(segments);
    setSegmentIndex(0);
    setFrameIndex(0);
    setIsAnimating(true);
    setCurrentState(target); // Update state immediately for logic purposes
  };
  
  // Animation frame playback (plays through activeSegments with crossfade)
  useEffect(() => {
    if (!isAnimating || activeSegments.length === 0) {
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
        animationIntervalRef.current = null;
      }
      return;
    }

    const FPS = 24;
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
            setSegmentIndex((s) => s + 1);
            return 0;
          } else {
            // Animation complete
            setIsAnimating(false);
            return 0;
          }
        }

        return next;
      });
    }, 1000 / FPS);

    animationIntervalRef.current = interval;

    return () => {
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
      }
    };
  }, [isAnimating, segmentIndex, activeSegments]);

  // Update displayed frame with crossfade
  useEffect(() => {
    if (!isAnimating || activeSegments.length === 0) return;
    if (segmentIndex >= activeSegments.length) return;

    const currentSeg = activeSegments[segmentIndex];
    if (!currentSeg || !currentSeg.timeline) return;

    const frames = currentSeg.timeline.frames;
    const actualIndex = currentSeg.direction === "reverse" ? frames.length - 1 - frameIndex : frameIndex;
    
    if (actualIndex < 0 || actualIndex >= frames.length) return;

    const frame = frames[actualIndex];
    const url = `${API_BASE}/frames/${currentSeg.timeline.path_id}/${frame.file}`;

    // Crossfade between buffers
    if (activeBuffer === "A") {
      setBufferB(url);
      setActiveBuffer("B");
    } else {
      setBufferA(url);
      setActiveBuffer("A");
    }
  }, [frameIndex, segmentIndex, isAnimating, activeSegments.length]); // Fixed: removed activeBuffer dependency to prevent infinite loop
  
  // Load idle frame for current state (when not animating)
  useEffect(() => {
    if (isAnimating) return;
    
    const state = currentState;
    
    // Load idle frame
    const loadIdleFrame = async () => {
      try {
        if (state.expr === "neutral") {
          const tl = await fetchTimeline(`neutral_to_speaking_ah__${state.pose}`);
          if (tl.frames.length > 0) {
            const url = `${API_BASE}/frames/${tl.path_id}/${tl.frames[0].file}`;
            setCurrentImage(url);
            setBufferA(url);
            setBufferB(url);
          }
        } else {
          // Map expression to timeline
          const exprMap: Record<string, string> = {
            "speaking_ah": "neutral_to_speaking_ah",
            "happy_soft": "neutral_to_happy_soft",
            "happy_big": "happy_soft_to_happy_big",
            "speaking_ee": "neutral_to_speaking_ee",
            "speaking_uw": "neutral_to_speaking_uw",
            "oh_round": "neutral_to_oh_round",
            "concerned": "neutral_to_concerned",
            "surprised_ah": "speaking_ah_to_surprised",
          };
          
          const pathName = exprMap[state.expr];
          if (pathName) {
            const tl = await fetchTimeline(`${pathName}__${state.pose}`);
            if (tl.frames.length > 0) {
              const lastFrame = tl.frames[tl.frames.length - 1];
              const url = `${API_BASE}/frames/${tl.path_id}/${lastFrame.file}`;
              setCurrentImage(url);
              setBufferA(url);
              setBufferB(url);
            }
          }
        }
      } catch (err) {
        console.error("Failed to load idle frame:", err);
      }
    };
    
    loadIdleFrame();
  }, [currentState, isAnimating]);
  
  // Playback loop
  useEffect(() => {
    if (!isPlaying) return;
    
    const startTime = performance.now();
    const initialTime = currentTime;
    
    const tick = () => {
      const elapsed = performance.now() - startTime;
      const newTime = initialTime + elapsed;
      
      setCurrentTime(newTime);
      
      // Update audio sync
      if (audioRef.current && Math.abs(audioRef.current.currentTime * 1000 - newTime) > 100) {
        audioRef.current.currentTime = newTime / 1000;
      }
      
      // Check for transitions every 50ms
      if (newTime - lastUpdateTime.current > 50) {
        const newState = getCurrentStateFromTimeline(newTime);
        const prevState = currentStateRef.current;
        if (newState.expr !== prevState.expr || newState.pose !== prevState.pose) {
          executeTransition(newState);
        }
        lastUpdateTime.current = newTime;
      }
      
      if (newTime < audioDuration) {
        animationFrameRef.current = requestAnimationFrame(tick);
      } else {
        setIsPlaying(false);
        setCurrentTime(0);
      }
    };
    
    animationFrameRef.current = requestAnimationFrame(tick);
    
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, audioDuration]); // Removed currentTime and currentState from dependencies to prevent re-creation of animation loop
  
  // Playback controls
  const handlePlay = () => {
    if (audioRef.current && audioUrl) {
      audioRef.current.currentTime = currentTime / 1000;
      // Use play() with error handling to prevent multiple play attempts
      const playPromise = audioRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.error("Audio play error:", error);
        });
      }
    }
    setIsPlaying(true);
    lastUpdateTime.current = currentTime;
  };
  
  const handlePause = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    setIsPlaying(false);
  };
  
  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    setCurrentTime(0);
    setIsPlaying(false);
    setCurrentState({ expr: "neutral", pose: "center" });
  };
  
  // Export video
  const handleExport = async () => {
    if (combinedTimeline.length === 0) {
      alert("No timeline to export! Add some keyframes first.");
      return;
    }
    
    setIsExporting(true);
    
    try {
      // Upload audio file if present
      let audioUrl = "";
      if (audioFile) {
        const formData = new FormData();
        formData.append("file", audioFile);
        
        const uploadRes = await fetch(`${API_BASE}/audio/upload`, {
          method: "POST",
          body: formData,
        });
        
        if (!uploadRes.ok) {
          throw new Error("Failed to upload audio");
        }
        
        const uploadData = await uploadRes.json();
        audioUrl = `/audio/${uploadData.filename}`;
      }
      
      // Call export endpoint
      const response = await fetch(`${API_BASE}/export-video`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          combined_timeline: combinedTimeline,
          audio_url: audioUrl,
          format: exportFormat,
          fps: exportFps,
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Export failed");
      }
      
      // Download the video file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `animation_${Date.now()}.${exportFormat}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      alert("✅ Video exported successfully!");
    } catch (error) {
      console.error("Export error:", error);
      alert(`❌ Export failed: ${error.message}`);
    } finally {
      setIsExporting(false);
    }
  };
  
  // Timeline click to seek
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const newTime = (x / rect.width) * audioDuration;
    setCurrentTime(Math.max(0, Math.min(newTime, audioDuration)));
    setCurrentState(getCurrentStateFromTimeline(newTime));
  };
  
  const timelineWidth = 900;
  const pixelsPerMs = audioDuration > 0 ? timelineWidth / audioDuration : 0.1;
  
  return (
    <div style={{ padding: "20px", maxWidth: "1600px", margin: "0 auto" }}>
      <h1>🎞️ Timeline Director</h1>
      <p style={{ color: "#666", marginBottom: "30px" }}>
        Create layered animations: Pose + Expression + Phonemes → Final video
      </p>
      
      <div style={{ display: "flex", gap: "30px" }}>
        {/* Left: Timelines */}
        <div style={{ flex: 1 }}>
          {/* Audio Upload */}
          <div style={{ marginBottom: "20px", padding: "15px", border: "1px solid #ddd", borderRadius: "8px" }}>
            <h3>Audio Input</h3>
            <input type="file" accept="audio/*" onChange={handleAudioUpload} />
            {audioFile && <span style={{ marginLeft: "10px", fontSize: "14px" }}>✓ {audioFile.name} ({(audioDuration/1000).toFixed(1)}s)</span>}
            {audioUrl && <audio ref={audioRef} src={audioUrl} key={audioUrl} />}
          </div>
          
          {/* Transcript & AI Emotions */}
          <div style={{ marginBottom: "20px", padding: "15px", border: "1px solid #9C27B0", borderRadius: "8px", background: "#F3E5F5" }}>
            <h3 style={{ marginTop: 0 }}>Transcript & AI Emotions</h3>
            <div style={{ marginBottom: "10px" }}>
              <label style={{
                padding: "5px 10px",
                fontSize: "12px",
                background: "#9C27B0",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                display: "inline-block"
              }}>
                📄 Upload Transcript (.txt / .lab)
                <input 
                  ref={transcriptFileInputRef}
                  type="file" 
                  accept=".txt,.lab" 
                  onChange={handleTranscriptUpload} 
                  style={{ display: "none" }} 
                />
              </label>
              {transcript && (
                <span style={{ marginLeft: "10px", fontSize: "14px" }}>✓ {transcript.length} chars</span>
              )}
            </div>
            {transcript && (
              <div style={{ marginBottom: "10px", padding: "8px", background: "white", borderRadius: "4px", fontSize: "12px", maxHeight: "60px", overflow: "auto" }}>
                {transcript}
              </div>
            )}
            <button 
              onClick={generateAlignment}
              disabled={!audioFile || !transcript || isGeneratingAlignment}
              style={{
                padding: "8px 16px",
                fontSize: "14px",
                background: isGeneratingAlignment ? "#ccc" : "#00897B",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: isGeneratingAlignment ? "not-allowed" : "pointer",
                display: "block",
                width: "100%",
                marginBottom: "8px"
              }}
            >
              {isGeneratingAlignment ? "🎵 Aligning Audio..." : "🎵 Generate Phoneme Timeline (MFA)"}
            </button>
            <button 
              onClick={generateEmotions} 
              disabled={!transcript || phonemeTimeline.length === 0 || isGeneratingEmotions}
              style={{
                padding: "8px 16px",
                fontSize: "14px",
                background: isGeneratingEmotions ? "#ccc" : "#9C27B0",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: isGeneratingEmotions ? "not-allowed" : "pointer",
                display: "block",
                width: "100%"
              }}
            >
              {isGeneratingEmotions ? "🤖 Analyzing..." : "✨ Generate Emotions with AI"}
            </button>
            <div style={{ marginTop: "8px", fontSize: "11px", color: "#666" }}>
              Step 1: Generate phoneme timeline (requires audio + transcript + MFA)<br/>
              Step 2: Generate emotions (requires phoneme timeline + OPENAI_API_KEY)<br/>
              <br/>
              ⏱️ Alignment time scales with audio length (~90s per minute of audio)
            </div>
          </div>
          
          {/* Pose Timeline */}
          <div style={{ marginBottom: "15px", padding: "15px", border: "1px solid #2196F3", borderRadius: "8px", background: "#E3F2FD" }}>
            <h3 style={{ marginTop: 0 }}>Pose Timeline</h3>
            <div style={{ display: "flex", gap: "5px", marginBottom: "10px", flexWrap: "wrap" }}>
              {POSES.map(pose => (
                <button key={pose} onClick={() => addPoseKeyframe(pose)} style={{
                  padding: "5px 10px",
                  fontSize: "12px",
                  background: "#2196F3",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer"
                }}>
                  + {pose.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
            <div onClick={handleTimelineClick} style={{ 
              height: "50px", 
              background: "#fff", 
              position: "relative",
              border: "1px solid #2196F3",
              width: `${timelineWidth}px`,
              cursor: "crosshair"
            }}>
              {poseTimeline.map((kf) => (
                <div key={kf.id} 
                  style={{
                    position: "absolute",
                    left: `${kf.time_ms * pixelsPerMs}px`,
                    top: "5px",
                  }}
                >
                  <div
                    onClick={(e) => { e.stopPropagation(); setSelectedKeyframe(kf.id); }}
                    onMouseEnter={(e) => (e.currentTarget.style.width = "6px")}
                    onMouseLeave={(e) => (e.currentTarget.style.width = selectedKeyframe === kf.id ? "6px" : "3px")}
                    style={{
                      width: selectedKeyframe === kf.id ? "6px" : "3px",
                      height: "40px",
                      background: selectedKeyframe === kf.id ? "#FF5722" : "#2196F3",
                      cursor: "pointer",
                      borderRadius: "1px",
                      position: "relative",
                      transition: "width 0.1s"
                    }} 
                    title={`${kf.time_ms}ms: ${kf.target_pose}\nClick to select, then × to delete`}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteKeyframe(kf.id); }}
                    style={{
                      position: "absolute",
                      top: "-18px",
                      left: "-8px",
                      width: "18px",
                      height: "18px",
                      padding: "0",
                      background: "#f44336",
                      color: "white",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer",
                      fontSize: "10px",
                      lineHeight: "1",
                      display: selectedKeyframe === kf.id ? "block" : "none"
                    }}
                    title="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
              {/* Playhead */}
              <div style={{
                position: "absolute",
                left: `${currentTime * pixelsPerMs}px`,
                top: 0,
                width: "2px",
                height: "100%",
                background: "red",
                zIndex: 10,
                pointerEvents: "none"
              }} />
            </div>
          </div>
          
          {/* Expression Timeline */}
          <div style={{ marginBottom: "15px", padding: "15px", border: "1px solid #FF9800", borderRadius: "8px", background: "#FFF3E0" }}>
            <h3 style={{ marginTop: 0 }}>Expression Timeline</h3>
            <div style={{ display: "flex", gap: "5px", marginBottom: "10px", flexWrap: "wrap" }}>
              {EXPRESSIONS.map(expr => (
                <button key={expr} onClick={() => addExpressionKeyframe(expr)} style={{
                  padding: "5px 10px",
                  fontSize: "12px",
                  background: "#FF9800",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  cursor: "pointer"
                }}>
                  + {expr.replace(/_/g, ' ')}
                </button>
              ))}
            </div>
            <div onClick={handleTimelineClick} style={{ 
              height: "50px", 
              background: "#fff", 
              position: "relative",
              border: "1px solid #FF9800",
              width: `${timelineWidth}px`,
              cursor: "crosshair"
            }}>
              {expressionTimeline.map((kf) => (
                <div key={kf.id}
                  style={{
                    position: "absolute",
                    left: `${kf.time_ms * pixelsPerMs}px`,
                    top: "5px",
                  }}
                >
                  <div
                    onClick={(e) => { e.stopPropagation(); setSelectedKeyframe(kf.id); }}
                    onMouseEnter={(e) => (e.currentTarget.style.width = "6px")}
                    onMouseLeave={(e) => (e.currentTarget.style.width = selectedKeyframe === kf.id ? "6px" : "3px")}
                    style={{
                      width: selectedKeyframe === kf.id ? "6px" : "3px",
                      height: "40px",
                      background: selectedKeyframe === kf.id ? "#FF5722" : "#FF9800",
                      cursor: "pointer",
                      borderRadius: "1px",
                      position: "relative",
                      transition: "width 0.1s"
                    }} 
                    title={`${kf.time_ms}ms: ${kf.target_expr}\nClick to select, then × to delete`}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteKeyframe(kf.id); }}
                    style={{
                      position: "absolute",
                      top: "-18px",
                      left: "-8px",
                      width: "18px",
                      height: "18px",
                      padding: "0",
                      background: "#f44336",
                      color: "white",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer",
                      fontSize: "10px",
                      lineHeight: "1",
                      display: selectedKeyframe === kf.id ? "block" : "none"
                    }}
                    title="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
              <div style={{
                position: "absolute",
                left: `${currentTime * pixelsPerMs}px`,
                top: 0,
                width: "2px",
                height: "100%",
                background: "red",
                zIndex: 10,
                pointerEvents: "none"
              }} />
            </div>
          </div>
          
          {/* Phoneme Timeline */}
          <div style={{ marginBottom: "15px", padding: "15px", border: "1px solid #4CAF50", borderRadius: "8px", background: "#E8F5E9" }}>
            <h3 style={{ marginTop: 0 }}>Phoneme Timeline (Lip-sync)</h3>
            <div style={{ marginBottom: "10px" }}>
              <label style={{
                padding: "5px 10px",
                fontSize: "12px",
                background: "#4CAF50",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                display: "inline-block"
              }}>
                📂 Load TextGrid / JSON (Optional)
                <input type="file" accept=".TextGrid,.json" onChange={handleLoadPhonemeTimeline} style={{ display: "none" }} />
              </label>
              {phonemeTimeline.length > 0 && (
                <span style={{ marginLeft: "10px", fontSize: "14px" }}>✓ {phonemeTimeline.length} keyframes</span>
              )}
            </div>
            <div style={{ fontSize: "11px", color: "#666", marginBottom: "10px" }}>
              💡 Tip: Use "🎵 Generate Phoneme Timeline (MFA)" button in the "Transcript & AI Emotions" section above to auto-generate from audio + transcript
            </div>
            <div onClick={handleTimelineClick} style={{ 
              height: "50px", 
              background: "#fff", 
              position: "relative",
              border: "1px solid #4CAF50",
              width: `${timelineWidth}px`,
              cursor: "crosshair"
            }}>
              {phonemeTimeline.map((kf) => (
                <div key={kf.id}
                  style={{
                    position: "absolute",
                    left: `${kf.time_ms * pixelsPerMs}px`,
                    top: "5px",
                  }}
                >
                  <div
                    onClick={(e) => { e.stopPropagation(); setSelectedKeyframe(kf.id); }}
                    onMouseEnter={(e) => (e.currentTarget.style.width = "6px")}
                    onMouseLeave={(e) => (e.currentTarget.style.width = selectedKeyframe === kf.id ? "6px" : "3px")}
                    style={{
                      width: selectedKeyframe === kf.id ? "6px" : "3px",
                      height: "40px",
                      background: selectedKeyframe === kf.id ? "#FF5722" : "#4CAF50",
                      cursor: "pointer",
                      borderRadius: "1px",
                      position: "relative",
                      transition: "width 0.1s"
                    }} 
                    title={`${kf.time_ms}ms: ${kf.phoneme} → ${kf.target_expr}\nClick to select, then × to delete`}
                  />
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteKeyframe(kf.id); }}
                    style={{
                      position: "absolute",
                      top: "-18px",
                      left: "-8px",
                      width: "18px",
                      height: "18px",
                      padding: "0",
                      background: "#f44336",
                      color: "white",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer",
                      fontSize: "10px",
                      lineHeight: "1",
                      display: selectedKeyframe === kf.id ? "block" : "none"
                    }}
                    title="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
              <div style={{
                position: "absolute",
                left: `${currentTime * pixelsPerMs}px`,
                top: 0,
                width: "2px",
                height: "100%",
                background: "red",
                zIndex: 10,
                pointerEvents: "none"
              }} />
            </div>
          </div>
          
          {/* Combined Timeline */}
          <div style={{ padding: "15px", border: "2px solid #333", borderRadius: "8px", background: "#fafafa" }}>
            <h3 style={{ marginTop: 0 }}>Combined Timeline (Final Output)</h3>
            <div onClick={handleTimelineClick} style={{ 
              height: "70px", 
              background: "#fff", 
              position: "relative",
              border: "2px solid #333",
              width: `${timelineWidth}px`,
              cursor: "crosshair"
            }}>
              {combinedTimeline.map((kf, i) => (
                <div key={i} style={{
                  position: "absolute",
                  left: `${kf.time_ms * pixelsPerMs}px`,
                  top: "10px",
                  width: "4px",
                  height: "50px",
                  background: "#9C27B0",
                  border: "1px solid #333",
                  borderRadius: "2px"
                }} title={`${kf.time_ms}ms: ${kf.target_expr}__${kf.target_pose}`} />
              ))}
              <div style={{
                position: "absolute",
                left: `${currentTime * pixelsPerMs}px`,
                top: 0,
                width: "3px",
                height: "100%",
                background: "red",
                zIndex: 10,
                pointerEvents: "none"
              }} />
            </div>
            <div style={{ marginTop: "10px", fontSize: "12px", color: "#666" }}>
              {combinedTimeline.length} keyframes | Current: {currentState.expr}__{currentState.pose}
            </div>
          </div>
          
          {/* Controls */}
          <div style={{ marginTop: "20px", display: "flex", gap: "10px", alignItems: "center" }}>
            <button onClick={handlePlay} disabled={isPlaying} style={{
              padding: "10px 20px",
              fontSize: "16px",
              background: isPlaying ? "#ccc" : "#4CAF50",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: isPlaying ? "not-allowed" : "pointer"
            }}>
              ▶️ Play
            </button>
            <button onClick={handlePause} disabled={!isPlaying} style={{
              padding: "10px 20px",
              fontSize: "16px",
              background: !isPlaying ? "#ccc" : "#FF9800",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: !isPlaying ? "not-allowed" : "pointer"
            }}>
              ⏸️ Pause
            </button>
            <button onClick={handleStop} style={{
              padding: "10px 20px",
              fontSize: "16px",
              background: "#f44336",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer"
            }}>
              ⏹️ Stop
            </button>
            {selectedKeyframe && (
              <button onClick={() => deleteKeyframe(selectedKeyframe)} style={{
                padding: "10px 20px",
                fontSize: "16px",
                background: "#FF5722",
                color: "white",
                border: "none",
                borderRadius: "4px",
                cursor: "pointer",
                marginLeft: "20px"
              }}>
                🗑️ Delete ({selectedKeyframe})
              </button>
            )}
            <div style={{ marginLeft: "auto", fontSize: "14px" }}>
              ⏱️ {(currentTime / 1000).toFixed(2)}s / {(audioDuration / 1000).toFixed(2)}s
            </div>
          </div>
          
          {/* Export Controls */}
          <div style={{ marginTop: "20px", padding: "15px", border: "2px solid #673AB7", borderRadius: "8px", background: "#EDE7F6" }}>
            <h3 style={{ marginTop: 0 }}>🎬 Export Video</h3>
            <div style={{ display: "flex", gap: "15px", alignItems: "center", flexWrap: "wrap" }}>
              <div>
                <label style={{ marginRight: "10px", fontSize: "14px", fontWeight: "bold" }}>Format:</label>
                <select 
                  value={exportFormat} 
                  onChange={(e) => setExportFormat(e.target.value as "mp4" | "webm")}
                  style={{
                    padding: "5px 10px",
                    fontSize: "14px",
                    borderRadius: "4px",
                    border: "1px solid #673AB7"
                  }}
                >
                  <option value="mp4">MP4 (Standard)</option>
                  <option value="webm">WebM (Transparency)</option>
                </select>
              </div>
              
              <div>
                <label style={{ marginRight: "10px", fontSize: "14px", fontWeight: "bold" }}>FPS:</label>
                <select 
                  value={exportFps} 
                  onChange={(e) => setExportFps(parseInt(e.target.value))}
                  style={{
                    padding: "5px 10px",
                    fontSize: "14px",
                    borderRadius: "4px",
                    border: "1px solid #673AB7"
                  }}
                >
                  <option value="24">24 FPS (Cinematic)</option>
                  <option value="30">30 FPS (Standard)</option>
                  <option value="60">60 FPS (Smooth)</option>
                </select>
              </div>
              
              <button
                onClick={handleExport}
                disabled={isExporting || combinedTimeline.length === 0}
                style={{
                  padding: "10px 30px",
                  fontSize: "16px",
                  background: isExporting ? "#ccc" : "#673AB7",
                  color: "white",
                  border: "none",
                  borderRadius: "4px",
                  cursor: isExporting ? "not-allowed" : "pointer",
                  fontWeight: "bold"
                }}
              >
                {isExporting ? "⏳ Exporting..." : "🎬 Export Video"}
              </button>
            </div>
            <div style={{ marginTop: "10px", fontSize: "12px", color: "#666" }}>
              💡 MP4 for standard playback, WebM for OBS/streaming with transparency
              {isExporting && " • This may take 1-2 minutes depending on duration..."}
            </div>
          </div>
        </div>
        
        {/* Right: Preview */}
        <div style={{ width: "400px" }}>
          <h3>Preview</h3>
          <div style={{ 
            width: "100%", 
            height: "600px", 
            background: "#f5f5f5", 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            border: "2px solid #333",
            borderRadius: "8px",
            overflow: "hidden",
            position: "relative"
          }}>
            {(bufferA || bufferB || currentImage) ? (
              <div style={{ position: "relative", width: "100%", height: "100%" }}>
                {/* Buffer A */}
                {bufferA && (
                  <img
                    src={bufferA}
                    alt="character"
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      objectFit: "contain",
                      opacity: activeBuffer === "A" ? 1 : 0,
                      transition: "opacity 0.15s ease-in-out",
                    }}
                  />
                )}
                {/* Buffer B */}
                {bufferB && (
                  <img
                    src={bufferB}
                    alt="character"
                    style={{
                      position: "absolute",
                      top: 0,
                      left: 0,
                      width: "100%",
                      height: "100%",
                      objectFit: "contain",
                      opacity: activeBuffer === "B" ? 1 : 0,
                      transition: "opacity 0.15s ease-in-out",
                    }}
                  />
                )}
                {/* Fallback to currentImage if no buffers */}
                {!bufferA && !bufferB && currentImage && (
                  <img
                    src={currentImage}
                    alt="character"
                    style={{
                      width: "100%",
                      height: "100%",
                      objectFit: "contain",
                    }}
                  />
                )}
              </div>
            ) : (
              <div style={{ color: "#999" }}>Add keyframes to preview</div>
            )}
          </div>
          <div style={{ marginTop: "10px", fontSize: "14px", textAlign: "center" }}>
            {currentState.expr}__{currentState.pose}
          </div>
        </div>
      </div>
    </div>
  );
};
