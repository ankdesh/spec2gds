# End-to-end flows

## Create and edit a specification

```mermaid
sequenceDiagram
    actor User
    participant UI as Spec editor
    participant API as Spec API
    participant Package as .spec package

    User->>UI: File → New Specification; enter name and server-local path
    UI->>API: POST /documents/create with title and path
    API->>Package: Create and validate empty package
    Package-->>API: Source revision hash
    API-->>UI: Immutable snapshot + A2UI projection
    User->>UI: Edit structured content
    UI->>API: POST /transactions with expected hash
    API->>API: Apply operations and validate candidate
    alt candidate is valid and current
        API->>Package: Deterministic atomic save
        API-->>UI: New snapshot and hash
    else invalid or stale
        API-->>UI: Diagnostics; source is unchanged
    end
```

Scenario: a designer creates `timer.spec` with the visible name “Timer
Platform,” adds a component and entry design from their group menus, edits the
introductory paragraph, and adds wire, transactional, and packed structured
ports. Each port is shown in its own compact definition card.
Each Save submits one typed transaction. The API compares the submitted
revision hash with the active revision, constructs IP-XACT XML server-side, and
atomically saves a valid candidate. A stale or invalid candidate leaves the
file untouched and the inline draft available for correction. Creating a
package also fails closed when the requested path already exists.

The editor keeps package operations in the **File** menu. Accepted transactions
save automatically, so Save is informational rather than a second persistence
step. **File → Refresh From Disk** reopens the active server-local path.

Direct editor operations are intentionally narrower than the source format.
The editor creates components and entry designs with the fixed internal
`spec2gds.local:work:<name>:1.0` identity convention, edits paragraph text, and
adds or edits all three leaf-component port families. The visible specification
title is stored separately so renaming it does not migrate IDs or references.
Bus interfaces, detailed TLM protocol modeling, structured subports, identity
migration, port deletion, and composite boundaries remain separate workflows.

## Open a specification in Circuit Designer

```mermaid
sequenceDiagram
    actor User
    participant SE as Spec editor
    participant SA as Spec API
    participant CA as Circuit adapter
    participant CS as Circuit service
    participant CD as Circuit Designer

    User->>SE: Choose a component or design
    SE->>SA: POST /circuit-designer/launch
    SA->>CA: Project current SpecRevision
    CA-->>SA: CircuitDocument + omitted bus items/non-wire ports
    SA->>CS: Create or reuse source-owned session
    CS-->>SA: document_id and revision
    SA-->>SE: Editor URL and projection notes
    SE->>CD: Open new browser tab
    CD->>CS: Read session
    CS-->>CD: Read-only projected circuit
```

Scenario: a specification design contains direct port wiring and bus
interfaces. Direct ports appear in the circuit view. Unsupported bus items are
reported, not silently converted. Unused transactional and structured ports
are also reported as omitted. A connected non-wire port rejects the launch
because dropping a real design connection would be unsafe. The projected
session is read-only because the `.spec` file remains authoritative.

Users can launch from the grouped **Circuit** menu or from **Options → Open
circuit** on a design or component section. Non-circuit sections omit that
command. Entity-backed sections retain **Options → More actions**.

## Edit an independent circuit

```mermaid
sequenceDiagram
    actor User
    participant UI as Circuit Designer
    participant Service as Circuit service
    participant Draft as Private draft
    participant File as .circuit.json

    User->>UI: Start empty or open file
    UI->>Service: Create or join session
    User->>UI: Unlock
    UI->>Service: Acquire edit lease
    Service-->>UI: Base revision + lease
    User->>UI: Add, connect, move, or route
    UI->>Draft: Apply shared typed operations
    alt Save
        UI->>Service: Commit operation batch
        Service->>Service: Validate revision and semantics
        Service-->>UI: Accepted canonical snapshot
        UI->>File: Download new file
    else Cancel
        UI->>Draft: Discard private changes
    end
```

Scenario: a designer starts from the blank canvas, unlocks it, creates two
component definitions and connects their instances. Save validates the batch,
updates the ephemeral session, and downloads a new file. The service never
overwrites a local file in place.

## Review an assistant proposal

```mermaid
sequenceDiagram
    actor User
    participant Editor
    participant Assistant
    participant API as Owning API
    participant Source as Canonical source

    User->>Editor: Explore selected entity
    Editor->>Assistant: Launch entity-bound chat
    Assistant->>API: Read current context
    User->>Assistant: Request a change proposal
    Assistant->>API: Preview typed operations at base revision
    API-->>Editor: Candidate projection and diagnostics
    User->>API: Accept or reject
    alt accepted and current
        API->>Source: Validate and commit
        API-->>Editor: Source-changed event
    else rejected or stale
        API-->>Editor: No source change
    end
```

Scenario: the assistant proposes a description or circuit change. Discussion
alone changes nothing. The user reviews the typed candidate. Acceptance still
runs normal validation and revision checks; a stale proposal must be rebuilt.

## Import an existing document

```mermaid
flowchart LR
    Input["PDF, DOC/DOCX, or ODT"] --> Docling["Docling reader"]
    Docling --> Narrative["Typed narrative + retained source"]
    Tables["Supported hardware tables"] --> Extract["Optional OpenAI extraction"]
    Extract --> IPXACT["Validated IP-XACT"]
    Narrative --> Package["New .spec package"]
    IPXACT --> Package
```

Run `uv sync --extra document-import`, then
`uv run spec2gds-import-document path/to/input -o output.spec`. Add `--openai`
only when table-to-IP-XACT extraction is wanted and configured.
