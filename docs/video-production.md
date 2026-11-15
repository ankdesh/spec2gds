# spec2hw Video Production Guide

This document defines the architecture, operation inventory, CLI workflows, and verification standards for the automated **spec2hw tutorial video library**.

---

## 1. Architecture and Design Principles

The spec2hw video series delivers independent, modular instructional videos designed for digital hardware engineers. Each episode teaches a focused set of designer operations across the six core applications:
1. **Spec Editor**: Authoritative logical hardware document authoring, explicit port ranges, SystemVerilog implementation blocks, and Verilator linting.
2. **Circuit Designer**: Visual schematic authoring, net routing, port width mismatch inspection, and the canonical **Save to Spec** action.
3. **AI Assistant**: Human-in-the-loop co-design, architecture reviews, AST diff approvals, and circuit proposals.
4. **Verification Planner**: Verification intent, coverage contracts, simulation campaign traces, and simulator implementation bindings.
5. **Spec Catalog**: Browsing, inspecting provenance and verification evidence, and importing reusable IP blocks into the local workspace.
6. **Activities**: Automated workflows and jobs, including `rtl.generate` and Verilator simulation.

### Core Technical Tenets
- **Real Application Execution**: All recordings are captured in 1920x1080 resolution using Playwright Chromium against isolated, private loopback services. No product APIs or extension mechanisms are mocked.
- **Local AI Narration**: Spoken narration is generated entirely offline using **Piper 1.8.0** with the `en_US-ljspeech-high` voice model (22.05 kHz native sample rate, public domain dataset).
- **EBU R128 Loudness Normalization**: All audio tracks are normalized using FFmpeg's `loudnorm` filter to **-16.0 LUFS** (±0.5 LUFS) with true peaks capped at **<= -1.0 dBTP**.
- **Synchronized Subtitles & Chapters**: Every episode includes millisecond-accurate WebVTT (`.vtt`), SubRip (`.srt`), plaintext transcripts (`.txt`), and embedded MP4 chapter markers.
- **Offline Local Learning Library**: The delivered library in `release/` requires zero external fonts, remote CDNs, or network connectivity.

---

## 2. Directory Layout & Output Quarantine

In strict compliance with repository constitution (`AGENTS.md`), all media tools, caches, takes, and outputs reside inside the ignored directory `temp/TEMP_tutorial_videos/<run-id>/`:

```text
temp/TEMP_tutorial_videos/<run-id>/
├── environment/       # Private loopback service configurations, logs, process IDs
├── starts/            # Fresh isolated starting .spec archives and checkpoints
├── originals/         # 1080p raw Chromium recordings and Playwright action logs
├── narration/         # Raw generated WAV cues and -16 LUFS normalized audio
├── timelines/         # Timestamps, cut markers, and chapter timings
├── renders/           # Final 1080p H.264 MP4s, WebVTT, SRT, transcripts, posters
├── evidence/          # Preflight and operation coverage audit receipts
└── release/           # Self-contained offline HTML video library & web player
    ├── index.html     # Searchable episode catalogue and coverage dashboard
    ├── watch.html     # Standalone accessible HTML5 player with chapter navigation
    ├── styles.css     # Clean CSS styling (no remote fonts/CDNs)
    ├── manifest.json  # Comprehensive machine-readable series manifest
    └── media/         # Final MP4, VTT, SRT, and poster deliverables
```

---

## 3. Operation Inventory and Coverage Target

The production pipeline enforces a minimum **>= 80%** designer operation coverage across each individual application and overall.

| Application | Total Defined Operations | Priority Operations | Key Focus Areas |
|---|---|---|---|
| **Spec Editor** | 15 | `OP_SPEC_NEW`, `OP_SPEC_COMPONENT_ADD`, `OP_SPEC_PORT_RANGE`, `OP_SPEC_SV_SECTION_ADD`, `OP_SPEC_VERIFY_COMPONENT` | Logical document authoring, explicit ranges, SV section linting, Diagnostics. |
| **Circuit Designer** | 12 | `OP_CIRCUIT_LAUNCH`, `OP_CIRCUIT_EDIT_BEGIN`, `OP_CIRCUIT_ADD_INSTANCE`, `OP_CIRCUIT_SAVE_TO_SPEC` | Schematic placement, net routing, width warnings, Save to Spec. |
| **AI Assistant** | 6 | `OP_AI_LAUNCH_BOUND`, `OP_AI_CONVERSATION_TURN`, `OP_AI_ARCH_REVIEW_APPROVE`, `OP_AI_DIFF_REVIEW_APPROVE` | Document context, multi-turn dialogue, approval checkpoints. |
| **Verification Planner** | 6 | `OP_VERIF_IMPORT_SNAPSHOT`, `OP_VERIF_AUTHOR_INTENT`, `OP_VERIF_COVERAGE_POLICY` | Test plans, requirement intent, coverage thresholds, campaign traces. |
| **Spec Catalog** | 5 | `OP_CATALOG_BROWSE`, `OP_CATALOG_SEARCH_FILTER`, `OP_CATALOG_IMPORT_RENAMED` | IP catalog search, evidence inspection, renamed package import. |
| **Activities** | 5 | `OP_ACTIVITY_RTL_GENERATE`, `OP_ACTIVITY_MONITOR_PROGRESS`, `OP_ACTIVITY_DOWNLOAD_ARCHIVE` | Activity jobs, progress tracking, RTL downloads, Verilator lints. |

