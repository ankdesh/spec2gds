# V1.3 — Actions, Artifacts, and Reviewed Change Proposals

> Status: completed. This file is implementation and acceptance history; the
> active contract is in `docs/agent_spec_action_execution.md`.

## Goal

Provide generic, entity-targeted external actions that consume immutable SpecIR
snapshots, create traceable artifacts, report results, and optionally propose
reviewable source changes.

Use the term **action execution** for one invocation. Do not introduce new
public types, routes, or UI labels that use the current term “run.”

## Non-Goals

- SystemC, TLM, RTL, compilation, simulation, synthesis, or formal actions.
- Remote workers, queues, authentication, retries, cancellation, or
  multi-user coordination.
- Automatic source writes by external actions.
- Action-result caching or pipeline scheduling.

## Public Contracts

```text
ActionDefinition
  action_id
  version
  title
  target_entity_kinds
  input_schema
  required_capabilities
  consumed_artifact_roles
  produced_artifact_roles
  report_schema
  executor
  preconditions
  postconditions
  allows_change_proposals

ActionSnapshot
  snapshot_id
  source_revision_hash
  target
  dependency_closure
  linked_narrative
  accepted_annotations
  normalized_inputs
  input_artifacts

ActionExecution
  execution_id
  action_id
  action_version
  snapshot_id
  status
  events
  result_refs

ArtifactRef
  artifact_id
  role
  kind
  media_type
  sha256
  size
  storage_locator
  producer
  source_revision_hash
  source_entities
  input_artifact_ids
  parent_artifact_ids
  toolchain_identity
  normalized_inputs

ChangeProposal
  proposal_id
  base_source_revision_hash
  producer_execution_id
  rationale
  operations
  diagnostics
  review_status
```

## Snapshot SDK and Bundle

An action targets one component or design. Construct an immutable snapshot that
includes the target, its resolved transitive source closure, linked narrative,
required accepted annotations, normalized inputs, and selected input artifacts.

Expose this snapshot in two equivalent forms:

- A read-only Python SDK for in-process project actions.
- A language-neutral snapshot bundle for external commands.

The bundle contains a manifest, normalized source JSON/XML, selected assets,
and read-only input artifacts. An external executor never receives a mutable
repository or write access to the live `.spec` package.

## Executor and Completion Protocol

Implement a local out-of-process command adapter:

1. Create isolated input and output directories.
2. Write the snapshot bundle and normalized action inputs.
3. Invoke the configured command with explicit input/output paths.
4. Require a typed completion manifest in the output directory.
5. Validate report data, declared artifact roles, hashes, media types, and
   proposal shape before accepting results.

Record action version, executor identity, normalized inputs, source revision,
and toolchain identity. Treat malformed completion manifests, missing files,
non-zero exits, and timeouts as explicit failed action executions.

## Artifact Storage and Lineage

Store artifact metadata, small reports, execution records, and proposal records
under `activity/` in the package. Store large content in a content-addressed
sidecar keyed by SHA-256.

Generated or transformed artifacts are immutable. A transformation consumes an
artifact and creates a child artifact with its parent ID; it never overwrites
existing content.

Artifacts attach to stable component/design/entity references, not document
headings. Missing sidecar content is reported as an artifact diagnostic without
corrupting source state.

## Change-Proposal Workflow

Actions may return typed source patch operations only when their definition
allows proposals. The server must:

1. Validate the patch against the execution's base source revision.
2. Produce a preview and diagnostics.
3. Persist the proposal without altering source.
4. Accept only after explicit architect review.
5. Recheck the base revision and run the V1.2 edit transaction validator on
   acceptance.

Rejecting a proposal retains the action record but leaves source untouched.

## Reference Actions

Implement three external generic actions:

- **Snapshot summary:** emits a JSON/text summary artifact for a component or
  design snapshot.
- **Artifact transform:** consumes a selected text artifact and produces a
  child text artifact with lineage.
- **Narrative proposal:** returns a harmless reviewed narrative or concise
  description edit proposal.

These actions prove the platform without committing V1 to a SystemC or RTL
generator.

## Implementation Steps

1. Introduce action, execution, snapshot, artifact, and proposal contracts.
2. Replace new block/heading targeting with `EntityRef` targeting.
3. Implement dependency snapshots, SDK accessors, and bundle serialization.
4. Implement the local command executor and completion protocol.
5. Implement content-addressed sidecar ingestion and package activity metadata.
6. Implement artifact attachment and lineage queries.
7. Implement proposal preview, accept, and reject operations through V1.2
   transactions.
8. Add the three reference actions and durable execution/report views.

## Validation and Tests

- Snapshot contents, closure correctness, immutability, and deterministic
  snapshot hashing.
- SDK and serialized-bundle equivalence.
- Action input schemas and preconditions.
- Successful execution, non-zero exit, timeout, malformed completion, and
  missing output handling.
- Artifact hash, role, media type, sidecar location, attachment, and lineage
  enforcement.
- Action activity does not change `source_revision_hash`.
- Proposal preview, acceptance, rejection, stale-base rejection, and invalid
  patch rejection.
- Reopening a package preserves activity metadata and reports missing sidecar
  content safely.

## Assumptions

- V1 actions are local commands or trusted local Python integrations.
- Source changes always require architect review.
- Large artifact contents are not embedded in `.spec`; portable artifact
  bundles are a later enhancement.

## Exit Gate

A real out-of-process reference action consumes a design snapshot and attaches
an artifact. A second action produces a source proposal that creates a new
source revision only after acceptance. All execution, artifact, and proposal
tests pass.
