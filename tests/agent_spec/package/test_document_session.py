import os
import json
import tempfile
from pathlib import Path

import spec2gds.agent_spec.package.archive as container
import spec2gds.agent_spec.api.document_app as api_app
import spec2gds.agent_spec.document.semantic as editor_document
import spec2gds.agent_spec.document.ipxact_view as ipxact_view
import spec2gds.agent_spec.document.relations as editor_relations
import spec2gds.agent_spec.document.session as editor_session
import spec2gds.agent_spec.plugins.manager as manager
import spec2gds.agent_spec.package.verifier as verifier


SYNTHETIC_CONTENT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Overview</text:h>
      <text:p>Intro paragraph.</text:p>
      <text:h text:outline-level="2">Bus behavior//v1</text:h>
      <text:p>Version one text.</text:p>
      <text:list>
        <text:list-item><text:p>First list item</text:p></text:list-item>
      </text:list>
      <text:h text:outline-level="2">Bus behavior//v2</text:h>
      <text:p>Version two text.</text:p>
      <text:h text:outline-level="2">Other section</text:h>
      <text:p>Tail paragraph.</text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


SYNTHETIC_LINK_CONTENT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Links</text:h>
      <text:p><text:a xlink:type="simple" xlink:href="spec://simple-json/missing.json/title">Missing</text:a></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


SYNTHETIC_IPXACT_LINK_CONTENT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Overview</text:h>
      <text:p>No attachment here.</text:p>
      <text:h text:outline-level="2">IP-XACT reference</text:h>
      <text:p><text:a xlink:type="simple" xlink:href="spec://ipxact/uart.xml/VLNV/Name">Linked IP name</text:a></text:p>
    </office:text>
  </office:body>
</office:document-content>
"""


SYNTHETIC_RICH_CONTENT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<office:document-content
  xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
  xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
  xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
  xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
  xmlns:xlink="http://www.w3.org/1999/xlink"
  office:version="1.3">
  <office:body>
    <office:text>
      <text:h text:outline-level="1">Rich content</text:h>
      <text:p>Plain paragraph.</text:p>
      <text:p><text:a xlink:type="simple" xlink:href="https://example.com">Linked paragraph</text:a></text:p>
      <table:table>
        <table:table-row>
          <table:table-cell><text:p>Name</text:p></table:table-cell>
          <table:table-cell><text:p>Value</text:p></table:table-cell>
        </table:table-row>
        <table:table-row>
          <table:table-cell><text:p>CTRL</text:p></table:table-cell>
          <table:table-cell><text:p>0x00</text:p></table:table-cell>
        </table:table-row>
      </table:table>
      <draw:frame><draw:image xlink:href="Pictures/sample.png"/></draw:frame>
    </office:text>
  </office:body>
</office:document-content>
"""


SYNTHETIC_IPXACT_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2014">
  <ipxact:vendor>acme</ipxact:vendor>
  <ipxact:library>local</ipxact:library>
  <ipxact:name>uart</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:busInterfaces>
    <ipxact:busInterface>
      <ipxact:name>apb_slave</ipxact:name>
      <ipxact:busType vendor="amba.com" library="AMBA4" name="APB" version="r0p0"/>
      <ipxact:abstractionTypes>
        <ipxact:abstractionType vendor="amba.com" library="AMBA4" name="APB_rtl" version="r0p0"/>
      </ipxact:abstractionTypes>
      <ipxact:interfaceMode>slave</ipxact:interfaceMode>
      <ipxact:portMaps>
        <ipxact:portMap>
          <ipxact:logicalPort><ipxact:name>PADDR</ipxact:name></ipxact:logicalPort>
          <ipxact:physicalPort><ipxact:name>paddr_i</ipxact:name></ipxact:physicalPort>
        </ipxact:portMap>
      </ipxact:portMaps>
    </ipxact:busInterface>
  </ipxact:busInterfaces>
