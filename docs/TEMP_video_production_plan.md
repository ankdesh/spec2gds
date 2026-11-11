# Plan 2: Independent spec2hw video library

Handoff date: 2026-11-11.

Status: approved direction; production is for a later coding agent. This document
does not authorize public upload. Plan 1 (the written tutorial refresh) remains a
separate plan, unchanged and ready for implementation. The current request is to
save this Plan 2 handoff only. Do not start either implementation from this request.
Do not replace Plan 1's practical exercises with videos.

## 1. Purpose and confirmed decisions

Teach designers who know basic digital hardware and are new to spec2hw. Cover
approximately 80% of meaningful, supported end-user operations. The videos are
independent of written tutorial numbering and order. A designer can watch a video
without completing a tutorial or watching earlier episodes.

- Produce a 5–7 minute system overview and focused videos of about 6–12 minutes.
- Use real application recordings, English AI narration, captions, and chapters.
- Generate narration locally. Do not use a paid speech API or send scripts to a
  cloud speech service.
- Deliver a self-contained local learning library. Do not upload to a public
  channel or publish into a shared Catalog.
- Use prepared starts, but perform the operation being taught through the UI.
- Keep source recipes in Git. Keep models, recordings, intermediate media, logs,
  and rendered MP4 files in ignored repository `temp/TEMP_*` directories.

## 2. Read these sources first

Read `AGENTS.md`, `docs/TERMINOLOGY.md`, and `docs/testing-strategy.md`. Inspect the
current source and served UI before writing final narration. In particular:

- `docs/spec-editor.md`, `docs/circuit-designer.md`, and `docs/ai-assistant.md`;
- `docs/ai-assistant-flows.md`, `docs/verification-planner.md`, and
  `docs/systemc-activities.md`;
- `spec_catalog_service/README.md` and the Catalog browser UI;
- `scripts/prepare_tutorials.py`, `scripts/tutorial_verification.py`, and
  `docs/tutorials/example.json` for reusable prepared examples;
- `tests/ui-scenarios/e2e/fixtures.ts` for private service/process management;
- `tests/ui-scenarios/runner/run_scenario.ts` for Assistant launch, observable
  review states, and capture patterns.

Do not use the existing IRQ/timer presentation scenario as a registered-adder
recording. Do not infer current behavior from an old screenshot or this plan.
Preserve the intended teaching outcome when controls change; document deviations.

Use Spec Editor, Circuit Designer, AI Assistant, Verification Planner, Spec,
Component, Design, Section, Activity, job, flow, conversation, and Save to Spec
with their canonical meanings. Use spec2hw for the product and spec2gds for
existing repository identifiers. Do not describe a private draft or approval as a
saved result.

## 3. Operation inventory and coverage

Before production, inventory supported designer operations from the actual UI,
action definitions, help, and browser scenarios. Count a distinct user intention
once. For example, exporting a Circuit is an operation; every submenu click is
not another operation. Different domain outcomes can have separate entries.

For each operation record an ID, application, purpose, prerequisites, expected
visible result, durable result where applicable, priority, episode/scene IDs,
evidence references, coverage status, and any exclusion reason.

Coverage states are `planned`, `recorded`, `validated`, `blocked`, and `excluded`.
Only validated demonstrations count. A menu mention or screenshot alone does not
count as an operation demonstration. Freeze the inventory for the recorded source
revision and report changes to its denominator.

Target at least 80% of supported designer operations and all essential create,
edit, save, review, verify, generate, and export flows. Report coverage by
application as well as overall. Do not omit an application to reach the total.
Keep missing-tool and missing-credential operations blocked and visible; do not
remove them from the inventory to increase coverage.

Exclude developer APIs, SDK development, package releases, embedding components,
service administration, and unsupported future features. Installation is a
prerequisite, not the main subject of the series.

## 4. Independent episode catalogue

