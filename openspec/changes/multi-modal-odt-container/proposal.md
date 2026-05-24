## Why
Standard hardware documentation often forces a compromise between human readability (WYSIWYG editors) and machine readability (docs-as-code). The project requires a hybrid solution that allows subject matter experts to document hardware designs using rich text in the OpenDocument Format (ODT) while preserving strict machine-readable definitions (e.g., IP-XACT) natively within the same file. This enables a single source of truth for both documentation and downstream EDA toolchains without data loss when edited in standard office suites like LibreOffice.

## What Changes
- Introduce a new headless Python API and CLI tool within the `spec` submodule for extending ODT archives.
- Implement an ODT container manager (`HybridODTContainer`) utilizing `odfdo` to register custom directories in `META-INF/manifest.xml`.
- Implement a plugin architecture (`ModalityPlugin`) for handling different data schemas.
- Introduce the first plugin: `IPXACTPlugin`, utilizing `pyEDAA.IPXACT` for strict validation and data extraction.
- Introduce a custom generic URI scheme (`spec://<modality>/<path>/<node>`) within ODT `<text:a>` tags to allow semantic cross-linking between narrative text and embedded data.

## Capabilities

### New Capabilities
- `odt-container-api`: The core ODT manipulation, manifest registration, and plugin registry framework.
- `odt-ipxact-plugin`: The specific plugin for embedding, validating, and extracting IP-XACT IEEE 1685 data using `pyEDAA.IPXACT`.

### Modified Capabilities

## Impact
- **Code:** Adds a new `odt_container` package under `spec2gds/spec/`.
- **Dependencies:** Introduces `odfdo` (for ODF ZIP/XML manipulation) and `pyEDAA.IPXACT` (for schema validation).
- **Workflow:** Allows users to package IP-XACT data securely inside `.odt` files, which can be shared and edited in LibreOffice without destroying the hardware metadata.
