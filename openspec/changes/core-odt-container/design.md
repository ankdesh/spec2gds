# Design: Hybrid ODT Container Infrastructure

This document outlines the technical architecture, design decisions, and implementation details for the `core-odt-container` change. It establishes a robust, extensible Python library and CLI for embedding, managing, and validating domain-specific structured data within OpenDocument Text (ODT) containers.

---

## Context

Hardware specifications (ASIC/SoC architectures) require rich visual representation for human readers (paragraphs, tables, styling) and strict machine-readable definitions (registers, ports, interfaces) for electronic design automation (EDA) tools. Historically, teams either used fragile text scraping on office documents or complex, hard-to-maintain docs-as-code formats.

The ODF (OpenDocument Format) standard, standardized globally as ISO/IEC 26300, is a ZIP archive containing discrete XML documents, multimedia, and configuration files. By utilizing the ODT container as a hybrid format, we can co-locate human-readable narrative and machine-readable data without losing compatibility with standard readers (like LibreOffice Writer).

This design creates the core infrastructure to manipulate ODT containers, establish a modular plugin system for custom data modalities, and implement a test JSON modality to validate the entire end-to-end flow.

---

## Goals / Non-Goals

**Goals:**
- Provide a robust, typed Python engine (`HybridODTContainer`) built on `odfdo` to safely inject, extract, and delete custom data files inside ODT zip packages.
- Implement synchronous registration and preservation of all embedded files in `META-INF/manifest.xml` to prevent standard editors (LibreOffice) from stripping custom files during save actions.
- Establish a flexible, loosely coupled `ModalityPlugin` and `PluginManager` architecture to route custom semantic links and manage modality lifecycles.
- Implement a concrete `SimpleJSONPlugin` for embedding and parsing basic structured JSON structures as a baseline modality.
- Build a headless CLI to perform container operations, inject/extract payloads, and validate custom links and schemas.
- Enforce strict schemas utilizing **Pydantic** and **dataclasses** for validation and metadata representation.
- **Mojo-Readiness Assurance**: Ensure the entire Python codebase conforms strictly to the project's Mojo-readiness coding standards (strict type-locking, value copy semantics, composition over inheritance, sequential try blocks, entire namespace imports, module-scope unit testing) to facilitate seamless future compilation.

**Non-Goals:**
- **No IP-XACT Integration**: The complex IEEE 1685 (IP-XACT) parser and integration are explicitly deferred to a separate proposal and change.
- **No GUI Editor/Viewer**: This implementation is strictly headless (CLI/API). High-level desktop Qt viewers or split-pane editors are out of scope.
- **No Native ODF Styling Modification**: We do not aim to build tools to visually style the ODT document itself; we only handle text hyperlinks (`<text:a>`) and ZIP archive manipulation.

---

## Architecture Overview

The system uses a layered architecture to isolate the underlying ODT ZIP manipulation from the domain-specific modality logic.

```mermaid
graph TD
    CLI[Headless CLI] --> |Invokes| PM[PluginManager]
    CLI --> |Reads/Writes| HC[HybridODTContainer]
    PM --> |Coordinates| HC
    PM --> |Loads & Delegates| MP[ModalityPlugin Base]
    MP <|-- SP[SimpleJSONPlugin]
    HC --> |Uses| Odfdo[odfdo Library]
    HC --> |Uses| Lxml[lxml XML Parser]
    
    subgraph ODT Archive Zip Structure
        Mimetype[mimetype]
        ContentXML[content.xml]
        Manifest[META-INF/manifest.xml]
        SpecData[spec_data/ - Custom Files]
    end
    HC -.-> ODT Archive Zip Structure
```

### ODT Archive Folder Layout
Inside the hybrid ODT file (which is physically a ZIP), we establish a structured workspace:
```
odt_archive.odt/
├── mimetype (uncompressed magic number)
├── content.xml (narrative rich text + spec:// links)
├── META-INF/
│   └── manifest.xml (registered files metadata)
└── spec_data/
    └── <modality_id>/
        └── <file_path> (raw structured files, e.g., registers.json)
```

---

## Decisions

### 1. File Encapsulation and Manifest Preservation
- **Choice**: Encapsulate custom data in a dedicated sub-directory (`spec_data/`) and synchronously register every file in `META-INF/manifest.xml` using a custom media-type.
- **Alternatives Considered**: 
  1. *Inline XML namespace injection in `content.xml`*: Rejected because standard word processors (LibreOffice) load documents into internal memory structures and strip out unknown XML tags when the document is edited and saved.
  2. *RDF Metadata (`manifest.rdf`)*: Rejected due to high nesting complexity of hardware specs and vulnerability to privacy-clearing utilities in standard editors.
- **Rationale**: Standard editors ignore files with unknown media-types (e.g. `application/x-spec-json` or `application/json`) but preserve them *only if* they are registered in the manifest. If they are unregistered, editors treat them as corruption and delete them.

### 2. Low-Level XML Manipulation Layer
- **Choice**: Use the highly optimized C-backed `lxml` library for parsing and modifying `META-INF/manifest.xml` and extracting links from `content.xml`.
- **Alternatives Considered**: 
  1. *Python's built-in `xml.etree.ElementTree`*: Rejected due to poor namespace preservation, lack of XPath 1.0 support, and unstable element ordering.
