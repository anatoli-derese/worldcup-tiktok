"""Assemble slideshow video with FFmpeg."""
import shlex, subprocess, json
from pathlib import Path
from src.config import OUTPUT_DIR, VIDEO_WIDTH, VIDEO_HEIGHT
from src.utils import get_logger

logger = get_logger(__name__)


def assemble_video(image_paths: list[Path], audio_path: Path, output_name: str,
                   speed: float = 1.4) -> Path | None:
    """Create MP4 slideshow synced to audio duration. Speed 1.0=normal, 1.4=faster."""
    if not image_paths or not audio_path.exists():
        logger.error("Missing images or audio")
        return None

    audio_duration = _probe_duration(audio_path)
    if not audio_duration:
        logger.error("Could not determine audio duration")
        return None

    # Duration per image so they fill the entire (sped-up) audio timeline
    sped_up_duration = audio_duration / speed
    per_image = sped_up_duration / len(image_paths)
    logger.info(f"Audio: {audio_duration:.1f}s → {sped_up_duration:.1f}s @ {speed}x, "
                f"{len(image_paths)} images @ {per_image:.1f}s each")

    output_path = OUTPUT_DIR / f"{output_name}.mp4"
    list_file = OUTPUT_DIR / f"{output_name}_list.txt"
    lines = [f"file '{img.absolute()}'\nduration {per_image}" for img in image_paths]
    lines.append(f"file '{image_paths[-1].absolute()}'")
    list_file.write_text("\n".join(lines), encoding="utf-8")

    try:
        cmd = (
            f"ffmpeg -y -f concat -safe 0 -i {shlex.quote(str(list_file))} "
            f"-i {shlex.quote(str(audio_path))} "
            f"-filter_complex '[1:a]atempo={speed}[a]' "
            f"-map 0:v -map '[a]' "
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


def _probe_duration(path: Path) -> float | None:
    """Get audio duration in seconds using ffprobe."""
    try:
        r = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(path)
        ], capture_output=True, text=True, timeout=10)
        data = json.loads(r.stdout)
        return float(data["format"]["duration"])
    except Exception:
        return None
