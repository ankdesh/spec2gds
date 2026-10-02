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

from spec2gds.agent_spec.spec_format.ir import ComponentIR, DesignIR, SpecRevision
from spec2gds.agent_spec.spec_format.sections import EntitySectionIR

_CACHE: dict[tuple[str, str, str, str], "SectionValidation"] = {}
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
                 column: int | None = None, blocking: bool = False) -> None:
        self.code = code
        self.message = message
        self.line = line
        self.column = column
        self.blocking = blocking

    def as_json(self) -> dict[str, object]:
        """Serialize one diagnostic for API and document projections."""
        return {
            "code": self.code, "message": self.message, "line": self.line,
            "column": self.column, "blocking": self.blocking,
        }


class SectionValidation:
    """Derived validation status for one stable section identity."""

    def __init__(self, section_id: str, status: str,
                 diagnostics: tuple[SectionDiagnostic, ...]) -> None:
        self.section_id = section_id
        self.status = status
        self.diagnostics = diagnostics

    @property
    def blocking(self) -> bool:
        """Report whether any diagnostic prevents the candidate from saving."""
        return any(item.blocking for item in self.diagnostics)

    def as_json(self) -> dict[str, object]:
        """Serialize aggregate validation status and ordered diagnostics."""
        return {
            "section_id": self.section_id,
            "status": self.status,
            "diagnostics": [item.as_json() for item in self.diagnostics],
        }


def validate_revision_sections(
    revision: SpecRevision, section_ids: set[str] | None = None
) -> tuple[SectionValidation, ...]:
    """Validate selected SV sections in generated context when Verilator exists."""
    sections = tuple(
        item for item in revision.entity_sections
        if item.section_type == "sv" and (section_ids is None or item.section_id in section_ids)
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
        key = (section.section_id, section.source_sha256, revision.source_revision_hash, version)
        cached = _CACHE.get(key)
        if cached is not None:
            results.append(cached)
            continue
        result = _validate_one(revision, section, executable)
        _CACHE[key] = result
        results.append(result)
    return tuple(results)


def _targets(revision: SpecRevision, section: EntitySectionIR) -> tuple[DesignIR, ...]:
    if section.owner.entity_kind == "design":
        resolved = revision.resolve(section.owner)
        return (resolved,) if isinstance(resolved, DesignIR) else ()
    component = revision.resolve(section.owner)
    if not isinstance(component, ComponentIR):
        return ()
    internal = revision.internal_design(component)
    if internal is not None:
        return (internal,)
    return tuple(
        design for design in revision.designs
        if any(instance.component_vlnv == component.vlnv for instance in design.instances)
    )


def _validate_one(revision: SpecRevision, section: EntitySectionIR, executable: str) -> SectionValidation:
    # Imported lazily so the core transaction module does not create an
    # activities -> spec_format -> activities initialization cycle.
    from spec2gds.agent_spec.activities.rtl.codegen import generate_project
    from spec2gds.agent_spec.activities.view import SpecAccess

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
    revision: SpecRevision, section: EntitySectionIR, executable: str
) -> SectionValidation:
    entity = revision.resolve(section.owner)
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
    declaration = "module section_lint;"
    if ports:
        declaration = "module section_lint (\n" + ",\n".join(ports) + "\n);"
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
    files: dict[str, bytes], top_module: str, executable: str, section: EntitySectionIR
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
        ))
    if completed.returncode and not any(item.blocking for item in diagnostics):
        diagnostics.append(SectionDiagnostic(
            "VERILATOR_ERROR", "Verilator rejected the assembled RTL source.", blocking=True
        ))
    return diagnostics


def _unverified(section: EntitySectionIR, code: str, message: str) -> SectionValidation:
    return SectionValidation(section.section_id, "unverified", (SectionDiagnostic(code, message),))


def _status(section: EntitySectionIR, diagnostics: list[SectionDiagnostic]) -> SectionValidation:
    if any(item.code in {"VERILATOR_TIMEOUT", "VERILATOR_UNAVAILABLE"} for item in diagnostics):
        status = "unverified"
    elif any(item.blocking for item in diagnostics):
        status = "errors"
    elif diagnostics:
        status = "warnings"
    else:
        status = "verified"
    return SectionValidation(section.section_id, status, tuple(diagnostics))
