"""Adapt Docling's document tree to a small, stable importer contract."""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
from typing import Literal


TextKind = Literal["title", "section", "paragraph", "list_item"]


@dataclass(frozen=True)
class ParsedText:
    """One text node in Docling reading order."""

    text: str
    kind: TextKind
    level: int
    label: str = ""


@dataclass(frozen=True)
class ParsedTable:
    """One table represented as display-ready string rows."""

    rows: tuple[tuple[str, ...], ...]
    level: int


@dataclass(frozen=True)
class ParsedImage:
    """One extracted PNG image and its authored labels."""

    data: bytes
    level: int
    caption: str = ""
    alt_text: str = ""


ParsedItem = ParsedText | ParsedTable | ParsedImage


@dataclass(frozen=True)
class ParsedDocument:
    """The importer-facing result of one Docling conversion."""

    title: str
    items: tuple[ParsedItem, ...]


def _clean_cell(value: object) -> str:
    """Return stable display text for a DataFrame cell without importing pandas."""
    if value is None:
        return ""
    try:
        if value != value:  # NaN and pandas NA-like values.
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(value).split())


def _label_value(label: object) -> str:
    """Normalize Docling enum labels across compatible releases."""
    value = getattr(label, "value", label)
    return str(value).rsplit(".", 1)[-1].lower()


def _has_ancestor(item: object, document: object, ancestor_type: type) -> bool:
    """Return whether a Docling item's resolved parent chain has one type."""
    parent = getattr(item, "parent", None)
    seen: set[str] = set()
    while parent is not None:
        reference = str(getattr(parent, "cref", parent))
        if reference in seen:
            return False
        seen.add(reference)
        resolve = getattr(parent, "resolve", None)
        if not callable(resolve):
            return False
        resolved = resolve(document)
        if isinstance(resolved, ancestor_type):
            return True
        parent = getattr(resolved, "parent", None)
    return False


class DoclingDocumentReader:
    """Run Docling and expose overridable hooks for text, tables, and pictures."""

    def __init__(self, *, ocr: bool = True, image_scale: float = 2.0) -> None:
        if image_scale <= 0:
            raise ValueError("image_scale must be greater than zero.")
        self.ocr = ocr
        self.image_scale = image_scale

    def create_converter(self):
        """Create the configured Docling converter.

        Imports are intentionally lazy so package inspection and ``--help`` do
        not initialize Docling's model stack.
        """
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Docling is not installed. Run `uv sync --extra document-import`."
            ) from exc

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = self.ocr
        pdf_options.do_table_structure = True
        pdf_options.generate_picture_images = True
        pdf_options.images_scale = self.image_scale
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
            }
        )

    def convert(self, input_path: Path) -> ParsedDocument:
        """Parse one Docling-supported local file."""
        result = self.create_converter().convert(input_path)
        return self.from_docling_document(result.document, fallback_title=input_path.stem)

    def from_docling_document(self, document: object, *, fallback_title: str) -> ParsedDocument:
        """Traverse an existing ``DoclingDocument`` in reading order."""
        from docling_core.types.doc import PictureItem, TableItem, TextItem

        items: list[ParsedItem] = []
        title = " ".join(fallback_title.replace("_", " ").split()) or "Imported document"
        title_seen = False
        iterator = document.iterate_items(with_groups=True, traverse_pictures=False)
        for item, level in iterator:
            parsed: ParsedItem | None = None
            if isinstance(item, TextItem):
                # ODF backends expose table-cell text both through the table's
                # DataFrame export and as nested TextItems. Keep the table as
                # the single source representation instead of duplicating it.
                if _has_ancestor(item, document, TableItem):
                    continue
                parsed = self.handle_text_item(item, int(level))
                if parsed is not None and parsed.kind == "title" and not title_seen:
                    title = parsed.text
                    title_seen = True
            elif isinstance(item, TableItem):
                parsed = self.handle_table_item(item, document, int(level))
            elif isinstance(item, PictureItem):
                parsed = self.handle_picture_item(item, document, int(level))
            if parsed is not None:
                items.append(parsed)
        if not title_seen:
            first_text_index = next(
                (index for index, item in enumerate(items) if isinstance(item, ParsedText)),
                None,
            )
            if first_text_index is not None:
                first_text = items[first_text_index]
                if isinstance(first_text, ParsedText) and first_text.kind == "section":
                    title = first_text.text
                    items[first_text_index] = ParsedText(
                        text=first_text.text,
                        kind="title",
                        level=first_text.level,
                        label=first_text.label,
                    )
        return ParsedDocument(title=title, items=tuple(items))

    def handle_text_item(self, item: object, level: int) -> ParsedText | None:
        """Convert a Docling text item; subclasses may override this hook."""
        text = " ".join(str(getattr(item, "text", "")).split())
        if not text:
            return None
        label = _label_value(getattr(item, "label", ""))
        if label == "title":
            kind: TextKind = "title"
        elif label in {"section_header", "subtitle"}:
            kind = "section"
        elif label in {"list_item", "checkbox_selected", "checkbox_unselected"}:
            kind = "list_item"
        else:
            kind = "paragraph"
        return ParsedText(text=text, kind=kind, level=level, label=label)

    def handle_table_item(self, item: object, document: object, level: int) -> ParsedTable | None:
        """Convert a Docling table item; subclasses may override this hook."""
        dataframe = item.export_to_dataframe(doc=document)
        rows: list[tuple[str, ...]] = []
        columns = tuple(_clean_cell(value) for value in dataframe.columns)
        if columns and any(columns):
            rows.append(columns)
        rows.extend(tuple(_clean_cell(value) for value in row) for row in dataframe.itertuples(index=False, name=None))
        rows = [row for row in rows if any(row)]
        if not rows:
            return None
        width = max(len(row) for row in rows)
        normalized = tuple(row + ("",) * (width - len(row)) for row in rows)
        return ParsedTable(rows=normalized, level=level)

    def handle_picture_item(self, item: object, document: object, level: int) -> ParsedImage | None:
        """Extract a Docling picture as PNG; subclasses may override this hook."""
        image = item.get_image(document)
        if image is None:
            return None
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        caption = ""
        caption_method = getattr(item, "caption_text", None)
        if callable(caption_method):
            try:
                caption = " ".join(str(caption_method(doc=document)).split())
            except TypeError:
                caption = " ".join(str(caption_method(document)).split())
        return ParsedImage(
            data=buffer.getvalue(),
            level=level,
            caption=caption,
            alt_text=caption or "Image extracted from the source document.",
        )
