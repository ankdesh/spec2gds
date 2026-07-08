"""Semantic projection and text-edit helpers for ODT `content.xml`.

The editor does not work directly with ODT XML. Instead, this module converts
the human-readable document body into a compact list of semantic blocks
(headings, paragraphs, list items, tables, images) and applies plain-text edits
back to the matching XML elements when it is safe to do so.
"""

import copy
import typing

import lxml.etree as etree
import pydantic


OFFICE_DOCUMENT_NS: dict[str, str] = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "xml": "http://www.w3.org/XML/1998/namespace",
}

TEXT_NS: str = OFFICE_DOCUMENT_NS["text"]
XLINK_NS: str = OFFICE_DOCUMENT_NS["xlink"]
XML_NS: str = OFFICE_DOCUMENT_NS["xml"]


class Diagnostic(pydantic.BaseModel):
    """Diagnostic emitted by the lightweight editor engine."""

    severity: str
    source: str
    message: str
    block_id: typing.Optional[str] = None

    @property
    def blocks_save(self) -> bool:
        return self.severity in {"warning", "error"}


class DocumentLink(pydantic.BaseModel):
    """A hyperlink discovered in agent-spec content."""

    href: str
    text: str
    block_id: str


class TableCell(pydantic.BaseModel):
    """Plain-text projection of one table cell."""

    text: str


class TableRow(pydantic.BaseModel):
    """Plain-text projection of one table row."""

    cells: list[TableCell] = pydantic.Field(default_factory=list)


class ImageRef(pydantic.BaseModel):
    """Reference to an embedded image block in the ODT package."""

    asset_id: str
    href: str
    title: str = ""


class SemanticBlock(pydantic.BaseModel):
    """A small editable/readable projection of an agent-spec content block."""

    block_id: str
    block_type: str
    text: str
    display_text: str = ""
    level: typing.Optional[int] = None
    heading_id: typing.Optional[str] = None
    editable: bool = False
    editable_reason: str = ""
    links: list[DocumentLink] = pydantic.Field(default_factory=list)
    table_rows: list[TableRow] = pydantic.Field(default_factory=list)
    image: typing.Optional[ImageRef] = None
    style_name: typing.Optional[str] = None


class SectionVariant(pydantic.BaseModel):
    """One heading-delimited section variant."""

    version: str
    heading_block_id: str
    block_ids: list[str]


class SectionVariantGroup(pydantic.BaseModel):
    """Adjacent heading variants sharing the same base title and heading level."""

    group_id: str
    title: str
    level: int
    variants: list[SectionVariant]
    active_version: str


class SemanticDocument(pydantic.BaseModel):
    """Semantic projection used by the v1 editor."""

    blocks: list[SemanticBlock]
    section_groups: list[SectionVariantGroup]
    links: list[DocumentLink]
    diagnostics: list[Diagnostic] = pydantic.Field(default_factory=list)

    @property
    def has_blocking_diagnostics(self) -> bool:
        for diagnostic in self.diagnostics:
            if diagnostic.blocks_save:
                return True
        return False


def _local_name(element: etree._Element) -> str:
    """Return the namespace-free XML tag name for dispatch."""
    return etree.QName(element).localname


def _is_text_element(element: etree._Element, local_name: str) -> bool:
    """Return whether an element is an ODT `text:*` element by local name."""
    return element.tag == f"{{{TEXT_NS}}}{local_name}"


def _element_text(element: etree._Element) -> str:
    """Return visible text from an element, collapsed to a trimmed string."""
    return "".join(element.itertext()).strip()


def _display_text(text_value: str) -> str:
    """Return the text shown for a semantic block."""
    return text_value


def _style_name(element: etree._Element) -> str | None:
    """Return the ODT text style name attached to a block-like element."""
    return element.get(f"{{{TEXT_NS}}}style-name")


def _has_complex_inline_markup(element: etree._Element) -> bool:
    """Return true when editing plain text would destroy inline child markup."""
    for child in element:
        if isinstance(child.tag, str):
            return True
    return False


def _element_links(element: etree._Element, block_id: str) -> list[DocumentLink]:
    """Collect hyperlinks contained in one semantic block element."""
    links: list[DocumentLink] = []
    for link_element in element.xpath(".//text:a", namespaces=OFFICE_DOCUMENT_NS):
        href_value: typing.Optional[str] = link_element.get(f"{{{XLINK_NS}}}href")
        if href_value is None:
            continue
        links.append(
            DocumentLink(
                href=href_value,
                text=_element_text(link_element),
                block_id=block_id,
            )
        )
    return links


def _slug(value: str) -> str:
    """Normalize text into a compact id fragment."""
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    normalized = normalized.strip("-")
    return normalized or "heading"


def _xml_id(element: etree._Element) -> str | None:
    """Return the XML id used as the stable heading/block id."""
    return element.get(f"{{{XML_NS}}}id")


def _set_xml_id(element: etree._Element, value: str) -> None:
    """Set an XML id on a heading element."""
    element.set(f"{{{XML_NS}}}id", value)


