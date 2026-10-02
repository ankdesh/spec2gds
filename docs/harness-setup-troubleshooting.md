# Harness setup troubleshooting

Run the complete setup from the repository root:

```bash
scripts/setup-all.sh
```

Use `uv` for the root Python `.venv` and Node.js 24.2+ for the complete stack.
The Assistant alone also supports Node.js 22.19+ in the 22.x line. Setup follows
`DSH_BRANCH`, defaulting to `spec2gds/integration`; it does not enforce or update
`ai-assistant/harness.lock.json`. Packaging retains its clean-commit lock check.

## Outcomes of the five reported issues

1. **Obsolete setup command:** maintained guides use `scripts/setup-all.sh`.
   The removed `setup:harness` npm script must not be used. The current tutorial
   is [the event-driven Assistant tutorial](event-driven-assistant-tutorial.md).
2. **Missing `tsc` and `tsx`:** setup links Harness's `typescript`, `tsx`,
   `@types` and native packages into the Assistant. Executable links point to
   package binaries, because pnpm wrappers depend on their original directory.
   Repeated setup refreshes both valid and dangling links. Replaced real package
   directories and executable files remain in `node_modules/.harness-links-*`;
   unrelated installed dependencies remain in place. Missing toolchain files
   produce a diagnostic asking for `pnpm install` in the Harness checkout before
   replacing the Assistant's links.
3. **Stale `HARNESS_SOURCE`:** setup resolves nested checkouts and symlinks to
   the physical checkout directory and always upserts that path in the
   Assistant `.env`, including the default sibling destination. Duplicate
   assignments are removed while unrelated settings, comments, line endings
   and existing permissions are preserved. A new `.env` is created with mode
   `0600`. Relative destinations resolve from the repository root.
4. **Duplicate proposal replay:** the existing proposal normalization derives
   generated identities from the proposal ID. Rebuilding the same proposal
   produces the same artifact digest and returns the saved receipt, even after
   the owner revision advances. Reusing a call ID with changed content remains
   an `INVALID_PROPOSAL` error; references to creation aliases remain consistent.
5. **Directory-browser fixture contamination:** the existing browser test uses
   a dedicated child of `tmp_path`, so owner and Activity state directories do
   not alter the expected listing. The production browser continues listing
   actual filesystem contents.

## Recover after replacing or moving Harness

For the default sibling checkout, rerun `scripts/setup-all.sh`. To select a
different destination, set it explicitly for setup:

```bash
HARNESS_SOURCE="/absolute/path/to/deepseek-harness" scripts/setup-all.sh
```

Setup takes its destination from the invocation environment, not from a stale
Assistant `.env`. It builds Harness, refreshes links, updates `.env` and runs
the Assistant's ordinary `npm run build`. Installing the Assistant separately
with `npm install` or `npm ci` is unnecessary for this source-development path;
some native dependencies are unpublished.

## Verification

From the repository root, after setup:

```bash
npm --prefix ai-assistant run typecheck
npm --prefix ai-assistant run build
npm --prefix ai-assistant test
npm --prefix ai-assistant run test:harness
uv run pytest tests/agent_spec/spec_format/ -q
```

For focused setup regressions:

```bash
cd ai-assistant
node --import tsx --test tests/setup.test.ts
```

The setup tests create disposable Harness/package fixtures. They exercise fresh
linking, imports, executable launch, repeated setup, checkout switching, dangling
links, backups, missing dependencies, canonical symlink paths and `.env` updates.
They do not substitute for building the real branch and running the integration
tests. Validate a complete clean setup in a disposable workspace with its own
Harness destination, run setup twice, and keep the developer's existing checkout
intact. Model-provider credentials are unnecessary for the deterministic tests.

### Verification recorded on 2026-10-02

The checks passed with Node.js 22.23.1, pnpm 11.7.0 and the local
`spec2gds/integration` branch snapshot `3c98c5108b`: 118 Assistant unit tests,
3 Harness integration tests and 105 Python specification-format tests. Assistant
typechecking and both production bundles also passed.

Two complete setup runs succeeded in a disposable source copy, with a new
Harness clone from the local branch. The second run started with five dangling
package/executable links and duplicate stale `.env` assignments. It restored
working `tsc`/`tsx` executables and the canonical checkout path, retained the
unrelated setting and comment, and preserved the existing `0640` permissions.
The fresh workspace's Assistant unit and integration tests passed afterward.
The developer's existing Harness checkout was retained unchanged.
