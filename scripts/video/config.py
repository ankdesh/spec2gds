"""Centralized configuration and constants for spec2hw video production."""

from pathlib import Path
from typing import Final

# Repository root
REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent

# Output layout constants
DEFAULT_TEMP_DIR: Final[Path] = REPO_ROOT / "temp" / "TEMP_tutorial_videos"
DEFAULT_MODELS_DIR: Final[Path] = DEFAULT_TEMP_DIR / "models"
DEFAULT_MEDIA_ENV_DIR: Final[Path] = DEFAULT_TEMP_DIR / "media_env"

# Video specifications (1080p 30fps H.264)
TARGET_WIDTH: Final[int] = 1920
TARGET_HEIGHT: Final[int] = 1080
TARGET_FPS: Final[int] = 30
VIDEO_CODEC: Final[str] = "libx264"
VIDEO_PIXEL_FORMAT: Final[str] = "yuv420p"
VIDEO_CRF: Final[int] = 20
VIDEO_PRESET: Final[str] = "medium"

# Audio specifications (EBU R128 -16 LUFS, True Peak <= -1 dBTP, AAC 48kHz)
TARGET_LUFS: Final[float] = -16.0
LUFS_TOLERANCE: Final[float] = 0.5
TARGET_PEAK_DBTP: Final[float] = -1.0
TARGET_LRA: Final[float] = 11.0
AUDIO_SAMPLE_RATE: Final[int] = 48000
AUDIO_CODEC: Final[str] = "aac"
AUDIO_BITRATE: Final[str] = "192k"

# Piper TTS model constants
DEFAULT_VOICE_MODEL: Final[str] = "en_US-ljspeech-high"
VOICE_SAMPLE_RATE: Final[int] = 22050
MODEL_BASE_URL: Final[str] = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/high/"
)
MODEL_ONNX_FILENAME: Final[str] = "en_US-ljspeech-high.onnx"
MODEL_JSON_FILENAME: Final[str] = "en_US-ljspeech-high.onnx.json"
MODEL_CARD_FILENAME: Final[str] = "MODEL_CARD"

MODEL_ONNX_SHA256: Final[str] = "5d4f08ba6a2a48c44592eed3ce56bf85e9de3dd4e20df90541ae68a8310c029a"
MODEL_JSON_SHA256: Final[str] = "7e1f4634af596d83cca997fb7a931ba80b70f8a316a2655ee69c55365e0ace14"
MODEL_CARD_SHA256: Final[str] = "289f7421072d689a3d91f6c632f486af46f9b8b04417536104a4ea667b8a394b"

# Minimum disk space required for a production run (in bytes)
MIN_DISK_SPACE_BYTES: Final[int] = 2 * 1024 * 1024 * 1024  # 2 GB

# Supported applications
APPS = (
    "spec_editor",
    "circuit_designer",
    "ai_assistant",
    "verification_planner",
    "spec_catalog",
    "activities",
)
