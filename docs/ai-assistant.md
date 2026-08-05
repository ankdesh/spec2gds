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
