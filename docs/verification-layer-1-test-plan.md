# Layer 1 — Test Plan

Status: implementation plan. Read [the overall contract](verification-service-overall.md) first.
This document owns verification intent and its connection to the specification.

## 1. Purpose and hard boundary

Layer 1 answers **What must this component or design do, and why must we verify it?**
It must work before RTL, a simulator, a coverage model, or a backend is selected.
Users author every requirement selection, section and intent through forms or public API calls.
Importing a snapshot exposes source content; it does not automatically create a behavioral plan.

Layer 1 stores preconditions, trigger, expected behavior and externally meaningful observations in plain language. These can name specification ports and clock relationships. They cannot require UVM classes, Cocotb functions, assertion syntax, RTL hierarchical signal paths, coverage bins, random seeds or proof engines. A source's normative timing requirement, such as “on the next rising edge,” belongs here; the executable sampling expression belongs in Layer 3.

The main authoring objects are **Section** and **Intent**. Requirements are manually captured source statements in a side view. Scope comes from the selected snapshot's hierarchy. An intent is a leaf behavioral point, not a runnable test.

## 2. Information architecture

```text
Plan: FIFO pipeline verification
  Scope: fifo_pipeline                         [design occurrence]
    Section: Integration
      Intent: Preserve ordering across both FIFOs
      Intent: Preserve pending data during downstream stalls
    Scope: ingress                            [fifo component occurrence]
      Section: Reset
        Intent: Reset clears the queue
      Section: Boundary behavior
        Intent: Reject write while full
        Intent: Reject read while empty
    Scope: egress                             [same component, different occurrence]
      Section: Reset
      Section: Boundary behavior
```

Source scope and organization are distinct. Source hierarchy cannot be changed by dragging a plan section. Users may create any number of nested sections under one scope. Intents attach to a section or directly to a scope. Intents cannot contain children. Sections have no pass/fail state and do not count as intents.

### Scope rules

- Supported scope kinds: `design`, `component`, `interface`. `subsystem` is a user-facing label on a design occurrence, not a new source identity kind.
- A standalone component root is one component definition with one root occurrence. A design root includes its reachable occurrence tree. If the source contains recursive/unresolved hierarchy, expose the diagnostic and block review of the unresolved portion.
- Two instances of one component definition are distinct verification scopes. Each has an occurrence identity from its stable instance-ID chain, resolved parameters, and source definition reference.
- Interface scope must reference an interface/port-group object present in the snapshot. When the snapshot has no such object, organize interface behavior with a section under the owning component; do not invent authoritative source interfaces.
- Cross-component intent belongs to the lowest common design ancestor of its participating occurrences. Store those participants explicitly. Do not duplicate the integration intent into both components.
- Navigation shows source occurrence names and type names together, for example `ingress · sync_fifo`. Rename does not change identity.
- The source browser may expose content beyond the selected root for citations, but verification scopes must remain within the chosen root's reachable hierarchy.

## 3. Canonical records and fields

Shared IDs, timestamps, record revisions and archive behavior are defined in the overall document. Unless specified otherwise, strings are UTF-8, titles 1–200 characters after trimming, plain text/Markdown fields at most 16,000 characters, and lists have unique entries. Markdown renders sanitized text, links, lists and tables; no raw executable HTML.

### 3.1 Plan header

| Field | Type/default | Validation and behavior |
| --- | --- | --- |
| `name` | Required string | Visible in header and exports |
| `description` | String, empty | Human purpose and boundaries |
| `snapshot_id` | Required immutable snapshot reference | Exactly one active snapshot |
| `root_scope_id` | Required scope ID | Resolves to selected imported root |
| `owner_label` | Optional string | Responsibility label; not access control |
| `tags` | String array, empty | Up to 20 tags, each 40 characters |
| `source_audit` | Per-section dispositions | Tracks manual source review completeness |
| `schema_version` | `verification.plan.v1` | Explicit major version |

### 3.2 Source locator and requirement

