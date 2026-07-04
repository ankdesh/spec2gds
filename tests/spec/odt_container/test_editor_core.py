import os
import json
import tempfile
from pathlib import Path

import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.api.app as api_app
import spec2gds.spec.odt_container.editor_core.document as editor_document
import spec2gds.spec.odt_container.editor_core.ipxact_view as ipxact_view
import spec2gds.spec.odt_container.editor_core.session as editor_session
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.verifier as verifier


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
    """Test semantic parsing and adjacent heading version grouping."""
    parsed = editor_document.parse_content_xml(SYNTHETIC_CONTENT_XML)

    if parsed.has_blocking_diagnostics:
        raise AssertionError(f"Unexpected diagnostics: {parsed.diagnostics}")
    if len(parsed.blocks) != 9:
        raise AssertionError(f"Expected 9 semantic blocks, got {len(parsed.blocks)}")
    if len(parsed.section_groups) != 1:
        raise AssertionError(f"Expected 1 section version group, got {len(parsed.section_groups)}")

    group = parsed.section_groups[0]
    if group.title != "Bus behavior":
        raise AssertionError(f"Unexpected section title: {group.title}")
    versions = [variant.version for variant in group.variants]
    if versions != ["v1", "v2"]:
        raise AssertionError(f"Unexpected variants: {versions}")
    if group.active_version != "v1":
        raise AssertionError(f"Expected default active version v1, got {group.active_version}")


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
    """Test v1 editor session over a synthetic ODT container."""
    cont = container.HybridODTContainer()
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

    group = snapshot.document.section_groups[0]
    session.persist_active_versions({group.group_id: "v2"})
    updated_snapshot = session.snapshot()
    if updated_snapshot.document.section_groups[0].active_version != "v2":
        raise AssertionError("Active section version was not persisted in session state.")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".odt")
    os.close(temp_fd)
    try:
        session.save(temp_path)
        reloaded = editor_session.EditorSession.from_path(temp_path)
        reloaded_snapshot = reloaded.snapshot()
        if reloaded_snapshot.document.section_groups[0].active_version != "v2":
            raise AssertionError("Active section version did not survive ODT save/reload.")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_editor_session_blocks_save_on_unresolved_spec_link() -> None:
    """Test the v1 save gate blocks unresolved spec:// diagnostics."""
    cont = container.HybridODTContainer()
    cont.document.set_part("content.xml", SYNTHETIC_LINK_CONTENT_XML)
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()

    if not snapshot.has_blocking_diagnostics:
        raise AssertionError("Unresolved spec link should produce a blocking diagnostic.")

    temp_fd, temp_path = tempfile.mkstemp(suffix=".odt")
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
    cont = container.HybridODTContainer()
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
    cont = container.HybridODTContainer()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    session = editor_session.EditorSession(cont)
    snapshot = session.snapshot()
    group = snapshot.document.section_groups[0]
    session.persist_active_versions({group.group_id: "v2"})

    pm = manager.PluginManager()
    report = verifier.ContainerVerifier(cont, pm).verify_all()
    if not report.is_fully_consistent:
        raise AssertionError(f"Editor metadata should verify cleanly: {report}")


def test_editor_web_scaffold_is_minimal_and_present() -> None:
    """Test minimal frontend scaffold files and dependency policy."""
    web_root = Path("spec2gds/spec/odt_container/editor_web")
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

    allowed_dependencies = {"react", "react-dom"}
    actual_dependencies = set(package_data.get("dependencies", {}).keys())
    if actual_dependencies != allowed_dependencies:
        raise AssertionError(f"Unexpected frontend runtime dependencies: {actual_dependencies}")

    allowed_dev_dependencies = {
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
        "/documents/text-edits",
        "/documents/active-section-versions",
        "/ipxact/preview",
        "/documents/ipxact-xml",
    ]
    for fragment in expected_fragments:
        if fragment not in main_source:
            raise AssertionError(f"Frontend source does not call expected API: {fragment}")


def test_editor_api_endpoints_with_synthetic_odt() -> None:
    """Test local FastAPI endpoints against a synthetic ODT file."""
    cont = container.HybridODTContainer()
    cont.document.set_part("content.xml", SYNTHETIC_CONTENT_XML)
    temp_fd, temp_path = tempfile.mkstemp(suffix=".odt")
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
        if len(groups) != 1:
            raise AssertionError(f"Expected one section group from API, got {groups}")

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
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
