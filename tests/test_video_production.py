"""Automated tests for spec2hw video production pipeline."""

import json
import subprocess
import sys
from pathlib import Path

from scripts.video.compose import (
    VideoCompositor,
    format_timestamp_minsec,
    format_timestamp_srt,
    format_timestamp_vtt,
)
from scripts.video.config import (
    APPS,
    REPO_ROOT,
)
from scripts.video.episodes import Scene, get_episodes_catalog
from scripts.video.inventory import (
    calculate_coverage,
    get_default_operations_registry,
)
from scripts.video.preflight import PreflightChecker
from scripts.video.tts import (
    normalize_narration_text,
)
from scripts.video.web_library import WebLibraryBuilder


def test_inventory_registry_integrity() -> None:
    """Verifies that all operations have unique IDs, valid applications, and priorities."""
    ops = get_default_operations_registry()
    assert len(ops) >= 40, f"Expected at least 40 operations, found {len(ops)}"

    seen_ids = set()
    apps_seen = set()
    for op in ops:
        assert op.id not in seen_ids, f"Duplicate operation ID: {op.id}"
        seen_ids.add(op.id)
        assert op.application in APPS, f"Unknown application {op.application} for {op.id}"
        apps_seen.add(op.application)
        assert op.priority in ("essential", "high", "normal")
        assert len(op.episode_ids) > 0, f"Operation {op.id} must be mapped to at least one episode"

    # All 6 applications must be covered
    assert apps_seen == set(APPS), f"Missing applications in registry: {set(APPS) - apps_seen}"


