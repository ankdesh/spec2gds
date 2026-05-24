## Context

The system requires a hybrid documentation format where subject matter experts can write rich text using standard word processors (like LibreOffice Writer using ODT) while simultaneously embedding strict, machine-readable hardware data (like IP-XACT). The `spec2gds` project needs to extract this data to drive code generation and downstream EDA toolchains.

The constraints mandate that these data files survive edit cycles in standard office tools without corruption, which requires strictly adhering to the OpenDocument Format manifest rules. Additionally, the project intends to migrate to Mojo in the future, so the design must adhere to strict type-locking and explicit error flows.

## Goals / Non-Goals

**Goals:**
- Provide a headless Python API and CLI tool to inject and extract custom hardware data within `.odt` archives.
- Ensure that the injected files are preserved when the `.odt` file is edited and saved by standard office suites (LibreOffice).
- Create an extensible plugin architecture to support various modalities (e.g., IP-XACT).
- Provide a URI scheme (`spec://<modality>/<file_path>/<node>`) to robustly link narrative text to data nodes.
- Maintain a Mojo-ready architecture (strict types, specific exceptions).

**Non-Goals:**
- Creating a GUI for the ODT container management (only CLI and headless API).
- Mapping complex IP-XACT data structures to a custom Pydantic model (we will use `pyEDAA.IPXACT` raw objects instead).

## Decisions

1. **Modality Versioning (IP-XACT)**
   - *Decision:* Dynamically support both IEEE 1685-2009 and IEEE 1685-2014 standards using `pyEDAA.IPXACT`'s version-specific schema validation based on the XML namespace declaration.
   - *Rationale:* Abstracts away version differences, allowing users to embed either format without manual configuration.

2. **URI Path Resolution Strategy**
   - *Decision:* Implement a **Hybrid Approach** for URI node resolution. Primary resolution uses strict logical paths mapping to object attributes (e.g., `memoryMaps/AXI_Map`), falling back to XPath for complex XML selections.
   - *Rationale:* Logical paths are ideal for Custom UIs and code generators (SystemC/RTL) compared to brittle XPaths, while the fallback ensures we don't lose the native querying power of XML.

3. **Internal ZIP Storage Layout**
   - *Decision:* Store injected data in a namespaced directory structure: `spec_data/<modality_id>/<file_path>`.
   - *Rationale:* Aligns with the already implemented `HybridODTContainer` ZIP rules and completely eliminates any risk of file naming collisions if multiple modalities happen to inject files with the same name (e.g., `core.xml`).

4. **Error Handling & Mojo Readiness**
   - *Decision:* Use standard exceptions like `KeyError`, `ValueError`, and type-specific validations rather than custom complex schemas. The code relies on explicit error checking conforming to standard Python error hierarchies to remain compatible with standard tooling while being ready for value copy semantics.

5. **Manifest Injection Strategy**
   - *Decision:* Update `META-INF/manifest.xml` to assign custom media types (e.g., `application/xml+ipxact` or `application/x-spec-json`) immediately upon file injection via the `odfdo` library inside `HybridODTContainer`.
   - *Rationale:* Ensures office editors preserve the injected payload.

## Risks / Trade-offs

- **[Risk] Office Suite Stripping Unrecognized Data** → **Mitigation**: Thorough testing across LibreOffice versions to ensure that correctly registered `META-INF/manifest.xml` entries guarantee preservation of `spec_data/` directories.
- **[Risk] XPath Brittle to Namespaces** → **Mitigation**: The Hybrid Path Resolution prefers logical object mapping over raw XPath, isolating the user from underlying IEEE standard namespace shifts.
