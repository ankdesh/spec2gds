"""Small canonical source package used by V1.1 tests and documentation."""

import base64
from pathlib import Path

from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import ComponentComposition, EntityRef, NarrativeBlock


_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/"
    "jT9zNwAAAABJRU5ErkJggg=="
)


def _xml(root: str, entity_id: str, name: str, body: str = "") -> bytes:
    """Create a compact, valid IP-XACT identity document for the V1 sample."""
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<ipxact:{root} xmlns:ipxact=\"{_NS}\" xml:id=\"{entity_id}\">
  <ipxact:vendor>spec2gds.example</ipxact:vendor>
  <ipxact:library>demo</ipxact:library>
  <ipxact:name>{name}</ipxact:name>
  <ipxact:version>1.0</ipxact:version>{body}
</ipxact:{root}>
""".encode("utf-8")


def build_v1_sample() -> SpecPackage:
    """Build a minimal multi-entry V1 source package without implementation views."""
    package = SpecPackage.create("spec_v1_demo")
    bus = package.add_document(
        "bus_definition",
        _xml(
            "busDefinition",
            "bus_demo_link",
            "demo_link",
            """
  <ipxact:directConnection>true</ipxact:directConnection>
  <ipxact:isAddressable>false</ipxact:isAddressable>""",
        ),
    )
    abstraction = package.add_document(
        "abstraction_definition",
        _xml(
            "abstractionDefinition",
            "abstraction_demo_link_wire",
            "demo_link_wire",
            """
  <ipxact:busType vendor=\"spec2gds.example\" library=\"demo\" name=\"demo_link\" version=\"1.0\"/>
  <ipxact:ports>
    <ipxact:port>
      <ipxact:logicalName>payload</ipxact:logicalName>
      <ipxact:wire>
        <ipxact:onInitiator><ipxact:direction>out</ipxact:direction></ipxact:onInitiator>
        <ipxact:onTarget><ipxact:direction>in</ipxact:direction></ipxact:onTarget>
      </ipxact:wire>
    </ipxact:port>
  </ipxact:ports>""",
        ),
    )
    leaf = package.add_document(
        "component",
        _xml(
            "component",
            "component_leaf",
            "leaf",
            """
  <ipxact:model>
    <ipxact:ports>
      <ipxact:port><ipxact:name>irq</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction></ipxact:wire></ipxact:port>
    </ipxact:ports>
  </ipxact:model>""",
        ),
    )
    composite = package.add_document("component", _xml("component", "component_subsystem", "subsystem"))
    internal = package.add_document("design", _xml("design", "design_subsystem_internal", "subsystem_internal"))
    top_a = package.add_document("design", _xml("design", "design_top_a", "top_a"))
    top_b = package.add_document("design", _xml("design", "design_top_b", "top_b"))
    del bus, abstraction, leaf  # Present as source entities; the sample stays deliberately unconnected.

    asset = package.add_asset("asset_overview", _PIXEL_PNG, "image/png", "png")
    document_id = package.manifest.document_id
    package.narrative = package.narrative.model_copy(
        update={
            "blocks": [
                NarrativeBlock(
                    block_id="overview",
                    type="section",
                    text="V1 source-package demonstration",
                    children=[
                        NarrativeBlock(
                            block_id="overview_text",
                            type="paragraph",
                            text="The architecture is stored as IP-XACT source plus a typed narrative.",
                        ),
                        NarrativeBlock(
                            block_id="overview_table",
                            type="table",
                            rows=[["Entry design", "Purpose"], ["top_a", "Primary integration"]],
                        ),
                        NarrativeBlock(
                            block_id="overview_image",
                            type="image",
                            asset_id=asset.asset_id,
                            alt_text="One-pixel placeholder for a future architecture diagram.",
                        ),
                        NarrativeBlock(
                            block_id="top_a_link",
                            type="entity_link",
                            text="Primary entry design",
                            entity_refs=[EntityRef(document_id=document_id, entity_id=top_a.entity_id, entity_kind="design")],
                        ),
                    ],
                )
            ]
        }
    )
    package.manifest = package.manifest.model_copy(
        update={
            "entry_designs": [
                EntityRef(document_id=document_id, entity_id=top_a.entity_id, entity_kind="design"),
                EntityRef(document_id=document_id, entity_id=top_b.entity_id, entity_kind="design"),
            ],
            "component_compositions": [
                ComponentComposition(
                    component=EntityRef(document_id=document_id, entity_id=composite.entity_id, entity_kind="component"),
                    internal_design=EntityRef(document_id=document_id, entity_id=internal.entity_id, entity_kind="design"),
                )
            ],
        }
    )
    package.require_valid()
    return package


def write_v1_sample(path: str | Path) -> None:
    """Write the deterministic checked-in sample package to ``path``."""
    build_v1_sample().save(str(path))
