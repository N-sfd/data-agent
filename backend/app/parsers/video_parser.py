import subprocess
from pathlib import Path

import whisper

WHISPER_MODEL = "base"


def extract_audio(video_path: str, output_wav: str) -> str:
    """Step 1: Separate audio from video as PCM WAV."""
    Path(output_wav).parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            output_wav,
        ],
        check=True,
        capture_output=True,
    )

    return output_wav


def transcribe_audio(audio_path: str, model_name: str = WHISPER_MODEL) -> list[dict]:
    """Step 2: Transcribe audio into timestamped segments."""
    model = whisper.load_model(model_name)
    result = model.transcribe(audio_path)

    return [
        {
            "start": float(segment["start"]),
            "end": float(segment["end"]),
            "text": segment["text"].strip(),
        }
        for segment in result.get("segments", [])
    ]


def extract_frames(video_path: str, frames_dir: str, fps: str = "1/10") -> list[str]:
    """Step 3: Extract representative frames (default: 1 frame every 10 seconds)."""
    output_dir = Path(frames_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    frame_pattern = str(output_dir / "frame_%05d.jpg")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", f"fps={fps}",
            frame_pattern,
        ],
        check=True,
        capture_output=True,
    )

    return sorted(str(path) for path in output_dir.glob("frame_*.jpg"))


def parse_video(file_path: str, work_dir: str | None = None) -> dict:
    """
    Split a video into audio, transcript segments, and representative frames.
    """
    video_path = Path(file_path)
    base_dir = Path(work_dir) if work_dir else video_path.with_suffix("")
    base_dir.mkdir(parents=True, exist_ok=True)

    audio_path = str(base_dir / "audio.wav")
    frames_dir = str(base_dir / "frames")

    extract_audio(str(video_path), audio_path)
    transcript = transcribe_audio(audio_path)
    frames = extract_frames(str(video_path), frames_dir)

    return {
        "audio_path": audio_path,
        "transcript": transcript,
        "frames": frames,
    }
