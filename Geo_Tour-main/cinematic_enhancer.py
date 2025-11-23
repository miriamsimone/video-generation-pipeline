"""
Cinematic Prompt Enhancer - Transforms basic visual descriptions into IMAX-style prompts

This module enriches scene visual descriptions with:
- Professional camera terminology
- Cinematic lighting and composition
- Scale and depth cues
- Dynamic framing that works for image-to-video generation
"""

import random
import json
from typing import Dict, List

class CinematicEnhancer:
    """Enhances visual descriptions with cinematic vocabulary and framing"""

    def __init__(self):
        # Camera shots optimized for static→video (work well with limited motion)
        self.establishing_shots = [
            "Ultra-wide establishing shot",
            "Sweeping aerial perspective",
            "Expansive wide-angle view",
            "Bird's eye establishing view"
        ]

        self.medium_shots = [
            "Medium shot with shallow depth of field",
            "Three-quarter view with environmental context",
            "Balanced medium composition"
        ]

        self.close_shots = [
            "Intimate close-up",
            "Macro detail shot",
            "Extreme close-up revealing texture"
        ]

        # Lighting conditions that add cinematic quality
        self.lighting_conditions = [
            "golden hour lighting with warm glow",
            "dramatic volumetric lighting with god rays",
            "soft diffused natural light",
            "high-contrast cinematic lighting",
            "backlit with rim lighting",
            "ambient atmospheric lighting"
        ]

        # Camera movements implied through composition (works for I2V)
        self.movement_implications = [
            "framed as if camera is slowly pushing in",
            "composed for gentle drift forward",
            "perspective suggesting gradual reveal",
            "framing implies subtle parallax motion",
            "composed for slow dolly movement",
            "staged for gentle tracking shot"
        ]

        # Depth and scale cues (critical for static images)
        self.depth_cues = [
            "with clear foreground, mid-ground, and background layers",
            "showing atmospheric depth and scale",
            "emphasizing vast scale through perspective",
            "with visible depth of field separation",
            "revealing epic proportions"
        ]

        # Atmosphere and mood enhancers
        self.atmosphere = [
            "cinematic color grading",
            "IMAX-quality detail and clarity",
            "photorealistic with rich textures",
            "epic documentary cinematography",
            "stunning visual spectacle"
        ]

        # Subject-specific enhancement patterns
        self.subject_patterns = {
            "geological": {
                "keywords": ["rock", "stone", "mountain", "canyon", "cliff", "volcano", "lava", "glacier", "cave", "crystal"],
                "enhancements": [
                    "revealing geological layers and deep time",
                    "showing ancient rock formations in sharp detail",
                    "emphasizing scale of geological features",
                    "capturing primordial landscape"
                ]
            },
            "nature": {
                "keywords": ["forest", "tree", "jungle", "canopy", "wildlife", "animal", "plant", "flower", "meadow"],
                "enhancements": [
                    "capturing biodiversity and natural beauty",
                    "revealing lush ecosystem details",
                    "emphasizing organic textures and life",
                    "showcasing pristine wilderness"
                ]
            },
            "water": {
                "keywords": ["water", "ocean", "sea", "river", "lake", "wave", "rain", "waterfall", "ice"],
                "enhancements": [
                    "showing water dynamics and flow",
                    "capturing fluid motion and reflections",
                    "emphasizing aquatic environment",
                    "revealing underwater details"
                ]
            },
            "atmospheric": {
                "keywords": ["sky", "cloud", "storm", "aurora", "sunset", "sunrise", "star", "galaxy", "space"],
                "enhancements": [
                    "capturing atmospheric phenomena",
                    "showing celestial grandeur",
                    "emphasizing cosmic scale",
                    "revealing sky dynamics"
                ]
            },
            "planetary": {
                "keywords": ["planet", "mars", "moon", "crater", "terrain", "surface", "solar", "orbital"],
                "enhancements": [
                    "revealing planetary scale and features",
                    "showing extraterrestrial landscape",
                    "emphasizing alien terrain",
                    "capturing otherworldly atmosphere"
                ]
            }
        }

    def detect_subject_type(self, description: str) -> str:
        """Detect the primary subject type from description"""
        description_lower = description.lower()

        # Count keyword matches for each category
        matches = {}
        for category, data in self.subject_patterns.items():
            count = sum(1 for keyword in data["keywords"] if keyword in description_lower)
            if count > 0:
                matches[category] = count

        # Return category with most matches, or "general" if none
        if matches:
            return max(matches, key=matches.get)
        return "general"

    def determine_shot_type(self, description: str, scene_number: int, total_scenes: int) -> str:
        """Intelligently select shot type based on description and position"""
        description_lower = description.lower()

        # First scene often establishes context
        if scene_number == 1:
            return random.choice(self.establishing_shots)

        # Look for scale indicators
        if any(word in description_lower for word in ["vast", "expansive", "entire", "whole", "landscape", "panorama"]):
            return random.choice(self.establishing_shots)

        # Look for detail indicators
        if any(word in description_lower for word in ["detail", "texture", "close", "specific", "individual", "single"]):
            return random.choice(self.close_shots)

        # Default to medium shots for balanced composition
        return random.choice(self.medium_shots)

    def enhance_description(self, description: str, scene_number: int, total_scenes: int, 
                          original_user_prompt: str = "") -> str:
        """
        Transform basic visual description into cinematic prompt

        Args:
            description: Original visual description from scene planner
            scene_number: Current scene number (1-indexed)
            total_scenes: Total number of scenes
            original_user_prompt: Original user request for context

        Returns:
            Enhanced cinematic description
        """
        # Detect subject matter
        subject_type = self.detect_subject_type(description)

        # Select appropriate shot type
        shot_type = self.determine_shot_type(description, scene_number, total_scenes)

        # Select lighting (consistent with subject and scene position)
        lighting = random.choice(self.lighting_conditions)

        # Add depth cues (important for I2V motion)
        depth = random.choice(self.depth_cues)

        # Add movement implication (helps I2V understand desired motion)
        movement = random.choice(self.movement_implications)

        # Add atmosphere
        atmosphere = random.choice(self.atmosphere)

        # Get subject-specific enhancement if available
        subject_enhancement = ""
        if subject_type in self.subject_patterns:
            subject_enhancement = random.choice(self.subject_patterns[subject_type]["enhancements"])

        # Build enhanced prompt
        enhanced = f"{shot_type} of {description}"

        # Add enhancements
        enhanced += f", {lighting}"

        if subject_enhancement:
            enhanced += f", {subject_enhancement}"

        enhanced += f", {depth}"
        enhanced += f", {movement}"
        enhanced += f". {atmosphere}, 16:9 cinematic composition"

        return enhanced

    def enhance_scene_plan(self, scene_plan: Dict, original_user_prompt: str = "") -> Dict:
        """
        Enhance all scenes in a scene plan

        Args:
            scene_plan: Scene plan dict with 'scenes' list
            original_user_prompt: Original user request

        Returns:
            Enhanced scene plan with cinematic visual descriptions
        """
        if "scenes" not in scene_plan:
            raise ValueError("Scene plan must contain 'scenes' key")

        enhanced_plan = scene_plan.copy()
        total_scenes = len(scene_plan["scenes"])

        for i, scene in enumerate(enhanced_plan["scenes"]):
            original_desc = scene["visual_description"]
            scene_num = scene["scene_number"]

            # Create enhanced description
            enhanced_desc = self.enhance_description(
                original_desc, 
                scene_num, 
                total_scenes,
                original_user_prompt
            )

            # Store both for reference
            scene["original_visual_description"] = original_desc
            scene["visual_description"] = enhanced_desc

        return enhanced_plan