def _make_unique_id(candidate: str, used: set[str]) -> str:
    """Suffix an id candidate until it is unique within the document."""
    base = candidate
    ordinal = 2
    while candidate in used:
        candidate = f"{base}-{ordinal}"
        ordinal += 1
    used.add(candidate)
    return candidate


def _heading_level(element: etree._Element) -> int:
    """Read ODT outline level, defaulting to top-level headings on bad input."""
    level_attr = element.get(f"{{{TEXT_NS}}}outline-level")
    if level_attr is None:
        return 1
    try:
        return int(level_attr)
    except ValueError:
        return 1


def ensure_heading_ids(content_xml: bytes) -> bytes:
    """Assign stable `xml:id` values to headings that do not already have one."""
    root = etree.fromstring(content_xml)
    used: set[str] = set()
    headings = root.xpath("//text:h", namespaces=OFFICE_DOCUMENT_NS)
    for ordinal, heading in enumerate(headings):
        existing = _xml_id(heading)
        if existing:
            # Preserve author/editor-assigned ids; they may already be referenced
            # by graph metadata or editor relations.
            used.add(existing)
            continue
        text_value = _element_text(heading)
        candidate = f"h{_heading_level(heading)}-{_slug(text_value)}-{ordinal}"
        _set_xml_id(heading, _make_unique_id(candidate, used))
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def heading_ids(content_xml: bytes) -> list[str]:
    """Return all heading ids currently present in document order."""
    root = etree.fromstring(content_xml)
    values: list[str] = []
    for heading in root.xpath("//text:h", namespaces=OFFICE_DOCUMENT_NS):
        value = _xml_id(heading)
        if value is not None:
            values.append(value)
    return values


def _collect_blocks_from_element(
    element: etree._Element,
    blocks: list[SemanticBlock],
    links: list[DocumentLink],
) -> None:
    """Append semantic blocks discovered beneath one ODT XML element."""
    local = _local_name(element)
    if _is_text_element(element, "h"):
        # Headings are the only semantic blocks with stable ids because action
        # graph blocks are keyed by heading id.
        heading_id = _xml_id(element) or f"block-{len(blocks)}"
        block_id = heading_id
        level = _heading_level(element)
        block_links = _element_links(element, block_id)
        text_value = _element_text(element)
        complex_inline = _has_complex_inline_markup(element)
        block = SemanticBlock(
            block_id=block_id,
            block_type="heading",
            text=text_value,
            display_text=_display_text(text_value),
            level=level,
            heading_id=heading_id,
            editable=not complex_inline,
            editable_reason="contains inline markup" if complex_inline else "",
            links=block_links,
            style_name=_style_name(element),
        )
        blocks.append(block)
        links.extend(block_links)
        return

    if _is_text_element(element, "p"):
        # Paragraph ids are positional because ODT paragraphs do not have stable
        # ids in the current editor model.
        block_id = f"block-{len(blocks)}"
        block_links = _element_links(element, block_id)
        complex_inline = _has_complex_inline_markup(element)
        text_value = _element_text(element)
        block = SemanticBlock(
            block_id=block_id,
            block_type="paragraph",
            text=text_value,
            display_text=text_value,
            editable=not complex_inline,
            editable_reason="contains inline markup" if complex_inline else "",
            links=block_links,
            style_name=_style_name(element),
        )
        blocks.append(block)
        links.extend(block_links)
        return

    if _is_text_element(element, "list"):
        # Phase 2 flattens list item paragraphs into editable blocks while
        # preserving enough order to apply edits back to the original XML.
        for paragraph in element.xpath(".//text:list-item/text:p", namespaces=OFFICE_DOCUMENT_NS):
            block_id = f"block-{len(blocks)}"
            block_links = _element_links(paragraph, block_id)
            block = SemanticBlock(
                block_id=block_id,
                block_type="list_item",
                text=_element_text(paragraph),
                display_text=_element_text(paragraph),
                editable=not _has_complex_inline_markup(paragraph),
                editable_reason="contains inline markup" if _has_complex_inline_markup(paragraph) else "",
                links=block_links,
                style_name=_style_name(paragraph),
            )
            blocks.append(block)
            links.extend(block_links)
        return

    if local == "table":
        # Tables are visible to the UI but read-only in this implementation.
        block_id = f"block-{len(blocks)}"
        rows: list[TableRow] = []
        for row in element.xpath(".//table:table-row", namespaces=OFFICE_DOCUMENT_NS):
            cells: list[TableCell] = []
            for cell in row.xpath("./table:table-cell", namespaces=OFFICE_DOCUMENT_NS):
                cells.append(TableCell(text=_element_text(cell)))
            if cells:
                rows.append(TableRow(cells=cells))
        blocks.append(
            SemanticBlock(
                block_id=block_id,
                block_type="table",
                text=_element_text(element),
                display_text=_element_text(element),
                editable=False,
                editable_reason="tables are read-only in phase 2",
                table_rows=rows,
            )
        )
        return

    if local == "frame":
        # Image frames become asset references; bytes are served later through
        # `EditorSession.asset_bytes`.
        image_elements = element.xpath(".//draw:image", namespaces=OFFICE_DOCUMENT_NS)
        if image_elements:
            href = image_elements[0].get(f"{{{XLINK_NS}}}href") or ""
            block_id = f"block-{len(blocks)}"
            blocks.append(
                SemanticBlock(
                    block_id=block_id,
                    block_type="image",
                    text=href,
                    display_text=href,
                    editable=False,
                    editable_reason="images are read-only in phase 2",
                    image=ImageRef(asset_id=block_id, href=href, title=_element_text(element)),
                )
            )
            return

    for child in element:
        if isinstance(child.tag, str):
            # Recurse through wrapper elements we do not model directly.
            _collect_blocks_from_element(child, blocks, links)