def test_inventory_coverage_calculation() -> None:
    """Tests coverage calculation logic and verifies full series planned coverage >= 80%."""
    ops = get_default_operations_registry()
    catalog = get_episodes_catalog()

    # All episodes combined should cover 100% of defined operations
    all_ep_ids = set(catalog.keys())
    report_all = calculate_coverage(ops, validated_episode_ids=all_ep_ids)
    assert report_all.overall_coverage_percent >= 80.0
    assert report_all.overall_coverage_percent == 100.0

    # Test Phase 1 validated subset (pilot, V00, V01)
    phase1_ids = {"pilot", "V00", "V01"}
    report_phase1 = calculate_coverage(ops, validated_episode_ids=phase1_ids)
    assert report_phase1.validated_operations > 0
    # Spec Editor in Phase 1 should achieve >= 80% coverage
    assert report_phase1.by_application["spec_editor"].coverage_percent >= 80.0

    # Test Phase 2 validated subset (pilot, V00 through V08)
    phase2_ids = {
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
    report_phase2 = calculate_coverage(ops, validated_episode_ids=phase2_ids)
    assert report_phase2.validated_operations == 34
    assert report_phase2.by_application["spec_editor"].coverage_percent == 100.0
    assert report_phase2.by_application["spec_catalog"].coverage_percent == 100.0
    assert report_phase2.by_application["circuit_designer"].coverage_percent == 75.0


def test_phase2_episodes_scenes_integrity() -> None:
    """Verifies that all Phase 2 episodes (V02-V08) have populated scenes, narrations, and chapters."""
    catalog = get_episodes_catalog()
    for ep_id in ["V02", "V03", "V04", "V05", "V06", "V07", "V08"]:
        assert ep_id in catalog, f"Missing episode {ep_id}"
        ep = catalog[ep_id]
        assert len(ep.scenes) >= 3, f"Episode {ep_id} has fewer than 3 scenes"
        for scene in ep.scenes:
            assert scene.scene_id.startswith(f"{ep_id.lower()}_")
            assert len(scene.title) > 0
            assert len(scene.chapter_title) > 0
            assert len(scene.narration) > 20
            assert len(scene.caption) > 20
            assert scene.hold_duration > 0


def test_operation_scene_bidirectional_consistency() -> None:
    """Verifies that operation scene_ids and catalog Scene.operations match bidirectionally."""
    ops = get_default_operations_registry()
    catalog = get_episodes_catalog()

    op_to_scenes = {op.id: set(op.scene_ids) for op in ops}
    scene_to_ops = {}
    for _ep_id, ep in catalog.items():
        for s in ep.scenes:
            for op_id in s.operations:
                scene_to_ops.setdefault(s.scene_id, set()).add(op_id)

    # 1. Every scene in op.scene_ids must exist in catalog for that episode
    for op in ops:
        for ep_id in op.episode_ids:
            if ep_id in catalog and catalog[ep_id].scenes:
                valid_scenes = {s.scene_id for s in catalog[ep_id].scenes}
                for sc_id in op.scene_ids:
                    if sc_id.startswith(ep_id.lower() + "_"):
                        assert sc_id in valid_scenes, (
                            f"Op {op.id} references non-existent scene {sc_id} in {ep_id}"
                        )
                        assert op.id in scene_to_ops.get(sc_id, set()), (
                            f"Op {op.id} maps to scene {sc_id}, but scene does not list {op.id}"
                        )

    # 2. Every operation in Scene.operations must be mapped in the operations registry
    for sc_id, op_ids in scene_to_ops.items():
        for op_id in op_ids:
            assert op_id in op_to_scenes, f"Scene {sc_id} lists unregistered op {op_id}"
            assert sc_id in op_to_scenes[op_id], (
                f"Scene {sc_id} lists op {op_id}, but op.scene_ids lacks {sc_id}"
            )


def test_pronunciation_normalization() -> None:
    """Tests phonetic substitutions for speech synthesis while preserving identifiers."""
    sample = "In spec2hw, we use SystemVerilog to design an ALU and FIFO with clk and din."
    spoken = normalize_narration_text(sample)

    assert "spec to hardware" in spoken
    assert "System Verilog" in spoken
    assert "A L U" in spoken
    assert "fie-foe" in spoken
    assert "clock" in spoken
    assert "D in" in spoken

    # Word boundary test: "clockwork" should not replace "clk"
    assert normalize_narration_text("clockwork") == "clockwork"
    assert normalize_narration_text("include") == "include"


def test_subtitle_formatting() -> None:
    """Verifies WebVTT and SRT timestamp formatting."""
    assert format_timestamp_vtt(0.0) == "00:00:00.000"
    assert format_timestamp_vtt(65.5) == "00:01:05.500"
    assert format_timestamp_vtt(3661.123) == "01:01:01.123"

    assert format_timestamp_srt(0.0) == "00:00:00,000"
    assert format_timestamp_srt(65.5) == "00:01:05,500"
    assert format_timestamp_srt(3661.123) == "01:01:01,123"

    assert format_timestamp_minsec(65) == "01:05"
    assert format_timestamp_minsec(5) == "00:05"


def test_compositor_subtitle_files(tmp_path: Path) -> None:
    """Verifies that generated subtitle files are valid and match scene captions."""
    compositor = VideoCompositor()
    scenes = [
        Scene(
            scene_id="s1",
            episode_id="test",
            title="Scene 1",
            chapter_title="Intro",
            narration="Spoken one",
            caption="Welcome to spec2hw.",
            app="spec_editor",
        ),
        Scene(
            scene_id="s2",
            episode_id="test",
            title="Scene 2",
            chapter_title="Details",
            narration="Spoken two",
            caption="Configuring ports with Range 7:0.",
            app="spec_editor",
        ),
    ]
    timings = [(0.5, 4.0), (4.5, 9.0)]
    vtt_file = tmp_path / "test.vtt"
    srt_file = tmp_path / "test.srt"
    txt_file = tmp_path / "test.txt"
    meta_file = tmp_path / "test.meta"

    compositor.generate_subtitles(scenes, timings, vtt_file, srt_file)
    compositor.generate_transcript(scenes, timings, txt_file, "Test Episode")
    compositor.generate_chapters_metadata(scenes, timings, meta_file, "Test Episode")

    vtt_content = vtt_file.read_text(encoding="utf-8")
    assert vtt_content.startswith("WEBVTT")
    assert "00:00:00.500 --> 00:00:04.000" in vtt_content
    assert "Welcome to spec2hw." in vtt_content
    assert "00:00:04.500 --> 00:00:09.000" in vtt_content

    srt_content = srt_file.read_text(encoding="utf-8")
    assert "1\n00:00:00,500 --> 00:00:04,000" in srt_content
    assert "2\n00:00:04,500 --> 00:00:09,000" in srt_content

    meta_content = meta_file.read_text(encoding="utf-8")
    assert ";FFMETADATA1" in meta_content
    assert "title=Intro" in meta_content
    assert "START=500" in meta_content
    assert "END=4000" in meta_content


def test_web_library_offline_integrity(tmp_path: Path) -> None:
    """Verifies that the generated local learning library has zero external CDN dependencies."""
    release_dir = tmp_path / "release"
    builder = WebLibraryBuilder(release_dir)
    catalog = get_episodes_catalog()
    ops = get_default_operations_registry()
    coverage = calculate_coverage(ops, validated_episode_ids={"pilot"})

    # Mock media publish
    dummy_media = release_dir / "media" / "pilot"
    dummy_media.mkdir(parents=True)
    (dummy_media / "pilot.mp4").write_text("mp4", encoding="utf-8")
    (dummy_media / "pilot.vtt").write_text("WEBVTT\n", encoding="utf-8")
    (dummy_media / "pilot.srt").write_text("1\n", encoding="utf-8")
    (dummy_media / "pilot.txt").write_text("Transcript\n", encoding="utf-8")
    (dummy_media / "pilot_poster.jpg").write_text("jpg", encoding="utf-8")

    assets = {
        "pilot": {
            "mp4": "media/pilot/pilot.mp4",
            "vtt": "media/pilot/pilot.vtt",
            "srt": "media/pilot/pilot.srt",
            "txt": "media/pilot/pilot.txt",
            "poster": "media/pilot/pilot_poster.jpg",
        }
    }

    builder.build_library(list(catalog.values()), coverage, assets, ops)

    index_html = (release_dir / "index.html").read_text(encoding="utf-8")
    watch_html = (release_dir / "watch.html").read_text(encoding="utf-8")
    styles_css = (release_dir / "styles.css").read_text(encoding="utf-8")

    # Strict offline check: no remote CDN or fonts
    for page in [index_html, watch_html, styles_css]:
        assert "http://" not in page
        assert "https://" not in page
        assert "cdn" not in page.lower()
        assert "googleapis" not in page.lower()
        assert "cloudflare" not in page.lower()

    assert "spec2hw Video Library" in index_html
    assert "watch.html?episode=pilot" in index_html
    assert "styles.css" in index_html


def test_web_library_static_accessibility_and_tutorials(tmp_path: Path) -> None:
    """Verifies that tutorials are copied to release/ and watch player is accessible without JS."""
    release_dir = tmp_path / "release"
    builder = WebLibraryBuilder(release_dir)
    catalog = get_episodes_catalog()
    ops = get_default_operations_registry()
    coverage = calculate_coverage(ops, validated_episode_ids={"pilot"})

    # Create dummy media and timings
    dummy_media = release_dir / "media" / "pilot"
    dummy_media.mkdir(parents=True)
    (dummy_media / "pilot.mp4").write_text("mp4", encoding="utf-8")
    (dummy_media / "pilot.vtt").write_text(
        "WEBVTT\n00:00:00.500 --> 00:00:15.350\nIntro\n", encoding="utf-8"
    )
    (dummy_media / "pilot.srt").write_text(
        "1\n00:00:00,500 --> 00:00:15,350\nIntro\n", encoding="utf-8"
    )
    (dummy_media / "pilot.txt").write_text("Transcript for Pilot\n", encoding="utf-8")
    (dummy_media / "pilot_poster.jpg").write_text("jpg", encoding="utf-8")
    timings = [
        {
            "scene_id": "pilot_s01_intro",
            "start_seconds": 0.5,
            "end_seconds": 15.35,
            "time_label": "00:00",
            "chapter": "Spec Editor Setup",
        },
        {
            "scene_id": "pilot_s02_port_range",
            "start_seconds": 15.35,
            "end_seconds": 28.865,
            "time_label": "00:15",
            "chapter": "Port Validation",
        },
    ]
    (dummy_media / "pilot_timings.json").write_text(json.dumps(timings), encoding="utf-8")

    assets = {
        "pilot": {
            "mp4": "media/pilot/pilot.mp4",
            "vtt": "media/pilot/pilot.vtt",
            "srt": "media/pilot/pilot.srt",
            "txt": "media/pilot/pilot.txt",
            "poster": "media/pilot/pilot_poster.jpg",
            "timings": "media/pilot/pilot_timings.json",
        }
    }

    builder.build_library(list(catalog.values()), coverage, assets, ops)

    # 1. Tutorials copy verified
    assert (release_dir / "tutorials" / "index.html").exists()
    assert (release_dir / "tutorials" / "01-first-spec.html").exists()

    # 2. Static watch pages generated
    watch_pilot = (release_dir / "watch-pilot.html").read_text(encoding="utf-8")
    assert "Pilot: Validation & Application Handoff" in watch_pilot
    assert 'data-start-time="0.5"' in watch_pilot
    assert "00:00" in watch_pilot
    assert "Transcript for Pilot" in watch_pilot

    # 3. watch.html has pre-rendered default content and accurate seeking (no hardcoded i * 5.0)
    watch_html = (release_dir / "watch.html").read_text(encoding="utf-8")
    assert "i * 5.0" not in watch_html
    assert "sc.start_seconds" in watch_html
    assert "Written Tutorials" in watch_html


def test_preflight_checks(tmp_path: Path) -> None:
    """Verifies preflight checks execute and identify environment tools."""
    checker = PreflightChecker(repo_root=REPO_ROOT)
    report = checker.run_all(tmp_path, auto_setup=False)
    assert report.overall_ok is True
    check_names = {c.name for c in report.checks}
    assert "Python 3.12+" in check_names
    assert "Node.js" in check_names
    assert "FFmpeg / FFprobe" in check_names
    assert "Playwright Chromium" in check_names


def test_cli_dry_run() -> None:
    """Verifies produce_videos.py CLI works across all commands in dry-run mode."""
    script = REPO_ROOT / "scripts" / "produce_videos.py"
    temp_run = REPO_ROOT / "temp" / "TEMP_tutorial_videos" / "test-dry-run"

    for cmd in [
        "preflight",
        "inventory",
        "prepare",
        "narrate",
        "record",
        "compose",
        "library",
        "verify",
    ]:
        res = subprocess.run(
            [sys.executable, str(script), cmd, "--dry-run", "--output", str(temp_run)],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Command {cmd} failed: {res.stderr}"
