# AI Assistant

The optional `ai-assistant/` application provides conversations and reviewed
change proposals without becoming part of either editor's critical path. It is
a separate FastAPI/A2A service with a React client and its own `uv` environment.

## Specification editor connection

The specification editor owns the source and the integration contract:

1. `POST /assistant/launch` returns a URL for a fresh entity-bound chat.
2. The AI Assistant reads `GET /assistant/context` from the editor service.
3. A requested typed proposal is sent to `/assistant/proposals/preview`.
4. Only an explicitly accepted, current proposal is sent to
   `/assistant/proposals/apply`.
5. The editor backend revalidates ownership, the source revision, IP-XACT, and
   the spec2gds editing profile before committing atomically.

Discussion and draft generation never write the `.spec` package. A chat stays
bound to one existing component, design, protocol definition, or narrative
block. Document-level specification renaming and top-level component/design
creation are intentionally deferred until a document-bound assistant entry
point is designed.

## Choosing the owning application

A chat created from the AI Assistant home screen begins unbound and presents a
choice between Circuit Designer and Spec Editor. The choice controls which
connection form, context loader, agent behavior, proposal preview, and apply
action are used. Once connected, the domain badge in the sidebar identifies
the owning application and the binding cannot be changed.

The chooser reads the shared service directory and probes the owning APIs. It
shows their availability and pre-fills the resolved service URLs. Circuit
Designer's toolbar bypasses the manual form by calling `/launch/circuit` with
the active document; the Assistant validates that document before creating the
bound chat. Spec Editor's top button selects the Spec workspace, while its
entity action creates the fully bound Spec chat.

Circuit Designer chats are connected manually using the circuit service URL
and document ID. Spec Editor chats should normally be opened from an entity's
**Options → More actions… → Explore with AI Assistant** command, which supplies
the service URL, document ID, entity kind, and entity ID. The AI Assistant also
exposes an advanced manual Spec connection form when those identifiers are
already known.

## Circuit editing profile

Circuit chats receive a semantic snapshot, an exact endpoint catalog, and an
optional rendering. The semantic snapshot is authoritative; SVG and PNG are
visual aids. The context distinguishes four commonly confused objects:

- A component definition is a reusable type.
- An instance places one use of a component definition in the design.
- A component terminal is a pin repeated on every instance of its definition.
- A boundary terminal is a top-level design port.

The Assistant can propose local component definitions, component instances,
component-terminal updates, boundary terminals, nets, and endpoint connections.
For example, “add a component” normally places an instance of an available
definition, “add an input port” creates a boundary terminal, and “connect A to
B” creates a net containing both endpoints. If the user explicitly requests a
new component type, the proposal can add its definition before placing it.

Updates to component definitions, instances, boundary terminals, and nets are
complete replacements rather than partial patches. The prompt therefore
includes exact current JSON for copy-forward fields and orders dependent
operations so definitions and terminals exist before instances and nets refer
to them. Layout, routes, and geometry remain outside AI-authored proposals.

Both proposal models are kept within the OpenAI Structured Outputs JSON Schema
subset: object variants use `anyOf` rather than the unsupported `oneOf`, and
arbitrary parameter/property maps are presented as key/value lists to the model
before being normalized back to the owning API's map representation.

Design-bound Spec context includes each available component's exact ports and
bus interfaces, not only its VLNV. The proposal schema keeps interface
connections and ad-hoc port connections as separate shapes. Interface
connections may contain only interface endpoints; ad-hoc connections may
contain only internal/external port endpoints. The agent must return an
unsupported result when the referenced components do not expose compatible,
named endpoints instead of inventing a port or interface.

## Entity editing profile

Entity metadata and design component instances use the same semantic values as
the direct editor. Component-port proposals support three families:

- Wire: `in`, `out`, or `inout`, plus an optional compact Range.
- Transactional: `requires`, `provides`, or `both`, plus optional Kind, Custom
  kind, and Bus width.
- Structured: `in`, `out`, or `inout`; packing and hidden type definitions are
  server-owned.

Every port has an immutable Name and Family plus optional Display name and
Description. An upsert is a complete value, so unchanged fields must be copied
from context. Family conversion is rejected, and ports on components owning an
internal design are read-only just as they are in the direct editor.

## Naming and configuration

Run the service with `uv run spec2gds-ai-assistant`. The editor uses the shared
`config/services.json`, with `AI_ASSISTANT_URL` as its URL override. The neutral
`/assistant/*` routes, `assistant_url` response field, internal
`spec2gds_assistant` Python package, and `ASSISTANT_*` service settings remain
stable.

The Assistant permits non-loopback owning services only when their resolved
URLs are present in its configured allowlists.
