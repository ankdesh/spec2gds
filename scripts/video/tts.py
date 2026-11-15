"""TTS audio generation, phonetic dictionary, and EBU R128 LUFS normalization."""

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from scripts.video.config import (
    AUDIO_SAMPLE_RATE,
    DEFAULT_MEDIA_ENV_DIR,
    DEFAULT_MODELS_DIR,
    DEFAULT_VOICE_MODEL,
    MODEL_JSON_FILENAME,
    MODEL_ONNX_FILENAME,
    TARGET_LRA,
    TARGET_LUFS,
    TARGET_PEAK_DBTP,
)

# Canonical phonetic pronunciation substitutions
PRONUNCIATION_SUBSTITUTIONS: dict[str, str] = {
    "spec2hw": "spec to hardware",
    "spec2gds": "spec to G D S",
    "SystemVerilog": "System Verilog",
    "RTL": "R T L",
    "FIFO": "fie-foe",
    "FIFOs": "fie-foes",
    "IP-XACT": "I P exact",
    "Verilator": "verilator",
    "clk": "clock",
    "din": "D in",
    "dout": "D out",
    "modulo": "modulo",
    "reset_n": "reset N",
    "ALU": "A L U",
    "JSON": "Jason",
    "SVG": "S V G",
    "PNG": "P N G",
    "API": "A P I",
    "UI": "U I",
    "VTT": "V T T",
    "SRT": "S R T",
    "LUFS": "L U F S",
    "UUID": "U U I D",
    "AST": "A S T",
    "IR": "I R",
    "TLM": "T L M",
    "Playwright": "playwright",
    "Chromium": "chromium",
}


def normalize_narration_text(text: str) -> str:
    """Substitutes technical terms and acronyms with phonetic pronunciations for speech synthesis."""
    normalized = text
    for term, replacement in PRONUNCIATION_SUBSTITUTIONS.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        normalized = re.sub(pattern, replacement, normalized)
    return normalized


class AudioEngine:
    """Synthesizes voice cues using Piper and normalizes loudness with FFmpeg."""

    def __init__(
        self,
        media_env_dir: Path = DEFAULT_MEDIA_ENV_DIR,
        models_dir: Path = DEFAULT_MODELS_DIR,
        model_name: str = DEFAULT_VOICE_MODEL,
        cache_dir: Optional[Path] = None,
    ):
        self.media_env_dir = media_env_dir
        self.models_dir = models_dir
        self.model_name = model_name
        self.model_onnx = models_dir / MODEL_ONNX_FILENAME
        self.model_json = models_dir / MODEL_JSON_FILENAME
        self.cache_dir = cache_dir or (models_dir.parent / "audio_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_piper_executable(self) -> Path:
        local_bin = self.media_env_dir / "bin" / "piper"
        if local_bin.exists() and os.access(local_bin, os.X_OK):
            return local_bin
        system_bin = shutil.which("piper")
        if system_bin:
            return Path(system_bin)
        raise FileNotFoundError(f"Piper executable not found at {local_bin} or in PATH.")

    def synthesize_cue(
        self,
        text: str,
        output_wav: Path,
        use_cache: bool = True,
        speed: float = 1.0,
    ) -> Path:
        """Synthesizes text cue to a WAV file using Piper TTS."""
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        spoken_text = normalize_narration_text(text)

        # Cache key based on normalized text and model settings
        cache_key = hashlib.sha256(
            f"{spoken_text}:{self.model_name}:{speed}".encode("utf-8")
        ).hexdigest()
        cached_wav = self.cache_dir / f"{cache_key}.wav"

        if use_cache and cached_wav.exists() and cached_wav.stat().st_size > 0:
            shutil.copy2(cached_wav, output_wav)
            return output_wav

        if not self.model_onnx.exists():
            raise FileNotFoundError(f"Model file missing: {self.model_onnx}")

        piper_bin = self.get_piper_executable()
        cmd = [
            str(piper_bin),
            "-m",
            str(self.model_onnx),
            "-c",
            str(self.model_json),
            "-f",
            str(output_wav),
        ]
        if speed != 1.0:
            # Piper uses length-scale: 1.0 / speed
            cmd.extend(["--length-scale", str(1.0 / speed)])

        proc = subprocess.run(
            cmd,
            input=spoken_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Piper TTS synthesis failed: {proc.stderr or proc.stdout}")

        if not output_wav.exists() or output_wav.stat().st_size == 0:
            raise RuntimeError(f"Piper produced empty WAV file at {output_wav}")

        # Save to cache
        shutil.copy2(output_wav, cached_wav)
        return output_wav

    def normalize_loudness(
        self,
        input_wav: Path,
        output_wav: Path,
        target_lufs: float = TARGET_LUFS,
        true_peak: float = TARGET_PEAK_DBTP,
        lra: float = TARGET_LRA,
        sample_rate: int = AUDIO_SAMPLE_RATE,
    ) -> dict:
        """Normalizes audio to EBU R128 loudness standard (-16 LUFS, <= -1 dBTP)."""
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise FileNotFoundError("ffmpeg binary not found in PATH")

        filter_str = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_wav),
            "-af",
            filter_str,
            "-ar",
            str(sample_rate),
            str(output_wav),
        ]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg loudnorm failed: {proc.stderr}")

        # Parse JSON loudnorm output from stderr if available
        stats = {}
        try:
            stderr = proc.stderr
            match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)
            if match:
                stats = json.loads(match.group(0))
        except Exception:
            pass

        return stats

    @staticmethod
    def get_audio_duration(path: Path) -> float:
        """Uses ffprobe to obtain duration of audio file in seconds."""
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            raise FileNotFoundError("ffprobe binary not found in PATH")
        cmd = [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out)
