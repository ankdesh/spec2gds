# ODT Container Samples

This directory contains small ODT files for manual and automated smoke testing.

## Layout

```text
raw/        Source ODT files before IP-XACT injection.
generated/  Hybrid ODT files with embedded sample IP-XACT.
ipxact/     Sample IP-XACT XML payloads.
```

## Sources

- `raw/unoconv_document_example.odt` is downloaded from the public unoconv test
  corpus:
  `https://raw.githubusercontent.com/unoconv/unoconv/master/tests/document-example.odt`
- `raw/odfdo_lpod_styles.odt` is copied from the downloaded `odfdo` package
  template when available in the local `uv` environment.
- `raw/synthetic_basic.odt` and `raw/synthetic_versioned_sections.odt` are
  generated locally by `build_sample_documents.py`.

## Rebuild

From the repository root:

```bash
UV_CACHE_DIR="$PWD/.uv-cache" \
UV_PYTHON_INSTALL_DIR="$PWD/.uv-python" \
uv run python -m spec2gds.spec.odt_container.samples.build_sample_documents
```

The builder injects `ipxact/sample_component.xml` into each raw ODT as:

```text
spec_data/ipxact/sample_component.xml
```

The sample IP-XACT component is schema-valid IEEE 1685-2014 XML. It describes a
small `sample_timer` component with one APB-style slave bus interface, an
abstraction reference, and logical-to-physical port maps for clock, reset,
address, write data, and read data signals.

Each generated document is verified with `ContainerVerifier` before the builder
prints its path.
