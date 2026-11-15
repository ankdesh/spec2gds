"""spec2hw Video Production Pipeline Package."""

from scripts.video.config import (
    DEFAULT_VOICE_MODEL,
    MODEL_CARD_SHA256,
    MODEL_JSON_SHA256,
    MODEL_ONNX_SHA256,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_LUFS,
    TARGET_PEAK_DBTP,
    TARGET_WIDTH,
)

__all__ = [
    "MODEL_ONNX_SHA256",
    "MODEL_JSON_SHA256",
    "MODEL_CARD_SHA256",
    "DEFAULT_VOICE_MODEL",
    "TARGET_WIDTH",
    "TARGET_HEIGHT",
    "TARGET_FPS",
    "TARGET_LUFS",
    "TARGET_PEAK_DBTP",
]
