import pydantic
import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.verifier as verifier

def test_plugin_registration() -> None:
    """Test registering and retrieving plugins in PluginManager."""
    pm = manager.PluginManager()
    plug = json_plugin.SimpleJSONPlugin()
    pm.register_plugin(plug)

    if plug.config.modality_id not in pm.list_plugins():
        raise AssertionError("Plugin was not listed in registered modalities.")
    if pm.get_plugin("simple-json") is not plug:
        raise AssertionError("Failed to retrieve registered plugin instance.")

def test_json_validation() -> None:
    """Test valid and invalid JSON payloads against SimpleJSONPlugin."""
    plug = json_plugin.SimpleJSONPlugin()

    # Valid dictionary conforming to SimpleJSONSpecSchema
    valid_data = {
        "title": "UART Controller",
        "version": "1.0.0",
        "metadata": [
            {"name": "base_addr", "value": 0x4000, "description": "Base register address"},
            {"name": "baud_rate", "value": 115200}
        ]
    }
    
    if not plug.validate_data(valid_data):
        raise AssertionError("Failed to validate correct JSON structure.")

    # Invalid structure missing required 'title' field
    invalid_data = {
        "version": "1.0.0",
        "metadata": []
    }
    
    validation_failed = False
    try:
        plug.validate_data(invalid_data)
    except pydantic.ValidationError:
        validation_failed = True
        
    if not validation_failed:
        raise AssertionError("Pydantic validation failed to reject invalid JSON metadata structure.")

def test_json_injection_and_traversal() -> None:
    """Test injecting JSON payload, extracting it, and resolving paths."""
    pm = manager.PluginManager()
    plug = json_plugin.SimpleJSONPlugin()
    pm.register_plugin(plug)

    cont = container.HybridODTContainer()
    valid_data = {
        "title": "DMA Spec",
        "version": "2.1",
        "metadata": [
            {"name": "channels", "value": 8},
            {"name": "burst_mode", "value": "enabled"}
        ]
    }

    # Inject
    pm.inject_payload(cont, "simple-json", "dma.json", valid_data)

    # 1. Extract and verify value semantics deep copy
    extracted = pm.extract_payload(cont, "simple-json", "dma.json")
    if extracted["title"] != "DMA Spec":
        raise AssertionError("Extracted payload title does not match.")
    
    # Verify decoupled copy mutation doesn't affect cache
    extracted["title"] = "MUTATED"
    fresh_extracted = pm.extract_payload(cont, "simple-json", "dma.json")
    if fresh_extracted["title"] == "MUTATED":
        raise AssertionError("Extraction failed to enforce deep-copy value semantics.")

    # 2. Test JSON pointer path traversal
    val_title = pm.resolve_uri(cont, "spec://simple-json/dma.json/title")
    if val_title != "DMA Spec":
        raise AssertionError(f"Expected DMA Spec, got {val_title}")

    val_burst = pm.resolve_uri(cont, "spec://simple-json/dma.json/metadata/1/value")
    if val_burst != "enabled":
        raise AssertionError(f"Expected enabled, got {val_burst}")

def test_verifier_report() -> None:
    """Test verifier detects inconsistencies, unregistered files, and dangling spec links."""
    pm = manager.PluginManager()
    plug = json_plugin.SimpleJSONPlugin()
    pm.register_plugin(plug)

    cont = container.HybridODTContainer()
    valid_data = {
        "title": "DMA Spec",
        "version": "2.1",
        "metadata": [{"name": "channels", "value": 8}]
    }

    pm.inject_payload(cont, "simple-json", "dma.json", valid_data)

    # Add a mock hyperlink element inside content.xml to test link verification
    # Using odfdo Paragraph addition or direct set_part manipulation
    content_xml = cont.document.get_part("content.xml")
    
    # Let's insert a valid link and an invalid link into content.xml
    # For a high-integrity test, we can edit the raw content.xml string directly!
    content_bytes = content_xml.serialize()
    
    # Insert links before </office:text>
    valid_link = '<text:p><text:a xlink:type="simple" xlink:href="spec://simple-json/dma.json/title">Valid Link</text:a></text:p>'
    invalid_link = '<text:p><text:a xlink:type="simple" xlink:href="spec://simple-json/dma.json/metadata/99/value">Dangling Link</text:a></text:p>'
    
    modified_xml = content_bytes.replace(
        b"</office:text>",
        f"{valid_link}{invalid_link}</office:text>".encode("utf-8")
    )
    
    cont.document.set_part("content.xml", modified_xml)

    # Run verification
    engine = verifier.ContainerVerifier(cont, pm)
    report = engine.verify_all()

    # Verify report state
    if report.is_fully_consistent:
        raise AssertionError("Report should be inconsistent due to dangling link.")

    # There should be 1 injected file (which is valid and registered)
    if len(report.files) != 1:
        raise AssertionError(f"Expected 1 verified file, got {len(report.files)}")
    if not report.files[0].is_valid or not report.files[0].is_registered:
        raise AssertionError("Injected file should be valid and registered.")

    # There should be 2 verified links
    if len(report.links) != 2:
        raise AssertionError(f"Expected 2 verified links, got {len(report.links)}")

    # Valid link check
    valid_check = next(l for l in report.links if l.anchor_text == "Valid Link")
    if not valid_check.is_valid:
        raise AssertionError("Link to '/title' should resolve successfully.")

    # Dangling link check
    dangling_check = next(l for l in report.links if l.anchor_text == "Dangling Link")
    if dangling_check.is_valid:
        raise AssertionError("Link to '/metadata/99/value' should fail to resolve.")
