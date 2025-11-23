"""
Enhanced System Prompts for Cinematic Video Generation
Reduces AI hallucinations and increases visual quality through better initial guidance
"""

class CinematicSystemPrompts:
    """
    Optimized system prompts for each stage of video generation pipeline
    Designed to work WITH cinematic enhancer for maximum quality
    """

    @staticmethod
    def get_script_generation_prompt():
        """
        System prompt for script generator (script_generator.py)
        Goals:
        - Accurate, fact-based content
        - Visual-friendly descriptions
        - Natural narrative flow
        - Avoid abstract concepts that can't be visualized
        """
        return """You are an expert documentary scriptwriter specializing in visual storytelling.

CRITICAL RULES:
1. ACCURACY: Only include factually accurate information. If uncertain, stay general rather than specific.
2. VISUAL FOCUS: Every sentence should describe something that CAN BE SHOWN visually
3. CONCRETE OVER ABSTRACT: Prefer tangible objects/phenomena over abstract concepts
4. NO HALLUCINATIONS: Do not invent specific numbers, dates, or technical details unless they are well-established facts
5. NATURAL LANGUAGE: Write for spoken narration, conversational but authoritative tone

STRUCTURE GUIDELINES:
- Start with a clear, engaging hook
- Build narrative momentum through concrete examples
- Use present tense for timeless phenomena ("Water flows..." not "Water flowed...")
- End with satisfying conclusion or broader context

VISUAL STORYTELLING TIPS:
- Describe specific scenes, not general concepts
- Include scale references (comparative size, time periods)
- Mention colors, textures, movements when relevant
- Set clear locations/contexts for each idea

AVOID:
- Technical jargon without visual equivalent
- Abstract philosophical concepts
- Statistics without visual representation
- Made-up specific numbers or dates
- Statements that begin "Scientists believe..." (show the evidence instead)

Your script should be 30-60 seconds of narration that flows naturally and can be fully visualized.

OUTPUT FORMAT - REQUIRED JSON STRUCTURE:
You MUST return a JSON object with exactly this structure:
{
    "title": "engaging video title (string)",
    "script": "complete narration script that flows naturally (string)"
}

The "title" field should be a short, engaging title for the video.
The "script" field should contain the full narration text (30-60 seconds when spoken).

Return ONLY the JSON object, no other text."""

    @staticmethod
    def get_scene_planning_prompt():
        """
        System prompt for scene planner (scene_planner.py)
        Goals:
        - Specific, filmable visual descriptions
        - Avoid vague or impossible-to-generate scenes
        - Include concrete visual elements
        - Progression from establishing to detail shots
        """
        return """You are an expert documentary scene planner working with AI video generation tools.

CRITICAL RULES FOR VISUAL DESCRIPTIONS:
1. BE SPECIFIC: Describe exactly what should be visible in frame
2. CONCRETE OBJECTS: Name specific objects, not abstract concepts
3. REALISTIC SCENES: Only describe scenes that could actually be filmed or rendered
4. AVOID IMPOSSIBLE SHOTS: No "inside a single atom" or "the beginning of time"
5. SCALE APPROPRIATENESS: Match scale to what's visually comprehensible

SCENE DESCRIPTION BEST PRACTICES:
✓ "Volcanic crater with glowing molten lava, steam rising, dark rock formations surrounding the opening"
✗ "The concept of geological time represented visually"

✓ "Cross-section view of Earth's layers showing crust, mantle, and core with distinct colors"
✗ "Understanding of planetary formation dynamics"

✓ "Water droplets suspended in air, sunlight passing through creating rainbow spectrum"
✗ "The physics of light refraction explained visually"

VISUAL ELEMENTS TO INCLUDE:
- Specific objects/subjects (mountain, ocean, cell, crystal, etc.)
- Colors and textures (red rocks, crystalline ice, flowing water)
- Action/movement (erupting, flowing, rotating, growing)
- Environment/setting (canyon landscape, underwater reef, forest canopy)
- Lighting conditions (sunlit, shadowed, glowing, illuminated)
- Scale references when relevant (towering, microscopic, expansive)

SCENE PROGRESSION:
- Scene 1: Usually establishing/context shot (wide view)
- Middle scenes: Mix of medium and detail shots showing key concepts
- Final scene: Often broader context or conclusion (return to wide or meaningful close-up)

AVOID IN DESCRIPTIONS:
✗ Abstract concepts ("the meaning of evolution")
✗ Impossible perspectives ("view from inside a quark")
✗ Text/labels requirements ("showing labeled diagram")
✗ Cartoon/illustration style (aim for photorealistic unless specifically requested)
✗ Multiple disconnected elements in one scene
✗ Time-lapse spanning billions of years (unless explicitly about geological time)

HALLUCINATION PREVENTION:
- Don't invent specific scientific details not in the script
- Don't add technical specifications unless provided
- Keep descriptions grounded in observable reality
- If script mentions "ancient rocks," describe visible rock formations, not "3.5 billion year old specimens"

Each visual description should be 1-2 sentences of clear, specific, filmable content. Your output must be a single, valid JSON object."""

    @staticmethod
    def get_user_prompt_guidance():
        """
        Guidance to show users for creating better prompts
        This can be displayed in your UI as helper text
        """
        return """
🎬 TIPS FOR GREAT VIDEO PROMPTS

FOR BEST RESULTS:

✅ Be Specific About Subject:
   Good: "Explain how volcanic eruptions form new islands"
   Avoid: "Show stuff about volcanoes"

✅ Use Concrete Topics:
   Good: "Life cycle of a monarch butterfly"
   Avoid: "The concept of transformation in nature"

✅ Mention Key Visual Elements:
   Good: "Mars surface features including Olympus Mons volcano and Valles Marineris canyon"
   Avoid: "Mars geology"

✅ Indicate Desired Tone (Optional):
   - "Educational documentary style"
   - "Awe-inspiring nature footage"
   - "Scientific exploration"

✅ Specify Audience Level (Optional):
   - "For middle school students"
   - "Advanced planetary science"
   - "General audience"

❌ AVOID:
   • Extremely abstract concepts
   • Requests for text/labels/diagrams
   • Impossible perspectives ("inside an electron")
   • Mixing too many unrelated topics
   • Very long, complex prompts (keep under 100 words)

EXAMPLES OF GREAT PROMPTS:
• "How rainbows form when sunlight passes through water droplets"
• "The water cycle from ocean evaporation to rainfall"
• "Formation of the Grand Canyon through millions of years of erosion"
• "Coral reef ecosystem showing symbiotic relationships"
• "Phases of the moon and how they occur"
"""

    @staticmethod
    def get_enhanced_user_prompt_wrapper(user_prompt: str) -> str:
        """
        Wraps user prompt with additional context to improve generation
        Use this to preprocess user input before sending to script generator

        Args:
            user_prompt: Raw user input

        Returns:
            Enhanced prompt with guidance
        """
        return f"""Create a visually-focused documentary video script about: {user_prompt}

IMPORTANT REQUIREMENTS:
- Focus on concrete, observable phenomena that can be visualized
- Use specific examples rather than abstract concepts
- Describe scenes that could be filmed or realistically rendered
- Maintain scientific accuracy - no invented facts or hallucinated details
- Structure content to build visual narrative momentum
- Ensure every statement has a clear visual representation

Create a compelling 30-60 second narration script.

Return your response as a JSON object with this exact structure:
{{
    "title": "engaging video title",
    "script": "complete narration script text"
}}"""


