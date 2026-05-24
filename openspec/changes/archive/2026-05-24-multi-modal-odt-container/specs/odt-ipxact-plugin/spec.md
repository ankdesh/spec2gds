## ADDED Requirements

### Requirement: IP-XACT Hybrid Node Resolution
The `IPXACTPlugin` SHALL resolve query paths using a Hybrid strategy, favoring logical paths based on `pyEDAA.IPXACT` object attributes while providing an XPath fallback.

#### Scenario: Querying a Logical Path
- **WHEN** the `node_path` matches an attribute hierarchy (e.g., `memoryMaps/AXI_Map`)
- **THEN** the plugin resolves the node against the parsed object model and returns the raw `pyEDAA.IPXACT` object.

#### Scenario: Missing Node
- **WHEN** the logical path does not exist and XPath fallback yields no results
- **THEN** the plugin SHALL raise a `KeyError` exception

### Requirement: IP-XACT Version Dispatching
The `IPXACTPlugin` SHALL transparently support both IEEE 1685-2009 and IEEE 1685-2014 by validating against the appropriate schema based on the XML namespace declaration.

#### Scenario: Validating IEEE 1685-2009
- **WHEN** the injected payload contains the IEEE 1685-2009 XML namespace
- **THEN** the plugin validates the payload against the 2009 schema without user intervention.
