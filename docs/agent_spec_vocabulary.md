# Agent-Spec Vocabulary

This glossary is the shared language for the `agent-spec` architecture. It
captures current agreements and marks concepts that still need confirmation.

## Agreed Concepts

| Term | Meaning |
| --- | --- |
| Hardware spec document | The original human-written specification. It may arrive as Word, PDF, Markdown, agent-spec, or another source format. |
| Agent-spec document | The enriched agent-spec-based document produced from a hardware spec document. It remains readable by humans, but also contains deterministically defined artifacts for agents and pipelines. |
| Agent-spec conversion | The process that imports or translates a hardware spec document into an agent-spec document with blocks, tags, artifacts, and links. |
| agent-spec archive | The physical `.spec` package. It stores normal agent-spec content plus embedded artifact metadata under `spec_data/`. |
| Document content | The visible agent-spec material: headings, subheadings, paragraphs, tables, figures, and links. |
| Heading | An .spec heading or subheading. Every heading creates a block. |
| Block | The versioned unit of work created from one .spec heading or subheading. It can also be called a section or subsection. A block includes the content under that heading until the next heading at the same or higher level, plus linked artifacts. |
| Tag | A label assigned to a block that controls meaning and available actions. A block can have multiple tags. Example tags may include IP block, register map, interface, architecture note, generated-report target, or verification plan. |
| Block version | An immutable snapshot of a block. The snapshot includes both prose/document content and linked artifacts together. |
| Active version | The block version currently selected for viewing and for default action inputs. |
| Artifact | Deterministically defined data attached to a block. Artifacts include interface definitions, register maps in IP-XACT form, simulation results, performance numbers, SystemC code, RTL code, UVM code, synthesis reports, logs, metrics, diagrams, and generated structured data. Large artifacts live externally; hashes and summaries live in the agent-spec. |
| Artifact reference | The agent-spec-stored metadata that identifies an artifact, its hash, summary, type, storage location, producer, and related block. |
| Attachment | A relationship from a block to an artifact. IP-XACT attachments are the current example; generated artifacts should behave similarly. |
| Action | A configured operation exposed by the server and rendered by the UI. Examples: generate SystemC, generate RTL, run synthesis, update UVM, validate block. |
| Action tag rule | Logic or metadata that decides which actions are available for blocks with specific tags. |
| Run | One execution instance of an action with specific block versions and parameters. |
| Pipeline | The implementation behind an action. It may be a Python function, shell/tool wrapper, agent workflow, EDA tool invocation, or a combination. |
| Input snapshot | The immutable set of block versions, artifacts, parameters, and document hash used by a run. |
| Read set | The exact block versions and artifacts read by a run. |
| Write set | The exact artifacts, diagnostics, links, and metadata updates produced by a run. |
| Writeback record | The server-owned record of artifact attachments, metadata updates, diagnostics, feedback-needed status, or future reviewed source-update requests. Pipelines should not directly mutate source block content. |
| Spec graph | The server's typed model of blocks, block versions, tags, active versions, artifact references, attachments, and relationships. It is projected from and persisted into the agent-spec archive. |
| Event | A typed pub-sub message describing a change or lifecycle step, such as action requested, run started, artifact created, writeback applied, feedback needed, or document updated. |
| Central server | The Python service that owns document loading/saving, graph projection, action discovery, run coordination, events, and writeback application. |
| UI | A client of the central server. It renders document content, block versions, attachments, available actions, run status, artifact previews, and feedback-needed items. |

## Concepts Still To Confirm

| Term | Working meaning |
| --- | --- |
| Tag taxonomy | The first concrete set of tags that headings/blocks can use. |
| Native agent-spec schema | A project-owned structured schema that may sit beside IP-XACT for concepts IP-XACT does not express cleanly. |
| External artifact mechanism | The exact storage and retrieval mechanism for large artifacts whose hashes and summaries are embedded in agent-spec. |
| Action provider | The Python module, plugin, entry point, or config object that registers an action with the server. |
| Worker | The runtime process that executes actions. It may be in-process first and remote later. |
| Review policy | Whether writebacks are always reviewed by a human, or some trusted actions can auto-apply. |
