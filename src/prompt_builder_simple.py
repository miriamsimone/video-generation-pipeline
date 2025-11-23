"""Simplified prompt builder for video generation models.

Video generation models prefer shorter, simpler prompts than LLMs.
This module creates concise prompts suitable for models like minimax/video-01.
"""

from typing import Optional
from .models import ChunkData


def build_simple_video_prompt(
    global_style: str,
    chunk: ChunkData,
    max_length: int = 500,
) -> str:
    """
    Build a simplified, concise prompt for video generation.
    
    Video models work better with short, direct descriptions rather than
    detailed timelines. This creates a single cohesive description.

    Args:
        global_style: Global visual style description
        chunk: The chunk data with keyframes
        max_length: Maximum prompt length in characters

    Returns:
        A concise text prompt suitable for video generation
    """
    # Start with style
    prompt_parts = [global_style]
    
    # Get all keyframe descriptions
    sorted_keyframes = sorted(
        chunk.keyframes.items(),
        key=lambda x: int(x[0])
    )
    
    if not sorted_keyframes:
        return global_style[:max_length]
    
    # Take the first and last keyframes for start/end states
    first_time, first_desc = sorted_keyframes[0]
    
    if len(sorted_keyframes) == 1:
        # Only one keyframe - just use that
        prompt_parts.append(first_desc)
    else:
        # Multiple keyframes - describe the transition
        last_time, last_desc = sorted_keyframes[-1]
        
        # Create a flow description
        prompt_parts.append(f"Starting with: {first_desc}")
        
        # Add key middle actions if there are any
        if len(sorted_keyframes) > 2:
            middle_actions = []
            for time_ms, desc in sorted_keyframes[1:-1]:
                # Extract action words (verbs) from description
                # This is a simple heuristic - take first sentence
                action = desc.split('.')[0] if '.' in desc else desc
                if len(action) < 100:  # Only if it's concise
                    middle_actions.append(action)
            
            if middle_actions:
                # Take at most 2 middle actions
                for action in middle_actions[:2]:
                    prompt_parts.append(f"Then: {action}")
        
        prompt_parts.append(f"Ending with: {last_desc}")
    
    # Join and trim to max length
    full_prompt = ". ".join(prompt_parts)
    
    if len(full_prompt) > max_length:
        # Truncate and add ellipsis
        full_prompt = full_prompt[:max_length-3] + "..."
    
    return full_prompt


def build_super_simple_prompt(
    chunk: ChunkData,
    max_length: int = 200,
) -> str:
    """
    Build an extremely simple prompt - just the key action.
    
    For models that really prefer brevity.

    Args:
        chunk: The chunk data with keyframes
        max_length: Maximum prompt length

    Returns:
        Very concise prompt
    """
    sorted_keyframes = sorted(
        chunk.keyframes.items(),
        key=lambda x: int(x[0])
    )
    
    if not sorted_keyframes:
        return "An animated sequence"
    
    # Just use the first keyframe as the base
    _, first_desc = sorted_keyframes[0]
    
    # If there's progression, mention it
    if len(sorted_keyframes) > 1:
        _, last_desc = sorted_keyframes[-1]
        prompt = f"{first_desc}. Animated sequence progressing smoothly."
    else:
        prompt = first_desc
    
    return prompt[:max_length]



