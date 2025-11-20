// transitionGraph.ts

export type ExpressionId =
  | "neutral"
  | "happy_soft"
  | "happy_big"
  | "speaking_ah"
  | "surprised_ah"
  | "speaking_ee"
  | "speaking_uw"
  | "oh_round"
  | "concerned"
  | "blink_closed";

export type PoseId =
  | "center"
  | "tilt_left_small"
  | "tilt_right_small"
  | "nod_down_small"
  | "nod_up_small";

export type State = {
  expr: ExpressionId;
  pose: PoseId;
};

export type Segment = {
  pathId: string;             // sequence id, e.g. "neutral_to_speaking_ah__center"
  direction: "forward" | "backward";
  from: State;
  to: State;
};

// --- This mirrors expressions.json["base_paths"] ---

type BasePath = {
  id: string;
  start: ExpressionId;
  end: ExpressionId;
};

const BASE_PATHS: BasePath[] = [
  { id: "neutral_to_speaking_ah",  start: "neutral",     end: "speaking_ah" },
  { id: "speaking_ah_to_surprised",start: "speaking_ah", end: "surprised_ah" },

  { id: "neutral_to_speaking_ee",  start: "neutral",     end: "speaking_ee" },
  { id: "neutral_to_speaking_uw",  start: "neutral",     end: "speaking_uw" },
  { id: "neutral_to_oh_round",     start: "neutral",     end: "oh_round" },

  { id: "neutral_to_happy_soft",   start: "neutral",     end: "happy_soft" },
  { id: "happy_soft_to_happy_big", start: "happy_soft",  end: "happy_big" },

  { id: "neutral_to_concerned",    start: "neutral",     end: "concerned" },
  { id: "neutral_to_blink",        start: "neutral",     end: "blink_closed" },
  
  // Viseme-to-viseme direct transitions (for smooth lip-sync)
  { id: "speaking_ah_to_speaking_ee", start: "speaking_ah", end: "speaking_ee" },
  { id: "speaking_ee_to_speaking_ah", start: "speaking_ee", end: "speaking_ah" },
  { id: "speaking_ah_to_speaking_uw", start: "speaking_ah", end: "speaking_uw" },
  { id: "speaking_uw_to_speaking_ah", start: "speaking_uw", end: "speaking_ah" },
  { id: "speaking_ah_to_oh_round",    start: "speaking_ah", end: "oh_round" },
  { id: "oh_round_to_speaking_ah",    start: "oh_round",    end: "speaking_ah" },
  { id: "speaking_ee_to_speaking_uw", start: "speaking_ee", end: "speaking_uw" },
  { id: "speaking_uw_to_speaking_ee", start: "speaking_uw", end: "speaking_ee" },
  { id: "speaking_ee_to_oh_round",    start: "speaking_ee", end: "oh_round" },
  { id: "oh_round_to_speaking_ee",    start: "oh_round",    end: "speaking_ee" },
  { id: "speaking_uw_to_oh_round",    start: "speaking_uw", end: "oh_round" },
  { id: "oh_round_to_speaking_uw",    start: "oh_round",    end: "speaking_uw" },
];

// Note: All sequences are bidirectional! We can play any sequence backwards
// to go from end -> start. So neutral_to_speaking_ah can be used for both:
//   neutral -> speaking_ah (forward)
//   speaking_ah -> neutral (backward)
// 
// Viseme-to-viseme transitions are defined in both directions for clarity,
// but the system will automatically use reverse playback if only one direction exists.

// neutral pose timelines: created by generate_neutral_pose_sequences.py
// We assume we have sequences like:
//   neutral_center_to_neutral_tilt_left_small
//   neutral_center_to_neutral_tilt_right_small
//   neutral_center_to_neutral_nod_down_small
//   neutral_center_to_neutral_nod_up_small

// Helper to build expression timeline for a given pose.
function getExpressionSegment(
  from: State,
  to: State
): Segment | null {
  if (from.pose !== to.pose) return null;
  if (from.expr === to.expr) return null;

  const pose = from.pose;

  // Try forward base_path start->end
  let bp = BASE_PATHS.find(
    (b) => b.start === from.expr && b.end === to.expr
  );
  if (bp) {
    return {
      pathId: `${bp.id}__${pose}`,
      direction: "forward",
      from,
      to,
    };
  }

  // Try backwards (play the same sequence in reverse)
  bp = BASE_PATHS.find(
    (b) => b.start === to.expr && b.end === from.expr
  );
  if (bp) {
    return {
      pathId: `${bp.id}__${pose}`,
      direction: "backward",
      from,
      to,
    };
  }

  return null;
}

