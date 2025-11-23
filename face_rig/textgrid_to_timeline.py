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


def parse_textgrid(filepath: Path) -> Tuple[List[Tuple[float, float, str]], List[Tuple[float, float, str]]]:
    """
    Parse a TextGrid file and extract word and phoneme intervals.
    
    Returns:
        Tuple of (words, phonemes) where each is a list of (start_time, end_time, text) tuples in seconds
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the words tier
    words_tier_match = re.search(
        r'name = "words".*?intervals: size = (\d+)(.*?)(?=item \[|$)',
        content,
        re.DOTALL
    )
    
    words = []
    if words_tier_match:
        tier_content = words_tier_match.group(2)
        interval_pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "([^"]*)"'
        intervals = re.findall(interval_pattern, tier_content)
        
        for xmin, xmax, text in intervals:
            if text.strip():  # Skip empty intervals
                words.append((float(xmin), float(xmax), text.strip()))
    
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
    
    return words, phonemes


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


def create_timeline_from_words(
    words: List[Tuple[float, float, str]],
    phonemes: List[Tuple[float, float, str]],
    transition_duration_ms: int = 500,
    cooldown_ms: int = 0,
    return_to_expr: str = "neutral"
) -> Dict:
    """
    Create a keyframe timeline using first phoneme of each word.
    
    This is less frantic than animating every phoneme - we just find the
    first vowel phoneme in each word and hold it for the word duration,
    then return to the emotion that was active before the word.
    
    Args:
        words: List of (start_time, end_time, word_text) tuples
        phonemes: List of (start_time, end_time, phoneme) tuples
        transition_duration_ms: Transition time (default 500ms)
        return_to_expr: Expression to return to after each word (default "neutral")
    
    Returns:
        Timeline dictionary with keyframes
    """
    keyframes = []
    base_expr = return_to_expr  # The emotion to return to after each word
    
    for word_start, word_end, word_text in words:
        # Find all phonemes within this word's time range
        word_phonemes = [
            (start, end, ph) for start, end, ph in phonemes
            if start >= word_start and start < word_end
        ]
        
        if not word_phonemes:
            continue
        
        # Find the first vowel phoneme in the word (skip consonants at the beginning)
        target_expr = None
        first_phoneme = None
        
        for start, end, ph in word_phonemes:
            expr = phoneme_to_expression(ph)
            if expr != "neutral":  # Found a vowel
                target_expr = expr
                first_phoneme = ph
                break
        
        # If no vowel found, use the first phoneme (even if consonant)
        if target_expr is None and word_phonemes:
            start, end, first_phoneme = word_phonemes[0]
            target_expr = phoneme_to_expression(first_phoneme)
        
        # Add keyframe for the speaking expression at word start
        if target_expr:
            word_start_ms = int(word_start * 1000)
            word_end_ms = int(word_end * 1000)
            word_duration_ms = word_end_ms - word_start_ms
            
            # Quick transition to speaking shape
            speak_transition = min(150, word_duration_ms // 3)
            
            keyframes.append({
                "time_ms": word_start_ms,
                "target_expr": target_expr,
                "target_pose": "center",
                "transition_duration_ms": speak_transition,
                "phoneme": f"{word_text} ({first_phoneme})",
            })
            
            # Relax back to base expression near end of word
            # Leave buffer time for relax to complete before next word
            relax_duration = 100  # ms for mouth to relax
            relax_buffer = 30     # ms buffer after relax completes
            relax_time_ms = max(word_start_ms + speak_transition + 50, word_end_ms - relax_duration - relax_buffer)
            
            keyframes.append({
                "time_ms": relax_time_ms,
                "target_expr": base_expr,
                "target_pose": "center",
                "transition_duration_ms": relax_duration,
                "phoneme": f"(relax)",
            })
    
    timeline = {
        "id": f"word_animation_{int(words[0][0]*1000) if words else 0}",
        "keyframes": keyframes,
        "total_duration_ms": int(words[-1][1] * 1000) if words else 0,
    }
    
    return timeline


def create_timeline(
    phonemes: List[Tuple[float, float, str]],
    transition_duration_ms: int = 500,  # Long smooth transitions for lip-sync
    min_transition_ms: int = None,      # Ignored
    max_transition_ms: int = None,      # Ignored
    cooldown_ms: int = 0                # Minimum time between transitions (default: 0ms)
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
    
    # Don't add automatic neutral transition at end
    # Let the expression timeline control the ending
    
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
    parser.add_argument("--transition", type=int, default=500, help="Transition duration in ms (default: 500)")
    parser.add_argument("--mode", choices=["words", "phonemes"], default="words", 
                        help="Animation mode: 'words' (first vowel per word, less frantic) or 'phonemes' (every phoneme with cooldown)")
    parser.add_argument("--cooldown", type=int, default=0, help="Minimum time between transitions in ms (phonemes mode only, default: 0)")
    parser.add_argument("--min-transition", type=int, default=80, help="(Ignored, kept for compatibility)")
    parser.add_argument("--max-transition", type=int, default=200, help="(Ignored, kept for compatibility)")
    
    args = parser.parse_args()
    
    input_path = args.textgrid
    output_path = args.output if args.output else input_path.with_suffix('.timeline.json')
    
    print(f"📖 Reading TextGrid: {input_path}")
    words, phonemes = parse_textgrid(input_path)
    print(f"✅ Found {len(words)} words, {len(phonemes)} phonemes")
    
    print(f"\n🎬 Creating animation timeline...")
    print(f"   Mode: {args.mode}")
    print(f"   Transition: {args.transition}ms")
    
    if args.mode == "words":
        print(f"   Strategy: First vowel phoneme of each word (less frantic)")
        timeline = create_timeline_from_words(
            words,
            phonemes,
            transition_duration_ms=args.transition
        )
    else:
        print(f"   Strategy: Every phoneme with {args.cooldown}ms cooldown")
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

