# IP-XACT 1685-2022 Protocol Rules

IP-XACT is the canonical structural hardware source in V1. Project models and
UI projections must preserve IEEE 1685-2022 semantics rather than inventing
fallback interpretations.

## Accepted Document Roots

- `component`
- `design`
- `busDefinition`
- `abstractionDefinition`

Each document requires a four-part VLNV and stable `xml:id`. The manifest kind,
VLNV, entity ID, path, and hash must agree with normalized XML content.

## Component Semantics

- Physical or transactional ports live under `model/ports`.
- Formal protocol interfaces live under `busInterfaces/busInterface`.
- A bus interface references a bus definition and optionally an abstraction
  definition through their VLNV attributes.
- Port maps connect logical protocol ports to physical component ports.
- Interface roles use the schema vocabulary represented by the actual XML.

Never display every physical port as a bus interface. A formal bus interface
exists only when `busInterfaces/busInterface` exists in canonical source.

## Design Semantics

- `componentInstances` reference component VLNVs.
- `interconnections` connect instance bus interfaces and optional hierarchy
  interfaces.
- `adHocConnections` connect internal instance ports and external design
  boundaries.
- Instance and connection names are unique within a design.
- Endpoints must resolve through the referenced component definitions.

The editor derives topology from this validated data. It does not own another
graph format.

## Project-Owned Relationships

The V1 manifest adds two explicit relationships outside the narrowed IP-XACT
document subset:

- entry-design selection;
- component-to-internal-design ownership.

Both use local stable entity references and participate in semantic validation.

## Validation Pipeline

1. Parse with external entities, DTD loading, and network access disabled.
2. Remove comments and processing instructions during normalization.
3. Canonicalize the IP-XACT namespace prefix and attribute order.
4. Validate against the bundled IEEE 1685-2022 schema set from
   `pyedaa-ipxact`.
5. Apply the narrower V1 allowlist/profile.
6. Project immutable SpecIR and validate cross-document semantics.

## V1 Profile Exclusions

V1 excludes implementation views, design configurations, abstractors,
generators, memory/register models, structured ports, power intent, vendor
extensions, and downstream implementation content. These require explicit
future profile revisions; unknown elements are not silently ignored.

## Fidelity Tests

Protocol tests must validate real IP-XACT XML and semantic endpoint resolution,
not project-specific JSON summaries. The deterministic V1 sample contains a bus
definition, abstraction definition, formal bus interfaces, ports, port maps,
instances, interface connections, and ad-hoc connections.

Historical converted XML in `benchmarks/agent_spec/hw_docs/converted/ipxact/`
is source corpus material, not automatically accepted V1 fixture data.
