#!/usr/bin/env python3
"""Unified CLI and Production Engine for spec2hw tutorial video library."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.video.compose import VideoCompositor
from scripts.video.config import (
    DEFAULT_TEMP_DIR,
    REPO_ROOT,
    TARGET_HEIGHT,
    TARGET_LUFS,
    TARGET_WIDTH,
)
from scripts.video.episodes import get_episodes_catalog
from scripts.video.inventory import (
    calculate_coverage,
    get_default_operations_registry,
)
from scripts.video.preflight import PreflightChecker
from scripts.video.tts import AudioEngine
from scripts.video.web_library import WebLibraryBuilder

DEFAULT_EPISODES = [
    "pilot",
    "V00",
    "V01",
    "V02",
    "V03",
    "V04",
    "V05",
    "V06",
    "V07",
    "V08",
]


def get_default_output_dir() -> Path:
    run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    return DEFAULT_TEMP_DIR / run_id


def cmd_preflight(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    print(f"[CLI] Running preflight check on {output_dir}...")
    checker = PreflightChecker(repo_root=REPO_ROOT)
    report = checker.run_all(output_dir, auto_setup=not args.dry_run)
    report.print_summary()

    # Save preflight report
    if not args.dry_run:
        evidence_dir = output_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "preflight_report.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )

    return 0 if report.overall_ok else 1


def cmd_inventory(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    print("[CLI] Auditing designer operations inventory...")
    registry = get_default_operations_registry()

    # Determine which episodes are validated or planned
    if args.episode:
        validated_ids = set(args.episode.split(","))
    else:
        validated_ids = {
            "pilot",
            "V00",
            "V01",
            "V02",
            "V03",
            "V04",
            "V05",
            "V06",
            "V07",
            "V08",
        }
    report = calculate_coverage(registry, validated_episode_ids=validated_ids)
    report.print_summary()

    if not args.dry_run:
        evidence_dir = output_dir / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "operation_inventory.json").write_text(
            json.dumps([op.__dict__ for op in registry], indent=2),
            encoding="utf-8",
        )
        (evidence_dir / "coverage_report.json").write_text(
            json.dumps(report.to_dict(), indent=2), encoding="utf-8"
        )

    if report.overall_coverage_percent < 80.0:
        print(
            f"Warning: Overall coverage {report.overall_coverage_percent:.1f}% is below 80% target."
        )
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    print(f"[CLI] Preparing starts and checkpoints in {output_dir / 'starts'}...")
    if args.dry_run:
        print("[CLI] Dry-run: skipped example spec creation.")
        return 0

    starts_dir = output_dir / "starts"
    starts_dir.mkdir(parents=True, exist_ok=True)

    # Generate initial sample specs using repository test helper
    sample_spec = starts_dir / "tutorial.spec"
    python_bin = REPO_ROOT / ".venv" / "bin" / "python"
    cmd = [
        str(python_bin),
        "-c",
        "import sys; from spec2gds.spec.spec_format.testing import write_test_package; write_test_package(sys.argv[1])",
        str(sample_spec),
    ]
    subprocess.run(cmd, check=True)
    print(f"[CLI] Prepared clean start: {sample_spec}")
    return 0


def cmd_narrate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    target_episodes = args.episode.split(",") if args.episode else DEFAULT_EPISODES
    print(f"[CLI] Narrating episodes: {target_episodes}")

    if args.dry_run:
        print("[CLI] Dry-run: skipped narration synthesis.")
        return 0

    engine = AudioEngine()
    catalog = get_episodes_catalog()

    for ep_id in target_episodes:
        if ep_id not in catalog:
            print(f"Error: Episode {ep_id} not found in catalog.")
            return 1
        ep = catalog[ep_id]
        ep_audio_dir = output_dir / "narration" / ep_id
        ep_audio_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n[TTS] Synthesizing {len(ep.scenes)} scenes for {ep.id} ({ep.title})...")
        for i, scene in enumerate(ep.scenes):
            raw_wav = ep_audio_dir / f"{scene.scene_id}_raw.wav"
            norm_wav = ep_audio_dir / f"{scene.scene_id}.wav"

            print(f"  [{scene.scene_id}] Synthesizing: {scene.title}...")
            engine.synthesize_cue(scene.narration, raw_wav)
            print(f"  [{scene.scene_id}] Normalizing loudness to -16 LUFS...")
            engine.normalize_loudness(raw_wav, norm_wav)
            dur = engine.get_audio_duration(norm_wav)
            print(f"  [{scene.scene_id}] Done: {dur:.2f}s audio generated.")

    print("\n[CLI] Narration synthesis complete.")
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    target_episodes = args.episode.split(",") if args.episode else DEFAULT_EPISODES
    print(f"[CLI] Recording screen operations for episodes: {target_episodes}...")

    if args.dry_run:
        print("[CLI] Dry-run: skipped Playwright screen recording.")
        return 0

    recorder_ts = REPO_ROOT / "tests" / "ui-scenarios" / "runner" / "record_video.ts"
    node_bin = shutil.which("node")
    if not node_bin:
        print("Error: Node.js not found in PATH")
        return 1

    for ep_id in target_episodes:
        print(f"\n[Record] Executing Playwright recorder for episode {ep_id}...")
        cmd = [
            node_bin,
            "--import",
            "tsx",
            str(recorder_ts),
            "--episode",
            ep_id,
            "--output",
            str(output_dir.resolve()),
        ]
        proc = subprocess.run(cmd, cwd=REPO_ROOT / "tests" / "ui-scenarios", check=False)
        if proc.returncode != 0:
            print(f"Error: Recorder failed for episode {ep_id}")
            return proc.returncode

    print("\n[CLI] Recording completed.")
    return 0


def cmd_compose(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    target_episodes = args.episode.split(",") if args.episode else DEFAULT_EPISODES
    print(f"[CLI] Composing final video packages for: {target_episodes}...")

    if args.dry_run:
        print("[CLI] Dry-run: skipped FFmpeg composition.")
        return 0

    catalog = get_episodes_catalog()
    compositor = VideoCompositor()

    for ep_id in target_episodes:
        if ep_id not in catalog:
            print(f"Error: Episode {ep_id} not found in catalog.")
            return 1
        ep = catalog[ep_id]

        raw_dir = output_dir / "originals" / ep_id
        # Find recorded webm or mp4 file
        raw_files = sorted(
            list(raw_dir.glob("*.webm")) + list(raw_dir.glob("*.mp4")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not raw_files:
            print(f"Error: No raw video recording found in {raw_dir}")
            return 1
        raw_video = raw_files[0]

        # Gather audio cues
        ep_audio_dir = output_dir / "narration" / ep_id
        audio_cues = [ep_audio_dir / f"{scene.scene_id}.wav" for scene in ep.scenes]
        for cue in audio_cues:
            if not cue.exists():
                print(f"Error: Audio cue missing: {cue}. Run `narrate` first.")
                return 1

        render_dir = output_dir / "renders" / ep_id
        print(f"\n[Compose] Rendering 1080p MP4 for {ep_id}...")
        result = compositor.compose_episode(ep, raw_video, audio_cues, render_dir)
        print(
            f"[Compose] Successfully rendered {ep_id}: {result['mp4']} ({result['duration']:.1f}s)"
        )

    print("\n[CLI] Composition completed.")
    return 0


def cmd_library(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    print(f"[CLI] Building local offline learning library in {output_dir / 'release'}...")

    release_dir = output_dir / "release"
    builder = WebLibraryBuilder(release_dir)
    catalog = get_episodes_catalog()
    registry = get_default_operations_registry()

    # Check which episodes have renders
    rendered_assets: dict[str, dict[str, str]] = {}
    for ep_id in catalog.keys():
        render_dir = output_dir / "renders" / ep_id
        mp4 = render_dir / f"{ep_id}.mp4"
        vtt = render_dir / f"{ep_id}.vtt"
        srt = render_dir / f"{ep_id}.srt"
        txt = render_dir / f"{ep_id}.txt"
        poster = render_dir / f"{ep_id}_poster.jpg"
        timings = render_dir / f"{ep_id}_timings.json"

        if mp4.exists() and vtt.exists() and poster.exists():
            print(f"[Library] Publishing media for {ep_id}...")
            rel_urls = builder.publish_episode_assets(
                ep_id,
                mp4,
                vtt,
                srt,
                txt,
                poster,
                timings_path=timings if timings.exists() else None,
            )
            rendered_assets[ep_id] = rel_urls

    coverage_report = calculate_coverage(
        registry, validated_episode_ids=set(rendered_assets.keys())
    )
    builder.build_library(list(catalog.values()), coverage_report, rendered_assets, registry)
    print(f"[CLI] Learning library generated at {release_dir / 'index.html'}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    output_dir = Path(args.output)
    target_episodes = args.episode.split(",") if args.episode else DEFAULT_EPISODES
    print(f"[CLI] Verifying media deliverables for: {target_episodes}...")

    if args.dry_run:
        print("[CLI] Dry-run: skipped media deliverable verification.")
        return 0

    ffprobe_bin = shutil.which("ffprobe")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffprobe_bin or not ffmpeg_bin:
        print("Error: ffprobe and ffmpeg required for verification.")
        return 1

    all_ok = True
    for ep_id in target_episodes:
        ep_render = output_dir / "renders" / ep_id / f"{ep_id}.mp4"
        ep_vtt = output_dir / "renders" / ep_id / f"{ep_id}.vtt"
        ep_srt = output_dir / "renders" / ep_id / f"{ep_id}.srt"
        ep_poster = output_dir / "renders" / ep_id / f"{ep_id}_poster.jpg"

        for p in [ep_render, ep_vtt, ep_srt, ep_poster]:
            if not p.exists() or p.stat().st_size == 0:
                print(f"✗ [{ep_id}] Deliverable missing or empty: {p}")
                all_ok = False
            else:
                print(f"✓ [{ep_id}] Verified asset: {p.name} ({p.stat().st_size} bytes)")

        if ep_vtt.exists():
            vtt_text = ep_vtt.read_text(encoding="utf-8")
            if not vtt_text.startswith("WEBVTT"):
                print(f"✗ [{ep_id}] Subtitle file does not start with WEBVTT header: {ep_vtt}")
                all_ok = False
            else:
                print(f"✓ [{ep_id}] Subtitles verified (valid WEBVTT format)")

        if ep_render.exists():
            # Check video resolution and codec
            probe_cmd = [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,codec_name",
                "-of",
                "json",
                str(ep_render),
            ]
            probe_out = subprocess.check_output(probe_cmd, text=True)
            v_info = json.loads(probe_out)["streams"][0]
            if v_info["width"] != TARGET_WIDTH or v_info["height"] != TARGET_HEIGHT:
                print(
                    f"✗ [{ep_id}] Resolution mismatch: {v_info['width']}x{v_info['height']} != {TARGET_WIDTH}x{TARGET_HEIGHT}"
                )
                all_ok = False
            else:
                print(f"✓ [{ep_id}] 1080p resolution confirmed (1920x1080, {v_info['codec_name']})")

            # Check audio stream
            a_cmd = [
                ffprobe_bin,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate",
                "-of",
                "json",
                str(ep_render),
            ]
            a_out = subprocess.check_output(a_cmd, text=True)
            a_info = json.loads(a_out)["streams"][0]
            print(
                f"✓ [{ep_id}] Audio confirmed ({a_info['codec_name']}, {a_info['sample_rate']} Hz)"
            )

            # Check embedded chapters
            ch_cmd = [
                ffprobe_bin,
                "-v",
                "error",
                "-show_chapters",
                "-of",
                "json",
                str(ep_render),
            ]
            ch_out = subprocess.check_output(ch_cmd, text=True)
            chapters = json.loads(ch_out).get("chapters", [])
            if not chapters:
                print(f"✗ [{ep_id}] No embedded chapters found in MP4!")
                all_ok = False
            else:
                print(f"✓ [{ep_id}] Embedded chapters confirmed: {len(chapters)} chapters")

            # Check EBU R128 integrated loudness via ebur128 filter
            ebur_cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(ep_render),
                "-filter:a",
                "ebur128=framelog=verbose",
                "-f",
                "null",
                "-",
            ]
            ebur_proc = subprocess.run(ebur_cmd, capture_output=True, text=True, check=False)
            m_lufs = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", ebur_proc.stderr)
            if m_lufs:
                val = float(m_lufs.group(1))
                if abs(val - TARGET_LUFS) > 2.0:
                    print(
                        f"✗ [{ep_id}] Loudness out of tolerance: {val} LUFS (expected {TARGET_LUFS} ± 2.0)"
                    )
                    all_ok = False
                else:
                    print(f"✓ [{ep_id}] Loudness within spec: {val} LUFS (target {TARGET_LUFS})")
            else:
                print(f"Warning: Could not measure ebur128 loudness for {ep_id}")

    # Check release catalog deliverables if release/ exists
    release_dir = output_dir / "release"
    if release_dir.exists():
        for req in ["index.html", "watch.html", "styles.css", "manifest.json"]:
            rf = release_dir / req
            if not rf.exists() or rf.stat().st_size == 0:
                print(f"✗ [Library] Missing or empty deliverable: {rf.name}")
                all_ok = False
            else:
                print(f"✓ [Library] Verified deliverable: {rf.name}")

        tut_idx = release_dir / "tutorials" / "index.html"
        if not tut_idx.exists():
            print(f"✗ [Library] Written tutorials copy missing: {tut_idx}")
            all_ok = False
        else:
            print("✓ [Library] Verified written tutorials copy in release/tutorials/")

    return 0 if all_ok else 1


def cmd_all(args: argparse.Namespace) -> int:
    """Executes the complete production pipeline."""
    steps = [
        ("Preflight", cmd_preflight),
        ("Inventory", cmd_inventory),
        ("Prepare", cmd_prepare),
        ("Narrate", cmd_narrate),
        ("Record", cmd_record),
        ("Compose", cmd_compose),
        ("Library", cmd_library),
        ("Verify", cmd_verify),
    ]

    for name, func in steps:
        print(f"\n{'=' * 20} Pipeline Step: {name} {'=' * 20}")
        ret = func(args)
        if ret != 0:
            print(f"Error: Step '{name}' failed with code {ret}")
            return ret

    print("\n🎉 Complete video production pipeline finished successfully!")
    print(f"Deliverables ready at: {Path(args.output) / 'release' / 'index.html'}\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="spec2hw Automated Video Production Pipeline")
    parser.add_argument(
        "command",
        choices=[
            "preflight",
            "inventory",
            "prepare",
            "narrate",
            "record",
            "compose",
            "library",
            "verify",
            "all",
        ],
        help="Pipeline command to execute",
    )
    parser.add_argument(
        "--episode",
        default=",".join(DEFAULT_EPISODES),
        help="Comma-separated episode IDs (e.g. pilot,V00,V01,...)",
    )
    parser.add_argument(
        "--output",
        default=str(get_default_output_dir()),
        help="Run directory inside temp/TEMP_tutorial_videos/",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect plan and validate parameters without executing long processes",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume production run reusing existing intermediate caches",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debugging output",
    )

    args = parser.parse_args()

    # Quarantine check: ensure output is within temp/TEMP_*
    out_path = Path(args.output).resolve()
    temp_dir = (REPO_ROOT / "temp").resolve()
    if not str(out_path).startswith(str(temp_dir)):
        print(f"Error: Output directory {out_path} must reside strictly inside {temp_dir}.")
        return 1

    handlers = {
        "preflight": cmd_preflight,
        "inventory": cmd_inventory,
        "prepare": cmd_prepare,
        "narrate": cmd_narrate,
        "record": cmd_record,
        "compose": cmd_compose,
        "library": cmd_library,
        "verify": cmd_verify,
        "all": cmd_all,
    }

    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
