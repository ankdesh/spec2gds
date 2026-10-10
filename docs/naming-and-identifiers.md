# Names and identifiers

Users manage a readable name. Stable identifiers continue to bind packages,
entities, sections, proposals, revisions, and provenance. A display rename
does not change a hardware symbol, an existing `.spec` path, or a chat binding.

## Sources of truth

| Item | Authoritative name | Uniqueness scope |
| --- | --- | --- |
| Specification | Narrative `title` | Spec service known-package catalog |
| Component, design, bus or abstraction definition | IP-XACT `displayName` | All entities in one package |
| Authored narrative section | Existing heading text | Sibling authored sections |
| Standalone circuit | Circuit document `label` | Circuit service documents |
| Circuit component | Component `label` | One circuit document |
| Bound Assistant source | Names returned by the selected owner | Exact owner, package, and permitted target |
| Conversation | Editable conversation title | Independent of source name |
| Verification record | Title/name and useful engineering key | Existing verification record scope |

Spec's resolver is `spec2gds/spec/spec_format/naming.py`. Projections,
Activity SDK summaries, Assistant context, Circuit adapters, verification
decoding, and public generation paths consume it. TypeScript consumers use
owner-provided labels. Circuit's standalone naming rules live in
`circuit-designer/packages/core/src/naming.ts`; its Unicode case-fold table
matches Python's case-fold behavior.

Names use Unicode NFKC, collapsed whitespace, and a 200-character limit.
Comparison additionally uses Unicode case folding. Creation and rename reject
duplicates and suggest the next available name, such as `Timer 2`. Admission
normalization applies that suffix automatically and deterministically. Section
rules apply to authored narrative headings; standard headings such as Ports
and SystemVerilog stay fixed.

New component/design creation derives a valid hardware identifier once.
Hardware collisions use numbered underscores. Later display renames preserve
VLNVs, module names, port names, instance names, wiring, and stable entity IDs.
Names with spaces are supported by Spec → Circuit → Spec round trips.

## Exposure inventory and source locations

Paths below are relative to the repository root. Default presentation uses
names; exact machine contracts retain their existing fields.

| Scenario | Presentation | Implementation |
| --- | --- | --- |
| Cover, headings, navigation | Document/entity names, fixed standard headings | `spec_format/document.py`, `packages/document-a2ui-react/src/index.tsx` |
| Instance component and internal-design references | Linked entity names; raw VLNV remains the reference value | `spec_format/document.py` |
| Related entities and live-view callouts | Linked names or readable view descriptions | `spec_format/document.py`, document renderer |
| Rename/create dialogs, launch notices | Name input, named targets | `spec_format/transactions.py`, `apps/editor/src/App.tsx` |
| Source review and validation | Qualified section name and source line/column | `spec_format/sv_validation.py`, editor app |
| Assistant creation and retries | One Name input, owner-derived filename, reserved destination and identity | `ai-assistant/src/source-creation.ts`, `spec_service_store.py`, `v1_api.py` |
| Assistant source labels and workspaces | Owner names; numbered workspace collisions | `ai-assistant/src/naming.ts`, `state.ts`, `workspaces.ts`, `index.ts` |
| Assistant proposals/history/replies | Named changes, state, review numbers | `spec_format/assistant.py`, `spec_service_store.py`, `ai-assistant/src/proposal-presentation.ts`, client |
| Architecture reviews and CLI decisions | Document-scoped review numbers; exact IDs accepted in technical workflows | `ai-assistant/src/state.ts`, `scripts/spec2gds_spec.py` |
| Circuit selectors/inspectors | Readable owner context and exact signal/instance names | `packages/core/src/naming.ts`, `packages/app-react/src/CircuitDialogs.tsx` |
| Circuit JSON, SVG, PNG and topology previews | Safe readable filename stems | `packages/service/src/session-backend.ts`, `packages/app-react/src/circuit-files.ts`, topology live view |
| RTL and SystemC projects/reports | Named public directories, named targets; hardware code unchanged | `activities/view.py`, `activities/{rtl,systemc_at,systemc_rtl}`, `activities/scratch_directory.py` |
| Verification source snapshots | Actual entity names, qualified occurrence context | `testplan-service/.../integrations/snapshot_decoder.py` |
| Verification scopes, dependencies, bindings, backends, checkpoints and evidence | Searchable named choices, retained requirement/checkpoint codes | Verification `ui/static/app.js`, `domain/recipes.py`, `application/command_handler.py` |
| Verification exports and generation receipts | Named files/records, stable readable generation numbers | Verification `application/export_service.py`, `api/routes_exports.py`, `storage/sqlite_repo.py` |
| Assistant execution, subscriptions and events | Named roles/actions; exact configuration under details | `ai-assistant/client/index.js` |
| Activity summaries and command targets | Owner-resolved names, package-scoped name selection | `activities/view.py`, `scripts/run_rtl_activity.py` |
| Assistant command targets | Owner-resolved document/entity/qualified section names, exact package constraints | `ai-assistant/scripts/request.mjs`, Spec and Circuit `/documents/resolve` |

`spec_format` paths are under `spec2gds/spec/`; `packages` and `apps`
paths are under `circuit-designer/`; verification paths are under
`testplan-service/src/testplan_service/`.

