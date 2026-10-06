# End-to-end flows

## Create and edit a specification

```mermaid
sequenceDiagram
    actor User
    participant UI as Spec editor
    participant API as Spec API
    participant Package as .spec package

    User->>UI: File → New Spec; enter name and server-local path
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
ports. Ports appear as rows in one definition table. The designer can then add
top-level component instances to the entry design by choosing from the
specification’s component list.
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
migration, port deletion, and composite boundaries remain separate flows.
Existing bus interfaces, port maps, channels, interface connections, and
bus/abstraction definitions are preserved in the package but hidden from the
editor document until those flows are ready.

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
    CA-->>SA: CircuitDocument + source map + omission notes
    SA->>CS: Create/refresh session and register source binding
    CS-->>SA: document_id, revision, and writable capability
    SA-->>SE: Editor URL, binding metadata, and projection notes
    SE->>CD: Open new browser tab
    CD->>CS: Read session
    CS-->>CD: Projected circuit and source binding
    User->>CD: Begin editing and change topology/layout
    CD->>CS: Save to Spec(candidate, base source revision)
    CS->>SA: Authenticated preview, then idempotent commit
    SA->>SA: Validate and atomically save .spec
    SA-->>CS: Authoritative re-projection and new source revision
    CS-->>CD: Replace session, release lease, exit edit mode
    SA-->>SE: source.changed; refresh tables and SVG
```

Scenario: a specification design contains direct port wiring and bus
interfaces. Direct ports appear in the circuit view. Unsupported bus items are
reported, not silently converted. Unused transactional and structured ports
are also reported as omitted. A connected non-wire port rejects the launch
because dropping a real design connection would be unsafe. Eligible design
sessions are editable, but the `.spec` package remains authoritative because
the source transaction must succeed before the ephemeral Circuit session is
updated. Leaf-component previews remain read-only.

Users can launch from the grouped **Circuit** menu or from **Options → Open
circuit** on a design or component section. Non-circuit sections omit that
command. Entity-backed sections retain **Options → More actions**. See
[Circuit Designer specification synchronization](circuit-designer-spec-sync.md)
for conflicts, recovery, and the semantic layout annotation.

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
    User->>UI: Begin editing
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

Scenario: a designer starts from the blank canvas, begins editing, creates two
component definitions and connects their instances. Save validates the batch,
updates the ephemeral session, and downloads a new file. The service never
overwrites a local file in place.

## Submit or review an Assistant proposal

```mermaid
sequenceDiagram
    actor User
    participant Editor
    participant Assistant
    participant Owner
    participant Source
    User->>Editor: Open document/entity-bound chat
    User->>Assistant: Request a supported edit
    Assistant->>Owner: Read fresh context and authored revision
    Assistant->>Owner: Preview typed candidate
    alt Automatic Spec policy
      Assistant->>Owner: Submit validated artifact
      Owner->>Source: Guarded atomic save with decision
      Owner-->>Assistant: Applied receipt and saved revision
    else Restricted Spec policy
      Owner-->>Assistant: Stored proposal awaiting review
      User->>Assistant: Approve or discard exact proposal
      Assistant->>Owner: Explicit stored-ID decision
      Owner->>Source: Revalidate and save if approved/current
    else Circuit handoff
      User->>Assistant: Send reviewed proposal
      Assistant->>Owner: Store pending Circuit proposal
      User->>Editor: Accept into private draft
      User->>Editor: Save to Spec or download independent file
    end
```

Discussion alone changes nothing. Spec application follows the owner's automatic
or restricted policy and always validates the authored revision. Circuit send
and acceptance are separate from saved source; source-bound changes require
**Save to Spec**. A stale or rejected proposal leaves source unchanged.

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
