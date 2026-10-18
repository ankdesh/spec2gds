---
name: Temporary Artifacts and Output Location
description: Enforces placing generated artifacts (pics, specs, activity outputs, test logs) into temporary ignored directories.
---
# Temporary Artifacts and File Hygiene

When running tests, capturing visual baselines/screenshots, generating temporary specs, or executing activities:

1. **Temporary Output Location**:
   - All generated artifacts like pictures/screenshots (`.png`, `.svg`), temporary `.spec` packages, activity outputs, test progress summaries, and logs MUST be written to an ignored temporary directory (`tmp/`, `.tmp/`, `temp/`, or `artifacts/`) or system `/tmp`.
   - Never write temporary artifacts, test pictures/screenshots, scratch specs, or activity run outputs directly to tracked source directories.

2. **Gitignore Protection**:
   - Ensure all designated temporary output folders (e.g., `tmp/`, `.tmp/`, `temp/`, `TEMP-*/`, `artifacts/`, `*.artifacts/`, `**/.spec2gds/`) are present in `.gitignore`.

3. **Cleanup**:
   - Clean up temporary plans, test artifacts, and scratch files when a task or review phase is concluded.
