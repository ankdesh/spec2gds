"""FFmpeg timeline composition, H.264 encoding, subtitle, chapter, and poster generation."""

import json
import shutil
import subprocess
from pathlib import Path

from scripts.video.config import (
    AUDIO_BITRATE,
    AUDIO_CODEC,
    AUDIO_SAMPLE_RATE,
    TARGET_FPS,
    TARGET_HEIGHT,
    TARGET_WIDTH,
    VIDEO_CODEC,
    VIDEO_CRF,
    VIDEO_PIXEL_FORMAT,
    VIDEO_PRESET,
)
from scripts.video.episodes import Episode, Scene


def format_timestamp_vtt(seconds: float) -> str:
    """Formats seconds to WebVTT timestamp (HH:MM:SS.mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msec = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{msec:03d}"


def format_timestamp_srt(seconds: float) -> str:
    """Formats seconds to SubRip SRT timestamp (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    msec = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msec:03d}"


def format_timestamp_minsec(seconds: float) -> str:
    """Formats seconds to MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


class VideoCompositor:
    """Coordinates FFmpeg post-processing, audio sync, and metadata delivery."""

    def __init__(self) -> None:
        self.ffmpeg_bin = shutil.which("ffmpeg")
        self.ffprobe_bin = shutil.which("ffprobe")
        if not self.ffmpeg_bin or not self.ffprobe_bin:
            raise FileNotFoundError("FFmpeg and FFprobe are required for VideoCompositor.")

    def generate_subtitles(
        self,
        scenes: list[Scene],
        timings: list[tuple[float, float]],
        output_vtt: Path,
        output_srt: Path,
    ) -> None:
        """Generates WebVTT and SubRip SRT subtitle files matching scene timings."""
        output_vtt.parent.mkdir(parents=True, exist_ok=True)
        output_srt.parent.mkdir(parents=True, exist_ok=True)

        vtt_lines = ["WEBVTT - spec2hw Tutorial Series", ""]
        srt_lines = []

        for idx, (scene, (start, end)) in enumerate(zip(scenes, timings), start=1):
            # VTT
            vtt_lines.append(f"{format_timestamp_vtt(start)} --> {format_timestamp_vtt(end)}")
            vtt_lines.append(scene.caption)
            vtt_lines.append("")

            # SRT
            srt_lines.append(str(idx))
            srt_lines.append(f"{format_timestamp_srt(start)} --> {format_timestamp_srt(end)}")
            srt_lines.append(scene.caption)
            srt_lines.append("")

        output_vtt.write_text("\n".join(vtt_lines), encoding="utf-8")
        output_srt.write_text("\n".join(srt_lines), encoding="utf-8")

    def generate_transcript(
        self,
        scenes: list[Scene],
        timings: list[tuple[float, float]],
        output_txt: Path,
        episode_title: str,
    ) -> None:
        """Generates clean plaintext transcript with timestamps and chapter headings."""
        output_txt.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"Transcript: {episode_title}", "=" * 50, ""]
        for scene, (start, _) in zip(scenes, timings):
            ts = format_timestamp_minsec(start)
            lines.append(f"[{ts}] {scene.chapter_title}")
            lines.append(f"{scene.caption}")
            lines.append("")
        output_txt.write_text("\n".join(lines), encoding="utf-8")

    def generate_chapters_metadata(
        self,
        scenes: list[Scene],
        timings: list[tuple[float, float]],
        output_meta: Path,
        episode_title: str,
    ) -> None:
        """Generates FFmetadata file for embedding chapter markers into MP4."""
        output_meta.parent.mkdir(parents=True, exist_ok=True)
        meta_lines = [
            ";FFMETADATA1",
            f"title={episode_title}",
            "artist=spec2hw",
            "",
        ]
        for scene, (start, end) in zip(scenes, timings):
            start_ms = int(round(start * 1000))
            end_ms = int(round(end * 1000))
            meta_lines.append("[CHAPTER]")
            meta_lines.append("TIMEBASE=1/1000")
            meta_lines.append(f"START={start_ms}")
            meta_lines.append(f"END={end_ms}")
            meta_lines.append(f"title={scene.chapter_title}")
            meta_lines.append("")
        output_meta.write_text("\n".join(meta_lines), encoding="utf-8")

    def extract_poster(self, video_file: Path, output_jpg: Path, timestamp: float = 2.0) -> Path:
        """Extracts high-resolution poster JPEG from key frame in video."""
        output_jpg.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-ss",
            str(timestamp),
            "-i",
            str(video_file),
            "-vframes",
            "1",
            "-q:v",
            "2",
            str(output_jpg),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_jpg

    def stitch_audio_cues(
        self,
        audio_cues: list[Path],
        timings: list[tuple[float, float]],
        total_duration: float,
        output_combined_wav: Path,
    ) -> Path:
        """Combines discrete audio cues into a single synchronized master track with exact padding."""
        output_combined_wav.parent.mkdir(parents=True, exist_ok=True)

        # Build filtergraph to delay and mix cues at respective start timestamps
        # adelay filter uses milliseconds: adelay=1500|1500
        inputs = []
        filter_parts = []
        for i, (cue, (start, _)) in enumerate(zip(audio_cues, timings)):
            inputs.extend(["-i", str(cue)])
            delay_ms = int(round(start * 1000))
            filter_parts.append(
                f"[{i}:a]adelay={delay_ms}|{delay_ms},aformat=sample_rates=48000:channel_layouts=stereo[{f'a{i}'}]"
            )

        mix_inputs = "".join(f"[a{i}]" for i in range(len(audio_cues)))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(audio_cues)}:duration=longest:dropout_transition=0:normalize=0,apad=whole_dur={total_duration}[outa]"
        )

        filter_complex = ";".join(filter_parts)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[outa]",
            "-ar",
            str(AUDIO_SAMPLE_RATE),
            str(output_combined_wav),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_combined_wav

    def compose_episode(
        self,
        episode: Episode,
        raw_video_path: Path,
        audio_cues: list[Path],
        output_dir: Path,
    ) -> dict:
        """Renders complete 1080p H.264 MP4 with AAC, embedded chapters, WebVTT, SRT, and poster."""
        output_dir.mkdir(parents=True, exist_ok=True)
        final_mp4 = output_dir / f"{episode.id}.mp4"
        output_vtt = output_dir / f"{episode.id}.vtt"
        output_srt = output_dir / f"{episode.id}.srt"
        output_txt = output_dir / f"{episode.id}.txt"
        output_poster = output_dir / f"{episode.id}_poster.jpg"
        meta_file = output_dir / f"{episode.id}_metadata.txt"

        # Probe raw video duration
        cmd = [
            self.ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(raw_video_path),
        ]
        video_dur = float(subprocess.check_output(cmd, text=True).strip())

        # Compute scene timings
        timings: list[tuple[float, float]] = []
        current_time = 0.5  # brief initial hold
        for i, scene in enumerate(episode.scenes):
            cue_dur = 4.0
            if i < len(audio_cues):
                # get cue duration
                c_dur_cmd = [
                    self.ffprobe_bin,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(audio_cues[i]),
                ]
                cue_dur = float(subprocess.check_output(c_dur_cmd, text=True).strip())
            scene_len = max(cue_dur + 0.5, scene.hold_duration)
            timings.append((current_time, current_time + cue_dur))
            current_time += scene_len

        total_audio_dur = current_time + 1.0
        final_duration = max(video_dur, total_audio_dur)

        # Stitch master audio track
        master_audio = output_dir / "master_audio.wav"
        self.stitch_audio_cues(audio_cues, timings, final_duration, master_audio)

        # Generate subtitles and chapter files
        self.generate_subtitles(episode.scenes, timings, output_vtt, output_srt)
        self.generate_transcript(episode.scenes, timings, output_txt, episode.title)
        self.generate_chapters_metadata(episode.scenes, timings, meta_file, episode.title)

        # Render final H.264 MP4 with faststart and embedded chapters
        # Loop or pad video if audio is longer than raw recording
        if video_dur < final_duration:
            pad_needed = final_duration - video_dur
            vf = f"tpad=stop_mode=clone:stop_duration={pad_needed},scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format={VIDEO_PIXEL_FORMAT}"
        else:
            vf = f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}:force_original_aspect_ratio=decrease,pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format={VIDEO_PIXEL_FORMAT}"

        render_cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i",
            str(raw_video_path),
            "-i",
            str(master_audio),
            "-i",
            str(meta_file),
            "-map_metadata",
            "2",
            "-filter:v",
            vf,
            "-c:v",
            VIDEO_CODEC,
            "-preset",
            VIDEO_PRESET,
            "-crf",
            str(VIDEO_CRF),
            "-r",
            str(TARGET_FPS),
            "-c:a",
            AUDIO_CODEC,
            "-b:a",
            AUDIO_BITRATE,
            "-ar",
            str(AUDIO_SAMPLE_RATE),
            "-movflags",
            "+faststart",
            "-t",
            str(final_duration),
            str(final_mp4),
        ]
        subprocess.run(render_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Save structured scene timings for WebLibrary and player navigation
        timings_data = []
        for scene, (start, end) in zip(episode.scenes, timings):
            timings_data.append(
                {
                    "scene_id": scene.scene_id,
                    "title": scene.title,
                    "chapter": scene.chapter_title,
                    "caption": scene.caption,
                    "start_seconds": round(start, 3),
                    "end_seconds": round(end, 3),
                    "time_label": format_timestamp_minsec(start),
                }
            )
        timings_json = output_dir / f"{episode.id}_timings.json"
        timings_json.write_text(json.dumps(timings_data, indent=2), encoding="utf-8")

        # Extract poster image
        self.extract_poster(final_mp4, output_poster, timestamp=min(2.0, final_duration / 2))

        return {
            "mp4": str(final_mp4),
            "vtt": str(output_vtt),
            "srt": str(output_srt),
            "transcript": str(output_txt),
            "poster": str(output_poster),
            "timings_json": str(timings_json),
            "duration": final_duration,
            "timings": timings_data,
        }
