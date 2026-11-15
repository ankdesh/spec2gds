"""Preflight checks and environment setup for spec2hw video production."""

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

from scripts.video.config import (
    DEFAULT_MEDIA_ENV_DIR,
    DEFAULT_MODELS_DIR,
    MIN_DISK_SPACE_BYTES,
    MODEL_BASE_URL,
    MODEL_CARD_FILENAME,
    MODEL_CARD_SHA256,
    MODEL_JSON_FILENAME,
    MODEL_JSON_SHA256,
    MODEL_ONNX_FILENAME,
    MODEL_ONNX_SHA256,
    REPO_ROOT,
)


@dataclass
class CheckResult:
    """Represents the outcome of a single preflight check."""

    name: str
    status: str  # "ok", "warning", "missing", "failed"
    details: str
    required: bool = True
    metadata: dict = field(default_factory=dict)


@dataclass
class PreflightReport:
    """Aggregate report of all preflight checks."""

    overall_ok: bool
    checks: list[CheckResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_ok": self.overall_ok,
            "checks": [asdict(c) for c in self.checks],
        }

    def print_summary(self) -> None:
        print("\n=== spec2hw Video Production Preflight ===")
        for c in self.checks:
            mark = "✓" if c.status == "ok" else ("!" if c.status == "warning" else "✗")
            req = "[Required]" if c.required else "[Optional]"
            print(f" {mark} {req} {c.name}: {c.details}")
        print(f"Overall status: {'READY' if self.overall_ok else 'INCOMPLETE'}\n")


