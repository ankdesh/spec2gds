# Circuit Designer Web Client

This React application is the human client for Independent Circuit Designer
v1. It renders the existing canvas and communicates exclusively with the
versioned Circuit Designer REST service.

It does not use IndexedDB, SQLite, Python, SpecIR, IP-XACT, or browser
filesystem handles.

## Run

From `circuit-designer/`:

```bash
npm install
npm run dev
```

Open <http://127.0.0.1:4180>. The command starts the React/Vite client and the
ephemeral Node service. To run only this Vite process, use
`npm run dev:standalone` and start `npm run service` separately.

## File workflow

- **Open file** uses a standard hidden `<input type="file">`.
- The browser parses and validates the selected canonical `CircuitDocument`.
- A valid document creates or joins a matching ephemeral REST session.
- An invalid file leaves the current session unchanged and displays
  diagnostics.
- **Save** commits a private draft and downloads the accepted document.
- **Download file** downloads the current committed document.
- Files are named `<document_id>.circuit.json`.
- Existing local files are never overwritten in place.

Opening a file and all export actions are disabled while a private draft is
active. Save or Cancel first.

Terminals may be `input`, `output`, or `inout`. Widths may be positive integers
or opaque symbolic text. Symbolic widths are displayed as supplied and support
whole-terminal connections; numeric slices require a numeric terminal width.

## Runtime dependencies

```text
React web client
  |
  +-- @spec2gds/circuit-client-http
  |     REST transport and response validation
  |
  +-- @spec2gds/circuit-core
  |     portable contracts, private draft, render projection
  |
  +-- @spec2gds/circuit-layout
  |     cancellable placement and routing
  |
  +-- @spec2gds/circuit-react
        canvas rendering and gestures
```

The service is the only live session authority. It keeps documents, revisions,
leases, proposals, and idempotency results in process memory. Durable ownership
belongs to the client that supplied the circuit.

See:

- [`docs/circuit_designer_architecture_v1.md`](../../../docs/circuit_designer_architecture_v1.md)
- [`docs/circuit_designer_protocol_v1.md`](../../../docs/circuit_designer_protocol_v1.md)
- [`docs/circuit_designer_run_v1.md`](../../../docs/circuit_designer_run_v1.md)
