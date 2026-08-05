"""Programmatic package fixtures used by tests.

Nothing from this module is shipped as a generated demo. The factory covers
the complete source shape so contract tests can stay compact and deterministic.
"""

from pathlib import Path

from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import ComponentComposition, EntityRef, NarrativeBlock

_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"
_ARCHITECTURE_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="360" viewBox="0 0 960 360">
  <rect width="960" height="360" rx="24" fill="#f5f8f2"/>
  <text x="54" y="55" fill="#214d3d" font-family="system-ui" font-size="17" font-weight="700">V1 SOURCE ARCHITECTURE</text>
  <rect x="54" y="96" width="230" height="176" rx="16" fill="#214d3d"/>
  <text x="82" y="136" fill="#d9ef9f" font-family="system-ui" font-size="14" font-weight="700">COMPOSITE</text>
  <text x="82" y="171" fill="white" font-family="Georgia" font-size="27">subsystem</text>
  <rect x="80" y="201" width="82" height="42" rx="8" fill="#b8e0cb"/>
  <rect x="177" y="201" width="82" height="42" rx="8" fill="#b8e0cb"/>
  <text x="101" y="227" fill="#214d3d" font-family="system-ui" font-size="13">leaf0</text>
  <text x="198" y="227" fill="#214d3d" font-family="system-ui" font-size="13">sink0</text>
  <path d="M284 183 H390" stroke="#668e9f" stroke-width="3"/>
  <circle cx="390" cy="183" r="6" fill="#668e9f"/>
  <rect x="410" y="99" width="220" height="80" rx="14" fill="white" stroke="#b8c8bd" stroke-width="2"/>
  <rect x="410" y="198" width="220" height="80" rx="14" fill="white" stroke="#b8c8bd" stroke-width="2"/>
  <text x="437" y="128" fill="#68756f" font-family="system-ui" font-size="12" font-weight="700">ENTRY DESIGN</text>
  <text x="437" y="157" fill="#15231f" font-family="Georgia" font-size="23">top_a</text>
  <text x="437" y="227" fill="#68756f" font-family="system-ui" font-size="12" font-weight="700">ENTRY DESIGN</text>
  <text x="437" y="256" fill="#15231f" font-family="Georgia" font-size="23">top_b</text>
  <path d="M630 139 H727 M630 238 H727" stroke="#9aac9f" stroke-width="2" stroke-dasharray="6 5"/>
  <rect x="747" y="130" width="160" height="118" rx="14" fill="#e7efe9"/>
  <text x="775" y="166" fill="#52645a" font-family="system-ui" font-size="12" font-weight="700">IMMUTABLE SPECIR</text>
  <text x="775" y="195" fill="#214d3d" font-family="system-ui" font-size="14">queries</text>
  <text x="775" y="218" fill="#214d3d" font-family="system-ui" font-size="14">actions</text>
