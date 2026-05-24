# odt-container-api Specification

## Purpose
TBD - created by archiving change multi-modal-odt-container. Update Purpose after archive.
## Requirements
### Requirement: ODT Plugin Registry and Routing
The `PluginManager` SHALL route URIs formatted as `spec://<modality_id>/<file_path>/<node_path>` to the appropriate registered `ModalityPlugin`.

#### Scenario: Valid URI routing
- **WHEN** a valid URI is parsed by the PluginManager
- **THEN** the manager delegates the extraction to the correct modality plugin

#### Scenario: Unregistered Modality
- **WHEN** a URI specifies an unregistered modality
- **THEN** the manager SHALL raise a `KeyError` exception

### Requirement: ODF Manifest Injection
The `HybridODTContainer` SHALL inject files into the `.odt` ZIP archive using a namespaced layout (`spec_data/<modality_id>/<file_path>`) and synchronously register the custom MIME type in `META-INF/manifest.xml`.

#### Scenario: Injecting a raw data payload
- **WHEN** a payload is injected for a modality
- **THEN** the payload is saved in the `spec_data/<modality_id>/<file_path>` path and the manifest is updated to prevent data stripping.

