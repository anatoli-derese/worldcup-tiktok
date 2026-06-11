"""Assemble slideshow video with FFmpeg."""
import shlex
import subprocess
from pathlib import Path
from src.config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.utils import get_logger

logger = get_logger(__name__)


def assemble_video(image_paths: list[Path], audio_path: Path, output_name: str, duration_per_image: float = 5.0) -> Path | None:
    """Create MP4 slideshow from images + audio. Returns output path or None."""
    if not image_paths or not audio_path.exists():
        logger.error("Missing images or audio")
        return None

    output_path = OUTPUT_DIR / f"{output_name}.mp4"
    list_file = OUTPUT_DIR / f"{output_name}_list.txt"
    lines = [f"file '{img.absolute()}'\nduration {duration_per_image}" for img in image_paths]
    lines.append(f"file '{image_paths[-1].absolute()}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    try:
        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i {shlex.quote(str(list_file))} "
            f"-i {shlex.quote(str(audio_path))} "
            f"-vf 'scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black' "
            f"-c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k "
            f"-shortest -pix_fmt yuv420p -movflags +faststart "
            f"{shlex.quote(str(output_path))}"
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"FFmpeg failed: {result.stderr[:500]}")
            return None

        logger.info(f"Video: {output_path} ({output_path.stat().st_size / 1e6:.1f} MB)")
        return output_path
    except subprocess.TimeoutExpired:
        logger.error("FFmpeg timed out")
        return None
    finally:
        list_file.unlink(missing_ok=True)