class PreflightChecker:
    """Performs environment and dependency verification."""

    def __init__(
        self,
        repo_root: Path = REPO_ROOT,
        media_env_dir: Path = DEFAULT_MEDIA_ENV_DIR,
        models_dir: Path = DEFAULT_MODELS_DIR,
    ):
        self.repo_root = repo_root
        self.media_env_dir = media_env_dir
        self.models_dir = models_dir

    def check_python(self) -> CheckResult:
        version = sys.version_info
        ver_str = f"{version.major}.{version.minor}.{version.micro}"
        if version >= (3, 12):
            return CheckResult("Python 3.12+", "ok", f"Found Python {ver_str}", required=True)
        return CheckResult(
            "Python 3.12+",
            "failed",
            f"Python {ver_str} is below required 3.12+",
            required=True,
        )

    def check_node(self) -> CheckResult:
        node_bin = shutil.which("node")
        if not node_bin:
            return CheckResult("Node.js", "failed", "node binary not found in PATH", required=True)
        try:
            out = subprocess.check_output([node_bin, "--version"], text=True).strip()
            return CheckResult("Node.js", "ok", f"Found {out} at {node_bin}", required=True)
        except Exception as e:
            return CheckResult("Node.js", "failed", f"Failed checking node: {e}", required=True)

    def check_playwright_chromium(self) -> CheckResult:
        browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or str(
            self.repo_root / "circuit-designer" / ".playwright-browsers"
        )
        browsers_dir = Path(browsers_path)
        if not browsers_dir.exists():
            return CheckResult(
                "Playwright Chromium",
                "missing",
                f"Browsers directory {browsers_path} not found",
                required=True,
            )
        chromium_dirs = list(browsers_dir.glob("chromium-*"))
        if not chromium_dirs:
            return CheckResult(
                "Playwright Chromium",
                "missing",
                f"No chromium installation found in {browsers_path}",
                required=True,
            )
        return CheckResult(
            "Playwright Chromium",
            "ok",
            f"Found Chromium at {chromium_dirs[0]}",
            required=True,
            metadata={"path": str(chromium_dirs[0])},
        )

    def check_ffmpeg(self) -> CheckResult:
        ffmpeg_bin = shutil.which("ffmpeg")
        ffprobe_bin = shutil.which("ffprobe")
        if not ffmpeg_bin or not ffprobe_bin:
            return CheckResult(
                "FFmpeg / FFprobe",
                "failed",
                "ffmpeg or ffprobe not found in PATH",
                required=True,
            )
        try:
            filters_out = subprocess.check_output(
                [ffmpeg_bin, "-filters"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            has_loudnorm = "loudnorm" in filters_out
            codecs_out = subprocess.check_output(
                [ffmpeg_bin, "-codecs"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            has_h264 = "libx264" in codecs_out

            if not has_loudnorm or not has_h264:
                return CheckResult(
                    "FFmpeg Codecs & Filters",
                    "failed",
                    f"Missing required features (libx264={has_h264}, loudnorm={has_loudnorm})",
                    required=True,
                )
            return CheckResult(
                "FFmpeg / FFprobe",
                "ok",
                f"Found ffmpeg with libx264 and loudnorm filter at {ffmpeg_bin}",
                required=True,
            )
        except Exception as e:
            return CheckResult(
                "FFmpeg / FFprobe",
                "failed",
                f"Error checking ffmpeg features: {e}",
                required=True,
            )

    def check_piper(self) -> CheckResult:
        piper_bin = self.get_piper_binary()
        if not piper_bin:
            return CheckResult(
                "Piper TTS 1.8.0",
                "missing",
                "Piper binary not found (can auto-setup via `uv pip install piper-tts`)",
                required=True,
            )
        return CheckResult("Piper TTS 1.8.0", "ok", f"Found Piper at {piper_bin}", required=True)

    def get_piper_binary(self) -> Path | None:
        local_bin = self.media_env_dir / "bin" / "piper"
        if local_bin.exists() and os.access(local_bin, os.X_OK):
            return local_bin
        system_bin = shutil.which("piper")
        if system_bin:
            return Path(system_bin)
        return None

    def check_voice_model(self) -> CheckResult:
        onnx_file = self.models_dir / MODEL_ONNX_FILENAME
        json_file = self.models_dir / MODEL_JSON_FILENAME
        card_file = self.models_dir / MODEL_CARD_FILENAME

        if not onnx_file.exists() or not json_file.exists() or not card_file.exists():
            return CheckResult(
                "Piper Voice Model (en_US-ljspeech-high)",
                "missing",
                f"Model files missing from {self.models_dir}",
                required=True,
            )

        # Verify sha256 checksums
        def sha256_of(p: Path) -> str:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            return h.hexdigest()

        onnx_hash = sha256_of(onnx_file)
        json_hash = sha256_of(json_file)
        card_hash = sha256_of(card_file)

        if onnx_hash != MODEL_ONNX_SHA256:
            return CheckResult(
                "Piper Voice Model Checksum",
                "failed",
                f"ONNX checksum mismatch: got {onnx_hash[:8]}..., expected {MODEL_ONNX_SHA256[:8]}...",
                required=True,
            )
        if json_hash != MODEL_JSON_SHA256:
            return CheckResult(
                "Piper Voice Model Checksum",
                "failed",
                f"JSON config checksum mismatch: got {json_hash[:8]}...",
                required=True,
            )
        if card_hash != MODEL_CARD_SHA256:
            return CheckResult(
                "Piper Voice Model Checksum",
                "failed",
                f"Model card checksum mismatch: got {card_hash[:8]}...",
                required=True,
            )

        return CheckResult(
            "Piper Voice Model (en_US-ljspeech-high)",
            "ok",
            f"All model files verified with SHA-256 at {self.models_dir}",
            required=True,
        )

    def check_verilator(self) -> CheckResult:
        verilator_bin = shutil.which("verilator")
        make_bin = shutil.which("make")
        if verilator_bin and make_bin:
            return CheckResult(
                "Verilator & Make (RTL Tools)",
                "ok",
                f"Found Verilator at {verilator_bin} and Make at {make_bin}",
                required=False,
            )
        return CheckResult(
            "Verilator & Make (RTL Tools)",
            "warning",
            "Verilator or Make missing; RTL simulation checks will be skipped",
            required=False,
        )

    def check_assistant_credentials(self) -> CheckResult:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key and len(api_key.strip()) > 0:
            return CheckResult(
                "AI Assistant Credentials",
                "ok",
                "OPENAI_API_KEY is configured",
                required=False,
            )
        return CheckResult(
            "AI Assistant Credentials",
            "warning",
            "OPENAI_API_KEY not set; Assistant live model calls will be unavailable",
            required=False,
        )

    def check_disk_space(self, target_dir: Path) -> CheckResult:
        target_dir.mkdir(parents=True, exist_ok=True)
        stat = shutil.disk_usage(target_dir)
        free_gb = stat.free / (1024 * 1024 * 1024)
        if stat.free >= MIN_DISK_SPACE_BYTES:
            return CheckResult(
                "Disk Space",
                "ok",
                f"{free_gb:.1f} GB available (min 2.0 GB required)",
                required=True,
            )
        return CheckResult(
            "Disk Space",
            "failed",
            f"Insufficient disk space: {free_gb:.1f} GB available (need 2.0 GB)",
            required=True,
        )

    def setup_media_env(self) -> bool:
        """Sets up media_env with piper-tts using uv."""
        if self.get_piper_binary():
            return True
        self.media_env_dir.mkdir(parents=True, exist_ok=True)
        uv_bin = shutil.which("uv")
        if not uv_bin:
            print("Error: 'uv' not found to set up media_env.")
            return False
        try:
            print(f"Creating isolated media virtual environment at {self.media_env_dir}...")
            subprocess.run([uv_bin, "venv", str(self.media_env_dir)], check=True)
            python_bin = self.media_env_dir / "bin" / "python"
            print("Installing piper-tts==1.8.0...")
            subprocess.run(
                [uv_bin, "pip", "install", "--python", str(python_bin), "piper-tts==1.8.0"],
                check=True,
            )
            return True
        except Exception as e:
            print(f"Failed to auto-setup media_env: {e}")
            return False

    def setup_voice_model(self) -> bool:
        """Downloads Piper voice model files and verifies SHA-256."""
        self.models_dir.mkdir(parents=True, exist_ok=True)
        files = [
            (MODEL_CARD_FILENAME, MODEL_CARD_SHA256),
            (MODEL_JSON_FILENAME, MODEL_JSON_SHA256),
            (MODEL_ONNX_FILENAME, MODEL_ONNX_SHA256),
        ]
        for fname, expected_hash in files:
            dest = self.models_dir / fname
            if dest.exists():
                h = hashlib.sha256(dest.read_bytes()).hexdigest()
                if h == expected_hash:
                    continue
            print(f"Downloading {fname} from Hugging Face...")
            url = MODEL_BASE_URL + fname
            urllib.request.urlretrieve(url, dest)
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
            if h != expected_hash:
                raise ValueError(f"Downloaded {fname} hash mismatch: {h} != {expected_hash}")
        return True

    def run_all(self, target_dir: Path, auto_setup: bool = True) -> PreflightReport:
        if auto_setup:
            if not self.get_piper_binary():
                self.setup_media_env()
            if not (self.models_dir / MODEL_ONNX_FILENAME).exists():
                self.setup_voice_model()

        checks = [
            self.check_python(),
            self.check_node(),
            self.check_playwright_chromium(),
            self.check_ffmpeg(),
            self.check_piper(),
            self.check_voice_model(),
            self.check_disk_space(target_dir),
            self.check_verilator(),
            self.check_assistant_credentials(),
        ]
        overall_ok = all(c.status in ("ok", "warning") for c in checks if c.required)
        return PreflightReport(overall_ok=overall_ok, checks=checks)
