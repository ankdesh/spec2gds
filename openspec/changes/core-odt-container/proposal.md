## Why
Standard hardware documentation tools either focus heavily on human readability (WYSIWYG editors) or machine readability (docs-as-code), but rarely both. To solve this, we are building a hybrid container format based on the OpenDocument Format (ODT) that allows rich text narrative to coexist with strict, embedded data structures. This change focuses on building the foundational infrastructure to embed, manage, and test a simple custom data modality within an ODT archive, acting as a stepping stone for more complex plugins like IP-XACT in the future.

## What Changes
- Build the `HybridODTContainer` using `odfdo` to handle zip structure management and `META-INF/manifest.xml` registration.
- Create a `ModalityPlugin` architecture to easily add new data handlers.
- Create a `PluginManager` to route custom URIs (e.g., `spec://<modality>/...`) to the correct plugin.
- Implement a `SimpleJSONPlugin` as a test modality to prove the infrastructure works end-to-end without introducing complex external dependencies.
- Build a headless CLI to inject and validate simple JSON payloads within an ODT container.

## Capabilities

### New Capabilities
- `odt-container-core`: The base infrastructure for manipulating ODT files, registering embedded data, and the plugin registry.
- `odt-simple-json-plugin`: A basic plugin for embedding and validating JSON structures, serving as the first test case for the container architecture.

### Modified Capabilities

## Impact
- **Code**: Adds the foundational `odt_container` package under `spec2gds/spec/`.
- **Dependencies**: Introduces `odfdo` as a core dependency for ODF manipulation.
- **Workflow**: Establishes the pattern for how future modalities (like IP-XACT or SystemRDL) will be plugged into the ODT container ecosystem.