</ipxact:component>
"""


def test_parse_synthetic_content_and_group_heading_versions() -> None:
    """Test semantic parsing keeps `//` heading text literal."""
    parsed = editor_document.parse_content_xml(SYNTHETIC_CONTENT_XML)

    if parsed.has_blocking_diagnostics:
        raise AssertionError(f"Unexpected diagnostics: {parsed.diagnostics}")
    if len(parsed.blocks) != 9:
        raise AssertionError(f"Expected 9 semantic blocks, got {len(parsed.blocks)}")
    if parsed.section_groups:
        raise AssertionError(f"Heading text should not create section groups: {parsed.section_groups}")
    headings = [block for block in parsed.blocks if block.block_type == "heading"]
    if headings[1].display_text != "Bus behavior//v1":
        raise AssertionError(f"Expected literal heading text, got {headings[1].display_text}")


def _version_relations_from_snapshot(
    snapshot: editor_session.EditorSnapshot,
) -> editor_relations.EditorRelations:
    """Create an explicit relation group for the synthetic v1/v2 headings."""
    heading_by_text = {
        block.text: block
        for block in snapshot.document.blocks
        if block.block_type == "heading"
    }
    v1_heading = heading_by_text["Bus behavior//v1"]
    v2_heading = heading_by_text["Bus behavior//v2"]
    return editor_relations.EditorRelations(
        section_groups=[
            editor_relations.SectionVersionGroup(
                group_id="bus-behavior",
                title="Bus behavior",
                level=2,
                variants=[
                    editor_relations.SectionVersionRef(
                        version="v1",
                        heading_id=v1_heading.heading_id or v1_heading.block_id,
                        block_ids=[v1_heading.block_id, "block-3", "block-4"],
                    ),
                    editor_relations.SectionVersionRef(
                        version="v2",
                        heading_id=v2_heading.heading_id or v2_heading.block_id,
                        block_ids=[v2_heading.block_id, "block-6"],
                    ),
                ],
                active_version="v1",
            )
        ],
        ipxact_attachments=snapshot.relations.ipxact_attachments,
    )


def test_apply_text_edits_to_synthetic_content() -> None:
    """Test v1 plain-text edits for headings, paragraphs, and list items."""
    edited_xml = editor_document.apply_text_edits_to_content_xml(
        SYNTHETIC_CONTENT_XML,
        {
            "block-1": "Updated intro.",
            "block-4": "Updated list item",
        },
    )
    parsed = editor_document.parse_content_xml(edited_xml)
    text_by_id = {block.block_id: block.text for block in parsed.blocks}

    if text_by_id["block-1"] != "Updated intro.":
        raise AssertionError("Paragraph edit was not applied.")
    if text_by_id["block-4"] != "Updated list item":
        raise AssertionError("List item edit was not applied.")


def test_phase2_parser_assigns_heading_ids_and_renders_rich_blocks() -> None:
    """Test phase 2 parser fields for stable headings, tables, images, and edit safety."""
    content_with_ids = editor_document.ensure_heading_ids(SYNTHETIC_RICH_CONTENT_XML)
    parsed = editor_document.parse_content_xml(content_with_ids)
    blocks = parsed.blocks

    heading = blocks[0]
    if heading.heading_id is None or not heading.block_id.startswith("h1-rich-content"):
        raise AssertionError(f"Expected stable heading id, got {heading}")
    if not heading.editable:
        raise AssertionError("Plain heading should be editable.")

    plain = blocks[1]
    linked = blocks[2]
    if not plain.editable:
        raise AssertionError("Plain paragraph should be editable.")
    if linked.editable or linked.editable_reason != "contains inline markup":
        raise AssertionError("Linked paragraph should be read-only to preserve inline markup.")

    table = blocks[3]
    if table.block_type != "table" or table.editable:
        raise AssertionError(f"Expected read-only table block, got {table}")
    if table.table_rows[1].cells[0].text != "CTRL":
        raise AssertionError(f"Expected table cell extraction, got {table.table_rows}")

    image = blocks[4]
    if image.block_type != "image" or image.image is None:
        raise AssertionError(f"Expected image block, got {image}")
    if image.image.href != "Pictures/sample.png":
        raise AssertionError(f"Unexpected image href: {image.image.href}")


def test_ipxact_interface_summary_from_synthetic_xml() -> None:
    """Test interface-focused IP-XACT table extraction."""
    summary = ipxact_view.extract_ipxact_summary("spec_data/ipxact/uart.xml", SYNTHETIC_IPXACT_XML)

    if summary.has_blocking_diagnostics:
        raise AssertionError(f"Unexpected IP-XACT diagnostics: {summary.diagnostics}")
    if summary.component.name != "uart":
        raise AssertionError(f"Unexpected component name: {summary.component.name}")
    if len(summary.interfaces) != 1:
        raise AssertionError(f"Expected 1 interface, got {len(summary.interfaces)}")

    interface = summary.interfaces[0]
    if interface.name != "apb_slave" or interface.mode != "slave":
        raise AssertionError(f"Unexpected interface summary: {interface}")
    if interface.bus_type.name != "APB":
        raise AssertionError(f"Unexpected bus type: {interface.bus_type}")
    if len(interface.port_maps) != 1:
        raise AssertionError("Expected one port map.")
    if interface.port_maps[0].physical_port != "paddr_i":
        raise AssertionError(f"Unexpected physical port: {interface.port_maps[0]}")


def test_editor_session_snapshot_persists_active_versions_and_saves() -> None:
    """Test active section versions are stored through explicit relations."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    cont.inject_file(
        "spec_data/ipxact/uart.xml",
        SYNTHETIC_IPXACT_XML,
        "application/xml+ipxact",
    )

    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()
    if snapshot.has_blocking_diagnostics:
        raise AssertionError(f"Unexpected snapshot diagnostics: {snapshot}")
    if snapshot.document.section_groups:
        raise AssertionError("Section groups should come only from relations metadata.")

    session.persist_relations(_version_relations_from_snapshot(snapshot))
    snapshot = session.snapshot()
    group = snapshot.document.section_groups[0]
    session.persist_active_versions({group.group_id: "v2"})
    updated_snapshot = session.snapshot()
    if updated_snapshot.document.section_groups[0].active_version != "v2":
        raise AssertionError("Active section version was not persisted in session state.")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_fd)
    try:
        session.save(temp_path)
        reloaded = editor_session.EditorSession.from_path(temp_path)
        reloaded_snapshot = reloaded.snapshot()
        if reloaded_snapshot.document.section_groups[0].active_version != "v2":
            raise AssertionError("Active section version did not survive agent-spec save/reload.")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_editor_session_does_not_migrate_title_version_headings_to_relations() -> None:
    """Test `Title//version` headings are not inferred as relation groups."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    session = editor_session.EditorSession(cont)

    snapshot = session.snapshot()
    if snapshot.relations.section_groups:
        raise AssertionError(f"Unexpected inferred relation group: {snapshot.relations}")

    session.persist_relations(_version_relations_from_snapshot(snapshot))
    snapshot = session.snapshot()
    if [variant.version for variant in snapshot.relations.section_groups[0].variants] != ["v1", "v2"]:
        raise AssertionError(f"Explicit relation group was not preserved: {snapshot.relations}")
    if "spec_data/agent-spec-editor/relations.json" not in cont.custom_files:
        raise AssertionError("Relations metadata was not persisted.")


def test_editor_session_validates_multiple_ipxact_attachments() -> None:
    """Test heading-level IP-XACT attachment relations and missing file diagnostics."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    cont.inject_file(
        "spec_data/ipxact/uart.xml",
        SYNTHETIC_IPXACT_XML,
        "application/xml+ipxact",
    )
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()
    heading_id = snapshot.document.blocks[0].heading_id
    if heading_id is None:
        raise AssertionError("Expected heading id.")

    draft = snapshot.relations
    draft.ipxact_attachments[heading_id] = [
        {"file_path": "spec_data/ipxact/uart.xml"},
        {"file_path": "missing.xml"},
    ]
    session.persist_relations(draft)
    updated = session.snapshot()

    if updated.relations.ipxact_attachments[heading_id][0].file_path != "spec_data/ipxact/uart.xml":
        raise AssertionError("Existing attachment was not preserved.")
    if not any("missing" in diagnostic.message for diagnostic in updated.diagnostics):
        raise AssertionError(f"Expected missing attachment diagnostic, got {updated.diagnostics}")