class HallucinationPrevention:
    """
    Utilities to detect and prevent common AI hallucinations in video generation
    """

    # Red flags that often indicate hallucinations or problematic content
    HALLUCINATION_INDICATORS = [
        # Overly specific fake data
        "exactly",
        "precisely",
        # Impossible perspectives
        "inside a single atom",
        "at the moment of the Big Bang",
        "view from inside a black hole",
        # Abstract non-visual concepts
        "the concept of",
        "the idea of",
        "symbolizing",
        "representing the theory",
        # Text/diagram requirements
        "labeled diagram",
        "showing text",
        "with annotations",
        "displaying numbers",
        # Speculation presented as fact
        "will definitely",
        "proves that",
        "scientists discovered last week"  # Likely hallucinated recent "discoveries"
    ]

    VAGUE_DESCRIPTIONS = [
        "various things",
        "different elements",
        "multiple aspects",
        "some features",
        "certain characteristics"
    ]

    @staticmethod
    def check_for_hallucinations(text: str) -> dict:
        """
        Analyze text for potential hallucination indicators

        Returns:
            dict with 'warnings' list and 'risk_level' (low/medium/high)
        """
        warnings = []
        text_lower = text.lower()

        # Check for hallucination indicators
        for indicator in HallucinationPrevention.HALLUCINATION_INDICATORS:
            if indicator in text_lower:
                warnings.append(f"Potential hallucination: '{indicator}' detected")

        # Check for vague descriptions
        for vague in HallucinationPrevention.VAGUE_DESCRIPTIONS:
            if vague in text_lower:
                warnings.append(f"Vague description: '{vague}' - be more specific")

        # Determine risk level
        if len(warnings) == 0:
            risk_level = "low"
        elif len(warnings) <= 2:
            risk_level = "medium"
        else:
            risk_level = "high"

        return {
            "warnings": warnings,
            "risk_level": risk_level,
            "safe": len(warnings) == 0
        }

    @staticmethod
    def suggest_improvements(visual_description: str) -> list:
        """
        Suggest improvements for visual descriptions
        """
        suggestions = []
        desc_lower = visual_description.lower()

        # Check for concrete nouns
        concrete_indicators = ["rock", "water", "mountain", "tree", "cloud", "ocean", 
                              "crystal", "lava", "ice", "canyon", "forest", "crater"]
        has_concrete = any(word in desc_lower for word in concrete_indicators)

        if not has_concrete:
            suggestions.append("Add specific objects or features (e.g., 'volcanic rocks', 'flowing water')")

        # Check for color mentions
        colors = ["red", "blue", "green", "yellow", "orange", "purple", "white", 
                 "black", "golden", "silver", "brown"]
        has_color = any(color in desc_lower for color in colors)

        if not has_color:
            suggestions.append("Consider adding color descriptions for visual richness")

        # Check for action/movement
        movements = ["flowing", "erupting", "rotating", "growing", "falling", "rising",
                    "moving", "swirling", "cascading", "drifting"]
        has_movement = any(move in desc_lower for move in movements)

        if not has_movement:
            suggestions.append("Add dynamic elements or movement for engaging visuals")

        # Check length
        word_count = len(visual_description.split())
        if word_count < 5:
            suggestions.append("Description too brief - add more specific visual details")
        elif word_count > 30:
            suggestions.append("Description too long - focus on key visual elements")

        return suggestions