</svg>"""


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


def build_test_package() -> SpecPackage:
    """Build a multi-entry architecture sample without implementation views."""
    package = SpecPackage.create("spec_v1_test")
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
  <ipxact:busInterfaces>
    <ipxact:busInterface>
      <ipxact:name>link</ipxact:name>
      <ipxact:busType vendor=\"spec2gds.example\" library=\"demo\" name=\"demo_link\" version=\"1.0\"/>
      <ipxact:abstractionTypes><ipxact:abstractionType>
        <ipxact:abstractionRef vendor=\"spec2gds.example\" library=\"demo\" name=\"demo_link_wire\" version=\"1.0\"/>
        <ipxact:portMaps><ipxact:portMap><ipxact:logicalPort><ipxact:name>payload</ipxact:name></ipxact:logicalPort><ipxact:physicalPort><ipxact:name>irq</ipxact:name></ipxact:physicalPort></ipxact:portMap></ipxact:portMaps>
      </ipxact:abstractionType></ipxact:abstractionTypes>
      <ipxact:initiator/>
    </ipxact:busInterface>
  </ipxact:busInterfaces>
  <ipxact:model>
    <ipxact:ports>
      <ipxact:port><ipxact:name>irq</ipxact:name><ipxact:wire><ipxact:direction>out</ipxact:direction></ipxact:wire></ipxact:port>
      <ipxact:port><ipxact:name>irq_in</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port>
    </ipxact:ports>
  </ipxact:model>""",
        ),
    )
    sink = package.add_document(
        "component",
        _xml(
            "component",
            "component_sink",
            "sink",
            """
  <ipxact:busInterfaces>
    <ipxact:busInterface>
      <ipxact:name>link</ipxact:name>
      <ipxact:busType vendor=\"spec2gds.example\" library=\"demo\" name=\"demo_link\" version=\"1.0\"/>
      <ipxact:abstractionTypes><ipxact:abstractionType>
        <ipxact:abstractionRef vendor=\"spec2gds.example\" library=\"demo\" name=\"demo_link_wire\" version=\"1.0\"/>
        <ipxact:portMaps><ipxact:portMap><ipxact:logicalPort><ipxact:name>payload</ipxact:name></ipxact:logicalPort><ipxact:physicalPort><ipxact:name>payload_in</ipxact:name></ipxact:physicalPort></ipxact:portMap></ipxact:portMaps>
      </ipxact:abstractionType></ipxact:abstractionTypes>
      <ipxact:target/>
    </ipxact:busInterface>
  </ipxact:busInterfaces>
  <ipxact:model><ipxact:ports><ipxact:port><ipxact:name>payload_in</ipxact:name><ipxact:wire><ipxact:direction>in</ipxact:direction></ipxact:wire></ipxact:port></ipxact:ports></ipxact:model>""",
        ),
    )
    composite = package.add_document("component", _xml("component", "component_subsystem", "subsystem"))
    internal = package.add_document(
        "design",
        _xml(
            "design",
            "design_subsystem_internal",
            "subsystem_internal",
            """
  <ipxact:componentInstances>
    <ipxact:componentInstance>
      <ipxact:instanceName>leaf0</ipxact:instanceName>
      <ipxact:componentRef vendor=\"spec2gds.example\" library=\"demo\" name=\"leaf\" version=\"1.0\"/>
    </ipxact:componentInstance>
    <ipxact:componentInstance>
      <ipxact:instanceName>sink0</ipxact:instanceName>
      <ipxact:componentRef vendor=\"spec2gds.example\" library=\"demo\" name=\"sink\" version=\"1.0\"/>
    </ipxact:componentInstance>
  </ipxact:componentInstances>
  <ipxact:interconnections>
    <ipxact:interconnection>
      <ipxact:name>link0</ipxact:name>
      <ipxact:activeInterface componentInstanceRef="leaf0" busRef="link"/>
      <ipxact:activeInterface componentInstanceRef="sink0" busRef="link"/>
    </ipxact:interconnection>
  </ipxact:interconnections>""",
        ),
    )
    top_a = package.add_document(
        "design",
        _xml(
            "design",
            "design_top_a",
            "top_a",
            """
  <ipxact:componentInstances>
    <ipxact:componentInstance>
      <ipxact:instanceName>subsystem0</ipxact:instanceName>
      <ipxact:componentRef vendor=\"spec2gds.example\" library=\"demo\" name=\"subsystem\" version=\"1.0\"/>
    </ipxact:componentInstance>
  </ipxact:componentInstances>""",
        ),
    )
    top_b = package.add_document(
        "design",
        _xml(
            "design",
            "design_top_b",
            "top_b",
            """
  <ipxact:componentInstances>
    <ipxact:componentInstance>
      <ipxact:instanceName>leaf1</ipxact:instanceName>
      <ipxact:componentRef vendor=\"spec2gds.example\" library=\"demo\" name=\"leaf\" version=\"1.0\"/>
    </ipxact:componentInstance>
  </ipxact:componentInstances>""",
        ),
    )
    del bus, abstraction, leaf, sink  # Source entities are connected by the internal design below.

    asset = package.add_asset("asset_architecture", _ARCHITECTURE_SVG, "image/svg+xml", "svg")
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
                            text="This sample stores reusable hardware structure as canonical IP-XACT and keeps architectural intent in a typed narrative tree.",
                        ),
                        NarrativeBlock(
                            block_id="review_goals",
                            type="list",
                            children=[
                                NarrativeBlock(block_id="review_goal_structure", type="paragraph", text="Inspect leaf and composite component boundaries."),
                                NarrativeBlock(block_id="review_goal_reuse", type="paragraph", text="Compare two explicit entry designs that reuse the same source definitions."),
                                NarrativeBlock(block_id="review_goal_provenance", type="paragraph", text="Execute a reference action and review its immutable provenance."),
                            ],
                        ),
                        NarrativeBlock(
                            block_id="overview_table",
                            type="table",
                            rows=[
                                ["Entry design", "Purpose", "Key instance"],
                                ["top_a", "Composite integration", "subsystem0"],
                                ["top_b", "Leaf reuse", "leaf1"],
                            ],
                        ),
                        NarrativeBlock(
                            block_id="overview_image",
                            type="image",
                            asset_id=asset.asset_id,
                            alt_text="Diagram showing a composite subsystem reused by two entry designs.",
                            caption="The source package owns hierarchy; the editor derives this presentation.",
                        ),
                        NarrativeBlock(
                            block_id="top_a_link",
                            type="entity_link",
                            text="Primary entry design",
                            entity_refs=[EntityRef(document_id=document_id, entity_id=top_a.entity_id, entity_kind="design")],
                        ),
                        NarrativeBlock(
                            block_id="topology_live_view",
                            type="live_view",
                            renderer_id="design.topology",
                            entity_refs=[EntityRef(document_id=document_id, entity_id=internal.entity_id, entity_kind="design")],
                            options={"show_interfaces": True, "compact": False},
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


def write_test_package(path: str | Path) -> None:
    """Write the deterministic checked-in sample package to ``path``."""
    build_test_package().save(str(path))
