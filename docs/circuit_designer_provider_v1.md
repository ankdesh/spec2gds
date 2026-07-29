# Circuit Designer v1 Provider Boundary

Circuit Designer does not model IP-XACT wrappers, views, VLNVs, composition
records, or provider entity mappings. Provider-specific identifiers belong in
provider-owned sidecars.

Any component may resolve one shared child `CircuitDocument`.
`resolveComponentDesign(component_id)` returns an available document or an
unavailable result. Every child boundary terminal ID, direction, and width must
match the parent component definition. Resolution rejects hierarchy cycles.
Navigation from a dirty draft is blocked until Save or Cancel.

In-process hosts implement `ComponentDesignProvider`. The Node service can
register an HTTP callback base URL. It posts the component and resolution
context to `resolve`; writable providers may also implement `commit`. Provider
commit receives the base provider revision, normalized operation batch,
diagnostics, and final document. The provider's returned revision and normalized
document are authoritative.

Callback URLs are loopback-only by default. A non-loopback hostname must be in
the service allowlist or be explicitly enabled at registration. Production
deployments should add authentication at their hosting boundary; authentication
is not part of v1.

Provider-owned component updates must replace the definition and repair affected
instances/connectivity in one accepted operation or be rejected. Read-only
provider and built-in definitions cannot be edited by normal user operations.
