"""
Script generation module - converts user prompts into video scripts
"""
from openai import OpenAI
import json
from config import OPENAI_API_KEY, OPENAI_MODEL, SCRIPT_MAX_TOKENS
from system_prompts import CinematicSystemPrompts

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except (IOError, OSError, ValueError):
        pass


class ScriptGenerator:
    def __init__(self, api_key=None):
        self.api_key = api_key or OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        self.client = OpenAI(api_key=self.api_key)
    
    def generate(self, user_prompt):
        """
        Generate a video script from user prompt
        
        Args:
            user_prompt (str): User's description of desired video
            
        Returns:
            dict: Script data with title and full narration
        """
        safe_print("📝 Generating script...")
        
        prompt = f"""Create a short video script (30-60 seconds) based on this prompt: {user_prompt}

Return ONLY a JSON object with this structure:
{{
    "title": "engaging video title",
    "script": "complete narration script that flows naturally"
}}

Make the script engaging and suitable for narration. DO NOT include any text outside the JSON."""

        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                max_tokens=SCRIPT_MAX_TOKENS,
                messages=[
                    {"role": "system", "content": CinematicSystemPrompts.get_script_generation_prompt()},
                    {"role": "user", "content": CinematicSystemPrompts.get_enhanced_user_prompt_wrapper(user_prompt)}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse response
            script_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON if there's extra text
            if script_text.startswith("```json"):
                script_text = script_text.replace("```json", "").replace("```", "").strip()
            elif script_text.startswith("```"):
                script_text = script_text.replace("```", "").strip()
            
            script_data = json.loads(script_text)
            
            # Validate structure
            if "title" not in script_data or "script" not in script_data:
                safe_print(f"❌ Invalid script structure. Received keys: {list(script_data.keys())}")
                safe_print(f"Response preview: {script_text[:200]}...")
                raise ValueError(f"Invalid script structure returned. Expected 'title' and 'script' fields, but got: {list(script_data.keys())}")
            
            # Validate that fields are not empty
            if not script_data.get("title") or not script_data.get("script"):
                raise ValueError("Script structure is valid but 'title' or 'script' field is empty")
            
            safe_print(f"✅ Script generated: '{script_data['title']}'")
            return script_data
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse script response: {e}")
        except Exception as e:
            raise RuntimeError(f"Script generation failed: {e}")


if __name__ == "__main__":
    # Test the script generator
    generator = ScriptGenerator()
    script = generator.generate("Explain how rainbows form")
    print(json.dumps(script, indent=2))
