"""Acceptance tests for Docling document-to-``.spec`` imports."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest

from spec2gds.agent_spec.importers.cli import main
from spec2gds.agent_spec.importers.docling_reader import (
    DoclingDocumentReader,
    ParsedDocument,
    ParsedImage,
    ParsedTable,
    ParsedText,
    _has_ancestor,
)
from spec2gds.agent_spec.importers.document import (
    DocumentImportOptions,
    DocumentToSpecConverter,
)
from spec2gds.agent_spec.importers.ipxact_from_tables import (
    ExtractedBusInterface,
    ExtractedPort,
    ExtractedPortMap,
    HardwareTableExtraction,
    OpenAIHardwareTableEnricher,
)
from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.ir import SpecRevision


_PNG = b"\x89PNG\r\n\x1a\nimported-image"


def _parsed_document() -> ParsedDocument:
    return ParsedDocument(
        title="Timer Peripheral",
        items=(
            ParsedText("Timer Peripheral", "title", 0, "title"),
            ParsedText("Overview", "section", 1, "section_header"),
            ParsedText("A programmable timer.", "paragraph", 2, "paragraph"),
            ParsedText("One-shot mode", "list_item", 2, "list_item"),
            ParsedText("Periodic mode", "list_item", 2, "list_item"),
            ParsedTable(
                rows=(
                    ("Signal", "Direction", "Width", "Protocol"),
                    ("PCLK", "input", "1", "APB target"),
                    ("PADDR", "input", "32", "APB target"),
                    ("PRDATA", "output", "32", "APB target"),
                ),
                level=2,
            ),
            ParsedImage(_PNG, 2, caption="Timer block", alt_text="Timer block diagram"),
        ),
    )


def _extraction() -> HardwareTableExtraction:
    return HardwareTableExtraction(
        component_name="timer",
        ports=[
            ExtractedPort(name="PCLK", direction="in"),
            ExtractedPort(name="PADDR", direction="in", width=32),
            ExtractedPort(name="PRDATA", direction="out", width=32),
        ],
        bus_interfaces=[
            ExtractedBusInterface(
                name="apb_target",
                bus_name="apb",
                role="target",
                port_maps=[
                    ExtractedPortMap(logical_port="PCLK", physical_port="PCLK"),
                    ExtractedPortMap(logical_port="PADDR", physical_port="PADDR"),
                    ExtractedPortMap(logical_port="PRDATA", physical_port="PRDATA"),
                ],
            )
        ],
    )


class _FakeEnricher:
    model = "test-model"

    def __init__(self, extraction: HardwareTableExtraction) -> None:
        self.extraction = extraction
        self.calls: list[tuple[object, str]] = []

    def extract(self, tables, *, document_title: str) -> HardwareTableExtraction:
        self.calls.append((tables, document_title))
        return self.extraction


def _walk(blocks):
    for block in blocks:
        yield block
        yield from _walk(block.children)


def test_offline_import_preserves_narrative_assets_and_source(tmp_path: Path) -> None:
    source = tmp_path / "timer.odt"
    source.write_bytes(b"ODT source evidence")
    converter = DocumentToSpecConverter()

    first, extraction, table_count, image_count = converter.build_package(
        _parsed_document(),
        input_path=source,
    )
    second, _, _, _ = converter.build_package(_parsed_document(), input_path=source)
    output = tmp_path / "timer.spec"
    first.save(str(output))
    loaded = SpecPackage.load(str(output))
    blocks = list(_walk(loaded.narrative.blocks))

    assert extraction is None
    assert table_count == 1
    assert image_count == 1
    assert first.source_hash() == second.source_hash()
    assert {block.type for block in blocks} >= {
        "section",
        "paragraph",
        "list",
        "table",
        "image",
    }
    assert loaded.files["annotations/document_import/source.odt"] == b"ODT source evidence"
    metadata = json.loads(loaded.files["annotations/document_import/import.json"])
    assert metadata["source_name"] == "timer.odt"
    assert metadata["source_sha256"].startswith("sha256:")
    assert loaded.manifest.documents == []
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist()[0] == "mimetype"


def test_table_enrichment_adds_valid_ipxact_component_and_protocol(tmp_path: Path) -> None:
    source = tmp_path / "timer.pdf"
    source.write_bytes(b"%PDF-source-evidence")
    enricher = _FakeEnricher(_extraction())
    converter = DocumentToSpecConverter(enricher=enricher)

    package, extraction, _, _ = converter.build_package(
        _parsed_document(),
        input_path=source,
        options=DocumentImportOptions(
            vendor="example.org",
            library="peripherals",
            component_name="timer_override",
            component_version="2.0",
        ),
    )
    revision = SpecRevision.from_package(package)
    blocks = list(_walk(package.narrative.blocks))

    assert extraction is not None
    assert enricher.calls[0][1] == "Timer Peripheral"
    assert {entry.kind for entry in package.manifest.documents} == {
        "component",
        "bus_definition",
        "abstraction_definition",
    }
    assert [port.name for port in revision.components[0].ports] == ["PCLK", "PADDR", "PRDATA"]
    assert revision.components[0].interfaces[0].name == "apb_target"
    assert revision.components[0].interfaces[0].role == "target"
    assert any(block.type == "entity_link" for block in blocks)
    audit = json.loads(package.files["annotations/document_import/openai-extraction.json"])
    assert audit["model"] == "test-model"
    component_xml = next(
        package.files[entry.path]
        for entry in package.manifest.documents
        if entry.kind == "component"
    )
    assert b"<ipxact:left>31</ipxact:left>" in component_xml
    assert b"<ipxact:name>timer_override</ipxact:name>" in component_xml


def test_openai_enricher_uses_responses_structured_outputs() -> None:
    class FakeResponses:
        def __init__(self) -> None:
            self.kwargs = {}

        def parse(self, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(output_parsed=_extraction())

    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    enricher = OpenAIHardwareTableEnricher(model="gpt-test", client=client)

    result = enricher.extract(
        [[["Signal", "Direction"], ["PCLK", "input"]]],
        document_title="Timer",
    )

    assert result.ports[0].name == "PCLK"
    assert responses.kwargs["model"] == "gpt-test"
    assert responses.kwargs["reasoning"] == {"effort": "low"}
    assert responses.kwargs["store"] is False
    assert responses.kwargs["text_format"] is HardwareTableExtraction
    assert "table_0001" in responses.kwargs["input"][1]["content"]


def test_unresolved_interface_port_map_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "bad.docx"
    source.write_bytes(b"docx evidence")
    extraction = _extraction().model_copy(
        update={
            "bus_interfaces": [
                ExtractedBusInterface(
                    name="apb",
                    bus_name="apb",
                    role="target",
                    port_maps=[
                        ExtractedPortMap(logical_port="PSEL", physical_port="missing_port")
                    ],
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="unknown physical ports"):
        DocumentToSpecConverter(enricher=_FakeEnricher(extraction)).build_package(
            _parsed_document(),
            input_path=source,
        )


def test_docling_reader_hooks_normalize_items() -> None:
    class FakeFrame:
        columns = (" Signal ", "Direction")

        @staticmethod
        def itertuples(*, index: bool, name):
            assert index is False
            assert name is None
            return iter([(" PCLK ", " input ")])

    class FakeTable:
        @staticmethod
        def export_to_dataframe(*, doc):
            assert doc == "document"
            return FakeFrame()

    class FakeImageData:
        @staticmethod
        def save(buffer, *, format: str):
            assert format == "PNG"
            buffer.write(_PNG)

    class FakePicture:
        @staticmethod
        def get_image(document):
            assert document == "document"
            return FakeImageData()

        @staticmethod
        def caption_text(*, doc):
            assert doc == "document"
            return " Timer diagram "

    reader = DoclingDocumentReader()
    text = reader.handle_text_item(
        SimpleNamespace(text="  Port list  ", label=SimpleNamespace(value="section_header")),
        1,
    )
    table = reader.handle_table_item(FakeTable(), "document", 2)
    image = reader.handle_picture_item(FakePicture(), "document", 2)

    assert text == ParsedText("Port list", "section", 1, "section_header")
    assert table == ParsedTable((("Signal", "Direction"), ("PCLK", "input")), 2)
    assert image == ParsedImage(_PNG, 2, "Timer diagram", "Timer diagram")


def test_docling_reader_detects_text_nested_inside_a_table() -> None:
    class FakeTable:
        parent = None

    table = FakeTable()
    group = SimpleNamespace(parent=SimpleNamespace(cref="#/table"))
    resolved = {
        "#/group": group,
        "#/table": table,
    }

    class Ref:
        def __init__(self, cref: str) -> None:
            self.cref = cref

        def resolve(self, document):
            assert document == "document"
            return resolved[self.cref]

    group.parent = Ref("#/table")
    text = SimpleNamespace(parent=Ref("#/group"))

    assert _has_ancestor(text, "document", FakeTable)


def test_cli_converts_with_an_injected_docling_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "timer.odt"
    source.write_bytes(b"source")
    output = tmp_path / "result.spec"
    monkeypatch.setattr(
        DoclingDocumentReader,
        "convert",
        lambda self, input_path: _parsed_document(),
    )

    assert main([str(source), "--output", str(output)]) == 0
    report = json.loads(capsys.readouterr().out)

    assert report["output_path"] == str(output)
    assert report["table_count"] == 1
    assert report["port_count"] == 0
    assert SpecPackage.load(str(output)).diagnostics() == []
