import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.ipxact_plugin as ipxact_plugin

# Dynamic valid/invalid XML schemas for testing 2009 and 2014 standards
VALID_IPXACT_2009 = """<?xml version="1.0" encoding="UTF-8"?>
<spirit:component xmlns:spirit="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009
                                      http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009/index.xsd">
  <spirit:vendor>acme</spirit:vendor>
  <spirit:library>local</spirit:library>
  <spirit:name>uart_2009</spirit:name>
  <spirit:version>1.0</spirit:version>
  <spirit:description>UART Controller in 1685-2009 standard</spirit:description>
</spirit:component>
"""

VALID_IPXACT_2014 = """<?xml version="1.0" encoding="UTF-8"?>
<ipxact:component xmlns:ipxact="http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.accellera.org/XMLSchema/IPXACT/1685-2014
                                      http://www.accellera.org/XMLSchema/IPXACT/1685-2014/index.xsd">
  <ipxact:vendor>acme</ipxact:vendor>
  <ipxact:library>local</ipxact:library>
  <ipxact:name>uart_2014</ipxact:name>
  <ipxact:version>1.0</ipxact:version>
  <ipxact:description>UART Controller in 1685-2014 standard</ipxact:description>
</ipxact:component>
"""

INVALID_IPXACT = """<?xml version="1.0" encoding="UTF-8"?>
<spirit:component xmlns:spirit="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  xsi:schemaLocation="http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009
                                      http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009/index.xsd">
  <!-- Missing vendor, library, name, version which violates the schema -->
  <spirit:description>Invalid Component</spirit:description>
</spirit:component>
"""

def test_ipxact_plugin_registration() -> None:
    """Test registering IPXACTPlugin in PluginManager."""
    pm = manager.PluginManager()
    plug = ipxact_plugin.IPXACTPlugin()
    pm.register_plugin(plug)

    if "ipxact" not in pm.list_plugins():
        raise AssertionError("ipxact plugin was not registered.")
    if pm.get_plugin("ipxact") is not plug:
        raise AssertionError("Failed to retrieve registered ipxact plugin.")

def test_ipxact_validation() -> None:
    """Test dynamic validation of both 2009 and 2014 IP-XACT payloads."""
    plug = ipxact_plugin.IPXACTPlugin()

    # 1. 2009 Validation
    if not plug.validate_data(VALID_IPXACT_2009.encode("utf-8")):
        raise AssertionError("Failed to validate correct 2009 XML.")

    # 2. 2014 Validation
    if not plug.validate_data(VALID_IPXACT_2014.encode("utf-8")):
        raise AssertionError("Failed to validate correct 2014 XML.")

    # 3. Invalid payload should fail
    failed = False
    try:
        plug.validate_data(INVALID_IPXACT.encode("utf-8"))
    except ValueError:
        failed = True
    if not failed:
        raise AssertionError("Should have failed schema validation for invalid XML.")

def test_ipxact_injection_extraction_and_resolution() -> None:
    """Test injection, extraction, and hybrid resolution of IP-XACT specs."""
    pm = manager.PluginManager()
    plug = ipxact_plugin.IPXACTPlugin()
    pm.register_plugin(plug)

    cont = container.HybridODTContainer()

    # 1. Inject 2014 payload
    pm.inject_payload(cont, "ipxact", "core.xml", VALID_IPXACT_2014.encode("utf-8"))

    # 2. Extract and verify parsing
    comp = pm.extract_payload(cont, "ipxact", "core.xml")
    if comp.VLNV.Name != "uart_2014":
        raise AssertionError(f"Expected Name 'uart_2014', got '{comp.VLNV.Name}'")

    # 3. Resolve logically (properties)
    vendor = pm.resolve_uri(cont, "spec://ipxact/core.xml/VLNV/Vendor")
    if vendor != "acme":
        raise AssertionError(f"Expected Vendor 'acme', got '{vendor}'")

    name = pm.resolve_uri(cont, "spec://ipxact/core.xml/VLNV/Name")
    if name != "uart_2014":
        raise AssertionError(f"Expected Name 'uart_2014', got '{name}'")

    # 4. Resolve via XPath fallback
    # Since logical resolution won't match lowercased xpath, it falls back to lxml xpath
    desc = pm.resolve_uri(cont, "spec://ipxact/core.xml//ipxact:description")
    if desc != "UART Controller in 1685-2014 standard":
        raise AssertionError(f"Expected description, got '{desc}'")

    # Invalid logical/XPath resolutions should raise KeyError
    failed = False
    try:
        pm.resolve_uri(cont, "spec://ipxact/core.xml/VLNV/NonExistent")
    except KeyError:
        failed = True
    if not failed:
        raise AssertionError("Expected KeyError for missing node.")