## Ownership, retries, and technical details

Name resolution is limited to the explicitly selected package and permitted
entity kinds. Unknown or ambiguous targets return readable choices. Names
never broaden a binding or select a different package. Owner document keys
distinguish copied packages even when they share a document ID.

Document names are reserved by the existing owner SQLite catalog. The same
creation request retains its internal identity and reserved destination over
retries. Changing a reserved request requires a new request rather than
silently producing another package. Validated saves refresh owner metadata and
invalidate stale proposals through the existing revision mechanism.

IDs, full VLNVs, hashes, raw operations, endpoint keys, and correlation data
remain in machine APIs, immutable artifacts, ownership manifests, diagnostic
payloads, and collapsed Technical details. Source paths and standard source
locations remain available. Engineering names—including ports, signals,
instances, RTL symbols, `REQ-001`, and checkpoint `P1`—stay visible where useful.
Assistant conversation titles remain editable and do not change on source
rename; source labels and workspace names refresh separately.

Public filename stems use ASCII transliteration, lowercase letters/digits,
hyphens, a length limit, and Windows reserved-name protection. Filename
collisions receive readable numbers. Exports use the current display name.
Private content-addressed storage stays ID-based. Generated-directory
replacement checks Activity/document/target provenance before overwriting;
foreign valid owners get numbered destinations, while unmanaged, malformed,
or symlinked destinations fail safely. A display rename may leave an older
owned generated directory intact; it is not a source-path migration.

## Normalization and commands

Repository samples and service-known packages are normalized through validated
source saves. Subsequent open/import admission fills missing titles from the
filename and missing entity names from hardware names, preserving valid names.
Names duplicated by admission receive numbers in stable source/catalog order.
The operation is idempotent and does not rewrite immutable historical records.

```bash
uv sync
uv run python -m scripts.normalize_spec_names --repository
uv run spec2gds-spec create --output timer.spec --name "Timer controller"
uv run spec2gds-spec inspect --container timer.spec
uv run python scripts/run_rtl_activity.py design.spec generated --target "Timer controller"
uv run spec2gds-spec reviews design.spec
uv run spec2gds-spec history design.spec --limit 25
uv run spec2gds-spec architecture-reviews design.spec
cd ai-assistant
npm run request -- --domain spec --service-url http://127.0.0.1:6010 --document-name "Timer controller" --entity-name "Cycle timing" -- "Explain the timing requirements."
```

Use `inspect --format json`, review/history `--json`, or RTL `--json` when
integrations need exact identifiers. API target references continue to require
their existing stable reference fields.

## Acceptance checklist

- Missing names, duplicate names, Unicode/case equivalence, numbered migration,
  and repeated normalization preserve identity and behave deterministically.
- Display renames preserve VLNVs, hardware symbols, package bindings, and source
  paths; cross-package lookup is rejected.
- Descriptive Circuit component labels survive saving and projection with wiring
  unchanged; exact signal names remain accessible.
- Document views, source labels, Activity summaries, and newly imported
  verification snapshots use current owner names.
- Name-based CLI targets and review numbers handle ambiguity, deleted targets,
  replayed requests, and stale revisions.
- Default views and filenames favor readable names; technical details retain
  exact values for diagnosis and automation.
- Slug collisions and existing generated directories retain ownership protection.
- Python suites run with `uv` and `.venv`; TypeScript tests/checks and both editor
  and Assistant browser flows run, then served frontend bundles are rebuilt.

The implementation uses existing title/display metadata and owner transactions
instead of introducing a parallel name-to-ID registry in each frontend. This
keeps ownership and rename behavior maintainable; unavailable owners can leave
a cached Assistant source label visible until the next successful refresh.

## Validation recorded on 2026-10-02

| Check | Result |
| --- | --- |
| `uv run --no-sync --offline pytest tests testplan-service/tests -q` | 241 passed; 9 environment-dependent skips |
| Added snapshot/name acceptance tests | 11 passed, including two snapshot tests added after full-suite collection |
| Circuit workspace `npm test` | 120 passed |
| Assistant `npm test` | 119 passed |
| Assistant `npm run test:harness` | 3 passed, including a document-name command through the real headless profile |
| Spec Editor browser suite | 15 passed |
| Circuit browser suite | 13 passed, including file import/export |
| Assistant browser suite | 3 passed |
| Verification browser smoke | Named scope selection, literal punctuation in headings, inspector rendering, and source views passed without JavaScript errors |
| Circuit workspace build, Assistant build/typecheck, generated-schema check | Passed; served frontend bundles rebuilt |
| Repository normalization rerun | No changes; idempotent |
| RTL example regeneration check | Passed; existing instance topology and source identities preserved |
| `git diff --check` | Passed |

The Python skips require optional CIRCT/SystemC toolchain configuration. Existing
deprecation/serializer warnings and the frontend bundle-size advisory remain.
The latest snapshot tests cover source titles independent of IDs, nested
qualified headings, and distinct occurrences of repeated composite components.
Owner lookup tests cover Unicode names, duplicate section headings, copied
packages, absent targets, and rejection of mismatched package constraints.

After installing these changes, restart the running services with
`scripts/serve-all.sh restart` and reload open browser tabs to use the rebuilt
code. Already running services were preserved during validation; browser tests
used isolated services where required.
