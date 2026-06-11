"""Assemble slideshow video with FFmpeg."""
import subprocess
import shlex
from pathlib import Path
from src.config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.utils import get_logger

logger = get_logger(__name__)


def assemble_video(
    image_paths: list[Path],
    audio_path: Path,
    output_name: str,
    duration_per_image: float = 5.0,
) -> Path | None:
    """
    Create MP4 slideshow from images + audio.

    Args:
        image_paths: ordered list of image files
        audio_path: path to .mp3 voiceover audio
        output_name: base name for output file (no extension)
        duration_per_image: seconds each image stays on screen

    Returns:
        Path to output .mp4 file, or None on failure
    """
    if not image_paths:
        logger.error("No images provided")
        return None

    if not audio_path.exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None

    output_path = OUTPUT_DIR / f"{output_name}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a temporary text file listing images for FFmpeg concat demuxer
    list_file = OUTPUT_DIR / f"{output_name}_list.txt"
    lines = []
    for img in image_paths:
        lines.append(f"file '{img.absolute()}'")
        lines.append(f"duration {duration_per_image}")
    # Last frame repeats for concat to terminate properly
    if lines:
        lines.append(f"file '{image_paths[-1].absolute()}'")

    list_file.write_text("\n".join(lines), encoding="utf-8")

    try:
        # Build FFmpeg command
        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i {shlex.quote(str(list_file))} "
            f"-i {shlex.quote(str(audio_path))} "
            f"-vf 'scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black' "
            f"-c:v libx264 -preset fast -crf 23 "
            f"-c:a aac -b:a 128k "
            f"-shortest -pix_fmt yuv420p "
            f"-movflags +faststart "
            f"{shlex.quote(str(output_path))}"
        )

        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr[:500]}")
            return None

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Video assembled: {output_path} ({size_mb:.1f} MB)")
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out after 120s")
        return None
    finally:
        if list_file.exists():
            list_file.unlink()
