---
name: Temporary Artifacts and Output Location
description: Enforces placing disposable generated artifacts (pics, specs, activity outputs, test logs) into temp/ with prefix TEMP_, and temp docs in docs/ with prefix TEMP_, strictly forbidding /tmp.
---
# Temporary Artifacts and File Hygiene

When running tests, capturing visual baselines/screenshots, generating temporary specs, executing activities, or authoring plans:

1. **Disposable Temporary Output Folders (`temp/TEMP_*`)**:
   - All disposable generated artifacts like pictures/screenshots (`.png`, `.svg`), temporary `.spec` packages, candidate authoring outputs, activity outputs, test progress summaries, and execution logs MUST be written to an ignored temporary directory inside the `temp/` folder prefixed with `TEMP_` (e.g., `temp/TEMP_artifacts/`, `temp/TEMP_tests/`, `temp/TEMP_run/`, `temp/TEMP_p1/`, etc.).
   - Do NOT create disposable `TEMP_*` folders directly in the repository root or scattered across source directories.
   - **Do NOT use the system `/tmp` directory or any path outside the repository.** All temporary files and generated artifacts must be kept within the repo under `temp/`.
   - Never write temporary artifacts, test pictures/screenshots, scratch specs, or activity run outputs directly to tracked source directories.

2. **Temporary Planning Documents (`docs/TEMP_*`)**:
   - Temporary documents, plans, roadmaps, and audit notes (e.g., `docs/TEMP_spec_library_plan/`, `docs/TEMP_plan.md`, `docs/TEMP_*.md`) MUST be created inside `docs/` with the `TEMP_` prefix.

3. **Gitignore Protection**:
   - Ensure all designated temporary output folders (e.g., `temp/`, `**/temp/`, `TEMP_*`, `**/TEMP_*`, `TEMP-*/`, `tmp/`, `.tmp/`, `artifacts/`, `*.artifacts/`, `**/.spec2gds/`) are present in `.gitignore` to prevent any disposable temporary files from being added to git.
   - Ensure `!docs/TEMP_*` and `!docs/**/TEMP_*` allow tracking temporary planning documents when intended.

4. **Cleanup**:
   - Periodically clean up disposable test folders and scratch files under `temp/` when a task or review phase is concluded.