`SourceLocator` fields: `snapshot_id`, `entity_ref`, `section_id`, optional `text_range` with Unicode code-point start/end offsets, `quoted_text`, and `section_digest`. For structured facts use `structured_path` instead of `text_range`, with a canonical JSON value and digest. Exactly one locator mode is required. Store enough quoted content to read an old requirement without a live source service. Browser UTF-16 offsets must be converted to code-point offsets before submission.

| Requirement field | Required | Meaning |
| --- | --- | --- |
| `title` | Yes | Short source requirement name |
| `statement` | Yes | User-curated atomic behavioral statement |
| `source_locators` | At least one | Exact source section/range/structured fact |
| `interpretation_note` | If paraphrased | Explain how the statement follows the source |
| `scope_id` | Yes | Owning occurrence/design |
| `disposition` | Yes, default `unassessed` | `unassessed`, `verify`, `informational`, `out_of_scope`, `ambiguous` |
| `disposition_reason` | For informational/out-of-scope/ambiguous | Visible reason, not hidden metadata |
| `issue_ids` | Empty default | Open source/requirement questions |

User-selected requirements do not exhaustively represent the source by themselves. Each in-scope source section has a separate audit entry: `unreviewed`, `requirements_captured`, `informational`, or `out_of_scope`. Last two require a reason; `requirements_captured` requires one or more linked requirement IDs. Structured entity facts are represented as generated source sections for audit, without generating verification requirements. Store reviewer label and source digest on each audit entry.

The source review checklist therefore distinguishes **source sections reviewed** from **requirements mapped**. Neither metric claims that software has understood all implied behavior in the prose. The reviewer explicitly confirms extraction sufficiency when creating the Plan checkpoint.

### 3.3 Section

| Field | Default | Rule |
| --- | --- | --- |
| `title` | Required | Descriptive human grouping |
| `description` | Empty | Optional introduction, not an implicit requirement |
| `scope_id` | Required | Fixed source occurrence |
| `parent_section_id` | Null | Parent in the same scope |
| `child_ids` | Empty | Ordered sections/intents; canonical ordering |
| `default_priority` | `medium` | Inherited by descendants with no override |
| `tags` | Empty | Up to 20 |

Cycles, duplicate child membership and references to another scope's sections are invalid saves. Max nesting is 32 including source scopes. Duplicate sibling titles are allowed but produce an advisory warning; stable keys disambiguate them. A section with no intents is valid draft content and appears in review as an empty-section warning requiring acknowledgement.

### 3.4 Intent

| Field | UI label | Rule |
| --- | --- | --- |
| `title` | Intent | Required to save |
| `scope_id` | Verification scope | Required, source-derived |
| `parent_section_id` | Section | Optional, same scope |
| `requirement_ids` | Why this is required | Many-to-many; at least one `verify` requirement before review |
| `preconditions` | Given | Plain-language state/configuration before the event |
| `trigger` | When | Event, action or condition being considered |
| `expected_behavior` | Then | Normative result and timing where specified |
| `observations` | What the user can observe | Array of named semantic observations, description, optional source locator |
| `rationale` | Why this point matters | Required if intent is a derived interpretation |
| `origin` | Origin | `direct_requirement` or `derived_interpretation`; user selected |
| `priority_override` | Priority | Null inherits; otherwise low/medium/high/critical |
| `tags` | Tags | Empty by default |
| `participants` | Related components/interfaces | Required for composition intent; distinct descendant scope IDs |
| `dependency_ids` | Depends on | Other intents, e.g. reset behavior; acyclic |
| `issue_ids` | Open questions | Explicit ambiguity/observability/source issues |
| `authoring_state` | Authoring | `draft`, `ready`, `blocked` |

Draft intents may omit Given/When/Then or source links. Save returns readiness diagnostics without rejecting a structurally valid draft. **Mark ready** requires nonempty Given, When, Then, at least one meaningful observation, a verifiable linked requirement, and no unresolved blocking issue. Preconditions can explicitly say “No additional precondition”; blank is not equivalent. A change to semantic fields resets a ready intent to draft; title/order/tag changes do not. Review is recorded by checkpoint, not a mutable `approved` state on the record.