# Utility functions for integration
def enhance_for_storyboard(visual_description: str, scene_number: int = 1, 
                          total_scenes: int = 1) -> str:
    """Quick function to enhance a single visual description"""
    enhancer = CinematicEnhancer()
    return enhancer.enhance_description(visual_description, scene_number, total_scenes)


def enhance_scene_plan_quick(scene_plan: Dict) -> Dict:
    """Quick function to enhance an entire scene plan"""
    enhancer = CinematicEnhancer()
    return enhancer.enhance_scene_plan(scene_plan)


if __name__ == "__main__":
    # Test the enhancer
    enhancer = CinematicEnhancer()

    # Test basic description
    test_desc = "Sunlight passing through water droplets creating a rainbow"
    enhanced = enhancer.enhance_description(test_desc, 1, 3)
    print("Original:", test_desc)
    print("Enhanced:", enhanced)
    print()

    # Test with geological content
    geo_desc = "Ancient rock layers exposed in the Grand Canyon walls"
    geo_enhanced = enhancer.enhance_description(geo_desc, 2, 3)
    print("Geological Original:", geo_desc)
    print("Geological Enhanced:", geo_enhanced)
    print()

    # Test scene plan enhancement
    test_plan = {
        "scenes": [
            {
                "scene_number": 1,
                "narration": "Water droplets form in the atmosphere",
                "visual_description": "Microscopic water droplets floating in air",
                "duration": 6
            },
            {
                "scene_number": 2,
                "narration": "Light refracts through the droplets",
                "visual_description": "Sunlight beam entering a water droplet and separating into colors",
                "duration": 6
            }
        ]
    }

    enhanced_plan = enhancer.enhance_scene_plan(test_plan, "Explain how rainbows form")
    print("Enhanced Scene Plan:")
    print(json.dumps(enhanced_plan, indent=2))