def parse_content_xml(
    content_xml: bytes,
    active_versions: typing.Optional[dict[str, str]] = None,
) -> SemanticDocument:
    """Parse ODT `content.xml` into the v1 semantic editor projection."""
    diagnostics: list[Diagnostic] = []
    # Section-version groups are now metadata-owned (`relations.json`). Keep
    # this optional parameter for older callers, but do not infer groups from
    # heading text.
    _ = active_versions
    try:
        root = etree.fromstring(content_xml)
    except Exception as exc:
        return SemanticDocument(
            blocks=[],
            section_groups=[],
            links=[],
            diagnostics=[
                Diagnostic(
                    severity="error",
                    source="content.xml",
                    message=f"Failed to parse content.xml: {exc}",
                )
            ],
        )

    text_nodes = root.xpath("//office:text", namespaces=OFFICE_DOCUMENT_NS)
    if not text_nodes:
        return SemanticDocument(
            blocks=[],
            section_groups=[],
            links=[],
            diagnostics=[
                Diagnostic(
                    severity="error",
                    source="content.xml",
                    message="content.xml does not contain office:text.",
                )
            ],
        )

    blocks: list[SemanticBlock] = []
    links: list[DocumentLink] = []
    office_text = text_nodes[0]
    for child in office_text:
        if isinstance(child.tag, str):
            # The parser starts at the document body and recursively descends
            # through supported block-level structures.
            _collect_blocks_from_element(child, blocks, links)

    return SemanticDocument(
        blocks=blocks,
        section_groups=[],
        links=links,
        diagnostics=diagnostics,
    )


def _set_element_plain_text(element: etree._Element, text_value: str) -> None:
    """Replace one editable XML element with plain text content."""
    element.clear(keep_tail=True)
    element.text = text_value


def _collect_editable_elements(
    element: etree._Element,
    elements: list[tuple[str, etree._Element]],
    block_index: list[int],
) -> None:
    """Collect XML elements that can map to editable semantic block ids."""
    local = _local_name(element)
    if _is_text_element(element, "h"):
        elements.append((_xml_id(element) or f"block-{block_index[0]}", element))
        block_index[0] += 1
        return
    if _is_text_element(element, "p"):
        elements.append((f"block-{block_index[0]}", element))
        block_index[0] += 1
        return
    if _is_text_element(element, "list"):
        for paragraph in element.xpath(".//text:list-item/text:p", namespaces=OFFICE_DOCUMENT_NS):
            elements.append((f"block-{block_index[0]}", paragraph))
            block_index[0] += 1
        return
    if local == "table":
        # Tables consume one semantic block id but are not editable.
        block_index[0] += 1
        return
    if local == "frame" and element.xpath(".//draw:image", namespaces=OFFICE_DOCUMENT_NS):
        # Image frames also consume one semantic block id and remain read-only.
        block_index[0] += 1
        return
    for child in element:
        if isinstance(child.tag, str):
            _collect_editable_elements(child, elements, block_index)


def _editable_elements(root: etree._Element) -> list[tuple[str, etree._Element]]:
    """Return editable XML elements paired with their semantic block ids."""
    elements: list[tuple[str, etree._Element]] = []
    text_nodes = root.xpath("//office:text", namespaces=OFFICE_DOCUMENT_NS)
    if not text_nodes:
        return elements
    office_text = text_nodes[0]
    block_index = [0]
    for child in office_text:
        if isinstance(child.tag, str):
            _collect_editable_elements(child, elements, block_index)
    return elements


def apply_text_edits_to_content_xml(
    content_xml: bytes,
    edits: dict[str, str],
) -> bytes:
    """
    Apply v1 plain-text edits to heading, paragraph, and list paragraph blocks.

    The edit operation intentionally replaces inline markup inside edited blocks.
    This keeps v1 understandable and is appropriate only for the supported
    semantic editor scope.
    """
    if not edits:
        return copy.deepcopy(content_xml)

    root = etree.fromstring(content_xml)
    editable = _editable_elements(root)
    for block_id, element in editable:
        if block_id not in edits:
            continue
        if _has_complex_inline_markup(element):
            # Skip complex blocks defensively even if the caller sends an edit;
            # the snapshot marks them read-only because plain-text replacement
            # would discard inline XML.
            continue
        _set_element_plain_text(element, edits[block_id])
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)
