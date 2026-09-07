from __future__ import annotations

import sys
from pathlib import Path

from spec2gds.agent_spec.spec_format.archive import SpecPackage
from spec2gds.agent_spec.spec_format.models import EntityRef

# Usage:
# python scripts/gen_spec.py output.spec top.xml component1.xml component2.xml

output = Path(sys.argv[1])
design_xml = Path(sys.argv[2])
component_xmls = [Path(value) for value in sys.argv[3:]]

package = SpecPackage.create(
    document_id="spec_raw_ipxact_test",
    title="Raw IP-XACT RTL test",
)

for component_path in component_xmls:
    package.add_document("component", component_path.read_bytes())

design = package.add_document("design", design_xml.read_bytes())

package.manifest = package.manifest.model_copy(
    update={
        "entry_designs": [
            EntityRef(
                document_id=package.manifest.document_id,
                entity_id=design.entity_id,
                entity_kind="design",
            )
        ]
    }
)

package.require_valid()
package.save(str(output))

print(f"Created {output}")
