# Historical: Circuit Designer Phase 1

> Archived and superseded. See the current
> [Circuit Designer design](../circuit_designer_architecture_v1.md).

Phase 1 connects the independent Phase 0 canvas to the active validated
SpecIR revision. It is a read-only vertical slice: users can select and inspect
real designs, but the circuit designer cannot yet modify source or layout.

## Delivered behavior

The existing FastAPI process exposes two circuit-specific read endpoints:

```text
GET /circuit-designer/catalog
GET /circuit-designer/designs/{design_id}
```

The catalog identifies the document and immutable source revision, lists every
design, and marks explicit entry designs. The graph endpoint resolves a stable
design entity ID and projects current SpecIR semantics into
`CircuitGraphSnapshot`. Unknown IDs return `404`; requests without an active
session retain the existing actionable `400` response.

Both responses use transport contracts from
`spec2gds.agent_spec.circuit_designer`. FastAPI does not expose SpecIR or
IP-XACT objects directly, and the projection remains read-only.

## Shared programmatic interface

`CircuitDesignerReadApi` is the common TypeScript query interface:

```ts
interface CircuitDesignerReadApi {
  getCatalog(options?): Promise<CircuitDesignCatalog>;
  getGraph(designId, options?): Promise<CircuitGraphSnapshot>;
}
```

`@spec2gds/circuit-client-http` implements this interface without React or layout
dependencies. It supports cancellation, URL-safe design IDs, runtime JSON
Schema validation, and structured HTTP errors. A future agent integration can
use the same interface as the UI rather than reaching into React state.

The data-source interface is intentionally read-only in Phase 1. Mutations
will use the command-batch contracts rather than adding imperative setters to
this API.

## UI workflow

Start the Python server:

```bash
uv sync
uv run spec2gds-server
```

Open `http://127.0.0.1:8000/editor` and open a sample or another V1 `.spec`
package. This establishes the active single-user SpecIR session.

In another terminal, start the circuit designer:

```bash
cd circuit-designer
npm install
npm run dev:specir
```

Open `http://127.0.0.1:4173` and change **Source** to **Active SpecIR
session**. The Vite development proxy maps `/api` to the FastAPI server on
port 8000. Select any design from the returned catalog or use **Refresh** after
opening a different package. Fixture mode remains the default and does not
require Python.

For a backend at another origin, construct `HttpCircuitDesignerReadApi` with a
custom `baseUrl`; deployment/CORS policy is deliberately left to the hosting
application.

## Verification

Phase 1 tests cover:

- catalog projection and explicit entry-design IDs;
- active-session FastAPI catalog and graph routes, including `404` behavior;
- generated schema synchronization;
- valid and invalid HTTP client payloads and server error propagation;
- every Phase 0 fixture, orthogonal route validation, and the 200-node scale
  case;
- TypeScript package checks and the Vite production build.

## Phase boundary

Included: active-document catalog discovery, immutable revision identity,
per-design graph queries, runtime response validation, cancellation, live
source/design selection, loading/error/refresh behavior, and continued fixture
operation.

Deferred at the Phase 1 boundary: topology or property mutation, persisted
manual layout, undo/redo, human/agent edit leases, command preview/execution,
proposal review, hierarchy drill-down behavior, automatic session
notifications, FastAPI hosting of the compiled React assets, and IP-XACT
writes. These are delivered by the subsequent phases documented in
[Circuit Designer Complete Roadmap](circuit_designer_complete.md), within the
project's deliberately limited IP-XACT profile.