| ID | Episode | Required demonstrations |
| --- | --- | --- |
| V00 | System tour | Roles of Spec Editor, Circuit Designer, AI Assistant, Verification Planner, Catalog, and Activities; show their handoffs and source authority. |
| V01 | Spec files and navigation | New, open, copy, rename, Contents, draft saves/cancel, refresh, and read-only notices. |
| V02 | Components, ports, and parameters | Create/edit definitions; add, edit, duplicate, and delete ports; Save and add another; scalar and explicit Range inputs; parameter controls. |
| V03 | Sections, behavior, and previews | Narrative, SystemVerilog, hardware settings, compact interface previews, Expand, and original SVG download. |
| V04 | Verification and Diagnostics | Verify, result notification, manual panel opening, failed/current/stale results, source navigation, generated-file locations, and Technical details. |
| V05 | Catalog reuse and publishing | Browse, search, filter, inspect versions/evidence, import review, renamed-copy conflicts, local origin, and publish a teaching package into a private Catalog copy. |
| V06 | Design composition | Boundary interfaces, Internal Design, instance references, entry Design, and definition reuse. |
| V07 | Circuit editing and connections | Selection, movement, boundary controls, connections, width errors, undo, cancel, Save to Spec, and persistence. |
| V08 | Circuit layout and routing | Pan, zoom, fit, Inspector, arrangement, bends, rerouting, and route locks. |
| V09 | Hierarchy and timing | Child Designs, navigation, cycle edges, clock domains, timing analysis, warnings, and timing annotations versus actual RTL. |
| V10 | Circuit files and preferences | Independent files, source binding, JSON/SVG/PNG exports, themes, shortcuts, and shortcut conflicts. |
| V11 | Assistant conversations and context | Bound launches, target scope, supported conversation modes, context, history, and the effect of opening a different Spec. |
| V12 | Assistant architecture and Spec changes | Architecture review/revise/approve, execution progress and supported controls, restricted content approval/rejection, and confirmed saved receipts. |
| V13 | Assistant Circuit proposals | Circuit binding, proposal review, acceptance into a private draft, inspection, save, cancel, and final persistence. |
| V14 | Activities and RTL outputs | Availability, launch, progress, cancellation, failures, results, downloads, revision identity, and actual RTL project inspection/lint. |
| V15 | Verification Planner: intent | Snapshot import, source audit, captured requirements, intent authoring, review blockers, and P1. |
| V16 | Verification Planner: coverage | Objectives, policies, C1, campaigns/profiles, staged result import, gaps, trace, and failure retention. |
| V17 | Verification Planner: implementation | Bindings, recipes, Test IR, backend configuration, I1, preflight, reference generation, and supported exports/imports. |
| V18 | Optional SystemC and TLM | Compatible input profiles, tool requirements, availability limits, both generation paths, output inspection, and actual build checks when prerequisites exist. |

Adjust scene boundaries to current supported controls. Keep these episode purposes
and independent starts. Use chapters within longer videos. Do not require a
designer to remember earlier narration to understand a save or approval boundary.

## 5. Source and output layout

Implement a permanent `docs/video-production.md` handbook from this plan. Keep
episode descriptions, operation inventory, scene definitions, narration,
pronunciation substitutions, render configuration, and tool dependency pins in
maintained source files. Use the existing Playwright workspace instead of adding
a second browser automation stack. Keep video definitions separate from written
lesson data; optional cross-links may connect them.

For each production run use a fresh directory such as:

```text
temp/TEMP_tutorial_videos/<run-id>/
  environment/       # private service registry, state, preferences, process IDs
  starts/            # independent source copies and checkpoint manifest
  originals/        # raw per-page recordings, traces, unmodified screenshots
  narration/        # cue text, native WAV files, audio metadata
  timelines/        # measured cuts, scene markers, caption/chapter timing
  renders/          # final MP4, posters, VTT, SRT, transcript, chapters
  evidence/         # assertions, commands, outcomes, limitations, checksums
  release/          # self-contained local learning library
```

Put the media-tool environment, model files, package/model caches, and subprocess
temporary files under `temp/TEMP_tutorial_videos/` too. Set TMPDIR, TMP, and TEMP
for child processes. Never use `/tmp` for these outputs. Refuse to overwrite an
existing run. Keep resuming explicit and verify input hashes first.

## 6. Production procedure for a coding agent

### A. Preflight and private services

1. Inspect Git status and preserve unrelated changes. Record the source commit,
   dirty-source digest, browser, tool versions, and served bundle hashes.
2. Check Python, Node, Playwright Chromium, FFmpeg, FFprobe, Piper, fonts, and disk
   space. Use the repository's supported Node version for the combined apps.
3. Check actual model access for Assistant authoring scenes. Speech is local, but
   demonstrating the AI Assistant still needs configured model credentials.
4. Check Verilator and Make for RTL; check CIRCT, the native emitter, SystemC,
   and CMake for the applicable optional scenes. Separate required and optional
   prerequisites in the report.
5. Start private processes on available loopback ports with private configuration,
   Spec root, service state, Catalog copy, preferences, downloads, and job outputs.
   Reuse the isolation pattern from the browser tests. Do not enable their fake
   Activity extensions in the production capture environment.
6. Preserve document-binding, edit-access, revision, review, and download checks.
   Do not disable product checks to make a recording succeed.
7. Track child process groups and stop only those groups. Do not restart shared
   services or use the combined launcher's shared process record for capture.
8. Report missing prerequisites per scene. Continue independent episodes. Never
   report a missing-tool scene as demonstrated or silently replace live inference.