- **Rationale**: `lxml` supports precise, high-performance XPath lookups and preserves exact namespaces, which is critical for making surgical changes to ODF XML structures without corrupting them.

### 3. XML/Zip Bridge Integration
- **Choice**: Inherit and bridge `odfdo.Document` using a custom wrapper (`HybridODTContainer`) that manages both high-level ODT constructs (via `odfdo`) and raw ZIP streams (via standard `zipfile` with `mimetype` preservation).
- **Rationale**: `odfdo` is highly pythonic and actively maintained, making it ideal for interacting with document objects. However, we must augment it with custom low-level ZIP manipulation to handle byte-accurate mimetype injection (uncompressed, byte-offset 30) and direct `spec_data/` file management.

### 4. Custom URI Scheme for Cross-Linking
- **Choice**: Use standard ODT hyperlinks (`<text:a>`) pointing to custom URIs with the syntax:
  `spec://<modality_id>/<file_path>/<node_path>`
- **Example**: `<text:a xlink:href="spec://simple-json/registers.json/block/0/name">Control Register</text:a>`
- **Rationale**: standard editors will render this as a clickable hyperlink. In standard tools, clicking it will gracefully degrade (doing nothing or showing a protocol error), while our custom toolchain can parse it, fetch the modality plugin, load `registers.json`, and run a programmatic extraction/validation step.

### 5. Architectural Alignment for Mojo Compatibility
- **Choice**: Structure the entire package and its component code to anticipate Mojo struct, trait, and memory layouts:
  - *No Concrete Subclassing*: Implement `ModalityPlugin` strictly as a Python `Protocol` or basic abstract interface class (`abc.ABC`). The concrete plugins (e.g. `SimpleJSONPlugin`) implement this interface using composition.
  - *Strict Type-Locking and Nullability*: All classes pre-declare their fields inside the class body, with mandatory constructor initialization. Explicit `Optional[T]` annotations are used to facilitate future compile-time null-safety checks.
  - *Explicit Deep Copies*: The data parsed from files is cloned/copied explicitly before returned from the extract API to align with Mojo's default value semantics.
  - *Isolated exception handling*: Error management routines in `HybridODTContainer` parse processes in separate, sequential `try-except` blocks.
- **Rationale**: Enforcing these constraints at the Python architecture level ensures that the codebase can be ported to Mojo without requiring major component restructuring or logic rewrites.

---

## Data Schemas

Per project rules, all configurations, verification results, and core representations are represented using Pydantic models.

### Modality Plugin Configuration Schema
```python
from pydantic import BaseModel, Field

class ModalityPluginConfig(BaseModel):
    modality_id: str = Field(..., description="Unique alphanumeric identifier of the modality")
    file_extensions: list[str] = Field(..., description="List of supported file extensions (e.g., ['.json'])")
    media_type: str = Field(..., description="Standard or custom media-type registered in the manifest")
```

### Link Resolution Schema
```python
from pydantic import BaseModel
from typing import Any

class LinkResolutionResult(BaseModel):
    uri: str
    modality_id: str
    file_path: str
    node_path: str
    resolved_value: Any
    is_valid: bool
    error_message: str | None = None
```

### Container Verification Summary
```python
from pydantic import BaseModel
from datetime import datetime

class FileVerification(BaseModel):
    file_path: str
    media_type: str
    is_registered: bool
    is_valid: bool
    error_message: str | None = None

class LinkVerification(BaseModel):
    anchor_text: str
    uri: str
    is_valid: bool
    error_message: str | None = None

class ContainerVerificationReport(BaseModel):
    container_path: str
    timestamp: datetime
    files: list[FileVerification]
    links: list[LinkVerification]
    is_fully_consistent: bool
```

---

## Risks / Trade-offs

- **[Risk] Editor Auto-Formatting & Link Destruction** → When an engineer changes text in LibreOffice, they might break the text formatting or split the `<text:a>` tags into fragmented XML child nodes.
  - *Mitigation*: Our validation engine parses the XML tree, normalizes adjacent text elements, and runs syntactic/referential integrity checks across all custom hyperlinks to warn developers of structural anomalies.
- **[Risk] Namespace Corruption in `manifest.xml`** → Hand-writing manifest XML nodes can corrupt the namespace declarations (`xmlns:manifest=...`).
  - *Mitigation*: All edits to `META-INF/manifest.xml` are routed through a robust XML helper utilizing `lxml` that validates namespaces and checks schema compliance before saving.
- **[Risk] Mimetype Byte-Offset Corruption** → Modifying the ZIP archive via standard Python `zipfile` calls can sometimes compress or re-order the `mimetype` file, making standard OS file association systems fail.
  - *Mitigation*: The `HybridODTContainer.save()` method forces the `mimetype` file to be written as the absolute first, uncompressed entry in the ZIP stream.

---

## Migration & Deployment Plan

Since this is the baseline framework:
1. **Developer Bootstrap**: All core code will be written in Python. Installing the `spec2gds` package will expose the library and standard CLI wrapper.
2. **Backward Compatibility**: Any legacy standard ODT file can be processed by `HybridODTContainer`; it will simply identify 0 registered plugins, 0 custom files, and 0 links. It will instantly upgrade the ODT structure when the first custom payload is injected.
3. **Rollback Strategy**: The Python CLI will always make atomic backup saves (e.g. saving to `.tmp` first, then renaming) so if any step fails, the original ODT file remains intact.