Observations here name outcomes such as “FIFO occupancy and later read sequence.” They do not imply internal RTL pointers are available. Missing visibility can be a documented issue; the implementation layer must later provide the actual binding or report unsupported observability.

`derived_interpretation` is still linked to source requirement(s), with rationale and explicit review. It is not a license to invent unspecified behavior. If expected behavior is undecidable from source, create a blocking issue and keep the intent blocked. No backend or future assistant can resolve that ambiguity by choosing its own answer.

### 3.5 Source/intent issue

Fields: title, kind (`source_ambiguity`, `source_missing`, `contradiction`, `observation_unclear`, `other`), description, linked record IDs, severity (`blocking`, `advisory`), state (`open`, `resolved`), resolution text, resolver/time. Resolving a blocking ambiguity requires a source update or an explicitly reviewed interpretation with cited source rationale. “Ignore” cannot resolve it. Reopening is an audited operation.

### 3.6 Relationships and interpretation

- Requirements may map to multiple intents; one intent may address multiple requirements. Never enforce one requirement = one test.
- Duplicate detection is advisory: exact normalized title+scope+requirement set flags a candidate; no automatic merging or deletion.
- Dependencies express explanatory prerequisites, not test execution ordering. Layer 3 does not automatically turn them into test steps.
- Priority helps filtering/review ordering; no weighted success score that hides a failed critical intent.
- The UI computes effective priority and shows inherited vs explicit. Export includes both.

## 4. UI specification

### 4.1 Default view and empty state

Test Plan defaults to an outline, grouped by selected scope, with columns **Intent**, **Priority**, **Source**, **Authoring**, **Coverage**. The last column is a read-only link badge supplied by Layer 2: **Not mapped**, **Mapped**, or **Changed since coverage review**. Evidence pass/fail is not painted onto authoring state.

The top toolbar offers **Add section**, **Add intent**, **Source & requirements**, **Review plan**, and an overflow menu containing export and archive. For a new plan, show: “Start by selecting a source section, or add an intent and link its source before review.” Buttons: **Browse source** and **Add first section**. Do not show an AI prompt or generate action.

Selected section shows its description followed by child rows. Selected intent shows a readable Given/When/Then block plus source excerpt(s), observations and related links. The right panel has **Details**, **Source**, **Related**, **History** tabs. Normal reading view is not a wall of editable inputs.

### 4.2 Creating and editing intent

The edit form groups fields in this order:

1. Title; section/scope; priority.
2. **Behavior**: Given, When, Then; named observations.
3. **Source**: linked requirements; button **Link requirement** opens source/requirement selector.
4. **More details** disclosure: rationale/origin, tags, participants, dependencies.
5. Inline issues/readiness checklist; **Save draft**, **Save and mark ready**, **Cancel**.

Source selection lets the user highlight exact text or select a structured fact, preview the quote, and enter a requirement title/statement. The user can create a requirement and link it to the intent in one atomic save. No automatic paraphrase or suggested normative behavior. A pasted multi-line intent remains one field; it is not silently split into multiple points.

Add-intent defaults to the selected section, or selected scope if no section. A selected intent supplies its parent as the destination, not itself. New intent initially inherits priority. **Duplicate intent** copies behavior/source links into a new draft with new identity and no coverage/evidence/recipe links; it prompts for a new title and shows “Coverage and implementations are not copied.”

### 4.3 Source & requirements view

Show two panes inside the center workspace: source sections with review dispositions, and captured requirement rows. Selecting a requirement highlights its source and mapped intents. Filters: unreviewed source sections; unmapped requirements; ambiguous requirements; source changed. Counts are explicit, e.g. “8 of 10 in-scope sections reviewed; 6 of 7 verifiable requirements have intent.”

Source viewer is read-only. **Open in Spec Editor** is optional navigation when configured, never required. Missing neighboring service leaves the cached snapshot readable. Full source identity and hash are in a collapsible source details panel.

