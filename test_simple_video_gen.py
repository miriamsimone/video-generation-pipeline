"""Simple test of video generation with Replicate."""

import asyncio
import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def test_simple_generation():
    """Test a very simple video generation."""
    logger.info("Testing simple video generation with minimax/video-01")
    
    try:
        import replicate
        client = replicate.Client(api_token=os.environ.get("REPLICATE_API_TOKEN"))
        
        # Very simple prompt
        prompt = "A red ball bouncing on a white surface"
        
        logger.info(f"Prompt: {prompt}")
        logger.info("Starting generation...")
        
        output = client.run(
            "minimax/video-01",
            input={
                "prompt": prompt,
            }
        )
        
        logger.success(f"Success! Output type: {type(output)}")
        logger.info(f"Output: {output}")
        
        # Download the video
        if isinstance(output, str):
            logger.info("Downloading video...")
            import httpx
            async with httpx.AsyncClient(timeout=300.0) as http_client:
                response = await http_client.get(output)
                response.raise_for_status()
                video_bytes = response.content
                
                # Save it
                with open("test_output.mp4", "wb") as f:
                    f.write(video_bytes)
                
                logger.success(f"Video saved to test_output.mp4 ({len(video_bytes)} bytes)")
        
    except Exception as e:
        logger.error(f"Failed: {e}")
        logger.exception("Full error:")


if __name__ == "__main__":
    asyncio.run(test_simple_generation())



