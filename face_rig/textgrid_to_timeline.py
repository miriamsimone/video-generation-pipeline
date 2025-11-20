#!/usr/bin/env python3
"""
Convert TextGrid phoneme alignments to animation keyframe timeline.

Usage:
    python textgrid_to_timeline.py aligned/my_clip.TextGrid output_timeline.json
"""

import re
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple


# Map ARPABET phonemes to expressions
# ARPABET reference: https://en.wikipedia.org/wiki/ARPABET
PHONEME_TO_EXPRESSION = {
    # AH sounds (open mouth, relaxed)
    "AH0": "speaking_ah",
    "AH1": "speaking_ah",
    "AH2": "speaking_ah",
    "AA0": "speaking_ah",
    "AA1": "speaking_ah",
    "AA2": "speaking_ah",
    "AO0": "speaking_ah",
    "AO1": "speaking_ah",
    "AO2": "speaking_ah",
    
    # EE sounds (wide smile, teeth showing)
    "IY0": "speaking_ee",
    "IY1": "speaking_ee",
    "IY2": "speaking_ee",
    "IH0": "speaking_ee",
    "IH1": "speaking_ee",
    "IH2": "speaking_ee",
    "EH0": "speaking_ee",
    "EH1": "speaking_ee",
    "EH2": "speaking_ee",
    "EY0": "speaking_ee",
    "EY1": "speaking_ee",
    "EY2": "speaking_ee",
    "AE0": "speaking_ee",
    "AE1": "speaking_ee",
    "AE2": "speaking_ee",
    "AY0": "speaking_ee",
    "AY1": "speaking_ee",
    "AY2": "speaking_ee",
    
    # OO/UW sounds (rounded lips)
    "UW0": "speaking_uw",
    "UW1": "speaking_uw",
    "UW2": "speaking_uw",
    "UH0": "speaking_uw",
    "UH1": "speaking_uw",
    "UH2": "speaking_uw",
    "OW0": "oh_round",
    "OW1": "oh_round",
    "OW2": "oh_round",
    "OY0": "oh_round",
    "OY1": "oh_round",
    "OY2": "oh_round",
    "AW0": "oh_round",
    "AW1": "oh_round",
    "AW2": "oh_round",
    
    # ER sounds (r-colored vowel)
    "ER0": "speaking_ah",
    "ER1": "speaking_ah",
    "ER2": "speaking_ah",
}

# All consonants and silence return to neutral
CONSONANTS = {
    "B", "CH", "D", "DH", "F", "G", "HH", "JH", "K", "L", "M", "N", 
    "NG", "P", "R", "S", "SH", "T", "TH", "V", "W", "Y", "Z", "ZH"
}