At planning time FFmpeg was available; Piper still needed installation. The Snap
uv launcher could not run in the restricted environment. Resolve the current
tool path before production; do not assume the earlier environment still applies.

### B. Prepare examples and scene definitions

Use the canonical registered adder where it fits. Use separate named examples
for Catalog publication and TLM. Prepare data through supported public service
interfaces, and copy each episode's start before recording. Do not patch archives
or directly write product databases to create a review or saved-result state.

Each scene must specify:

- Scene ID, episode ID, operation IDs, and one learning purpose.
- Starting source/checkpoint, exact target, source revision, and review policy.
- Ordered UI actions using stable roles, labels, or maintained test IDs.
- Assertions for the initial state, important transitions, and final result.
- Saved-state assertions for source-changing operations, including a reopen.
- Narration text, caption text, pronunciation substitutions, and chapter label.
- Framing, intended pauses, expected duration, and output names.
- Reset procedure and supported failure/recovery branch.

Audit new Spec Editor behavior explicitly: manual Diagnostics/Activity opening;
notifications with View details; no inline verification report; explicit port
Ranges; retained invalid drafts; no Paste rows; bounded previews; published
Catalog evidence separate from verification of current source.

Create a pilot with port validation, a Diagnostics finding, and an application
handoff. Complete the pilot's quality checks before bulk recording.

### C. Capture real application operations

- Use Chromium, a 1920 x 1080 viewport, device scale factor 1, and matching
  Playwright recordVideo dimensions. Do not accept its smaller default recording.
- Use Clean in Spec Editor and each other application's normal theme. Include
  theme/narrow-layout changes when they teach a meaningful operation.
- Record each page separately. Make application changes explicit in the edit.
- Record real typing, selection, dragging, dialogs, reviews, and result states.
- Wait for observable UI/API conditions; use bounded waits, not arbitrary sleeps.
- Capture action and scene timestamps. Close the recording context so Playwright
  flushes its video. Keep the raw file and trace.
- Keep controls and messages visible. Add cursor emphasis in editing if needed.
  Do not alter application state or replace screen content to improve appearance.
- Use real services and live Assistant execution for model-authoring scenes.
  Introduce prepared content as prepared content. Fixture demonstrations do not
  establish live Assistant behavior and cannot satisfy those scene requirements.
- Retain failures and reset from a fresh start for another take. A quickly
  completed job is not evidence of cancellation; retry that scene or mark it
  incomplete. Never manufacture a running state.

Show architecture approval, content approval, Circuit proposal acceptance, and
Save to Spec separately. Verify the actual saved outcome. Preserve the distinction
between lint, reference generation, synthetic evidence, and hardware simulation.

### D. Local narration

Default tooling: Piper 1.8.0, CPU inference, `en_US-ljspeech-high`, one consistent
English voice. Use a separate media-tool environment, not the product runtime.

Primary references checked during planning:

