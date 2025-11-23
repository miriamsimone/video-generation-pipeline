import config
import os
from video_assembler import VideoAssembler

print(f"FFMPEG_PATH after importing config: {os.getenv('FFMPEG_PATH', 'not set')}")

va = VideoAssembler()
print(f'FFmpeg available: {va.ffmpeg_available}')
print(f'FFmpeg command: {va.ffmpeg_cmd}')