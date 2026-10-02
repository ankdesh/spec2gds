# Circuit Designer specification synchronization

For a diagram-led explanation of the complete structure and request flow, see
[Spec Editor and Circuit Designer integration architecture](spec-circuit-integration-architecture.md).

Circuit Designer can edit a design whose authoritative source is an open
`.spec` package. The Circuit service still keeps only an ephemeral working
session: **Save to Specification** is the durable write boundary and the Spec
API remains the owner of IP-XACT.

Leaf components without an internal design are previews and remain read-only.
Entry designs, other design entities, and components that resolve to an
internal design receive a writable source binding.

## Start the services

Install the Python and JavaScript workspaces, then start the combined stack:

```bash
scripts/setup-all.sh
scripts/serve-all.sh start
```

Open a `.spec` package in the Specification Editor. Use a design section's
**Open Circuit Designer** preview action, **Options → Open circuit**, or the
top-level **Circuit** menu. The Spec API projects the immutable source revision,
creates or refreshes a stable Circuit session, and registers a server-to-server
source binding with the Circuit service. The binding credential is never sent
to the browser. Callback validation trusts loopback plus the Spec API host from
the shared service directory; unrelated non-loopback callback hosts remain
blocked unless explicitly allowlisted by the embedding service.

## Edit and save

Choose **Edit → Begin Editing**, make topology or layout changes, and use
**File → Save to Specification**, its configured shortcut, or the compact
header button shown for a dirty draft. Supported source edits include:

- placing package components and creating or deleting instances;
- creating a local reusable component and its first instance atomically;
- adding, updating, renaming, or deleting visible ad-hoc connections;
- numeric LSB/Width endpoint slices;
- instance geometry, terminal placement, routes, labels, grid, and direction;
- cycle-edge markers, stage labels, clock references, and optional domain
  assignments; and
- boundary-port creation and editing for internal designs.

The Circuit service first asks the Spec API to preview the candidate. The Spec
API compiles minimal typed operations against the bound source identities and
validates the complete candidate package. A commit then saves the `.spec`
atomically. Only after source acceptance does the Circuit service replace its
session with the authoritative re-projection, release the edit lease, and leave
edit mode.

The Spec API publishes `source.changed` after the package commit. A
Specification Editor with no local form open refreshes its tables and derived
SVG immediately. If an inline form has unsaved input, the editor preserves it
and offers an explicit refresh instead.

**File → Cancel Changes** discards only the private Circuit draft. It never
touches the `.spec` package. When an Assistant proposal is pending, **Accept**
stages its operations in that draft and leaves the proposal pending. Save
resolves the proposal only after the Spec commit succeeds; Cancel or an
unchanged-source reload allows the proposal to be staged again. A rejected or
stale source save keeps the draft and proposal. **Reject** removes the
proposal. Direct API acceptance and ordinary Circuit write routes refuse
source-bound documents.

## Conflicts and recovery

Every source binding records the source revision used to create the Circuit
draft. If another editor or Circuit session saves first, the stale save is
rejected. Circuit Designer keeps the entire private draft and shows:

- **Reopen Latest**, which discards the private draft and re-projects the
  current `.spec` revision; and
- **Download Circuit JSON**, which saves the stale candidate for inspection or
  manual recovery.

There is no automatic rebase and no force-overwrite path. The first successful
save wins. Commit requests are idempotent, so retrying after a lost
cross-service response resolves to the already committed source result rather
than applying the changes twice.

## Preserved and guarded source

Circuit IDs are mapped to stable specification identities; display labels are
never used to guess ownership. The reverse adapter changes visible instances,
ad-hoc connections, and supported boundary ports without replacing the design.
Omitted interface connections, bus data, and unsupported unused ports are
preserved by the package transaction.

An edit is rejected when it could corrupt hidden topology. Examples include
deleting an instance referenced by an omitted interface connection, deleting a
boundary port used outside its internal design, or reducing a port width below
an existing connected slice. Symbolic IP-XACT part-selects cannot be represented
by the Circuit LSB/Width model and therefore make the projection unavailable
with an actionable diagnostic.

## Layout annotations

Saved visual state is stored as one `DesignCircuitLayoutV1` document per design
under `annotations/circuit-layout/` in the registered
`spec2gds.circuit-layout` namespace. Geometry is keyed by source instance,
port, boundary, and ad-hoc-connection names rather than generated Circuit IDs.
The annotation contains no SVG or PNG. Both the embedded preview and Circuit
Designer derive their rendering from the authoritative IP-XACT topology plus
this annotation.

Missing layout annotations are valid and use deterministic automatic layout.
Annotations are schema-versioned and validated for ownership, finite
coordinates, route references, and payload size as part of the package
transaction.

Timing metadata is stored separately under `annotations/circuit-timing/` in
the `spec2gds.circuit-timing` namespace. It uses the same semantic identity
rule as layout and is committed by the same atomic source transaction. See
[Circuit Designer timing stages](circuit-designer-timing-stages.md).