---

## 4. Episode Catalogue

The series consists of the foundational Pilot episode followed by 19 independent episodes (V00–V18):

| ID | Title | Target Application | Focus & Demonstrated Capabilities |
|---|---|---|---|
| **Pilot** | Validation & Application Handoff | Spec Editor & Circuit Designer | End-to-end component creation, explicit port ranges, SV linting, Diagnostics, and handoff to Circuit Designer. |
| **V00** | System Tour | All Applications | System overview, source authority of Spec Editor, Circuit topology, Assistant co-design, Planner contracts, Catalog & Activities. |
| **V01** | Spec Files and Navigation | Spec Editor | New, open, copy, rename, Contents navigation, draft saves/cancellation, and theme selection. |
| **V02** | Components, Ports, and Parameters | Spec Editor | Scalar and vector ranges, port duplication, port deletion, parameter controls. |
| **V03** | Sections, Behavior, and Previews | Spec Editor | Narrative authoring, SystemVerilog implementation, topology previews, and SVG download. |
| **V04** | Verification and Diagnostics | Spec Editor | Automated Verilator lint, Diagnostics drawer, error line navigation, and draft source retention. |
| **V05** | Catalog Reuse and Publishing | Spec Catalog | Catalog search/filtering, evidence inspection, collision-free imports, local publishing. |
| **V06** | Design Composition | Spec Editor | Composite Designs, instance referencing, boundary interfaces. |
| **V07** | Circuit Editing and Connections | Circuit Designer | Schematic editing session, node placement, net routing, width warnings, Save to Spec. |
| **V08** | Circuit Layout and Routing | Circuit Designer | Pan, zoom, fit-to-view, inspector controls, net routing, and route locking. |
| **V09** | Hierarchy and Timing | Circuit Designer | Hierarchy traversal, clock domain badges, timing analysis warnings. |
| **V10** | Circuit Files and Preferences | Circuit Designer | Standalone exports (JSON, SVG, PNG), theme switches, keyboard shortcuts. |
| **V11** | Assistant Conversations and Context | AI Assistant | Bound Spec context, multi-turn conversation, history persistence. |
| **V12** | Assistant Architecture & Spec Changes | AI Assistant | Architecture plan approvals, AST diff reviews, rejected change handling. |
| **V13** | Assistant Circuit Proposals | AI Assistant | Circuit proposal generation, review in private draft, and committing to Spec. |
| **V14** | Activities and RTL Outputs | Activities | `rtl.generate` execution, log streaming, archive downloads, Verilator lints. |
| **V15** | Verification Planner: Intent | Verification Planner | Spec snapshot import, requirements capture, review blockers. |
| **V16** | Verification Planner: Coverage | Verification Planner | Coverage policies, simulation campaign imports, trace retention. |
| **V17** | Verification Planner: Implementation | Verification Planner | Backend recipe bindings, Test IR, preflight checks, reference testbench generation. |
| **V18** | Optional SystemC and TLM | Activities | SystemC transaction modeling, tool requirements, and build checks. |

---

## 5. Unified CLI Reference (`scripts/produce_videos.py`)

All video production operations are executed through the unified entry point:

```bash
# 1. Verify system prerequisites, tools, and models
python3 scripts/produce_videos.py preflight

# 2. Audit operation registry and verify >=80% coverage
python3 scripts/produce_videos.py inventory

# 3. Prepare clean starting specs and checkpoints
python3 scripts/produce_videos.py prepare

# 4. Synthesize narration audio with Piper TTS and EBU R128 loudnorm
python3 scripts/produce_videos.py narrate --episode pilot,V00,V01

# 5. Record 1080p screen interactions via Playwright Chromium
python3 scripts/produce_videos.py record --episode pilot,V00,V01

# 6. Compose video, audio, subtitles (VTT/SRT), and embedded chapters
python3 scripts/produce_videos.py compose --episode pilot,V00,V01

# 7. Generate offline learning library and HTML player
python3 scripts/produce_videos.py library

# 8. Run automated quality assertions on rendered media
python3 scripts/produce_videos.py verify --episode pilot,V00,V01

# 9. Run the entire production pipeline end-to-end
python3 scripts/produce_videos.py all --episode pilot,V00,V01
```

### CLI Flags
- `--episode <ids>`: Comma-separated list of episode IDs to process (default: `pilot,V00,V01`).
- `--output <path>`: Custom output run directory (must reside inside `temp/TEMP_*`).
- `--dry-run`: Validates manifests and commands without executing long child processes or model inference.
- `--resume`: Reuses existing audio caches and intermediate renders.

---

## 6. Testing & Quality Assurance

Automated unit and integration checks are verified with `pytest`:

```bash
uv run pytest tests/test_video_production.py -v
```

This validates:
- Operations registry uniqueness, application distribution, and coverage calculation.
- Phonetic pronunciation substitutions (e.g. `spec2hw` -> "spec to hardware", `clk` -> "clock").
- Subtitle formatting compliance (WebVTT timestamps with periods, SRT with commas).
- FFmetadata chapter syntax and timestamp alignment.
- Zero-external-dependency integrity of generated HTML/CSS player assets.
- CLI argument parsing and dry-run execution.
