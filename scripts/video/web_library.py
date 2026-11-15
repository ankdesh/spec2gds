"""Self-contained, offline HTML/CSS learning library and video player generator."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional

from scripts.video.config import REPO_ROOT
from scripts.video.episodes import Episode
from scripts.video.inventory import CoverageReport, DesignerOperation

# Mapping from episode ID to written tutorial guide
TUTORIAL_LINKS: dict[str, tuple[str, str]] = {
    "pilot": ("tutorials/01-first-spec.html", "First Spec Tutorial"),
    "V00": ("tutorials/index.html", "Tutorial Overview"),
    "V01": ("tutorials/01-first-spec.html", "First Spec Tutorial"),
    "V02": ("tutorials/02-component-ports.html", "Component & Ports Guide"),
    "V03": ("tutorials/03-hardware-behavior.html", "Hardware Behavior Guide"),
    "V04": ("tutorials/validation.html", "Validation & Lint Guide"),
    "V06": ("tutorials/05-compose-design.html", "Compose Design Guide"),
    "V07": ("tutorials/06-connect-save.html", "Circuit Connections & Save Guide"),
    "V08": ("tutorials/circuit-independent.html", "Circuit Layout Reference"),
    "V09": ("tutorials/circuit-timing.html", "Timing Analysis Guide"),
    "V11": ("tutorials/04-assistant-register.html", "Assistant Register Guide"),
    "V12": ("tutorials/assistant-restricted.html", "Assistant Changes Guide"),
    "V13": ("tutorials/assistant-circuit.html", "Assistant Circuit Guide"),
    "V14": ("tutorials/07-generate-rtl.html", "RTL Generation Guide"),
    "V15": ("tutorials/verification-plan.html", "Verification Plan Guide"),
    "V16": ("tutorials/verification-coverage.html", "Verification Coverage Guide"),
    "V17": ("tutorials/verification-implementation.html", "Verification Implementation Guide"),
    "V18": ("tutorials/systemc-at.html", "SystemC Activities Guide"),
}


class WebLibraryBuilder:
    """Generates an offline, accessible local learning library with zero CDN dependencies."""

    def __init__(self, release_dir: Path):
        self.release_dir = release_dir
        self.media_dir = release_dir / "media"
        self.release_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)

    def publish_episode_assets(
        self,
        episode_id: str,
        mp4_path: Path,
        vtt_path: Path,
        srt_path: Path,
        txt_path: Path,
        poster_path: Path,
        timings_path: Optional[Path] = None,
    ) -> dict[str, str]:
        """Copies episode media files into release/media/<episode_id>/ and returns relative URLs."""
        ep_media_dir = self.media_dir / episode_id
        ep_media_dir.mkdir(parents=True, exist_ok=True)

        dest_mp4 = ep_media_dir / f"{episode_id}.mp4"
        dest_vtt = ep_media_dir / f"{episode_id}.vtt"
        dest_srt = ep_media_dir / f"{episode_id}.srt"
        dest_txt = ep_media_dir / f"{episode_id}.txt"
        dest_poster = ep_media_dir / f"{episode_id}_poster.jpg"

        shutil.copy2(mp4_path, dest_mp4)
        shutil.copy2(vtt_path, dest_vtt)
        shutil.copy2(srt_path, dest_srt)
        shutil.copy2(txt_path, dest_txt)
        shutil.copy2(poster_path, dest_poster)

        res = {
            "mp4": f"media/{episode_id}/{episode_id}.mp4",
            "vtt": f"media/{episode_id}/{episode_id}.vtt",
            "srt": f"media/{episode_id}/{episode_id}.srt",
            "txt": f"media/{episode_id}/{episode_id}.txt",
            "poster": f"media/{episode_id}/{episode_id}_poster.jpg",
        }

        if timings_path and timings_path.exists():
            dest_timings = ep_media_dir / f"{episode_id}_timings.json"
            shutil.copy2(timings_path, dest_timings)
            res["timings"] = f"media/{episode_id}/{episode_id}_timings.json"

        return res

    def copy_written_tutorials(self) -> None:
        """Copies the repository's written tutorial HTML guides and assets into release/tutorials/."""
        src = REPO_ROOT / "docs" / "tutorials"
        dest = self.release_dir / "tutorials"
        if src.exists():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)

    def build_library(
        self,
        episodes: list[Episode],
        coverage_report: CoverageReport,
        rendered_assets: dict[str, dict[str, str]],
        operations_registry: list[DesignerOperation],
    ) -> None:
        """Builds index.html, watch.html, styles.css, static watch pages, and library data."""
        self._write_styles_css()
        self.copy_written_tutorials()
        ep_data = self._prepare_episodes_data(episodes, rendered_assets)
        self._write_index_html(
            episodes, coverage_report, rendered_assets, operations_registry, ep_data
        )
        self._write_watch_html(ep_data, selected_id="pilot", output_filename="watch.html")
        # Also generate dedicated static watch pages for rendered episodes
        for ep_id in rendered_assets.keys():
            self._write_watch_html(
                ep_data, selected_id=ep_id, output_filename=f"watch-{ep_id}.html"
            )
        self._write_manifest(
            episodes, coverage_report, rendered_assets, operations_registry, ep_data
        )

    def _prepare_episodes_data(
        self,
        episodes: list[Episode],
        rendered_assets: dict[str, dict[str, str]],
    ) -> dict[str, dict]:
        """Prepares comprehensive metadata and accurate scene timings for all episodes."""
        ep_data: dict[str, dict] = {}
        for ep in episodes:
            has_media = ep.id in rendered_assets
            media = rendered_assets.get(ep.id, {})

            # Read transcript if exists
            txt_content = ""
            if has_media and (self.release_dir / media.get("txt", "")).exists():
                txt_content = (self.release_dir / media.get("txt", "")).read_text(encoding="utf-8")

            # Read timings if available
            timings_map: dict[str, dict] = {}
            timings_file = self.release_dir / media.get("timings", "")
            if not timings_file.exists():
                timings_file = self.media_dir / ep.id / f"{ep.id}_timings.json"
            if timings_file.exists():
                try:
                    for item in json.loads(timings_file.read_text(encoding="utf-8")):
                        timings_map[item["scene_id"]] = item
                except Exception:
                    pass

            scene_items = []
            cumulative_s = 0.5
            for i, s in enumerate(ep.scenes):
                if s.scene_id in timings_map:
                    t_info = timings_map[s.scene_id]
                    start_s = float(t_info.get("start_seconds", cumulative_s))
                    end_s = float(t_info.get("end_seconds", start_s + 4.0))
                    time_lbl = t_info.get(
                        "time_label",
                        f"{int(start_s // 60):02d}:{int(start_s % 60):02d}",
                    )
                    scene_items.append(
                        {
                            "title": s.title,
                            "chapter": s.chapter_title,
                            "caption": s.caption,
                            "start_seconds": start_s,
                            "end_seconds": end_s,
                            "time_label": time_lbl,
                        }
                    )
                    cumulative_s = end_s + 0.5
                else:
                    start_s = round(cumulative_s, 2)
                    end_s = round(cumulative_s + s.hold_duration, 2)
                    time_lbl = f"{int(start_s // 60):02d}:{int(start_s % 60):02d}"
                    scene_items.append(
                        {
                            "title": s.title,
                            "chapter": s.chapter_title,
                            "caption": s.caption,
                            "start_seconds": start_s,
                            "end_seconds": end_s,
                            "time_label": time_lbl,
                        }
                    )
                    cumulative_s += s.hold_duration + 0.5

            tut_link, tut_title = TUTORIAL_LINKS.get(ep.id, ("", ""))

            ep_data[ep.id] = {
                "id": ep.id,
                "title": ep.title,
                "app": ep.application.replace("_", " "),
                "summary": ep.summary,
                "target_duration": ep.target_duration,
                "has_media": has_media,
                "video_src": media.get("mp4", ""),
                "vtt_src": media.get("vtt", ""),
                "srt_src": media.get("srt", ""),
                "poster_src": media.get("poster", ""),
                "transcript": txt_content,
                "operations": ep.operations,
                "scenes": scene_items,
                "tutorial_link": tut_link,
                "tutorial_title": tut_title,
            }
        return ep_data

    def _write_styles_css(self) -> None:
        css_content = """/* Offline, zero-external-dependency styles for spec2hw video library */
:root {
  --bg-primary: #0f172a;
  --bg-secondary: #1e293b;
  --bg-card: #182234;
  --text-primary: #f8fafc;
  --text-secondary: #94a3b8;
  --accent: #38bdf8;
  --accent-hover: #0284c7;
  --border: #334155;
  --success: #10b981;
  --warning: #f59e0b;
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--font-family);
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 0 0 4rem 0;
}

header {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border);
  padding: 1.5rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}
header h1 { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
header .nav-links a {
  color: var(--text-primary);
  text-decoration: none;
  font-weight: 500;
  margin-left: 1.5rem;
  transition: color 0.2s;
}
header .nav-links a:hover { color: var(--accent); }

.container { max-width: 1200px; margin: 2rem auto; padding: 0 1.5rem; }

/* Coverage Banner */
.coverage-banner {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 2rem;
}
.coverage-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
.coverage-score { font-size: 2rem; font-weight: 800; color: var(--success); }
.app-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 1rem;
}
.app-stat {
  background: var(--bg-card);
  padding: 0.75rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
}
.app-stat .name { font-size: 0.85rem; color: var(--text-secondary); text-transform: capitalize; }
.app-stat .val { font-size: 1.25rem; font-weight: 700; color: var(--accent); }

/* Controls */
.filter-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 2rem;
  flex-wrap: wrap;
}
.search-input {
  flex: 1;
  min-width: 280px;
  padding: 0.75rem 1rem;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 1rem;
}
.search-input:focus { outline: none; border-color: var(--accent); }

/* Episode Grid */
.episode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.5rem;
}
.episode-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s, border-color 0.2s;
}
.episode-card:hover { transform: translateY(-4px); border-color: var(--accent); }
.thumbnail-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
}
.thumbnail-wrapper img { width: 100%; height: 100%; object-fit: cover; }
.duration-tag {
  position: absolute;
  bottom: 8px;
  right: 8px;
  background: rgba(0,0,0,0.8);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}
.card-content { padding: 1.25rem; flex: 1; display: flex; flex-direction: column; }
.card-meta { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.8rem; }
.badge {
  background: rgba(56, 189, 248, 0.2);
  color: var(--accent);
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}
.card-title { font-size: 1.2rem; font-weight: 700; margin-bottom: 0.5rem; }
.card-desc { font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem; flex: 1; }
.op-pills { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 1rem; }
.op-pill { font-size: 0.7rem; background: var(--border); padding: 2px 6px; border-radius: 4px; }
.card-actions { display: flex; gap: 0.5rem; align-items: center; }
.btn-watch {
  display: inline-block;
  text-align: center;
  background: var(--accent);
  color: #000;
  font-weight: 600;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  text-decoration: none;
  transition: background 0.2s;
  flex: 1;
}
.btn-watch:hover { background: var(--accent-hover); }
.btn-disabled { background: var(--border); color: var(--text-secondary); cursor: not-allowed; }
.link-guide {
  font-size: 0.8rem;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
}
.link-guide:hover { text-decoration: underline; }

/* Watch Player Page */
.player-layout { display: grid; grid-template-columns: 2fr 1fr; gap: 2rem; }
@media (max-width: 900px) { .player-layout { grid-template-columns: 1fr; } }
.video-panel video { width: 100%; border-radius: 12px; border: 1px solid var(--border); background: #000; }
.side-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.5rem;
  height: fit-content;
  max-height: 850px;
  overflow-y: auto;
}
.panel-tab-title { font-size: 1.1rem; font-weight: 700; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
.chapter-item {
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
  transition: background 0.2s;
  border-left: 3px solid transparent;
}
.chapter-item:hover { background: var(--bg-card); color: var(--accent); }
.chapter-item.active { background: var(--bg-card); color: var(--accent); font-weight: 600; border-left: 3px solid var(--accent); }
.ch-title { flex: 1; margin-right: 0.5rem; }
.ch-time { font-size: 0.8rem; color: var(--text-secondary); font-family: monospace; }
.transcript-box { font-size: 0.9rem; line-height: 1.7; color: var(--text-secondary); white-space: pre-line; }

.noscript-banner {
  background: rgba(245, 158, 11, 0.15);
  border: 1px solid var(--warning);
  color: var(--warning);
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1.5rem;
  font-size: 0.9rem;
}
.noscript-banner a { color: var(--accent); text-decoration: underline; margin: 0 0.25rem; }
"""
        (self.release_dir / "styles.css").write_text(css_content, encoding="utf-8")

    def _write_index_html(
        self,
        episodes: list[Episode],
        coverage_report: CoverageReport,
        rendered_assets: dict[str, dict[str, str]],
        operations_registry: list[DesignerOperation],
        ep_data: dict[str, dict],
    ) -> None:
        cards_html = []
        for ep in episodes:
            has_media = ep.id in rendered_assets
            data = ep_data.get(ep.id, {})
            poster = data.get("poster_src", "")
            watch_url = f"watch.html?episode={ep.id}" if has_media else "#"
            btn_class = "btn-watch" if has_media else "btn-watch btn-disabled"
            btn_text = "Watch Episode" if has_media else "Planned (Phase 2)"

            pills = "".join(f'<span class="op-pill">{op}</span>' for op in ep.operations[:4])
            if len(ep.operations) > 4:
                pills += f'<span class="op-pill">+{len(ep.operations) - 4} more</span>'

            guide_link_html = ""
            if data.get("tutorial_link"):
                guide_link_html = f'<a href="{data["tutorial_link"]}" class="link-guide" title="{data["tutorial_title"]}">Written Guide →</a>'

            card = f"""
            <div class="episode-card" data-app="{ep.application}">
              <div class="thumbnail-wrapper">
                {f'<img src="{poster}" alt="{ep.title}">' if poster else '<div style="height:100%;display:flex;align-items:center;justify-content:center;color:#64748b;">Preview Poster</div>'}
                <span class="duration-tag">{ep.target_duration}</span>
              </div>
              <div class="card-content">
                <div class="card-meta">
                  <span class="badge">{ep.id}</span>
                  <span style="color:var(--text-secondary);text-transform:capitalize;">{ep.application.replace("_", " ")}</span>
                </div>
                <h2 class="card-title">{ep.title}</h2>
                <p class="card-desc">{ep.summary}</p>
                <div class="op-pills">{pills}</div>
                <div class="card-actions">
                  <a href="{watch_url}" class="{btn_class}">{btn_text}</a>
                  {guide_link_html}
                </div>
              </div>
            </div>
            """
            cards_html.append(card)

        app_stats_html = []
        for app, stats in coverage_report.by_application.items():
            app_stats_html.append(
                f'<div class="app-stat"><div class="name">{app.replace("_", " ")}</div>'
                f'<div class="val">{stats.coverage_percent:.1f}%</div></div>'
            )

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>spec2hw Tutorial Video Library</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <h1>spec2hw Video Library</h1>
    <div class="nav-links">
      <a href="index.html">Catalogue</a>
      <a href="watch.html?episode=pilot">Pilot Player</a>
      <a href="tutorials/index.html">Written Tutorials</a>
    </div>
  </header>

  <div class="container">
    <section class="coverage-banner">
      <div class="coverage-header">
        <div>
          <h2>Designer Operations Coverage</h2>
          <p style="color:var(--text-secondary);">Independent instructional modules covering core hardware engineering workflows</p>
        </div>
        <div class="coverage-score">{coverage_report.overall_coverage_percent:.1f}% Covered</div>
      </div>
      <div class="app-grid">
        {"".join(app_stats_html)}
      </div>
    </section>

    <div class="filter-bar">
      <input type="text" id="searchInput" class="search-input" placeholder="Search by episode title, application, or operation ID...">
    </div>

    <div class="episode-grid" id="episodeGrid">
      {"".join(cards_html)}
    </div>
  </div>

  <script>
    const searchInput = document.getElementById('searchInput');
    const cards = document.querySelectorAll('.episode-card');

    searchInput.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase();
      cards.forEach(card => {{
        const text = card.textContent.toLowerCase();
        card.style.display = text.includes(query) ? 'flex' : 'none';
      }});
    }});
  </script>