### 4.4 Moving, archiving and multi-select

Move within the same scope changes organization only. Moving to another source scope opens a preview listing invalid requirement/participant links; it may save only after explicit link remapping, creates a new draft state, and never transfers coverage/evidence implicitly. Composition scope must still satisfy the lowest-common-ancestor rule.

Archive section offers **Archive section and its descendants** or **Move contents, then archive section**. Show all downstream objective/recipe references. Referenced records are soft archived and remain visible in historical checkpoints. Current coverage mappings become dangling diagnostics until repaired; no evidence is removed.

Multi-select supports priority, tags, move, mark ready, and archive. All selected records validate in one transaction. A readiness error on one record prevents the whole mark-ready batch and links to each blocker.

### 4.5 Reuse without hidden inheritance

Initial reuse is **Copy section to scope…**, a deliberate copy with provenance. This supports the two-FIFO example without introducing live template inheritance.

- Preview target occurrence, resolved parameters, mapped source requirements and created record count.
- Create new section/intent/requirement IDs, retain `copied_from` provenance, reset all intents to draft, and remap requirement locators to the target occurrence's same definition only if stable source references resolve.
- Copy dependencies only when both endpoints are in the copied set; list external dependencies for explicit remapping.
- Do not copy coverage objectives, evidence, backend configurations or readiness.
- Changes to the original do not update copies. Show their origin in History.
- A future versioned template library may be an extension; live inheritance and automatic component-proof reuse are outside the initial contract.

## 5. Review checkpoint and completeness

**Review plan** previews a fixed candidate and reports:

| Check | Severity |
| --- | --- |
| Snapshot/root invalid, unresolved source occurrence | Blocker |
| In-scope source section has no audit disposition | Blocker |
| Requirement is unassessed/ambiguous without a resolved interpretation | Blocker |
| Verifiable requirement has no active linked intent | Blocker |
| Active intent is draft/blocked or has invalid source references | Blocker |
| Active intent lacks Given/When/Then/observation | Blocker |
| Dependency cycle or invalid composition participants | Structural error; also prevents save |
| Derived interpretation lacks rationale | Blocker |
| Empty section, duplicate candidate, advisory issue | Warning, explicit acknowledgement |

Review confirmation text: “I reviewed the selected source sections and the behavioral points for this scope. The plan captures the intended requirements identified in that review.” Record the checklist, acknowledged warning IDs and comment. Do not claim automatic completeness of natural-language specifications.

Successful review creates `PlanCheckpoint` with all source audit entries, requirements, sections, intents, scopes and issues, exact snapshot/root, content hash, reviewer/time. It is a baseline for Layer 2, independent of test execution.

When opening an existing checkpoint, show a read-only banner with **Return to working plan**. Do not label it as the current plan if working edits exist.

## 6. API operation catalog

Use the common preview/commands envelope. Every field below has an equivalent UI control; scripts need no browser session or assistant proposal endpoint.

| Operation | Parameters beyond `op` | Behavior |
| --- | --- | --- |
| `plan.update` | `changes` | Name, description, owner, tags |
| `source_section.assess` | `section_id`, disposition, reason, requirement_ids | Store explicit source audit decision |
| `requirement.create` | ID optional, full requirement fields | Capture cited statement |
| `requirement.update` | ID, allowed changes | Revalidate linked intents; semantic edits reset their readiness |
| `section.create` | ID optional, title, scope, parent, optional before_id | Insert into ordered parent list |
| `section.update` | ID, title/description/default_priority/tags | No implicit relocation |
| `intent.create` | ID optional, intent fields, optional before_id | Save draft by default |
| `intent.update` | ID, allowed field changes | Maintain readiness rules |
| `intent.set_state` | ID, draft/ready/blocked | Validate ready; blocked needs open blocking issue |
| `intent.link_requirement` | intent_id, requirement_id | Idempotent relation addition |
| `intent.unlink_requirement` | intent_id, requirement_id | Reset readiness if required |
| `item.move` | ID, target_scope_id, parent_section_id, before_id/null | Cycle/scope/remapping validation |
| `section.copy` | source_id, target_scope_id, source_ref_map, dependency_map | Fresh draft identities, provenance |
| `record.archive` | ID, explicit descendant IDs if section | No implicit cascade |
| `record.restore` | ID, destination if parent archived | Validated restoration; readiness draft |
| `record.delete_draft` | ID | Only never-reviewed and unreferenced draft record |
| `issue.create/update/resolve/reopen` | Typed issue fields/resolution | Auditable source/intent issue lifecycle |
| `source.update` | staged_import_id, locator_map, expected_preview_digest | Accept source-change preview; mark affected intents draft |

