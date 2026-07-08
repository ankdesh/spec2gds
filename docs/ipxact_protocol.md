# IP-XACT Protocol Rules

This project treats IP-XACT as an external standard, not as a loose internal
shape. Agent-spec may embed, attach, preview, and edit IP-XACT payloads, but it
must not redefine IP-XACT semantics for UI convenience.

## Standard

- Use IEEE 1685 IP-XACT XML for hardware component payloads.
- Current benchmark XML targets the 1685-2014 namespace:
  `http://www.accellera.org/XMLSchema/IPXACT/1685-2014`.
- Validate benchmark and generated IP-XACT payloads with the project IP-XACT
  plugin, which uses pyEDAA.IPXACT schema validation.

## Archive Storage

- Store embedded IP-XACT payloads under `spec_data/ipxact/`.
- Register embedded payloads with media type `application/xml+ipxact`.
- Attach an embedded payload to document headings through editor relations,
  not by changing the meaning of the XML payload.

## Component Ports

- Physical component signals belong under `ipxact:model/ipxact:ports`.
- `model/ports` entries are not bus interfaces.
- Do not display or persist `model/ports` as a synthetic bus interface.

## Bus Interfaces

- Bus interfaces must be represented by formal
  `ipxact:busInterfaces/ipxact:busInterface` records.
- A bus interface should include:
  - `ipxact:name`
  - `ipxact:busType`
  - `ipxact:abstractionTypes/ipxact:abstractionType`
  - `ipxact:abstractionRef`
  - `ipxact:portMaps`
  - an interface mode such as `ipxact:slave`
- Port maps should relate logical bus signal names to physical component port
  names through `logicalPort/name` and `physicalPort/name`.

## Editor Behavior

- The editor summary may be namespace-tolerant and lightweight, but it must
  preserve protocol meaning.
- If no formal bus interfaces exist, report a diagnostic instead of inventing
  one from component ports.
- Saves and imports should prefer explicit errors or diagnostics over silent
  fallback behavior.

## Benchmark Policy

- PDF and HTML benchmark inputs are ground truth.
- Converted ODT/XML and generated `.spec` files may be regenerated to keep the
  benchmark loadable and protocol-correct.
- Benchmark XML must validate as IP-XACT and expose formal bus interfaces.
- Tests should fail if a benchmark relies on a project-specific reinterpretation
  of IP-XACT.
