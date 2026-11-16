"""Derived, cached Verilator validation for persisted SystemVerilog bodies.

Reviewer path: build validation context from declared ports and stored body,
run the configured Verilator check when available, and distinguish unavailable
validation from a successful lint. Diagnostics must preserve rejected drafts.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from spec2gds.spec.spec_format.ir import ComponentIR, DesignIR, SpecRevision
from spec2gds.spec.spec_format.naming import qualified_reference_name
from spec2gds.spec.spec_format.sections import SectionIR

_CACHE: dict[tuple[str, str, str, str, str], "SectionValidation"] = {}


def cached_revision_sections(revision: SpecRevision, section_ids: set[str] | None = None) -> tuple["SectionValidation", ...]:
    """Read checked results without finding or starting a compiler."""
    results = []
    for section in revision.entity_sections:
        if section.section_type != "sv" or section.usage != "implementation" or section_ids is not None and section.section_id not in section_ids:
            continue
        # A containing Design's lint cannot establish a leaf Section's status.
        found = next((result for key, result in reversed(tuple(_CACHE.items()))
                      if key[:3] == (section.section_id, section.source_sha256, revision.source_revision_hash)
                      and key[4] == "section"), None)
        results.append(found or SectionValidation(section.section_id, "unverified", ()))
    return tuple(results)
_SAFETY_WARNINGS = {
    "ALWCOMBORDER", "CASEINCOMPLETE", "CASEOVERLAP", "COMBDLY", "LATCH",
    "MULTIDRIVEN", "UNDRIVEN", "UNOPTFLAT", "WIDTH", "WIDTHCONCAT",
    "WIDTHEXPAND", "WIDTHTRUNC",
}
_DIAGNOSTIC = re.compile(
    r"^%(?P<severity>Error|Warning)(?:-(?P<code>[A-Z0-9_]+))?:\s*"
    r"(?:(?P<path>.*?):(?P<line>[0-9]+):(?P<column>[0-9]+):\s*)?(?P<message>.*)$"
)


class SectionDiagnostic:
    """JSON-friendly source diagnostic without coupling validation to Pydantic."""

    def __init__(self, code: str, message: str, line: int | None = None,
                 column: int | None = None, blocking: bool = False,
                 file_path: str | None = None, source_kind: str | None = None) -> None:
        self.code = code
        self.message = message
        self.line = line
        self.column = column
        self.blocking = blocking
        self.file_path = file_path
        self.source_kind = source_kind

    def as_json(self) -> dict[str, object]:
        """Serialize one diagnostic for API and document projections."""
        return {
            "code": self.code, "message": self.message, "line": self.line,
            "column": self.column, "blocking": self.blocking,
            "file_path": self.file_path, "source_kind": self.source_kind,
        }


class SectionValidation:
    """Derived validation status for one stable section identity."""

    def __init__(self, section_id: str, status: str,
                 diagnostics: tuple[SectionDiagnostic, ...]) -> None:
        self.section_id = section_id
        self.status = status
        self.diagnostics = diagnostics
        self.target_name = ""
        self.section_name = "SystemVerilog"

    @property
    def blocking(self) -> bool:
        """Report whether any diagnostic prevents the candidate from saving."""
        return any(item.blocking for item in self.diagnostics)

    def as_json(self) -> dict[str, object]:
        """Serialize aggregate validation status and ordered diagnostics."""
        return {
            "section_id": self.section_id,
            "target_name": self.target_name,
            "section_name": self.section_name,
            "status": self.status,
            "diagnostics": [item.as_json() for item in self.diagnostics],
        }


def validate_revision_sections(
    revision: SpecRevision, section_ids: set[str] | None = None, *, context: str = "hierarchy"
) -> tuple[SectionValidation, ...]:
    results = _validate_revision_sections(revision, section_ids, context=context)
    owners = {section.section_id: section.parent for section in revision.entity_sections}
    for result in results:
        result.target_name = qualified_reference_name(revision, owners[result.section_id])
    return results


def _validate_revision_sections(
    revision: SpecRevision, section_ids: set[str] | None = None, *, context: str = "hierarchy"
) -> tuple[SectionValidation, ...]:
    """Validate selected SV sections in generated context when Verilator exists."""
    sections = tuple(
        item for item in revision.entity_sections
        if item.section_type == "sv" and item.usage == "implementation" and (section_ids is None or item.section_id in section_ids)
    )
    if not sections:
        return ()
    executable = shutil.which("verilator")
    if executable is None:
        return tuple(_unverified(item, "VERILATOR_MISSING", "Verilator 5.x is not installed; the section was saved without RTL lint.") for item in sections)
    try:
        version = subprocess.run(
            [executable, "--version"], check=True, capture_output=True, text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return tuple(_unverified(item, "VERILATOR_UNAVAILABLE", "Verilator could not be started; the section was saved without RTL lint.") for item in sections)
    if not re.search(r"\b5\.", version):
        return tuple(_unverified(item, "VERILATOR_VERSION", f"{version or 'Unknown Verilator'} is not Verilator 5.x; lint was skipped.") for item in sections)

    results: list[SectionValidation] = []
    for section in sections:
        key = (section.section_id, section.source_sha256, revision.source_revision_hash, version, context)
        cached = _CACHE.get(key)
        if cached is not None:
            results.append(cached)
            continue
        result = _validate_one(revision, section, executable, context=context)
        if len(_CACHE) >= 512:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = result
        results.append(result)
    return tuple(results)


def _targets(revision: SpecRevision, section: SectionIR) -> tuple[DesignIR, ...]:
    if section.parent.entity_kind == "design":
        resolved = revision.resolve(section.parent)
        return (resolved,) if isinstance(resolved, DesignIR) else ()
    component = revision.resolve(section.parent)
    if not isinstance(component, ComponentIR):
        return ()
    internal = revision.internal_design(component)
    if internal is not None:
        return (internal,)
    return tuple(
        design for design in revision.designs
        if any(instance.component_vlnv == component.vlnv for instance in design.instances)
    )


def _validate_one(revision: SpecRevision, section: SectionIR, executable: str, *, context: str = "hierarchy") -> SectionValidation:
    # Imported lazily so the core transaction module does not create an
    # activities -> spec_format -> activities initialization cycle.
    from spec2gds.spec.activities.rtl.codegen import generate_project
    from spec2gds.spec.activities.view import SpecAccess

    entity = revision.resolve(section.parent)
    if context == "section" and isinstance(entity, ComponentIR) and revision.internal_design(entity) is None:
        return _lint_standalone_component(revision, section, executable)
    targets = _targets(revision, section)
    if not targets:
        return _lint_standalone_component(revision, section, executable)
    diagnostics: list[SectionDiagnostic] = []
    for target in targets:
        try:
            project = generate_project(SpecAccess(revision, target.ref), target.ref)
        except (KeyError, TypeError, ValueError) as exc:
            return _unverified(
                section, "RTL_PROFILE_UNSUPPORTED",
                f"The surrounding design is outside the supported wire-only RTL profile: {exc}",
            )
        diagnostics.extend(_run_project(project.files, project.top_module, executable, section))
    return _status(section, diagnostics)


def _lint_standalone_component(
    revision: SpecRevision, section: SectionIR, executable: str
) -> SectionValidation:
    entity = revision.resolve(section.parent)
    if not isinstance(entity, ComponentIR):
        return _unverified(section, "RTL_CONTEXT_UNAVAILABLE", "No generated module context is available for this section.")
    has_body = bool(section.content.strip())
    directions = {
        "in": "input logic" if has_body else "input wire",
        "out": "output logic" if has_body else "output wire",
        "inout": "inout wire",
    }
    ports: list[str] = []
    for port in entity.ports:
        if port.style != "wire" or not isinstance(port.width, (int, str)):
            return _unverified(section, "RTL_PROFILE_UNSUPPORTED", "The component uses ports outside the supported wire-only RTL profile.")
        range_text = "" if port.width == 1 else f" {port.width}"
        ports.append(f"    {directions[port.direction]}{range_text} {port.name}")
    from dataclasses import asdict

    from spec2gds.spec.spec_format.rtl_interface import module_declaration
    declaration = module_declaration("section_lint", [
        {"name": port.name, "direction": port.direction,
         "range": port.width[1:-1] if isinstance(port.width, str) else None}
        for port in entity.ports
    ], [asdict(parameter) for parameter in entity.parameters])
    scaffold: list[str] = []
    if not has_body:
        scaffold.extend(
            f"assign {port.name} = {'\'0' if port.direction == 'out' else '\'z'};"
            for port in entity.ports if port.direction in {"out", "inout"}
        )
    source = (
        declaration + f"\n`line 1 \"{section.source_path}\" 0\n"
        + section.content + "\n" + "\n".join(scaffold) + "\nendmodule\n"
    ).encode("utf-8")
    files = {"rtl/section_lint.sv": source, "rtl/files.f": b"section_lint.sv\n"}
    return _status(section, _run_project(files, "section_lint", executable, section))


def _run_project(
    files: dict[str, bytes], top_module: str, executable: str, section: SectionIR | None
) -> list[SectionDiagnostic]:
    try:
        with tempfile.TemporaryDirectory(prefix="spec2gds-sv-lint-") as temporary:
            root = Path(temporary)
            for path, data in files.items():
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
            completed = subprocess.run(
                [executable, "--lint-only", "--language", "1800-2017", "-Wall",
                 "-Wno-fatal", "--top-module", top_module, "-f", "files.f"],
                cwd=root / "rtl", capture_output=True, text=True, timeout=15,
            )
    except subprocess.TimeoutExpired:
        return [SectionDiagnostic("VERILATOR_TIMEOUT", "Verilator timed out; the section was saved without completed lint.")]
    except OSError as exc:
        return [SectionDiagnostic("VERILATOR_UNAVAILABLE", f"Verilator could not run: {exc}")]
    diagnostics: list[SectionDiagnostic] = []
    for line in (completed.stderr + "\n" + completed.stdout).splitlines():
        match = _DIAGNOSTIC.match(line.strip())
        if match is None:
            continue
        severity = match.group("severity")
        code = match.group("code") or ("VERILATOR_ERROR" if severity == "Error" else "VERILATOR_WARNING")
        blocking = severity == "Error" or code in _SAFETY_WARNINGS
        diagnostics.append(SectionDiagnostic(
            code, match.group("message").strip(),
            int(match.group("line")) if match.group("line") else None,
            int(match.group("column")) if match.group("column") else None,
            blocking,
            file_path=match.group("path"),
            source_kind="section" if section is not None and match.group("path") == section.source_path else "generated",
        ))
    if completed.returncode and not any(item.blocking for item in diagnostics):
        diagnostics.append(SectionDiagnostic(
            "VERILATOR_ERROR", "Verilator rejected the assembled RTL source.", blocking=True
        ))
    return diagnostics


def _unverified(section: SectionIR, code: str, message: str) -> SectionValidation:
    return SectionValidation(section.section_id, "unverified", (SectionDiagnostic(code, message),))


def _status(section: SectionIR, diagnostics: list[SectionDiagnostic]) -> SectionValidation:
    if any(item.code in {"VERILATOR_TIMEOUT", "VERILATOR_UNAVAILABLE"} for item in diagnostics):
        status = "unverified"
    elif any(item.blocking for item in diagnostics):
        status = "errors"
    elif diagnostics:
        status = "warnings"
    else:
        status = "verified"
    return SectionValidation(section.section_id, status, tuple(diagnostics))