Read projections: `GET /plans/:id/hierarchy`, `/source-sections`, `/requirements`, `/intents`, and `/readiness?layer=plan`. They use shared pagination/filter conventions. Hierarchy loads children by parent ID and returns descendant counts without embedding every child recursively. `GET /plans/:id/search?q=...` returns typed, scoped hits.

### Illustrative atomic authoring request

This is a contract example, not application implementation. IDs are shortened for readability; actual API UUID validation still applies.

```json
{
  "base_edit_revision": 1,
  "request_id": "example-request-id",
  "operations": [
    {"op": "section.create", "id": "section-boundary", "title": "Boundary behavior", "scope_id": "fifo-scope"},
    {"op": "intent.create", "id": "intent-full", "title": "Reject write while full",
     "scope_id": "fifo-scope", "parent_section_id": "section-boundary",
     "requirement_ids": ["requirement-full"],
     "preconditions": "FIFO is full; reset is inactive.",
     "trigger": "A write is requested without a read on the next clock edge.",
     "expected_behavior": "No item is accepted; occupancy and queued data remain unchanged.",
     "observations": [{"name": "Queue state", "description": "Occupancy, full indication, and the later read sequence."}],
     "origin": "direct_requirement", "authoring_state": "draft"}
  ]
}
```

The referenced requirement must already exist or be created earlier in the same transaction. Unknown IDs reject the full batch. API callers may build an incomplete draft plan over multiple transactions and obtain the same readiness diagnostics as the UI.

## 7. Shared example specification

The following is an explicit synthetic fixture specification to be authored as a spec2gds snapshot during implementation. It is not inferred from existing RTL. The same fixture semantics must be used by all three layers.

### Synchronous FIFO

- Parameters: `WIDTH=8`, `DEPTH=4`; one positive-edge clock; active-high synchronous reset.
- Ports: `clk`, `rst`, `wr_en`, `rd_en`, `din`, `dout`, `full`, `empty`, `count`.
- `count` is the number of queued words, from 0 to DEPTH. `full=(count==DEPTH)`, `empty=(count==0)` after each edge.
- Acceptance uses pre-edge occupancy: `read_accept=rd_en && count>0`; `write_accept=wr_en && count<DEPTH`. Reset overrides both.
- At full with simultaneous read/write, accept read and reject write, so count decreases by one. At empty with simultaneous read/write, accept write and reject read, so count increases by one. There is no bypass or full-throughput special case.
- Accepted read publishes the oldest word in `dout` after that edge; otherwise `dout` retains its value. Accepted write appends `din` after acceptance is evaluated.
- Reset empties the queue, sets `count=0`, `empty=1`, `full=0`, `dout=0`. Internal storage bits need not be cleared and are not observable requirements.
- A rejected write does not modify queued words. A rejected read does not change queue state or `dout`. Accepted words leave in order, including after index wrap-around.

Create these source requirements and atomic intents:

| Requirement | Intent(s) | Section |
| --- | --- | --- |
| R-reset: reset behavior | Reset clears queue; reset overrides simultaneous requests | Reset |
| R-write: accepted write | Write appends one word when space is available | Normal operation |
| R-read: accepted read | Read returns oldest word when data is available | Normal operation |
| R-full: full write rejection | Full write preserves occupancy; full write preserves queued data | Boundaries |
| R-empty: empty read rejection | Empty read preserves queue and output | Boundaries |
| R-both: simultaneous requests | Mid-occupancy accepts both; full accepts read only; empty accepts write only | Simultaneous requests |
| R-order: sequence retention | Ordering survives wrap-around | Ordering |
| R-flags: flag consistency | Full/empty agree with occupancy | Status |