- [Piper Python API, v1.8.0](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/docs/API_PYTHON.md)
- [Piper CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md)
- [LJ Speech voice model card](https://huggingface.co/rhasspy/piper-voices/blob/main/en/en_US/ljspeech/high/MODEL_CARD)

Verify the pinned package is available and record its actual dependency lock.
Download the ONNX model, JSON configuration, model card, and notices at one
recorded model-repository commit. Record SHA-256 values and verify them on reuse.
The checked voice card identifies US English, one speaker, 22,050 Hz, and a
public-domain training dataset. Preserve the actual engine and voice notices;
do not infer every model's terms from repository-wide metadata.

Load the voice once and synthesize short cues with `PiperVoice.synthesize_wav`.
Retain native WAV files and resample only for final rendering. Use default voice
settings initially; pin settings after the pilot. Aim for calm delivery at about
130–150 words per minute. Change sentence length and pauses before stretching
audio. Never change voices silently.

Cache cues by text, pronunciation rules, engine version, model checksum, and
synthesis settings. Once tools/models are downloaded, narration must work offline.
Do not substitute a cloud voice if local setup fails.

Maintain a pronunciation list for spec2hw, SystemVerilog, RTL, FIFO, IP-XACT,
Verilator, and identifiers. Spell out abbreviations when required. Keep exact
identifiers in the visible captions and transcript. Include a brief AI-narration
notice in the video information. No voice cloning is required.

### E. Timeline, editing, and rendering

Keep a machine-readable edit timeline that references original scene files and
measured narration lengths. Save the actual FFmpeg arguments and input hashes.
Make rebuilding and rendering a single episode possible without recording again.

- Cut setup noise and excessive waits. Label shortened waits.
- Preserve the order of approvals, writes, saved receipts, and verification.
- Use restrained crops/zooms for small controls, with enough context to locate
  them. Never crop away a material warning or bind a result to the wrong target.
- Hold the relevant screen while explaining it. Use actual captured frames for
  explanatory holds. Do not represent a still-image sequence as a live operation.
- Use no music, decorative transitions, or long introductions.
- Normalize narration to approximately -16 LUFS, with true peak <= -1 dBTP.
- Export 1920 x 1080 H.264 MP4, 30 fps, yuv420p, AAC audio, and fast-start
  metadata. Preserve originals if the recorder's native frame rate differs.
- Produce VTT, SRT, a transcript, chapter timestamps, and a poster per episode.

Derive caption and chapter timing from the final timeline, not the raw recording.
Use short cues, normally at most two lines. Keep captions clear of important
controls and source text. Synchronize after every timing change. Preserve
identifier casing and spelling. Include spoken explanations of visual outcomes.

### F. Quality checks and evidence

Automated checks must cover input/output existence, scene/operation IDs, hashes,
recording dimensions, final codecs and duration, audio presence, loudness/peaks,
caption/chapter bounds and order, local links, and operation coverage. Test error
paths: missing model, unavailable tools, invalid scene IDs, interrupted recordings,
failed product assertions, missing audio, and stale source inputs.

Review each complete rendered episode for readability, cursor clarity, action
order, narration correctness, pronunciation, caption synchronization, obstructed
controls, cut continuity, and accurate result claims. Use actual listening/audio
review where available; report any unreviewed audio quality explicitly. Automated
metadata checks alone do not establish pronunciation or instructional quality.

Inspect private data, credentials, unrelated tabs, host paths, and notifications
before packaging. Use only public teaching examples and generic run-local names.
Avoid collecting credentials in the first place; do not depend on later blurring.

Record commands, exit results, elapsed times, source and final revisions, download
identities, artifact hashes, failed takes, and remaining limits. Do not claim
human learner review based on an automated recording.

## 7. CLI and reproducibility requirements

Provide commands for preflight, example preparation, screenshots, scene recording,
narration, rendering, validation, and packaging. Every output-producing command
accepts a repository TEMP_ output path. Support selecting one episode or scene
and a dry-run mode that lists work without starting services or inference.

Validate prerequisites and manifests before work starts. Refuse destructive
overwrite. Cache only when source and configuration hashes match. Fail a scene
when a required assertion fails; never continue rendering it as successful.
Allow independent successful episodes to finish and report incomplete episodes.
Use native argument arrays or structured subprocess calls, not shell-interpolated
narration, JSON, or arbitrary file paths.

No product endpoint, archive migration, or runtime contract change is required.
If capture exposes a product defect, report it and add focused regression
protection for an authorized fix. Do not weaken product checks or existing tests.

## 8. Local library and final delivery

Build a self-contained directory under the run's `release/` directory containing:

- A searchable video catalogue by application and operation.
- Players with poster images, native controls, captions, transcripts, and chapters.
- Final MP4, VTT, SRT, transcript, chapter, and poster files per validated episode.
- A copy of the current written tutorials and assets, with optional relative
  cross-links. Preserve the written tutorials' independent learning path.
- Build/source versions, checksums, operation coverage, and validation report.
- Clear incomplete status for blocked episodes, without broken player links.

All media links must be relative within the release. Validate playback over a
local HTTP server and retain readable navigation/transcripts without JavaScript.
Do not require remote fonts, analytics, a public host, or a speech service to use
the library. Source pages must not contain broken links to ignored run artifacts.
Document how to rebuild the local library from a fresh checkout and required
assets. Keep raw media and voice models out of ordinary Git history.

## 9. Test commands and completion criteria

Follow the current testing strategy. Inspect selection before execution:

```bash
scripts/test-all.sh fast --dry-run
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --dry-run
scripts/test-all.sh fast --output temp/TEMP_tutorial_videos/tests-fast
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --output temp/TEMP_tutorial_videos/tests-integration
```

Use fresh evidence paths for subsequent runs. Add focused media tooling tests and
browser checks to their maintained subsystem. Run regression for broad/high-risk
changes to shared runtime, persistence, cross-application contracts, the Activity
SDK, model/prompt releases, or release preparation, as required by AGENTS.md.
Fast includes exactly three live model checks. Missing credentials/tools make
the applicable profile incomplete. Keep the failure report and coverage limits.

Deliver all source recipes and the handbook, validated playable episodes, synced
captions, transcripts, chapters, offline speech setup, the self-contained library,
and a coverage report meeting the target. Summarize executed checks and missing
prerequisites. A script-only delivery is not completed video production. An
unreviewed or blocked episode must not be called complete.

No videos or speech assets were created when this handoff was written. Start with
preflight, the operation inventory, and the pilot. Do not execute this plan merely
because the document is present. A later coding agent must receive a separate
request to implement Plan 2. Plan 1 remains intact and ready for separate
implementation.