// Helper for neutral pose transitions.
// generate_neutral_pose_sequences.py only generates center->other sequences:
//   neutral_center_to_neutral_tilt_left_small
//   neutral_center_to_neutral_tilt_right_small
//   neutral_center_to_neutral_nod_up_small
//   neutral_center_to_neutral_nod_down_small
// 
// So we need to:
// - center -> other: use forward direction
// - other -> center: use backward direction
// - other -> other: route via center (handled by planRoute)
function getNeutralPoseSegment(
  from: State,
  to: State
): Segment | null {
  if (from.expr !== "neutral" || to.expr !== "neutral") return null;
  if (from.pose === to.pose) return null;

  const fromPose = from.pose;
  const toPose = to.pose;

  // Case 1: center -> other pose
  if (fromPose === "center") {
    return {
      pathId: `neutral_center_to_neutral_${toPose}`,
      direction: "forward",
      from,
      to,
    };
  }

  // Case 2: other pose -> center
  if (toPose === "center") {
    return {
      pathId: `neutral_center_to_neutral_${fromPose}`,
      direction: "backward",
      from,
      to,
    };
  }

  // Case 3: other -> other (not directly supported, need to route via center)
  // This should be handled by planRoute doing two hops
  return null;
}

// High-level routing:
// - If same state: [].
// - If same pose, and we have a direct expression timeline: [segment].
// - If both neutral and different pose: [poseSegment].
// - Otherwise: detour through neutral:
//   (exprA, poseA) -> (neutral, poseA) -> (neutral, poseB) -> (exprB, poseB)
//   skipping steps that are already neutral.
export function planRoute(
  current: State,
  target: State
): Segment[] {
  // No-op
  if (current.expr === target.expr && current.pose === target.pose) {
    return [];
  }

  // 1. Same pose, try direct expression transition first
  if (current.pose === target.pose) {
    const directExprSeg = getExpressionSegment(current, target);
    if (directExprSeg) {
      console.log(`📍 Direct path: ${current.expr} → ${target.expr} @ ${current.pose}`);
      return [directExprSeg];
    }

    // No direct path found - route via neutral expression at this pose
    console.log(`🔄 No direct path from ${current.expr} to ${target.expr}, routing via neutral @ ${current.pose}`);
    
    const segments: Segment[] = [];
    const neutralHere: State = { expr: "neutral", pose: current.pose };

    if (current.expr !== "neutral") {
      const toNeutral = getExpressionSegment(current, neutralHere);
      if (!toNeutral) {
        // Special cases: some expressions must go through intermediate expressions
        if (current.expr === "surprised_ah") {
          console.log(`  Special routing: surprised_ah must go via speaking_ah to reach neutral`);
          const speakingAh: State = { expr: "speaking_ah", pose: current.pose };
          
          // surprised_ah → speaking_ah
          const toSpeakingAh = getExpressionSegment(current, speakingAh);
          if (!toSpeakingAh) {
            console.error(`❌ Cannot route from surprised_ah to speaking_ah @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 1a: surprised_ah → speaking_ah`);
          segments.push(toSpeakingAh);
          
          // speaking_ah → neutral
          const speakingToNeutral = getExpressionSegment(speakingAh, neutralHere);
          if (!speakingToNeutral) {
            console.error(`❌ Cannot route from speaking_ah to neutral @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 1b: speaking_ah → neutral`);
          segments.push(speakingToNeutral);
        } else if (current.expr === "happy_big") {
          console.log(`  Special routing: happy_big must go via happy_soft to reach neutral`);
          const happySoft: State = { expr: "happy_soft", pose: current.pose };
          
          // happy_big → happy_soft
          const toHappySoft = getExpressionSegment(current, happySoft);
          if (!toHappySoft) {
            console.error(`❌ Cannot route from happy_big to happy_soft @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 1a: happy_big → happy_soft`);
          segments.push(toHappySoft);
          
          // happy_soft → neutral
          const happyToNeutral = getExpressionSegment(happySoft, neutralHere);
          if (!happyToNeutral) {
            console.error(`❌ Cannot route from happy_soft to neutral @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 1b: happy_soft → neutral`);
          segments.push(happyToNeutral);
        } else {
          console.error(`❌ Cannot route to neutral from ${current.expr} @ ${current.pose}`);
          return [];
        }
      } else {
        console.log(`  Step 1: ${current.expr} → neutral (via ${toNeutral.pathId}, ${toNeutral.direction})`);
        segments.push(toNeutral);
      }
    }

    if (target.expr !== "neutral") {
      const fromNeutral = getExpressionSegment(neutralHere, target);
      if (!fromNeutral) {
        // Special cases: some expressions can only be reached via intermediate expressions
        if (target.expr === "surprised_ah") {
          console.log(`  Special routing: surprised_ah requires speaking_ah as intermediate`);
          const speakingAh: State = { expr: "speaking_ah", pose: current.pose };
          
          // neutral → speaking_ah
          const toSpeakingAh = getExpressionSegment(neutralHere, speakingAh);
          if (!toSpeakingAh) {
            console.error(`❌ Cannot route from neutral to speaking_ah @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 2a: neutral → speaking_ah`);
          segments.push(toSpeakingAh);
          
          // speaking_ah → surprised_ah
          const toSurprised = getExpressionSegment(speakingAh, target);
          if (!toSurprised) {
            console.error(`❌ Cannot route from speaking_ah to surprised_ah @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 2b: speaking_ah → surprised_ah`);
          segments.push(toSurprised);
        } else if (target.expr === "happy_big") {
          console.log(`  Special routing: happy_big requires happy_soft as intermediate`);
          const happySoft: State = { expr: "happy_soft", pose: current.pose };
          
          // neutral → happy_soft
          const toHappySoft = getExpressionSegment(neutralHere, happySoft);
          if (!toHappySoft) {
            console.error(`❌ Cannot route from neutral to happy_soft @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 2a: neutral → happy_soft`);
          segments.push(toHappySoft);
          
          // happy_soft → happy_big
          const toHappyBig = getExpressionSegment(happySoft, target);
          if (!toHappyBig) {
            console.error(`❌ Cannot route from happy_soft to happy_big @ ${current.pose}`);
            return [];
          }
          console.log(`  Step 2b: happy_soft → happy_big`);
          segments.push(toHappyBig);
        } else {
          console.error(`❌ Cannot route from neutral to ${target.expr} @ ${current.pose}`);
          return [];
        }
      } else {
        console.log(`  Step 2: neutral → ${target.expr} (via ${fromNeutral.pathId}, ${fromNeutral.direction})`);
        segments.push(fromNeutral);
      }
    }

    console.log(`✅ Route complete: ${segments.length} segment(s)`);
    return segments;
  }

  // 2. Different pose - must route via neutral expression
  console.log(`🔄 Cross-pose routing: ${current.expr} @ ${current.pose} → ${target.expr} @ ${target.pose}`);
  
  const segments: Segment[] = [];
  const neutralCurrent: State = { expr: "neutral", pose: current.pose };
  const neutralTarget: State = { expr: "neutral", pose: target.pose };
  const neutralCenter: State = { expr: "neutral", pose: "center" };

  // Step A: expression -> neutral at current pose (if needed)
  if (current.expr !== "neutral") {
    const toNeutral = getExpressionSegment(current, neutralCurrent);
    if (!toNeutral) {
      // Special cases: some expressions must go through intermediate expressions
      if (current.expr === "surprised_ah") {
        console.log(`  Step A: Special routing from surprised_ah via speaking_ah`);
        const speakingAh: State = { expr: "speaking_ah", pose: current.pose };
        
        // surprised_ah → speaking_ah
        const toSpeakingAh = getExpressionSegment(current, speakingAh);
        if (!toSpeakingAh) {
          console.error(`❌ Cannot route from surprised_ah to speaking_ah @ ${current.pose}`);
          return [];
        }
        console.log(`    A1: surprised_ah → speaking_ah @ ${current.pose}`);
        segments.push(toSpeakingAh);
        
        // speaking_ah → neutral
        const speakingToNeutral = getExpressionSegment(speakingAh, neutralCurrent);
        if (!speakingToNeutral) {
          console.error(`❌ Cannot route from speaking_ah to neutral @ ${current.pose}`);
          return [];
        }
        console.log(`    A2: speaking_ah → neutral @ ${current.pose}`);
        segments.push(speakingToNeutral);
      } else if (current.expr === "happy_big") {
        console.log(`  Step A: Special routing from happy_big via happy_soft`);
        const happySoft: State = { expr: "happy_soft", pose: current.pose };
        
        // happy_big → happy_soft
        const toHappySoft = getExpressionSegment(current, happySoft);
        if (!toHappySoft) {
          console.error(`❌ Cannot route from happy_big to happy_soft @ ${current.pose}`);
          return [];
        }
        console.log(`    A1: happy_big → happy_soft @ ${current.pose}`);
        segments.push(toHappySoft);
        
        // happy_soft → neutral
        const happyToNeutral = getExpressionSegment(happySoft, neutralCurrent);
        if (!happyToNeutral) {
          console.error(`❌ Cannot route from happy_soft to neutral @ ${current.pose}`);
          return [];
        }
        console.log(`    A2: happy_soft → neutral @ ${current.pose}`);
        segments.push(happyToNeutral);
      } else {
        console.error(`❌ Cannot route to neutral from ${current.expr} @ ${current.pose}`);
        return [];
      }
    } else {
      console.log(`  Step A: ${current.expr} → neutral @ ${current.pose}`);
      segments.push(toNeutral);
    }
  }

  // Step B: neutral pose transition current pose -> target pose
  // If neither pose is center, we need to route via center
  const poseSeg = getNeutralPoseSegment(neutralCurrent, neutralTarget);
  if (!poseSeg) {
    console.log(`  Step B: Routing via center pose (${current.pose} → center → ${target.pose})`);
    // Need to route via center: current pose -> center -> target pose
    if (current.pose !== "center") {
      const toCenter = getNeutralPoseSegment(neutralCurrent, neutralCenter);
      if (!toCenter) {
        console.error(`❌ Cannot route from ${current.pose} to center`);
        return [];
      }
      console.log(`    B1: neutral @ ${current.pose} → neutral @ center`);
      segments.push(toCenter);
    }
    
    if (target.pose !== "center") {
      const fromCenter = getNeutralPoseSegment(neutralCenter, neutralTarget);
      if (!fromCenter) {
        console.error(`❌ Cannot route from center to ${target.pose}`);
        return [];
      }
      console.log(`    B2: neutral @ center → neutral @ ${target.pose}`);
      segments.push(fromCenter);
    }
  } else {
    console.log(`  Step B: Direct pose transition ${current.pose} → ${target.pose}`);
    segments.push(poseSeg);
  }

  // Step C: neutral -> target expression at target pose (if needed)
  if (target.expr !== "neutral") {
    const fromNeutral = getExpressionSegment(neutralTarget, target);
    if (!fromNeutral) {
      // Special cases: some expressions can only be reached via intermediate expressions
      if (target.expr === "surprised_ah") {
        console.log(`  Step C: Special routing for surprised_ah via speaking_ah`);
        const speakingAh: State = { expr: "speaking_ah", pose: target.pose };
        
        // neutral → speaking_ah at target pose
        const toSpeakingAh = getExpressionSegment(neutralTarget, speakingAh);
        if (!toSpeakingAh) {
          console.error(`❌ Cannot route from neutral to speaking_ah @ ${target.pose}`);
          return [];
        }
        console.log(`    C1: neutral → speaking_ah @ ${target.pose}`);
        segments.push(toSpeakingAh);
        
        // speaking_ah → surprised_ah at target pose
        const toSurprised = getExpressionSegment(speakingAh, target);
        if (!toSurprised) {
          console.error(`❌ Cannot route from speaking_ah to surprised_ah @ ${target.pose}`);
          return [];
        }
        console.log(`    C2: speaking_ah → surprised_ah @ ${target.pose}`);
        segments.push(toSurprised);
      } else if (target.expr === "happy_big") {
        console.log(`  Step C: Special routing for happy_big via happy_soft`);
        const happySoft: State = { expr: "happy_soft", pose: target.pose };
        
        // neutral → happy_soft at target pose
        const toHappySoft = getExpressionSegment(neutralTarget, happySoft);
        if (!toHappySoft) {
          console.error(`❌ Cannot route from neutral to happy_soft @ ${target.pose}`);
          return [];
        }
        console.log(`    C1: neutral → happy_soft @ ${target.pose}`);
        segments.push(toHappySoft);
        
        // happy_soft → happy_big at target pose
        const toHappyBig = getExpressionSegment(happySoft, target);
        if (!toHappyBig) {
          console.error(`❌ Cannot route from happy_soft to happy_big @ ${target.pose}`);
          return [];
        }
        console.log(`    C2: happy_soft → happy_big @ ${target.pose}`);
        segments.push(toHappyBig);
      } else {
        console.error(`❌ Cannot route from neutral to ${target.expr} @ ${target.pose}`);
        return [];
      }
    } else {
      console.log(`  Step C: neutral → ${target.expr} @ ${target.pose}`);
      segments.push(fromNeutral);
    }
  }

  console.log(`✅ Route complete: ${segments.length} segment(s)`);
  return segments;
}

