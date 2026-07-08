import json
import zipfile

import benchmarks.agent_spec.hw_docs.build_benchmark as hw_docs_benchmark
import spec2gds.agent_spec.document.relations as relations
import spec2gds.agent_spec.document.session as editor_session
import spec2gds.agent_spec.package.archive as archive
import spec2gds.agent_spec.plugins.ipxact as ipxact_plugin


def test_hw_docs_benchmark_builds_loadable_spec_files() -> None:
    """Build benchmark `.spec` files and verify embedded XML attachments load."""
    manifest = hw_docs_benchmark.build_benchmark()
    if len(manifest["cases"]) != 6:
        raise AssertionError(f"Expected 6 hardware-doc benchmark cases: {manifest}")

    manifest_path = hw_docs_benchmark.MANIFEST_PATH
    persisted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if persisted_manifest != manifest:
        raise AssertionError("Persisted benchmark manifest does not match build output.")

    for case in manifest["cases"]:
        files = case["files"]
        for relative_path in files.values():
            path = hw_docs_benchmark.BENCHMARK_ROOT / relative_path
            if not path.exists():
                raise AssertionError(f"Benchmark file missing: {path}")

        spec_path = hw_docs_benchmark.BENCHMARK_ROOT / files["spec"]
        ipxact_path = case["ipxact_container_path"]
        with zipfile.ZipFile(spec_path, "r") as package:
            names = package.namelist()
            if names[0] != "mimetype":
                raise AssertionError(f"mimetype is not first in {spec_path}")
            if ipxact_path not in names:
                raise AssertionError(f"Embedded XML missing from {spec_path}: {ipxact_path}")
            if relations.RELATIONS_PATH not in names:
                raise AssertionError(f"Editor relation metadata missing from {spec_path}")

        spec_archive = archive.AgentSpecArchive(str(spec_path))
        session = editor_session.EditorSession(spec_archive)
        snapshot = session.snapshot()
        if len(snapshot.ipxact_components) != 1:
            raise AssertionError(f"Expected one embedded XML summary in {spec_path}")
        if not snapshot.ipxact_components[0].component.name:
            raise AssertionError(f"Embedded XML summary has no component name in {spec_path}")
        attachments = snapshot.relations.ipxact_attachments.get(case["attached_heading_id"], [])
        if not attachments or attachments[0].file_path != ipxact_path:
            raise AssertionError(f"IP-XACT relation missing from {spec_path}: {attachments}")

        if not case["strict_ipxact_schema_valid"]:
            raise AssertionError(f"Benchmark XML should be strict IP-XACT: {case}")
        if case["semantic_interface_count"] < 1:
            raise AssertionError("Benchmark XML should expose formal bus interfaces.")
        if snapshot.ipxact_components[0].diagnostics:
            raise AssertionError(f"Benchmark XML should have no IP-XACT diagnostics: {snapshot.ipxact_components[0].diagnostics}")
        if any(item.name == "component_ports" for item in snapshot.ipxact_components[0].interfaces):
            raise AssertionError(f"Benchmark XML must not rely on component-port fallback: {spec_path}")
        xml_path = hw_docs_benchmark.BENCHMARK_ROOT / files["ipxact_xml"]
        ipxact_plugin.IPXACTPlugin().validate_data(xml_path.read_bytes())
