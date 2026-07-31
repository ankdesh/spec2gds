# Circuit Designer v1 Provider Boundary

Circuit Designer does not model IP-XACT wrappers, views, VLNVs, composition
records, or provider entity mappings. Provider-specific identifiers and
sidecars belong to the provider.

## Resolution model

Any component may resolve one shared child `CircuitDocument`.
`resolveComponentDesign(component_id)` returns an available document or an
unavailable result. Every child boundary terminal ID, direction, and width must
match the parent component definition. Resolution rejects hierarchy cycles.
Navigation from a dirty browser draft is blocked until Save or Cancel.

Every instance of the same component resolves the same child design in v1.
Per-instance implementation overrides are not supported.

## In-process and HTTP providers

A Node host may inject a `ComponentDesignProvider` directly. External systems
register an HTTP callback base URL with:

```text
PUT /api/circuit-designer/v1/documents/{document_id}/provider
```

The registration applies only to that active parent-document session and
disappears when the service restarts.

The service calls:

```text
POST {callback_base}/resolve
POST {callback_base}/commit
```

Resolution receives the component definition and parent/ancestry context. It
returns unavailable or an available child document, provider revision, and
writable capability.

Writable commit receives:

- the component definition;
- base provider revision;
- structured `CircuitOperationBatch`;
- final child `CircuitDocument`;
- diagnostics.

The provider validates and durably persists the child according to its own
rules. Its accepted provider revision and returned normalized document become
canonical for the resolved child. The Circuit Designer service does not store a
durable copy.

## Safety and ownership

Callback URLs are loopback-only by default. A non-loopback hostname must be
allowlisted by the host or explicitly enabled at registration. The reference
service is unauthenticated; production authentication belongs at the hosting
boundary and is outside v1.

Provider-owned component definitions are read-only to normal user operations.
A provider-owned definition update must repair every affected instance and
connection in one accepted atomic change or be rejected.

The future SpecIR/IP-XACT translator may implement this provider contract, but
provider IDs and IP-XACT entity mappings remain in translator-owned sidecars,
never in portable circuit JSON.