</body>
</html>
"""
        (self.release_dir / "index.html").write_text(html, encoding="utf-8")

    def _write_watch_html(
        self,
        ep_data: dict[str, dict],
        selected_id: str = "pilot",
        output_filename: str = "watch.html",
    ) -> None:
        """Generates watch page with pre-rendered static content for No-JS accessibility."""
        default_ep = (
            ep_data.get(selected_id) or ep_data.get("pilot") or next(iter(ep_data.values()))
        )

        # Pre-render static HTML for default_ep so the page is fully accessible without JS
        static_chapters_html = []
        for i, sc in enumerate(default_ep.get("scenes", [])):
            active_cls = " active" if i == 0 else ""
            static_chapters_html.append(
                f'<div class="chapter-item{active_cls}" data-start-time="{sc["start_seconds"]}" data-end-time="{sc["end_seconds"]}">'
                f'<span class="ch-title">{i + 1}. {sc["chapter"]}</span>'
                f'<span class="ch-time">{sc["time_label"]}</span></div>'
            )

        static_ops_html = "".join(
            f'<span class="op-pill">{op}</span>' for op in default_ep.get("operations", [])
        )

        noscript_links = []
        for eid in ["pilot", "V00", "V01"]:
            if eid in ep_data:
                noscript_links.append(f'<a href="watch-{eid}.html">{eid}</a>')

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{default_ep["id"]}: {default_ep["title"]} - spec2hw</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header>
    <h1 id="headerTitle">{default_ep["id"]}: {default_ep["title"]}</h1>
    <div class="nav-links">
      <a href="index.html">← Back to Catalogue</a>
      <a href="tutorials/index.html">Written Tutorials</a>
    </div>
  </header>

  <div class="container">
    <noscript>
      <div class="noscript-banner">
        <strong>Offline Static Mode:</strong> Native video controls and chapter transcripts are fully functional without JavaScript.
        Switch episode: {" | ".join(noscript_links)}
      </div>
    </noscript>

    <div class="player-layout">
      <div class="video-panel">
        <video id="player" controls playsinline poster="{default_ep.get("poster_src", "")}">
          <source id="videoSource" src="{default_ep.get("video_src", "")}" type="video/mp4">
          <track id="captionTrack" kind="captions" src="{default_ep.get("vtt_src", "")}" srclang="en" label="English" default>
          Your browser does not support HTML5 video playback.
        </video>
        <div style="margin-top: 1rem;">
          <h2 id="epTitle" style="font-size: 1.5rem; margin-bottom: 0.5rem;">{default_ep["title"]}</h2>
          <p id="epSummary" style="color:var(--text-secondary);">{default_ep["summary"]}</p>
        </div>
      </div>

      <div class="side-panel">
        <div class="panel-tab-title">Chapters & Navigation</div>
        <div id="chapterList">
          {"".join(static_chapters_html)}
        </div>

        <div class="panel-tab-title" style="margin-top:1.5rem;">Demonstrated Operations</div>
        <div id="operationsList" class="op-pills">
          {static_ops_html}
        </div>

        <div class="panel-tab-title" style="margin-top:1.5rem;">Synchronized Transcript</div>
        <div id="transcriptBox" class="transcript-box">{default_ep.get("transcript", "Transcript available upon playback.")}</div>
      </div>
    </div>
  </div>

  <script>
    const episodes = {json.dumps(ep_data)};
    const urlParams = new URLSearchParams(window.location.search);
    const selectedId = urlParams.get('episode') || '{selected_id}';
    const ep = episodes[selectedId] || episodes['{selected_id}'];

    document.getElementById('epTitle').textContent = ep.title;
    document.getElementById('headerTitle').textContent = ep.id + ': ' + ep.title;
    document.getElementById('epSummary').textContent = ep.summary;

    const player = document.getElementById('player');
    const videoSource = document.getElementById('videoSource');
    const captionTrack = document.getElementById('captionTrack');

    if (ep.has_media) {{
      videoSource.src = ep.video_src;
      captionTrack.src = ep.vtt_src;
      player.poster = ep.poster_src;
      player.load();
    }} else {{
      document.querySelector('.video-panel').innerHTML = '<div style="background:var(--bg-secondary);padding:3rem;border-radius:12px;text-align:center;"><h2>Episode Planned for Phase 2</h2><p style="color:var(--text-secondary);margin-top:1rem;">This episode recipe is registered and will be rendered in Phase 2.</p><a href="index.html" class="btn-watch" style="margin-top:1.5rem;">Back to Catalogue</a></div>';
    }}

    // Accurate Chapters & Seek Actions
    const chapterList = document.getElementById('chapterList');
    chapterList.innerHTML = '';
    if (ep.scenes && ep.scenes.length > 0) {{
      ep.scenes.forEach((sc, i) => {{
        const item = document.createElement('div');
        item.className = 'chapter-item' + (i === 0 ? ' active' : '');
        item.dataset.startTime = sc.start_seconds;
        item.dataset.endTime = sc.end_seconds;
        item.innerHTML = '<span class="ch-title">' + (i + 1) + '. ' + sc.chapter + '</span><span class="ch-time">' + sc.time_label + '</span>';
        item.onclick = () => {{
          player.currentTime = sc.start_seconds;
          player.play();
        }};
        chapterList.appendChild(item);
      }});
    }}

    // Active Chapter Highlighting on Playback
    player.addEventListener('timeupdate', () => {{
      const cur = player.currentTime;
      const items = document.querySelectorAll('.chapter-item');
      items.forEach((it) => {{
        const start = parseFloat(it.dataset.startTime || '0');
        const end = parseFloat(it.dataset.endTime || '999999');
        if (cur >= start && cur < end) {{
          it.classList.add('active');
        }} else {{
          it.classList.remove('active');
        }}
      }});
    }});

    // Operations
    const opList = document.getElementById('operationsList');
    opList.innerHTML = '';
    ep.operations.forEach(op => {{
      const pill = document.createElement('span');
      pill.className = 'op-pill';
      pill.textContent = op;
      opList.appendChild(pill);
    }});

    // Transcript
    document.getElementById('transcriptBox').textContent = ep.transcript || 'Transcript generated with synchronized narration cues.';
  </script>
</body>
</html>
"""
        (self.release_dir / output_filename).write_text(html, encoding="utf-8")

    def _write_manifest(
        self,
        episodes: list[Episode],
        coverage_report: CoverageReport,
        rendered_assets: dict[str, dict[str, str]],
        operations_registry: list[DesignerOperation],
        ep_data: dict[str, dict],
    ) -> None:
        # Calculate checksums for rendered media
        checksums: dict[str, dict[str, str]] = {}
        for ep_id, assets in rendered_assets.items():
            ep_hashes = {}
            for k, rel_path in assets.items():
                full_path = self.release_dir / rel_path
                if full_path.exists() and full_path.is_file():
                    ep_hashes[k] = hashlib.sha256(full_path.read_bytes()).hexdigest()
            checksums[ep_id] = ep_hashes

        manifest = {
            "library": "spec2hw Tutorial Video Series",
            "coverage": coverage_report.to_dict(),
            "episodes": [ep.to_dict() for ep in episodes],
            "rendered_assets": rendered_assets,
            "checksums": checksums,
        }
        (self.release_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
