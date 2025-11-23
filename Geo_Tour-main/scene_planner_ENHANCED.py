"""
Scene planning module - breaks scripts into visual scenes
ENHANCED with automatic cinematic prompting
"""

from openai import OpenAI
import json
from config import OPENAI_API_KEY, OPENAI_MODEL, SCENE_MAX_TOKENS, TARGET_SCENES
from system_prompts import CinematicSystemPrompts

# ADDED: Import cinematic enhancer
from cinematic_enhancer import CinematicEnhancer

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        pass

class ScenePlanner:
    def __init__(self, api_key=None, use_cinematic_enhancement=True):
        """
        Initialize scene planner

        Args:
            api_key: OpenAI API key
            use_cinematic_enhancement: If True, automatically enhance visual 
                                      descriptions with cinematic vocabulary
        """
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        self.client = OpenAI(api_key=self.api_key)

        # ADDED: Cinematic enhancement
        self.use_cinematic_enhancement = use_cinematic_enhancement
        self.cinematic_enhancer = CinematicEnhancer() if use_cinematic_enhancement else None

    def create_plan(self, script_data, target_scenes=None, scene_duration=None):
        """
        Create a scene-by-scene plan from script

        Args:
            script_data (dict): Script with title and narration
            target_scenes (int): Number of scenes to create
            scene_duration (int): Duration per scene in seconds

        Returns:
            dict: Scene plan with visual descriptions and timing
        """
        safe_print("🎬 Creating scene plan...")

        ts = target_scenes or TARGET_SCENES
        sd = scene_duration or 6
        if sd > 12:
            sd = 12

        prompt = f"""Break this video script into {ts} scenes with detailed visual descriptions.

Title: {script_data['title']}
Script: {script_data['script']}

Return ONLY a JSON object with this structure:
{{
  "scenes": [
    {{
      "scene_number": 1,
      "narration": "portion of script for this scene",
      "visual_description": "detailed description of visuals to generate - be specific about what should be shown",
      "duration": {sd}
    }}
  ]
}}

Each scene should be {sd} seconds. Visual descriptions should be detailed and suitable for AI image/video generation.
DO NOT include any text outside the JSON."""

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=SCENE_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": CinematicSystemPrompts.get_scene_planning_prompt()},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            # Parse response
            plan_text = response.choices[0].message.content.strip()
            scene_plan = json.loads(plan_text)

            # Validate structure
            if "scenes" not in scene_plan or not scene_plan["scenes"]:
                raise ValueError("Invalid scene plan structure")

            for scene in scene_plan["scenes"]:
                required_fields = ["scene_number", "narration", "visual_description", "duration"]
                if not all(field in scene for field in required_fields):
                    raise ValueError(f"Scene missing required fields: {scene}")

                try:
                    scene["duration"] = sd
                except Exception:
                    pass

            safe_print(f"✅ Created {len(scene_plan['scenes'])} scenes")

            # ADDED: Apply cinematic enhancement
            if self.use_cinematic_enhancement and self.cinematic_enhancer:
                safe_print("🎥 Enhancing scenes with cinematic prompting...")
                scene_plan = self.cinematic_enhancer.enhance_scene_plan(
                    scene_plan, 
                    original_user_prompt=script_data.get('title', '')
                )
                safe_print("✅ Cinematic enhancement applied to all scenes")

            return scene_plan

        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse scene plan: {e}")
        except Exception as e:
            raise RuntimeError(f"Scene planning failed: {e}")


if __name__ == "__main__":
    # Test the enhanced scene planner
    planner = ScenePlanner(use_cinematic_enhancement=True)

    test_script = {
        "title": "How Rainbows Form",
        "script": "Rainbows appear when sunlight passes through water droplets in the air. The light bends and separates into different colors, creating the beautiful arc we see in the sky."
    }

    plan = planner.create_plan(test_script)

    print("\n" + "="*60)
    print("ENHANCED SCENE PLAN OUTPUT")
    print("="*60)
    print(json.dumps(plan, indent=2))