def test_editor_session_migrates_ipxact_links_to_nearest_heading() -> None:
    """Test legacy spec://ipxact links become heading-specific attachments."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_IPXACT_LINK_CONTENT_XML)
    cont.inject_file(
        "spec_data/ipxact/uart.xml",
        SYNTHETIC_IPXACT_XML,
        "application/xml+ipxact",
    )
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()
    headings = {
        block.display_text: block.heading_id
        for block in snapshot.document.blocks
        if block.block_type == "heading"
    }
    overview_id = headings["Overview"]
    ipxact_id = headings["IP-XACT reference"]

    if overview_id in snapshot.relations.ipxact_attachments:
        raise AssertionError("Overview heading should not receive IP-XACT attachments.")
    attached = snapshot.relations.ipxact_attachments.get(ipxact_id or "", [])
    if [item.file_path for item in attached] != ["spec_data/ipxact/uart.xml"]:
        raise AssertionError(f"Expected heading-specific IP-XACT attachment, got {attached}")


def test_editor_session_blocks_save_on_unresolved_spec_link() -> None:
    """Test the v1 save gate blocks unresolved spec:// diagnostics."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_LINK_CONTENT_XML)
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()

    if not snapshot.has_blocking_diagnostics:
        raise AssertionError("Unresolved spec link should produce a blocking diagnostic.")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_fd)
    try:
        failed = False
        try:
            session.save(temp_path)
        except ValueError:
            failed = True
        if not failed:
            raise AssertionError("Save should fail while unresolved link diagnostics remain.")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_editor_session_updates_ipxact_xml_with_preview_gate() -> None:
    """Test raw IP-XACT XML edit/import preview blocks malformed updates."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    session = editor_session.EditorSession(cont)

    invalid_preview = session.preview_ipxact_xml("bad.xml", "<broken>")
    if not invalid_preview.has_blocking_diagnostics:
        raise AssertionError("Malformed IP-XACT XML should produce blocking diagnostics.")

    failed = False
    try:
        session.update_ipxact_xml("bad.xml", "<broken>")
    except ValueError:
        failed = True
    if not failed:
        raise AssertionError("Malformed IP-XACT XML should not be imported.")

    session.update_ipxact_xml("uart.xml", SYNTHETIC_IPXACT_XML.decode("utf-8"))
    snapshot = session.snapshot()
    if len(snapshot.ipxact_components) != 1:
        raise AssertionError("Valid IP-XACT XML was not imported into the editor session.")
    if snapshot.ipxact_components[0].interfaces[0].name != "apb_slave":
        raise AssertionError("Imported IP-XACT interface summary is incorrect.")


def test_verifier_accepts_editor_state_metadata() -> None:
    """Test existing verifier accepts internal editor state JSON under spec_data."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()
    session.persist_relations(_version_relations_from_snapshot(snapshot))
    snapshot = session.snapshot()
    group = snapshot.document.section_groups[0]
    session.persist_active_versions({group.group_id: "v2"})

    pm = manager.PluginManager()
    report = verifier.ContainerVerifier(cont, pm).verify_all()
    if not report.is_fully_consistent:
        raise AssertionError(f"Editor metadata should verify cleanly: {report}")


