# Agent-Spec Roadmap and Open Decisions

V1 is complete: deterministic source packages, SpecIR, atomic edits, generic
actions, artifact provenance, reviewed proposals, local API, and browser editor
are implemented and tested. This document tracks decisions beyond that
boundary; it does not redefine current behavior.

The sequenced product roadmap remains in
[`pivot/future_v2_v3_v4_roadmap.md`](pivot/future_v2_v3_v4_roadmap.md).

## V2: Executable Performance Model

Planned direction:

- introduce an explicit SystemC capability pack;
- define typed implementation views without placing generated state in SpecIR;
- preserve action snapshot, provenance, and reviewed writeback rules;
- record toolchain/environment identity strongly enough for reproducibility.

Open decisions:

- What is the smallest SystemC input/output contract that remains vendor
  neutral?
- Which performance assumptions belong in source annotations versus generated
  artifacts?
- What validation proves generated model interfaces match canonical IP-XACT?

## V3: RTL Capability

Planned direction:

- add synthesizable RTL generation/analysis as another capability pack;
- make SystemC-to-RTL relationships explicit artifact lineage;
- require reviewed source proposals for discovered interface or constraint
  changes.

Open decisions:

- Which RTL languages and tool identities are first-class?
- How are generated/manual RTL divergence and back-documentation represented?
- Which checks form the acceptance boundary before downstream implementation?

## V4: Implementation and GDS

Planned direction:

- integrate synthesis, place-and-route, timing, power, and physical reports;
- keep downstream files in artifact storage rather than source packages;
- connect implementation evidence to stable source entities and revisions.

Open decisions:

- What is the project/tool abstraction for proprietary and open-source flows?
- How are large artifact retention and remote storage addressed?
- Which physical findings can generate safe reviewed source proposals?

## Cross-Cutting Decisions

### Multi-document and multi-user service

V1 intentionally has one active local session. A future service needs explicit
document/session identity, locks or merge policy, authorization, and lifecycle
management before remote exposure.

### Remote or untrusted actions

V1 actions are trusted local subprocesses. Remote execution requires capability
discovery, authentication, transport integrity, cancellation, streaming events,
resource policy, and a real security isolation boundary.

### Fine-grained component edit commands

V1 can replace a complete profiled IP-XACT document and has typed operations
for hierarchy, designs, narrative, and assets. Add component-field commands only
when form editing needs a stable granular public API.

### Schema evolution

Before V2 source fields land, define format/profile version compatibility,
migration ownership, and whether old packages are read-only or upgraded by an
explicit command.

### Artifact retention

Define garbage collection around durable `ArtifactRef` reachability. Never
delete sidecar content merely because it is not part of the source hash.

## Decision Method

For each roadmap change, record:

1. source-of-truth impact;
2. persisted contract and version impact;
3. validation and failure behavior;
4. action/artifact provenance impact;
5. UI/API impact;
6. deterministic sample and acceptance evidence;
7. migration or explicit incompatibility policy.
