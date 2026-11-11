# Maintain the hands-on tutorials

The written course teaches important operations through practical exercises.
The independent video series has a separate production plan. Do not make either
learning path depend on completing the other.

## Sources and lesson structure

Edit `scripts/build_tutorials.py`, then regenerate the HTML. Do not hand-edit
generated pages. Keep ports, behavior, connections, and reference observations in
`docs/tutorials/example.json`. Use the builder's content tokens for those values.

Each action has a title, an instruction, and an observable expected result. Give
the designer a result check after a save or application handoff. Keep the final
independent challenge without a complete click sequence. Add hints as needed.

Attach a picture to its action with an explicit action number, image name, and
caption. There is no fixed picture count. Update the action associations whenever
instructions move. A screenshot is an illustration of a known application state;
it is not evidence that a learner completed the exercise.

Keep URLs and existing anchors stable. Review menu labels in the served UI. Do
not carry forward inline verification reports, a full-page Activity view, Paste
rows, or implicit single-bound Range instructions. Reports belong in Diagnostics;
jobs and reviews belong in Activity. Both tabs open manually. Catalog evidence is
separate from verification of the current Spec.

## Prepare independent starts

From the repository root, with project prerequisites installed:

```bash
uv run python scripts/prepare_tutorials.py --output temp/TEMP_tutorial_refresh/starts-new
```

Use a fresh directory. The command refuses existing output and only accepts
`temp/TEMP_*` paths inside this repository. Each core lesson has a numbered start.
Optional Spec exercises have named starts; Verification Planner has separate plan,
coverage, evidence, and implementation records. The TLM example has its own source.

Preparation uses public production APIs and does not call a model or a simulator.
It does not modify a running editor. Read exact paths, source revisions, and plan
IDs from starts.json. Never repair an exercise by directly editing an archive or
product database. Never overwrite a designer's source.

## Capture screenshots

Use Node.js 24+, the project Python environment, and the installed Playwright
Chromium. Run the dry-run first. Commands below run from the repository root.

```bash
uv run python scripts/capture_tutorials.py --output temp/TEMP_tutorial_refresh/capture-new --dry-run
uv run python scripts/capture_tutorials.py --output temp/TEMP_tutorial_refresh/capture-new --starts temp/TEMP_tutorial_refresh/starts-new
```

The runner starts private local services and stops only its child process groups.
It uses real application data and compiler checks. Its default groups are spec,
systemc, catalog, circuit, planner, and layouts. Browser screenshots use 1440 by
900, device scale factor 1. Layout evidence also covers 1280, 1024, and 390 pixels
and both Clean and Obsidian, with the panel open and closed. Primary Spec Editor
illustrations use Clean. Circuit Designer and Verification Planner retain their
normal presentation. Keep browser downloads and all process temporary files in
the run directory.

Live Assistant illustration capture is a separate explicit group:

```bash
uv run python scripts/capture_tutorials.py --output temp/TEMP_tutorial_refresh/capture-new --starts temp/TEMP_tutorial_refresh/starts-new --resume --only assistant
```

Use configured model access and an authorization that permits sending the public
teaching example to that service. Never substitute a fixture response for live
authoring evidence. Missing credentials or authorization leaves these captures
incomplete. Credentials must not appear in screenshots, logs, or committed files.

Use `--only` to repeat a selected group and `--resume` to retain earlier takes.
The runner keeps originals and traces by take and records errors. Use a fresh
prepared source copy if the repeated scene requires an empty or unchanged start.
Do not describe a failed take or a quickly completed job as a successful cancel.

Publish only after the complete referenced capture set is present:

```bash
uv run python scripts/capture_tutorials.py --output temp/TEMP_tutorial_refresh/capture-new --publish
uv run python scripts/build_tutorials.py
```

Publishing checks capture hashes and copies only referenced images. It writes
`docs/tutorials/assets/captures.json` with source, theme, viewport, action links,
and hashes. It records UI source digests so later UI changes flag a required
capture review. A hash match does not replace visual review. Preserve raw files
and evidence under the ignored run directory.

Inspect every selected image at full size and in its lesson. Check that dialogs,
target names, control labels, errors, and source states match the instructions.
Remove obsolete unreferenced documentation images after checking references.

## Validation and evidence

```bash
uv run python scripts/build_tutorials.py --check
uv run python -m pytest tests/test_tutorials.py -q
cd tests/ui-scenarios
PLAYWRIGHT_BROWSERS_PATH=../../circuit-designer/.playwright-browsers \
  node --import tsx runner/check_tutorials.ts ../../temp/TEMP_tutorial_refresh/html-new
cd ../..
scripts/test-all.sh fast --dry-run
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --dry-run
scripts/test-all.sh fast --output temp/TEMP_tutorial_refresh/fast-new
scripts/test-all.sh integration --scope spec,circuit,assistant,verification,activities,shared --output temp/TEMP_tutorial_refresh/integration-new
```

Use fresh evidence directories for later runs. Follow `docs/testing-strategy.md`
and AGENTS.md for regression selection. Fast includes exactly three live checks;
do not replace them with fixtures or silently omit them. Report missing tools,
credentials, or external-service authorization as incomplete coverage.

Walk through each exercise from its own start. Reopen after saves. Compare the
Spec, Circuit, job output, or Test Plan with the claimed result. Keep actual
published RTL and its lint log. Preserve synthetic evidence labels. Record optional
SystemC generation, compilation, and simulation separately.

Read all pages at 1440, 1280, 1024, and 390 pixels. Check navigation with keyboard
and without JavaScript. Inspect images, code blocks, tables, mobile navigation,
and heading links. Automated runs do not establish human learner independence.
Record real learner practice time before publishing duration estimates; exclude
installation and tool queue time. Until measured, display action counts and mark
learner timing as unverified.

For each exercise record the source commit, start identity, prerequisite status,
completed actions, expected versus actual results, saved revision, image/trace
paths, elapsed automation time, and any incomplete work. Keep a validation report
under `temp/TEMP_tutorial_refresh/`. Do not claim all guides or profiles passed
when required checks remain incomplete.