def test_editor_web_scaffold_is_minimal_and_present() -> None:
    """Test minimal frontend scaffold files and dependency policy."""
    web_root = Path("spec2gds/agent_spec/document/editor_web")
    required_files = [
        "package.json",
        "index.html",
        "vite.config.ts",
        "tsconfig.json",
        "src/main.tsx",
        "src/styles.css",
    ]
    for file_name in required_files:
        if not (web_root / file_name).exists():
            raise AssertionError(f"Missing editor web scaffold file: {file_name}")

    package_data = json.loads((web_root / "package.json").read_text(encoding="utf-8"))
    scripts = package_data.get("scripts", {})
    for script_name in ["dev", "build", "preview"]:
        if script_name not in scripts:
            raise AssertionError(f"Missing frontend npm script: {script_name}")

    allowed_dependencies = {"@a2ui/react", "@a2ui/web_core", "react", "react-dom", "zod"}
    actual_dependencies = set(package_data.get("dependencies", {}).keys())
    if actual_dependencies != allowed_dependencies:
        raise AssertionError(f"Unexpected frontend runtime dependencies: {actual_dependencies}")

    allowed_dev_dependencies = {
        "@playwright/test",
        "@types/react",
        "@types/react-dom",
        "@vitejs/plugin-react",
        "typescript",
        "vite",
    }
    actual_dev_dependencies = set(package_data.get("devDependencies", {}).keys())
    if actual_dev_dependencies != allowed_dev_dependencies:
        raise AssertionError(f"Unexpected frontend dev dependencies: {actual_dev_dependencies}")

    main_source = (web_root / "src/main.tsx").read_text(encoding="utf-8")
    expected_fragments = [
        "/documents/snapshot",
        "/documents/save",
        "/documents/assets",
        "/files",
        "command-bar",
        "file-sidebar",
        "ipxact_attachments",
        "attachedComponents",
        "No IP-XACT attached to this heading.",
        "closeFloatingMenus",
        "pointerdown",
        "contentEditable",
        "Actions ▾",
        "ReportSurface",
    ]
    for fragment in expected_fragments:
        if fragment not in main_source:
            raise AssertionError(f"Frontend source does not call expected API: {fragment}")


