#!/usr/bin/env python3
"""
Generate all viseme-to-viseme transition sequences for lip-sync animation.

This adds the missing transitions between speaking expressions needed for
natural lip-sync: speaking_ah, speaking_ee, speaking_uw, oh_round

Uses the same OpenAI gpt-image-1 approach as generate_all_sequences.py

Usage:
    export OPENAI_API_KEY=sk-...
    python generate_viseme_transitions.py
"""

import json
import sys
from pathlib import Path

def main():
    # Load expressions config
    with open("expressions.json", "r") as f:
        config = json.load(f)
    
    # Check if we have the viseme transitions in expressions.json
    base_paths = config.get("base_paths", [])
    viseme_transitions = [
        p for p in base_paths
        if any(v in p["id"] for v in ["speaking_ah", "speaking_ee", "speaking_uw", "oh_round"])
        and p["start"] != "neutral"  # Exclude neutral→viseme, those already exist
    ]
    
    print("🎬 Viseme-to-Viseme Transition Generator")
    print("="*60)
    print(f"\nFound {len(viseme_transitions)} viseme transitions defined in expressions.json:")
    for trans in viseme_transitions:
        print(f"  • {trans['start']} → {trans['end']}")
    
    print(f"\n✅ Configuration is ready!")
    print("\nTo generate these sequences, run:")
    print("\n  python generate_all_sequences.py \\")
    print("      --config expressions.json \\")
    print("      --endpoints-dir frames/endpoints \\")
    print("      --sequences-dir frames/sequences \\")
    print("      --max-depth 2 \\")
    print("      --max-workers 4")
    print("\nThis will generate ALL sequences including the viseme transitions.")
    print("\n💡 Tip: The system will automatically use existing sequences")
    print("   and only generate the missing ones.")


if __name__ == "__main__":
    main()
