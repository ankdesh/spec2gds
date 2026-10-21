---
name: Temporary Artifacts and Output Location
description: Enforces placing generated artifacts (pics, specs, activity outputs, test logs) into in-repo temporary ignored directories with prefix TEMP_, strictly forbidding /tmp.
---
# Temporary Artifacts and File Hygiene

When running tests, capturing visual baselines/screenshots, generating temporary specs, or executing activities:

1. **Temporary Output Location**:
   - All generated artifacts like pictures/screenshots (`.png`, `.svg`), temporary `.spec` packages, activity outputs, test progress summaries, and logs MUST be written to an ignored temporary directory inside the repository prefixed with `TEMP_` (e.g., `TEMP_artifacts/`, `TEMP_tests/`, `TEMP_run/`, etc.).
   - **Do NOT use the system `/tmp` directory or any path outside the repository.** All temporary files and generated artifacts must be kept within the repo under an ignored `TEMP_` folder.
   - Never write temporary artifacts, test pictures/screenshots, scratch specs, or activity run outputs directly to tracked source directories.

2. **Gitignore Protection**:
   - Ensure all designated temporary output folders (e.g., `TEMP_*`, `**/TEMP_*`, `TEMP-*/`, `tmp/`, `.tmp/`, `temp/`, `artifacts/`, `*.artifacts/`, `**/.spec2gds/`) are present in `.gitignore` to prevent any temporary files from being added to git.

3. **Cleanup**:
   - Clean up temporary plans, test artifacts, and scratch files when a task or review phase is concluded.
