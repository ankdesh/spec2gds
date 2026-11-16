"""Explicit, revision-scoped lint for a manually authored hardware target."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict

from spec2gds.spec.spec_format.ir import ComponentIR, DesignIR, SpecRevision
from spec2gds.spec.spec_format.models import EntityRef
from spec2gds.spec.spec_format.sv_validation import validate_revision_sections


def verify_target(revision: SpecRevision, target: EntityRef) -> dict:
    """Check the saved target and its reachable implementations, never source text inferred from prose."""
    seen: set[str] = set()
    section_ids: set[str] = set()
    diagnostics: list[dict] = []
    interfaces: list[dict] = []

    def visit(entity: ComponentIR | DesignIR) -> None:
        if entity.ref.entity_id in seen:
            return
        seen.add(entity.ref.entity_id)
        sections = tuple(item for item in revision.entity_sections_for(entity.ref, "sv") if item.usage == "implementation")
        section_ids.update(section.section_id for section in sections)
        if isinstance(entity, ComponentIR):
            internal = revision.internal_design(entity)
            if internal is not None:
                visit(internal)
            elif not any(section.content.strip() for section in sections):
                diagnostics.append({"code": "IMPLEMENTATION_MISSING", "message": f"{entity.display_name or entity.vlnv} has no implementation.", "blocking": True})
            else:
                from spec2gds.spec.spec_format.rtl_interface import resolve_interface
                try:
                    interface = resolve_interface(
                        [{"name": port.name, "direction": port.direction,
                          "range": port.width[1:-1] if isinstance(port.width, str) else None}
                         for port in entity.ports if port.style == "wire"],
                        [asdict(parameter) for parameter in entity.parameters],
                        "\n".join(section.content for section in sections),
                    )
                    interfaces.append({"component": entity.display_name or entity.vlnv, **interface})
                    diagnostics.extend(interface["diagnostics"])
                except (ValueError, OSError, subprocess.SubprocessError) as exc:
                    diagnostics.append({"code": "INTERFACE_UNRESOLVED", "message": str(exc), "blocking": True})
        else:
            for instance in entity.instances:
                visit(revision.by_vlnv("component", instance.component_vlnv))

    entity = revision.resolve(target)
    if not isinstance(entity, (ComponentIR, DesignIR)):
        raise ValueError("Select a Component or Design to verify.")
    visit(entity)
    sections = validate_revision_sections(revision, section_ids, context="section")
    diagnostics.extend(item.as_json() for result in sections for item in result.diagnostics)
    if not sections:
        diagnostics.append({"code": "NO_IMPLEMENTATION", "message": "No SystemVerilog implementation is available to lint.", "blocking": True})
    executable = shutil.which("verilator")
    try:
        version = subprocess.run([executable, "--version"], capture_output=True, text=True, check=True, timeout=5).stdout.strip() if executable else "Unavailable"
    except (OSError, subprocess.SubprocessError):
        version = "Unavailable"
    hierarchy_checked = False
    if executable and sections and all(item.status in {"verified", "warnings"} for item in sections):
        # Check the selected hierarchy separately from its leaf implementations.
        from spec2gds.spec.activities.rtl.codegen import generate_project
        from spec2gds.spec.activities.view import SpecAccess
        from spec2gds.spec.spec_format.sv_validation import _run_project
        try:
            project = generate_project(SpecAccess(revision, target), target)
            checked = _run_project(project.files, project.top_module, executable, None)
            diagnostics.extend(item.as_json() for item in checked)
            hierarchy_checked = not any(item.code in {"VERILATOR_TIMEOUT", "VERILATOR_UNAVAILABLE"} for item in checked)
        except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as exc:
            diagnostics.append({"code": "TARGET_HIERARCHY_INVALID", "message": str(exc), "blocking": True})
    passed = hierarchy_checked and not any(item.get("blocking") for item in diagnostics) and all(
        item.status in {"verified", "warnings"} for item in sections
    )
    return {"target": target.model_dump(mode="json"), "source_revision_hash": revision.source_revision_hash,
            "status": "passed" if passed else "failed" if any(item.get("blocking") for item in diagnostics) else "unverified",
            "tool_version": version, "diagnostics": diagnostics,
            "interfaces": interfaces,
            "section_validation": [item.as_json() for item in sections], "functional_simulation": "unverified"}
