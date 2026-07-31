# IP-XACT to Circuit Designer Adapter v1

The specification editor owns the IP-XACT-aware adapter. Circuit Designer
continues to accept only its independent `CircuitDocument` REST contract.

## Run the integrated development flow

Start Circuit Designer in one terminal:

```bash
cd circuit-designer
npm install
npm run dev
```

This starts its ephemeral service on `127.0.0.1:4100` and browser client on
`127.0.0.1:4180`.

Start the specification editor from the repository root in another terminal:

```bash
uv sync
uv run spec2gds-editor --reload
```

Open <http://127.0.0.1:8000/editor>, select a `.spec` package and a component or
design, then choose **Open circuit**. The editor projects the selected source revision,
creates or reuses an ephemeral Circuit Designer session, and opens that exact
session in a new tab.

`CIRCUIT_DESIGNER_SERVICE_URL` and `CIRCUIT_DESIGNER_UI_URL` override the
default REST and browser locations when the two applications are composed
behind different local URLs.

## Initial mapping boundary

The adapter currently maps:

- design instances and their referenced component definitions;
- leaf components as circuit boundary-terminal views, or a component's owned
  internal design when one exists;
- physical wire ports with `in`, `out`, or `inout` direction;
- scalar width as integer `1`;
- one-dimensional vectors as opaque `[left:right]` text, without evaluation;
- IP-XACT ad-hoc connections as Circuit Designer nets;
- external port references as circuit boundary terminals for a component-owned
  internal design.

IP-XACT bus interfaces and interconnections are deliberately omitted in this
milestone. The launch response reports their connection names, and the editor
shows an omission notice. Physical ports mapped only through an omitted bus
interface are not exposed as unrelated scalar terminals.

The opened circuit is a source-owned, read-only projection. Editing and saving
back to IP-XACT require the reverse adapter and optimistic source-revision
transaction flow; until that exists, the UI does not offer **Unlock** for an
editor-linked projection.

The source revision hash is included in the generated circuit document ID.
Opening the same design revision reuses its live ephemeral session; changing
the IP-XACT source produces a new projection identity. Restarting the Circuit
Designer service discards those sessions, after which **Open circuit** creates
them again from canonical source.
