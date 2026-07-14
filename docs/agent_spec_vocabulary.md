# Agent-Spec Vocabulary

This glossary defines the terms used by the current `agent-spec` code and
documentation. Deferred terms are separated so implementation docs do not sound
like future features already exist.

## Current Terms

| Term | Meaning |
| --- | --- |
| Hardware specification | The human-authored description of a hardware component or subsystem. Source material may come from PDF, HTML, office documents, Markdown, or other formats before it is converted into this repository's `.spec` format. |
| `.spec` document | The project document package used by `agent-spec`. It keeps office-compatible document content plus project-owned metadata under `spec_data/`. |
| `AgentSpecArchive` | The package wrapper in `spec2gds/agent_spec/package/archive.py`. It loads/saves `.spec` packages and preserves `spec_data/` files. |
| Document content | The visible content stored in `content.xml`: headings, paragraphs, lists, tables, images, and links. |
| Semantic document | The editor-facing projection produced by `document/semantic.py`. It is smaller than a full office document model and contains only the fields the current editor needs. |
| Heading | A `text:h` element in `content.xml`. In the action graph, every heading becomes a block. |
| Block | A heading-backed unit of work in the action graph. Its ID is the heading `xml:id`; when a heading has no ID, the code assigns one. |
| Section | A user-facing way to talk about a heading and the content below it. In current action code, a section corresponds to a block plus the content until the next heading at the same or higher level. |
| Section version group | Editor metadata for adjacent legacy headings such as `Cache behavior//v1` and `Cache behavior//v2`. Stored in `spec_data/agent-spec-editor/relations.json`. |
| Block version | An immutable metadata snapshot for one block, stored as a `BlockVersionRecord`. The version ID is derived from a hash of the section content and attached artifact IDs. |
| Active version | The block version selected as the default action input. For editor section groups, the active section variant is tracked separately in editor relation metadata. |
| Executor | The external system identified by an action's `executor_id`; it later completes a dispatched run. |
| Artifact | A generated or embedded payload described by `ArtifactRef`, such as a SystemC output or an IP-XACT XML payload. |
| Artifact reference | The metadata stored for an artifact: ID, kind, media type, summary, hash, external URI, producer, source trace, role, and timestamp. |
| Attachment | An append-only relationship from a block to an artifact. Current action attachments are stored in the graph; editor IP-XACT heading attachments are stored in editor relations. |
| IP-XACT payload | XML stored under `spec_data/ipxact/` and handled by the IP-XACT plugin and editor summary view. |
| `spec://` link | A document link scheme resolved by the plugin manager. Current support resolves modality, file path, and node path through registered plugins. |
| Action | A declarative `ActionSpec` with input/report schemas and an executor identity. Enabled actions are selectable for every block. |
| Action registry | The in-process registry in `actions/builtin.py`. It registers built-in actions, loads optional modules, and applies config enablement. |
| Run | One execution of an action against an immutable input snapshot. Stored as a `RunRecord`. |
| Input snapshot | The captured block version, attached artifacts, document hash, validated inputs, and preconditions used by a run. Later document edits do not change this snapshot. |
| Precondition report | The checks that determine whether an action may be triggered for a block and input values. |
| Postcondition report | The checks that validate executor report data and returned artifacts. |
| Action report | Durable executor report data plus the derived read-only A2UI surface stream. |
| Read set | The block versions and artifact references recorded as inputs for a run. |
| Writeback record | The server-owned record of accepted artifact metadata or `needs_human_feedback` diagnostics produced by a run. |
| Run event | A durable audit event for one run, persisted as `events.ndjson` at run boundaries. |
| Sidecar | A directory beside the `.spec` file used for run output files and temporary artifacts. By default it is `<document>.agent-spec-sidecar/`. |
| Editor API | The local FastAPI app in `api/document_app.py`, used by the React editor for snapshots, saves, IP-XACT operations, assets, and file browsing. |
| Action API | The FastAPI app in `api/app.py`, mounted under `/agent-spec`, used for action discovery, preconditions, runs, executor completion, and reports. |

## Deferred Terms

These terms are useful for planning, but they are not complete subsystems in the
current implementation.

| Term | Current status |
| --- | --- |
| Remote worker | The current dispatcher records a run and awaits an executor callback. Queue, lease, and deployment support remain future work. |
| Event bus | Current events are per-run audit records in memory and in `events.ndjson`. There is no standalone pub-sub service. |
| External artifact store | A content-addressed or remote artifact store remains open design work. |
| Source update writeback | Current actions can attach artifacts and diagnostics. Direct edits to source prose from actions are not implemented. |
| Multi-user server | The current API is local and single-user, with no authentication. |
| Import adapter | The benchmark builder and sample tools produce `.spec` files, but general Word/PDF/Markdown/SystemRDL/CSV import adapters are not implemented as product flows. |