def test_editor_api_endpoints_with_synthetic_spec() -> None:
    """Test local FastAPI endpoints against a synthetic agent-spec file."""
    cont = container.AgentSpecArchive()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_fd)

    try:
        cont.save(temp_path)
        app = api_app.create_app()
        endpoints = {}
        for route in app.routes:
            route_path = getattr(route, "path", "")
            route_methods = getattr(route, "methods", set())
            for method in route_methods:
                endpoints[(method, route_path)] = route.endpoint

        snapshot = endpoints[("GET", "/documents/snapshot")](temp_path)
        groups = snapshot["document"]["section_groups"]
        if groups:
            raise AssertionError(f"Heading text should not create API section groups: {groups}")

        relation_payload = _version_relations_from_snapshot(
            editor_session.EditorSnapshot.model_validate(snapshot)
        )
        save_relations_payload = endpoints[("POST", "/documents/save")](
            temp_path,
            api_app.EditorSaveRequest(
                relations=relation_payload,
            ),
        )
        groups = save_relations_payload["document"]["section_groups"]
        if len(groups) != 1:
            raise AssertionError(f"Expected one explicit section group from API, got {groups}")

        group_id = groups[0]["group_id"]
        version_payload = endpoints[("POST", "/documents/active-section-versions")](
            temp_path,
            {group_id: "v2"},
        )
        if version_payload["document"]["section_groups"][0]["active_version"] != "v2":
            raise AssertionError("API did not persist active section version.")

        edit_payload = endpoints[("POST", "/documents/text-edits")](
            temp_path,
            {"block-1": "API updated intro."},
        )
        edited_blocks = edit_payload["document"]["blocks"]
        if edited_blocks[1]["text"] != "API updated intro.":
            raise AssertionError("API did not persist text edit.")

        preview_payload = endpoints[("POST", "/ipxact/preview")](
            api_app.IpxactXmlRequest(
                file_path="uart.xml",
                xml_text=SYNTHETIC_IPXACT_XML.decode("utf-8"),
            )
        )
        if preview_payload["interfaces"][0]["name"] != "apb_slave":
            raise AssertionError("API preview returned unexpected IP-XACT interface summary.")

        ipxact_payload = endpoints[("POST", "/documents/ipxact-xml")](
            temp_path,
            api_app.IpxactXmlRequest(
                file_path="uart.xml",
                xml_text=SYNTHETIC_IPXACT_XML.decode("utf-8"),
            ),
        )
        if len(ipxact_payload["ipxact_components"]) != 1:
            raise AssertionError("API did not persist imported IP-XACT XML.")

        save_payload = endpoints[("POST", "/documents/save")](
            temp_path,
            api_app.EditorSaveRequest.model_validate(
                {
                    "text_edits": {"block-1": "Explicit save intro."},
                    "relations": ipxact_payload["relations"],
                    "ipxact_xml_edits": {},
                }
            ),
        )
        if save_payload["document"]["blocks"][1]["text"] != "Explicit save intro.":
            raise AssertionError("Explicit save route did not apply text edits.")
        if "spec_data/agent-spec-editor/relations.json" not in container.AgentSpecArchive(temp_path).custom_files:
            raise AssertionError("Explicit save route did not persist relation metadata.")

        file_payload = endpoints[("GET", "/files")](str(Path(temp_path).parent))
        if not any(entry["name"] == Path(temp_path).name for entry in file_payload["entries"]):
            raise AssertionError(f"File browser did not list the synthetic agent-spec: {file_payload}")

        previous_cwd = Path.cwd()
        os.chdir("spec2gds/agent_spec/document/editor_web")
        try:
            generated_payload = endpoints[("GET", "/files")](api_app.GENERATED_SAMPLES_ALIAS)
        finally:
            os.chdir(previous_cwd)
        generated_files = {entry["name"] for entry in generated_payload["entries"]}
        if "synthetic_basic_with_ipxact.spec" not in generated_files:
            raise AssertionError(f"Generated samples were not listed from alias path: {generated_payload}")
        if any(entry["name"].endswith(".agent-spec-sidecar") for entry in generated_payload["entries"]):
            raise AssertionError(f"File browser should hide sidecar directories: {generated_payload}")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
