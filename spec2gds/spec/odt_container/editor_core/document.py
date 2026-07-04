import copy
import typing

import lxml.etree as etree
import pydantic


ODF_NS: dict[str, str] = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
}

TEXT_NS: str = ODF_NS["text"]
XLINK_NS: str = ODF_NS["xlink"]


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
    """A hyperlink discovered in ODT content."""

    href: str
    text: str
    block_id: str


class SemanticBlock(pydantic.BaseModel):
    """A small editable/readable projection of an ODT content block."""

    block_id: str
    block_type: str
    text: str
    level: typing.Optional[int] = None
    editable: bool = False
    links: list[DocumentLink] = pydantic.Field(default_factory=list)


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
    return etree.QName(element).localname


def _is_text_element(element: etree._Element, local_name: str) -> bool:
    return element.tag == f"{{{TEXT_NS}}}{local_name}"


def _element_text(element: etree._Element) -> str:
    return "".join(element.itertext()).strip()


def _element_links(element: etree._Element, block_id: str) -> list[DocumentLink]:
    links: list[DocumentLink] = []
    for link_element in element.xpath(".//text:a", namespaces=ODF_NS):
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


def _heading_parts(text_value: str) -> tuple[str, str] | None:
    if "//" not in text_value:
        return None
    title, version = text_value.rsplit("//", 1)
    title = title.strip()
    version = version.strip()
    if not title or not version:
        return None
    return title, version


def _make_group_id(title: str, level: int, ordinal: int) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "-" for ch in title)
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    normalized = normalized.strip("-")
    if not normalized:
        normalized = "section"
    return f"h{level}-{normalized}-{ordinal}"


def _collect_blocks_from_element(
    element: etree._Element,
    blocks: list[SemanticBlock],
    links: list[DocumentLink],
) -> None:
    local = _local_name(element)
    if _is_text_element(element, "h"):
        block_id = f"block-{len(blocks)}"
        level_attr = element.get(f"{{{TEXT_NS}}}outline-level")
        level = 1
        if level_attr is not None:
            try:
                level = int(level_attr)
            except ValueError:
                level = 1
        block_links = _element_links(element, block_id)
        block = SemanticBlock(
            block_id=block_id,
            block_type="heading",
            text=_element_text(element),
            level=level,
            editable=True,
            links=block_links,
        )
        blocks.append(block)
        links.extend(block_links)
        return

    if _is_text_element(element, "p"):
        block_id = f"block-{len(blocks)}"
        block_links = _element_links(element, block_id)
        block = SemanticBlock(
            block_id=block_id,
            block_type="paragraph",
            text=_element_text(element),
            editable=True,
            links=block_links,
        )
        blocks.append(block)
        links.extend(block_links)
        return

    if _is_text_element(element, "list"):
        for paragraph in element.xpath(".//text:list-item/text:p", namespaces=ODF_NS):
            block_id = f"block-{len(blocks)}"
            block_links = _element_links(paragraph, block_id)
            block = SemanticBlock(
                block_id=block_id,
                block_type="list_item",
                text=_element_text(paragraph),
                editable=True,
                links=block_links,
            )
            blocks.append(block)
            links.extend(block_links)
        return

    if _is_text_element(element, "table") or local == "table":
        block_id = f"block-{len(blocks)}"
        blocks.append(
            SemanticBlock(
                block_id=block_id,
                block_type="table",
                text=_element_text(element),
                editable=False,
            )
        )
        return

    for child in element:
        if isinstance(child.tag, str):
            _collect_blocks_from_element(child, blocks, links)


def _find_variant_end(blocks: list[SemanticBlock], start_index: int) -> int:
    heading = blocks[start_index]
    heading_level = heading.level if heading.level is not None else 1
    end_index = len(blocks)
    for idx in range(start_index + 1, len(blocks)):
        candidate = blocks[idx]
        if candidate.block_type != "heading":
            continue
        candidate_level = candidate.level if candidate.level is not None else 1
        if candidate_level <= heading_level:
            end_index = idx
            break
    return end_index


def _build_section_groups(
    blocks: list[SemanticBlock],
    active_versions: dict[str, str],
) -> list[SectionVariantGroup]:
    groups: list[SectionVariantGroup] = []
    group_ordinal: int = 0
    idx = 0
    while idx < len(blocks):
        block = blocks[idx]
        if block.block_type != "heading" or block.level is None:
            idx += 1
            continue
        first_parts = _heading_parts(block.text)
        if first_parts is None:
            idx += 1
            continue

        title, _version = first_parts
        level = block.level
        variant_starts: list[int] = [idx]
        cursor = _find_variant_end(blocks, idx)
        while cursor < len(blocks):
            next_block = blocks[cursor]
            if (
                next_block.block_type != "heading"
                or next_block.level != level
            ):
                break
            next_parts = _heading_parts(next_block.text)
            if next_parts is None or next_parts[0] != title:
                break
            variant_starts.append(cursor)
            cursor = _find_variant_end(blocks, cursor)

        if len(variant_starts) < 2:
            idx += 1
            continue

        group_id = _make_group_id(title, level, group_ordinal)
        group_ordinal += 1
        variants: list[SectionVariant] = []
        for variant_idx, start in enumerate(variant_starts):
            end = cursor
            if variant_idx + 1 < len(variant_starts):
                end = variant_starts[variant_idx + 1]
            variant_block = blocks[start]
            variant_parts = _heading_parts(variant_block.text)
            if variant_parts is None:
                continue
            block_ids = [candidate.block_id for candidate in blocks[start:end]]
            variants.append(
                SectionVariant(
                    version=variant_parts[1],
                    heading_block_id=variant_block.block_id,
                    block_ids=block_ids,
                )
            )

        active_version = variants[0].version
        if group_id in active_versions:
            requested_version = active_versions[group_id]
            for variant in variants:
                if variant.version == requested_version:
                    active_version = requested_version
                    break

        groups.append(
            SectionVariantGroup(
                group_id=group_id,
                title=title,
                level=level,
                variants=variants,
                active_version=active_version,
            )
        )
        idx = cursor
    return groups


def parse_content_xml(
    content_xml: bytes,
    active_versions: typing.Optional[dict[str, str]] = None,
) -> SemanticDocument:
    """Parse ODT content.xml into the v1 semantic editor projection."""
    diagnostics: list[Diagnostic] = []
    active_map: dict[str, str] = active_versions if active_versions is not None else {}
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

    text_nodes = root.xpath("//office:text", namespaces=ODF_NS)
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
            _collect_blocks_from_element(child, blocks, links)

    section_groups = _build_section_groups(blocks, active_map)
    return SemanticDocument(
        blocks=blocks,
        section_groups=section_groups,
        links=links,
        diagnostics=diagnostics,
    )


def _set_element_plain_text(element: etree._Element, text_value: str) -> None:
    element.clear(keep_tail=True)
    element.text = text_value


def _editable_elements(root: etree._Element) -> list[etree._Element]:
    elements: list[etree._Element] = []
    text_nodes = root.xpath("//office:text", namespaces=ODF_NS)
    if not text_nodes:
        return elements
    office_text = text_nodes[0]
    for element in office_text.iter():
        if not isinstance(element.tag, str):
            continue
        if _is_text_element(element, "h") or _is_text_element(element, "p"):
            elements.append(element)
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
    for idx, element in enumerate(editable):
        block_id = f"block-{idx}"
        if block_id not in edits:
            continue
        _set_element_plain_text(element, edits[block_id])
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)