if __name__ == "__main__":
    # Test the system prompts
    prompts = CinematicSystemPrompts()

    print("="*70)
    print("SCRIPT GENERATION SYSTEM PROMPT")
    print("="*70)
    print(prompts.get_script_generation_prompt())
    print()

    print("="*70)
    print("SCENE PLANNING SYSTEM PROMPT")
    print("="*70)
    print(prompts.get_scene_planning_prompt())
    print()

    print("="*70)
    print("USER GUIDANCE")
    print("="*70)
    print(prompts.get_user_prompt_guidance())
    print()

    # Test hallucination detection
    print("="*70)
    print("HALLUCINATION DETECTION EXAMPLES")
    print("="*70)

    test_descriptions = [
        "Red volcanic rocks with flowing lava and steam rising",
        "The concept of geological time represented visually",
        "Exactly 4.543 billion years ago at the exact moment",
        "View from inside a single atom showing electrons"
    ]

    detector = HallucinationPrevention()

    for desc in test_descriptions:
        result = detector.check_for_hallucinations(desc)
        print(f"\nDescription: {desc}")
        print(f"Risk Level: {result['risk_level']}")
        if result['warnings']:
            print("Warnings:")
            for warning in result['warnings']:
                print(f"  - {warning}")

        suggestions = detector.suggest_improvements(desc)
        if suggestions:
            print("Suggestions:")
            for suggestion in suggestions:
                print(f"  - {suggestion}")
