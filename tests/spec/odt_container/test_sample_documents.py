import zipfile

import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.editor_core.ipxact_view as ipxact_view
import spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.samples.build_sample_documents as sample_builder
import spec2gds.spec.odt_container.verifier as verifier


def _manager() -> manager.PluginManager:
    plugin_manager = manager.PluginManager()
    plugin_manager.register_plugin(json_plugin.SimpleJSONPlugin())
    plugin_manager.register_plugin(ipxact_plugin.IPXACTPlugin())
    return plugin_manager


def test_sample_documents_build_and_verify() -> None:
    """Test sample ODT documents can be generated with embedded IP-XACT."""
    generated_paths = sample_builder.build_samples()
    if len(generated_paths) < 3:
        raise AssertionError(f"Expected at least 3 sample documents, got {len(generated_paths)}")

    plugin_manager = _manager()
    for generated_path in generated_paths:
        if not generated_path.exists():
            raise AssertionError(f"Generated sample does not exist: {generated_path}")

        with zipfile.ZipFile(generated_path, "r") as archive:
            names = archive.namelist()
            if names[0] != "mimetype":
                raise AssertionError(f"mimetype is not first in {generated_path}")
            if "spec_data/ipxact/sample_component.xml" not in names:
                raise AssertionError(f"Sample IP-XACT payload missing from {generated_path}")
            ipxact_bytes = archive.read("spec_data/ipxact/sample_component.xml")
            summary = ipxact_view.extract_ipxact_summary(
                "spec_data/ipxact/sample_component.xml",
                ipxact_bytes,
            )
            if len(summary.interfaces) != 1:
                raise AssertionError(f"Expected one realistic interface in {generated_path}")
            interface = summary.interfaces[0]
            if interface.name != "apb_slave" or interface.mode != "slave":
                raise AssertionError(f"Unexpected interface in {generated_path}: {interface}")
            if interface.bus_type.name != "APB":
                raise AssertionError(f"Unexpected bus type in {generated_path}: {interface.bus_type}")
            if len(interface.port_maps) < 5:
                raise AssertionError(f"Expected APB port maps in {generated_path}: {interface.port_maps}")

        odt = container.HybridODTContainer(str(generated_path))
        report = verifier.ContainerVerifier(odt, plugin_manager).verify_all()
        if not report.is_fully_consistent:
            raise AssertionError(f"Generated sample failed verification: {report}")
