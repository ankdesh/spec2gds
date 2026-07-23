# Document Import Utility

`spec2gds-import-document` converts a Docling-supported source document into a
validated, deterministic V1 `.spec` package. It is an ingestion boundary, not a
replacement source format: the result uses the same typed narrative,
content-addressed assets, annotation registry, canonical IP-XACT documents, and
validation pipeline as every other V1 package.

## Install

The import stack is optional because Docling's PDF pipeline includes PyTorch and
document-analysis models:

```bash
uv sync --extra document-import
```

The project pins `torch` and `torchvision` to the official CPU wheel index so a
normal import setup does not pull several gigabytes of CUDA libraries. Teams
that require GPU processing should deliberately replace those `tool.uv`
sources with the accelerator-specific PyTorch index.

OpenDocument support is installed through
`docling-slim[format-opendocument]`. Legacy `.doc`, `.xls`, and `.ppt` parsing
also requires LibreOffice on the host. PDF layout/table models are downloaded
by Docling on first use.

Docling's current supported-format list is maintained in its
[official documentation](https://docling-project.github.io/docling/usage/supported_formats/).

## Offline Conversion

No API key is needed for the normal path:

```bash
uv run spec2gds-import-document docs/source.odt
uv run spec2gds-import-document docs/source.docx --output build/source.spec
uv run spec2gds-import-document docs/source.pdf --output build/source.spec
```

The default output is the input path with its extension replaced by `.spec`.
Existing output is protected unless `--force` is explicit. Use `--no-ocr` for
digitally generated PDFs where OCR is unnecessary, and `--image-scale` to
control PDF picture rendering resolution.

The importer projects content in Docling reading order:

- titles and section headers become nested `section` blocks;
- paragraphs and formulas/code text become `paragraph` blocks;
- consecutive list items become one typed `list`;
- tables become `table` blocks with string rows;
- extracted pictures become content-addressed PNG assets and `image` blocks.

The original input bytes are always retained at
`annotations/document_import/source.<extension>`. A deterministic
`import.json` records the source name, digest, Docling version, and annotation
path. This makes the generated narrative auditable against the exact input.

## Optional Table-to-IP-XACT Extraction

Use `--openai` to send the extracted tables—not the entire document binary—to
the OpenAI Responses API:

```bash
export OPENAI_API_KEY="..."
uv run spec2gds-import-document docs/timer.pdf \
  --output build/timer.spec \
  --openai \
  --vendor example.org \
  --library peripherals \
  --component-name timer \
  --component-version 1.0
```

The default is `gpt-5.6-sol`; override it with `--model`. The integration uses
`client.responses.parse(...)` with a Pydantic schema, low reasoning effort, and
`store=False`. OpenAI documents this typed Pydantic flow in its
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
and recommends the Responses API for direct model requests in the
[text-generation guide](https://developers.openai.com/api/docs/guides/text?api-mode=responses).

The extraction contract is deliberately narrow:

- return a port only when its name and direction are explicit;
- convert an explicit bit range to an integer width;
- create a bus interface only when protocol membership and
  initiator/target role are explicit;
- require every logical port map to resolve to a returned physical port;
- reject duplicate names, empty interfaces, unknown maps, and conflicting
  protocol directions before package creation.

Accepted results generate canonical IEEE 1685-2022 component, bus-definition,
and abstraction-definition documents. The result is then checked by the
project's XML schema, narrowed V1 profile, and cross-document SpecIR validator.
The structured API result and selected model are retained at
`annotations/document_import/openai-extraction.json`.

OpenAI enrichment is not deterministic across independent API calls. Once a
result is embedded, however, loading and re-saving that `.spec` package remains
byte deterministic.

## Command Options

```text
spec2gds-import-document INPUT
  [-o OUTPUT]
  [--openai]
  [--model MODEL]
  [--vendor VENDOR]
  [--library LIBRARY]
  [--component-name NAME]
  [--component-version VERSION]
  [--document-id ID]
  [--no-ocr]
  [--image-scale SCALE]
  [--force]
```

`--document-id` must follow the V1 XML-ID-compatible identifier grammar.
Without it, the utility derives a stable ID from the input filename.

## Python API and Hooks

The high-level API accepts an injected reader or enrichment provider:

```python
from pathlib import Path

from spec2gds.agent_spec.importers import (
    DoclingDocumentReader,
    DocumentImportOptions,
    DocumentToSpecConverter,
)

converter = DocumentToSpecConverter(
    reader=DoclingDocumentReader(ocr=True, image_scale=2.0),
)
result = converter.convert(
    Path("timer.odt"),
    Path("timer.spec"),
    options=DocumentImportOptions(
        vendor="example.org",
        library="peripherals",
        component_name="timer",
    ),
)
print(result.source_hash)
```

Subclass `DoclingDocumentReader` and override `handle_text_item`,
`handle_table_item`, or `handle_picture_item` to customize conversion at the
same hook points as the original prototype. Each hook returns the small
`ParsedText`, `ParsedTable`, or `ParsedImage` contract, which keeps Docling
types out of package-building code. `from_docling_document` also accepts an
already converted `DoclingDocument`.

For provider-independent tests, inject any object implementing
`HardwareTableEnricher`. This is how the OpenAI path is verified without making
network calls in the test suite.

## Verification

Run the importer tests:

```bash
uv run python -m pytest tests/agent_spec/importers -q
```

Validate any generated output through the existing package CLI:

```bash
uv run python -m spec2gds.agent_spec.spec_format.cli validate \
  --container build/timer.spec
```

The implementation has smoke coverage against actual DOCX, ODT, and PDF
inputs. The PDF corpus case produces headings, paragraphs, ten tables, and
eighteen extracted image assets before passing full V1 package validation.

## Current Limits

- API enrichment currently targets ports and formal bus interfaces. V1 itself
  excludes registers, memory maps, implementation views, and vendor extensions.
- Ambiguous table content remains narrative evidence and is not forced into
  IP-XACT.
- Old ODT-backed `.spec` containers are still rejected. Import the original
  document to a new path instead of treating it as a package migration.
- A live OpenAI call requires a user-provided `OPENAI_API_KEY`; the key is read
  by the official SDK and is never written into the package.