def parse_textgrid(filepath: Path) -> List[Tuple[float, float, str]]:
    """
    Parse a TextGrid file and extract phoneme intervals.
    
    Returns:
        List of (start_time, end_time, phoneme) tuples in seconds
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the phones tier
    phones_tier_match = re.search(
        r'name = "phones".*?intervals: size = (\d+)(.*?)(?=item \[|$)',
        content,
        re.DOTALL
    )
    
    if not phones_tier_match:
        raise ValueError("Could not find 'phones' tier in TextGrid")
    
    tier_content = phones_tier_match.group(2)
    
    # Extract all intervals
    interval_pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"'
    intervals = re.findall(interval_pattern, tier_content)
    
    phonemes = []
    for xmin, xmax, text in intervals:
        if text.strip():  # Skip empty intervals
            phonemes.append((float(xmin), float(xmax), text.strip()))
    
    return phonemes


def phoneme_to_expression(phoneme: str) -> str:
    """Convert a phoneme to an expression, defaulting to neutral for consonants."""
    # Remove stress markers for lookup
    base_phoneme = phoneme.rstrip('012')
    
    if phoneme in PHONEME_TO_EXPRESSION:
        return PHONEME_TO_EXPRESSION[phoneme]
    elif base_phoneme in CONSONANTS:
        return "neutral"
    else:
        # Unknown phoneme, default to neutral
        print(f"Warning: Unknown phoneme '{phoneme}', using neutral")
        return "neutral"


def is_vowel(phoneme: str) -> bool:
    """Check if a phoneme is a vowel (has an expression other than neutral)."""
    expr = phoneme_to_expression(phoneme)
    return expr != "neutral"


def create_timeline(
    phonemes: List[Tuple[float, float, str]],
    transition_duration_ms: int = 500,  # Long smooth transitions for lip-sync
    min_transition_ms: int = None,      # Ignored
    max_transition_ms: int = None,      # Ignored
    cooldown_ms: int = 175              # Minimum time between transitions (default: 175ms)
) -> Dict:
    """
    Create a keyframe timeline from phoneme alignments.
    
    Transitions START at the phoneme timing and play through the duration
    of the phoneme, syncing the visual change with the audio.
    
    Cooldown prevents rapid transitions: if a new phoneme occurs within
    cooldown_ms of the last keyframe, it's ignored for a less jarring
    experience.
    
    For example, with 500ms transition and 175ms cooldown:
    - Phoneme starts at 810ms
    - Transition starts at 810ms (right when sound plays)
    - Transition completes at 1310ms
    - Next transition must wait until 985ms (810 + 175)
    
    Consonants are conjoined with their following vowels.
    
    Args:
        phonemes: List of (start_time, end_time, phoneme) tuples
        transition_duration_ms: Transition time (default 500ms)
        cooldown_ms: Minimum time between keyframes (default 175ms)
    
    Returns:
        Timeline dictionary with keyframes
    """
    keyframes = []
    last_expr = "neutral"
    last_keyframe_arrival_ms = -cooldown_ms  # Allow first keyframe immediately
    i = 0
    
    while i < len(phonemes):
        start_s, end_s, phoneme = phonemes[i]
        start_ms = int(start_s * 1000)
        end_ms = int(end_s * 1000)
        
        expr = phoneme_to_expression(phoneme)
        
        # If this is a consonant (neutral), look ahead for a vowel
        if expr == "neutral" and i + 1 < len(phonemes):
            next_phoneme = phonemes[i + 1][2]
            next_expr = phoneme_to_expression(next_phoneme)
            
            # If next phoneme is a vowel, conjoin them
            if next_expr != "neutral":
                if next_expr != last_expr or i == 0:
                    # Check cooldown: has enough time passed since last keyframe?
                    time_since_last_arrival = start_ms - last_keyframe_arrival_ms
                    if time_since_last_arrival < cooldown_ms:
                        # Skip this transition - too soon after last one
                        i += 2
                        continue
                    
                    # Use fixed transition duration
                    adaptive_duration = transition_duration_ms
                    
                    # Start transition AT phoneme start for audio sync
                    keyframes.append({
                        "time_ms": start_ms,
                        "target_expr": next_expr,
                        "target_pose": "center",
                        "transition_duration_ms": adaptive_duration,
                        "phoneme": f"{phoneme}→{next_phoneme}",
                    })
                    last_expr = next_expr
                    last_keyframe_arrival_ms = start_ms  # Update cooldown timer
                
                # Skip the vowel phoneme since we already handled it
                i += 2
                continue
        
        # For vowels or standalone consonants, start transition early
        if expr != last_expr or i == 0:
            # Check cooldown: has enough time passed since last keyframe?
            time_since_last_arrival = start_ms - last_keyframe_arrival_ms
            if time_since_last_arrival < cooldown_ms:
                # Skip this transition - too soon after last one
                i += 1
                continue
            
            # Use fixed transition duration
            adaptive_duration = transition_duration_ms
            
            # Start transition AT phoneme start for audio sync
            keyframes.append({
                "time_ms": start_ms,
                "target_expr": expr,
                "target_pose": "center",
                "transition_duration_ms": adaptive_duration,
                "phoneme": phoneme,
            })
            
            last_expr = expr
            last_keyframe_arrival_ms = start_ms  # Update cooldown timer
        
        i += 1
    
    # Add final keyframe to return to neutral (if not already neutral)
    if phonemes and last_expr != "neutral":
        final_time_ms = int(phonemes[-1][1] * 1000)
        # Start transition at end of speech
        keyframes.append({
            "time_ms": final_time_ms,
            "target_expr": "neutral",
            "target_pose": "center",
            "transition_duration_ms": 300,
            "phoneme": "",
        })
    
    timeline = {
        "id": f"phoneme_animation_{int(phonemes[0][0]*1000) if phonemes else 0}",
        "keyframes": keyframes,
        "total_duration_ms": int(phonemes[-1][1] * 1000) if phonemes else 0,
    }
    
    return timeline


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convert TextGrid phoneme alignments to animation keyframe timeline"
    )
    parser.add_argument("textgrid", type=Path, help="Input TextGrid file")
    parser.add_argument("output", type=Path, nargs='?', help="Output JSON file (default: input.timeline.json)")
    parser.add_argument("--transition", type=int, default=500, help="Transition duration in ms - starts AT phoneme (default: 500)")
    parser.add_argument("--cooldown", type=int, default=175, help="Minimum time between transitions in ms (default: 175)")
    parser.add_argument("--min-transition", type=int, default=80, help="(Ignored, kept for compatibility)")
    parser.add_argument("--max-transition", type=int, default=200, help="(Ignored, kept for compatibility)")
    
    args = parser.parse_args()
    
    input_path = args.textgrid
    output_path = args.output if args.output else input_path.with_suffix('.timeline.json')
    
    print(f"📖 Reading TextGrid: {input_path}")
    phonemes = parse_textgrid(input_path)
    print(f"✅ Found {len(phonemes)} phonemes")
    
    print(f"\n🎬 Creating animation timeline...")
    print(f"   Transition: {args.transition}ms (starts AT phoneme, synced with audio)")
    print(f"   Cooldown: {args.cooldown}ms (minimum time between transitions)")
    timeline = create_timeline(
        phonemes,
        transition_duration_ms=args.transition,
        min_transition_ms=args.min_transition,
        max_transition_ms=args.max_transition,
        cooldown_ms=args.cooldown
    )
    print(f"✅ Created {len(timeline['keyframes'])} keyframes")
    
    print(f"\n💾 Writing timeline: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(timeline, f, indent=2)
    
    print(f"✅ Done!")
    print(f"\n📊 Timeline stats:")
    print(f"   Duration: {timeline['total_duration_ms']/1000:.2f}s")
    print(f"   Keyframes: {len(timeline['keyframes'])}")
    
    # Show expression distribution
    expr_counts = {}
    for kf in timeline['keyframes']:
        expr = kf['target_expr']
        expr_counts[expr] = expr_counts.get(expr, 0) + 1
    
    print(f"\n🎭 Expression distribution:")
    for expr, count in sorted(expr_counts.items(), key=lambda x: -x[1]):
        print(f"   {expr}: {count}")
    
    print(f"\n💡 You can now paste this JSON into the Keyframe Player!")
    print(f"   Or use it programmatically via the API.")


if __name__ == "__main__":
    main()

