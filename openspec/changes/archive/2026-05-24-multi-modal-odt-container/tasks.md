## 1. Implement IPXACTPlugin

- [x] 1.1 Create `spec2gds/spec/odt_container/ipxact_plugin.py`
  - Create the file and import only full namespaces (e.g., `import copy`, `import typing`, `import lxml.etree`, `import pyEDAA.IPXACT`).
  - Implement `class IPXACTPlugin` complying with `ModalityPlugin` protocol from `spec2gds/spec/odt_container/plugin.py`.
  - In `__init__`, initialize `config` as a `ModalityPluginConfig` with `modality_id="ipxact"`, `file_extensions=[".xml"]`, and `media_type="application/xml+ipxact"`.
  - Pre-declare `config` in the class body.
  - Make sure all parameters are treated as immutable and all functions have complete type annotations for Mojo-readiness.

- [x] 1.2 Implement Validation and XML Parsing
  - In `validate_data(self, data: typing.Any) -> bool`, ensure `data` is `bytes`.
  - Dynamically check the namespace of the XML `data` (IEEE 1685-2009 vs IEEE 1685-2014).
  - Use `pyEDAA.IPXACT` validation engine or `lxml.etree` validation using version-specific schemas to validate.
  - Return `True` on success, or raise standard exceptions on failure.

- [x] 1.3 Implement Injection and Extraction
  - In `inject_data(self, container_instance: container.HybridODTContainer, file_path: str, data: typing.Any) -> None`, ensure file extension `.xml` is present.
  - Call `validate_data` on `data` (XML bytes).
  - Call `container_instance.inject_file(f"spec_data/ipxact/{file_path}", data, self.config.media_type)`.
  - In `extract_data(self, container_instance: container.HybridODTContainer, file_path: str) -> typing.Any`, call `container_instance.extract_file(f"spec_data/ipxact/{file_path}")` to get XML bytes, parse them into a raw `pyEDAA.IPXACT` object tree, and return the tree.

- [x] 1.4 Implement Hybrid Path Resolution
  - In `resolve_path(self, container_instance: container.HybridODTContainer, file_path: str, node_path: str) -> typing.Any`:
  - Extract the parsed IP-XACT object tree.
  - Traverse logical paths by checking object attributes matching slash-separated components (e.g. `memoryMaps/AXI_Map/addressBlocks/Main`).
  - If logical resolution fails, fallback to standard XPath traversal via `lxml.etree` on the raw XML tree of the payload.
  - Raise `KeyError` if the node is not found in either the logical traversal or the XPath query.

## 2. Register Modality and Update CLI

- [x] 2.1 Register `IPXACTPlugin` in `spec2gds/spec/odt_container/__init__.py`
  - Import `spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin`
  - Expose `IPXACTPlugin = ipxact_plugin.IPXACTPlugin`

- [x] 2.2 Register and update XML injection logic in `spec2gds/spec/odt_container/cli.py`
  - Import `spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin`.
  - In `_build_default_manager()`, instantiate and register `ipxact_plugin.IPXACTPlugin()`.
  - In `main()` for the `inject` command, check if `args.modality == "ipxact"`. If so, skip `json.loads` and treat `payload` directly as raw bytes `raw_content.encode("utf-8")`.
  - In `main()` for the `extract` command, print the extracted IP-XACT XML contents (or write to file) if `args.modality == "ipxact"`, handling it as a string representation rather than JSON.

## 3. Testing

- [x] 3.1 Write Unit Tests for `IPXACTPlugin`
  - Create `tests/spec/odt_container/test_ipxact.py` matching the source structure.
  - Follow Mojo testing guidelines: module-scope zero-argument test functions returning `None`.
  - Provide valid and invalid IEEE 1685-2009 and 2014 XML fixtures to test namespace-dynamic validation.
  - Test logical and XPath hybrid resolution (e.g. URI `spec://ipxact/core.xml/memoryMaps/AXI_Map` or `spec://ipxact/core.xml/xpath/here`).
  - Use simple standard standard standard `assert` syntax.