This defines 8 requirements and 12 intents. Count the two reset intents, two normal-operation intents, three boundary intents, three simultaneous-request intents, one ordering intent, and one status intent. A fixture may add explanatory source sections marked informational, but must not silently add requirements or change expected counts.

### Two-FIFO design

`fifo_pipeline` contains `ingress` and `egress`, each the same FIFO definition with WIDTH=8, DEPTH=4 and common clock/reset. Source design narrative defines a one-entry holding register `bridge` with a valid bit. Its behavior is explicit to avoid assuming FIFO output is combinational:

- If bridge is empty and ingress is not empty before an edge, request one ingress read and capture that accepted read's word into bridge after the edge; no new egress write from that newly captured word on the same edge.
- If bridge is valid and egress is not full before an edge, write its held word to egress and clear bridge after the edge.
- Do not request ingress read while bridge is valid, including the edge where the held word is sent. This intentionally inserts a transfer bubble.
- While blocked, bridge retains its word. Reset clears bridge valid and both FIFO queues.
- External producer and consumer use the FIFO acceptance rules above.

Copy the 12-intent component plan into each occurrence: 24 distinct local intents. Add 4 design-level intents: end-to-end ordering/no loss; stalled egress preserves the held word; bridge never reads ingress while holding data; reset clears all pending data. Those cite 4 design requirements. Total: 20 occurrence-scoped requirements and 28 intents. Definition locators may be shared, but scope and identities differ. Composition closure cannot be inferred from the 24 component intents.

## 8. Layer 1 acceptance requirements

| ID | Test setup/action | Expected outcome |
| --- | --- | --- |
| L1-01 | Import valid FIFO snapshot; no authoring calls | Empty intent plan with browsable source; no generated requirements |
| L1-02 | Create section and incomplete intent via UI | Save succeeds as draft; exact missing fields appear |
| L1-03 | Run script creating 8 requirements/12 intents using REST | UI presents hierarchy, order, source quotes and Given/When/Then matching script |
| L1-04 | Review with one unmapped requirement or unreviewed source section | Checkpoint blocked; click diagnostic opens exact record/source |
| L1-05 | Complete fixture and acknowledge warnings | Immutable P1 created; no coverage or RTL required |
| L1-06 | Link one intent to two requirements and one requirement to two intents | Both directions shown; no duplicate-intent counting |
| L1-07 | Attempt section/dependency cycle, invalid parent or out-of-root scope | Atomic rejection with field diagnostics and no revision increment |
| L1-08 | Copy section to another occurrence | New identities and draft states; source refs mapped; no evidence copied |
| L1-09 | Create two-FIFO fixture | Exactly 28 intents; composition intents at design root; occurrence filters distinguish ingress/egress |
| L1-10 | Change source quote with same section ID, then preview update | Affected requirements/intents marked for review; old P1 and source remain readable |
| L1-11 | Rename occurrence with stable IDs | Link survives; display path changes; no name-based rematching |
| L1-12 | Archive section referenced by coverage | Historic trace works; new coverage review reports missing active intent; evidence retained |
| L1-13 | Invalid semantic field edit on ready intent | Save as draft with diagnostics; no continued ready state |
| L1-14 | Export Markdown and bundle, restart/reimport | Readable plan and exact stable hierarchy preserved; source remains available offline |
| L1-15 | API idempotent retry and two-client conflicting edit | One application of retry; stale writer gets 409 and UI retains its draft |

The implementation must include an API-only fixture-building script and a browser test that opens its output. Do not replace this with direct model insertion or database fixtures alone. Source decoding can use fixture snapshots; plan authoring must traverse public API boundaries.
