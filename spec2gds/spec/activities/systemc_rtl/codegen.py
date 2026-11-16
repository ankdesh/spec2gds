"""Independent Spec-to-CIRCT preparation and native SystemC project assembly."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from spec2gds.spec.activities.view import SpecAccess
from spec2gds.spec.spec_format.ir import ComponentIR, DesignIR, PortIR
from spec2gds.spec.spec_format.models import EntityRef, sha256_digest
from spec2gds.spec.spec_format.naming import entity_name
from spec2gds.spec.spec_format.sections import SectionIR

ACTIVITY_ID = "systemc.generate_cycle_accurate"
ACTIVITY_VERSION = "1.0.0"
GENERATION_SCHEMA = "spec2gds.systemc-cycle-accurate-generation.v1"
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*\Z")
_RANGE = re.compile(r"\[\s*(-?\d+)\s*:\s*(-?\d+)\s*\]\Z")
_CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "char8_t char16_t char32_t class compl concept const consteval constexpr "
    "constinit const_cast continue co_await co_return co_yield decltype default "
    "delete do double dynamic_cast else enum explicit export extern false float for "
    "friend goto if inline int long mutable namespace new noexcept not not_eq "
    "nullptr operator or or_eq private protected public register reinterpret_cast "
    "requires return short signed sizeof static static_assert static_cast struct "
    "switch template this thread_local throw true try typedef typeid typename union "
    "unsigned using virtual void volatile wchar_t while xor xor_eq".split()
)
_UNSUPPORTED_VALUES = re.compile(
    r"(?:\b\d*'[bBoOdDhH][0-9a-fA-F_?]*[xXzZ][0-9a-fA-F_?xXzZ]*\b|\B'[xXzZ]\b)"
)


@dataclass(frozen=True)
class PreparedProject:
    source_files: dict[str, bytes]
    top_module: str
    top_ports: tuple[tuple[str, str, int], ...]
    design_vlnv: str
    component_count: int
    instance_count: int
    connection_count: int
    source_sections: tuple[dict[str, str], ...]
    display_name: str = "Design"


@dataclass(frozen=True)
class GeneratedProject:
    files: dict[str, bytes]
    top_module: str
    design_vlnv: str
    component_count: int
    instance_count: int
    connection_count: int
    source_sections: tuple[dict[str, str], ...]
    tool_versions: dict[str, str]


def _port_width(port: PortIR) -> tuple[int, str]:
    if port.style != "wire" or port.direction not in {"in", "out"}:
        raise ValueError(f"Port {port.name!r} must be a physical input or output wire.")
    if port.width == 1:
        return 1, ""
    if not isinstance(port.width, str) or (match := _RANGE.fullmatch(port.width)) is None:
        raise ValueError(f"Port {port.name!r} has an unsupported symbolic range.")
    left, right = map(int, match.groups())
    width = abs(left - right) + 1
    if width < 1 or width > 64:
        raise ValueError(f"Port {port.name!r} width must be from 1 to 64 bits.")
    return width, f"[{left}:{right}]"


def _name(raw: str, prefix: str) -> str:
    normalized = re.sub(r"[^A-Za-z_0-9]", "_", raw)
    if not normalized or normalized[0].isdigit():
        normalized = f"{prefix}_{normalized}"
    return normalized


def _checked_identifier(name: str, description: str) -> None:
    generated_collision = (
        name == "update_comb"
        or re.fullmatch(r"(?:state|update_state|child)_\d+(?:_(?:in|out)_\d+)?", name)
        is not None
    )
    if (
        not _IDENTIFIER.fullmatch(name)
        or name in _CPP_KEYWORDS
        or name in {"sc_core", "sc_dt", "SC_MODULE", "SC_CTOR", "SC_METHOD"}
        or name.startswith("__")
        or (len(name) > 1 and name[0] == "_" and name[1].isupper())
        or generated_collision
    ):
        raise ValueError(f"{description} {name!r} must be a plain C++/SystemVerilog identifier.")


def _section_text(section: SectionIR | None) -> str:
    if section is None or not section.content.strip():
        return ""
    if _UNSUPPORTED_VALUES.search(section.content):
        raise ValueError(f"Section {section.section_id} uses X/Z or unknown-valued literals.")
    return (
        f"`line 1 \"{section.source_path}\" 0\n"
        + section.content.rstrip()
        + "\n"
    )


class _Assembler:
    def __init__(self, spec: SpecAccess, target: EntityRef) -> None:
        self.spec = spec
        self.target = target
        self.components = {item.vlnv: item for item in spec.low.components}
        self.components_by_id = {item.ref.entity_id: item for item in spec.low.components}
        self.owner_by_design = {
            item.internal_design.entity_id: self.components_by_id[item.component.entity_id]
            for item in spec.low.manifest.component_compositions
        }
        self.sections = {
            (item.parent.entity_kind, item.parent.entity_id): item
            for item in spec.low.entity_sections
            if item.section_type == "sv" and item.usage == "implementation"
        }
        self.files: dict[str, bytes] = {}
        self.section_records: list[dict[str, str]] = []
        self.done: set[str] = set()
        self.visiting: set[str] = set()
        self.component_count = 0
        self.instance_count = 0
        self.connection_count = 0

    def prepare(self) -> PreparedProject:
        design = self.spec.low.resolve(self.target)
        if not isinstance(design, DesignIR):
            raise ValueError("Cycle-accurate generation requires a selected design.")
        owner = self.owner_by_design.get(design.ref.entity_id)
        if owner is None:
            self._emit_design(design, None)
            top = self._design_name(design)
            top_ports: tuple[tuple[str, str, int], ...] = ()
        else:
            self._emit_component(owner)
            top = self._component_name(owner)
            top_ports = tuple(
                (p.name, p.direction, _port_width(p)[0]) for p in owner.ports
            )
        return PreparedProject(
            source_files=self.files,
            top_module=top,
            top_ports=top_ports,
            design_vlnv=design.vlnv,
            component_count=self.component_count,
            instance_count=self.instance_count,
            connection_count=self.connection_count,
            source_sections=tuple(self.section_records),
            display_name=entity_name(design),
        )

    @staticmethod
    def _component_name(component: ComponentIR) -> str:
        return "spec_component_" + _name(component.ref.entity_id, "component")

    @staticmethod
    def _design_name(design: DesignIR) -> str:
        return "spec_design_" + _name(design.ref.entity_id, "design")

    def _emit_component(self, component: ComponentIR) -> None:
        key = component.ref.entity_id
        if key in self.done:
            return
        if key in self.visiting:
            raise ValueError(f"Component hierarchy contains a cycle at {entity_name(component)}.")
        self.visiting.add(key)
        if component.interfaces:
            raise ValueError(f"Component {entity_name(component)} has unsupported bus interfaces.")
        for port in component.ports:
            _port_width(port)
            _checked_identifier(port.name, "Port")
        internal = self.spec.low.internal_design(component)
        if internal is None:
            body = self.sections.get(("component", key))
            if body is None or not body.content.strip():
                raise ValueError(f"Leaf component {entity_name(component)} has no SystemVerilog body.")
            self._write_module(self._component_name(component), component, "", (body,))
        else:
            self._emit_design(internal, component)
        self.component_count += 1
        self.visiting.remove(key)
        self.done.add(key)

    def _emit_design(self, design: DesignIR, owner: ComponentIR | None) -> None:
        for instance in design.instances:
            component = self.components.get(instance.component_vlnv)
            if component is None:
                raise ValueError(f"Unknown component {instance.component_vlnv}.")
            self._emit_component(component)
        if owner is not None:
            module_name = self._component_name(owner)
            component_body = self.sections.get(("component", owner.ref.entity_id))
        else:
            module_name = self._design_name(design)
            component_body = None
        design_body = self.sections.get(("design", design.ref.entity_id))
        structure = self._structure(design, owner)
        self._write_module(module_name, owner, structure, (component_body, design_body))

    def _structure(self, design: DesignIR, owner: ComponentIR | None) -> str:
        """Emit structural wiring only for the supported direct-wire hierarchy.

        Reject ambiguous endpoints, slices, widths and drivers before invoking CIRCT.
        Behavior comes from stored SystemVerilog, not inferred SystemC callbacks.
        """
        instances = {item.name: item for item in design.instances}
        for name in instances:
            _checked_identifier(name, "Instance")
        hookups: dict[tuple[str, str], str] = {}
        claimed: set[tuple[str, str]] = set()
        net_lines: list[str] = []
        for index, connection in enumerate(design.connections):
            if connection.kind != "ad_hoc" or connection.interface_endpoints or connection.hierarchy_interfaces:
                raise ValueError(f"Connection {connection.name!r} is not an ad-hoc wire connection.")
            if len(connection.external_ports) > 1:
                raise ValueError(f"Connection {connection.name!r} has multiple boundary ports.")
            if connection.external_ports and owner is None:
                raise ValueError(f"Connection {connection.name!r} exposes an unowned design boundary.")
            members: list[tuple[str, str, str, int]] = []
            for endpoint in connection.port_endpoints:
                if endpoint.slice or endpoint.symbolic_slice:
                    raise ValueError(f"Connection {connection.name!r} uses an unsupported port slice.")
                instance = instances.get(endpoint.instance_name)
                if instance is None:
                    raise ValueError(f"Unknown connection instance {endpoint.instance_name!r}.")
                component = self.components[instance.component_vlnv]
                port = next((p for p in component.ports if p.name == endpoint.port_name), None)
                if port is None:
                    raise ValueError(f"Unknown port {endpoint.port_name!r}.")
                key = (endpoint.instance_name, endpoint.port_name)
                if key in claimed:
                    raise ValueError(f"Port {key!r} occurs in multiple connections.")
                claimed.add(key)
                members.append((endpoint.instance_name, port.name, port.direction, _port_width(port)[0]))
            external = connection.external_ports[0] if connection.external_ports else None
            if external is not None:
                if external.slice or external.symbolic_slice:
                    raise ValueError(f"Connection {connection.name!r} uses a boundary slice.")
                assert owner is not None
                port = next((p for p in owner.ports if p.name == external.port_name), None)
                if port is None:
                    raise ValueError(f"Unknown boundary port {external.port_name!r}.")
                members.append(("", port.name, "out" if port.direction == "in" else "in", _port_width(port)[0]))
            widths = {member[3] for member in members}
            if len(widths) != 1 or not widths:
                raise ValueError(f"Connection {connection.name!r} has mismatched or missing widths.")
            drivers = [member for member in members if member[2] == "out"]
            sinks = [member for member in members if member[2] == "in"]
            if len(drivers) != 1 or not sinks:
                raise ValueError(f"Connection {connection.name!r} needs one driver and at least one sink.")
            source = drivers[0]
            if source[0] == "":
                expression = source[1]
            else:
                expression = f"spec_net_{index}"
                width = next(iter(widths))
                net_lines.append(f"wire {'[' + str(width - 1) + ':0] ' if width > 1 else ''}{expression};")
            for member in members:
                if member[0]:
                    hookups[(member[0], member[1])] = expression
                elif member != source:
                    net_lines.append(f"assign {member[1]} = {expression};")
            self.connection_count += 1
        instance_lines: list[str] = []
        for instance in design.instances:
            component = self.components[instance.component_vlnv]
            bindings: list[str] = []
            for port in component.ports:
                expression = hookups.get((instance.name, port.name))
                if expression is None:
                    if port.direction == "in":
                        expression = "'0"
                    else:
                        expression = f"spec_unused_{_name(instance.name, 'i')}_{_name(port.name, 'p')}"
                        width = _port_width(port)[0]
                        net_lines.append(
                            f"wire {'[' + str(width - 1) + ':0] ' if width > 1 else ''}{expression};"
                        )
                bindings.append(f".{port.name}({expression})")
            instance_lines.append(
                f"{self._component_name(component)} {instance.name} ("
                + ", ".join(bindings)
                + ");"
            )
            self.instance_count += 1
        return "\n".join((*net_lines, *instance_lines))

    def _write_module(
        self,
        name: str,
        component: ComponentIR | None,
        structure: str,
        sections: tuple[SectionIR | None, ...],
    ) -> None:
        ports = component.ports if component is not None else ()
        has_body = any(item is not None and item.content.strip() for item in sections)
        declarations = []
        for port in ports:
            _, range_text = _port_width(port)
            direction = "input" if port.direction == "in" else "output"
            wire_kind = "logic" if has_body else "wire"
            declarations.append(f"{direction} {wire_kind} {range_text} {port.name}".replace("  ", " "))
        header = f"module {name}" + (" (" + ", ".join(declarations) + ")" if declarations else "") + ";\n"
        path = f"source/{name}.sv"
        body = structure + ("\n" if structure else "")
        for section in sections:
            if section is None or not section.content.strip():
                continue
            body += _section_text(section)
            self.section_records.append({
                "section_id": section.section_id,
                "sha256": section.source_sha256,
                "source_path": section.source_path,
                "output_path": path,
            })
        self.files[path] = (header + body + "endmodule\n").encode("utf-8")


def prepare_project(spec: SpecAccess, target: EntityRef) -> PreparedProject:
    """Normalize only the supported, two-state Spec profile into complete SV."""
    return _Assembler(spec, target).prepare()


def _tool_paths() -> tuple[Path, Path]:
    raw = os.environ.get("CIRCT_PREFIX")
    if not raw:
        raise ValueError("Set CIRCT_PREFIX to a pinned CIRCT installation.")
    prefix = Path(raw).expanduser()
    frontend = prefix / "bin" / "circt-verilog"
    emitter = prefix / "bin" / "spec2gds-systemc-emit"
    for tool in (frontend, emitter):
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise ValueError(f"Required compiler executable is missing: {tool}")
    return frontend, emitter


def _run(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"Compiler failed to start or timed out: {args[0]}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"Compiler {Path(args[0]).name} rejected the design: {detail}")
    return result


def _compile(prepared: PreparedProject) -> tuple[bytes, dict[str, str]]:
    frontend, emitter = _tool_paths()
    versions = {
        "circt": _run([str(frontend), "--version"], timeout=10).stdout.strip(),
        "systemc_emitter": _run([str(emitter), "--version"], timeout=10).stdout.strip(),
    }
    with tempfile.TemporaryDirectory(prefix="spec2gds-systemc-rtl-") as scratch:
        root = Path(scratch)
        sources: list[str] = []
        for name, data in prepared.source_files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            sources.append(str(path))
        mlir = root / "design.mlir"
        header = root / "design.h"
        _run([
            str(frontend), *sources, "--top", prepared.top_module,
            "-g", "--mlir-print-debuginfo", "-o", str(mlir),
        ])
        _run([str(emitter), "--input", str(mlir), "--output", str(header), "--top", prepared.top_module])
        if not header.is_file() or not header.read_bytes():
            raise ValueError("SystemC emitter produced no module header.")
        return header.read_bytes(), versions


def validate_project(spec: SpecAccess, target: EntityRef, *, check_compiler: bool = True) -> tuple[str, ...]:
    """Reject unsupported source and toolchains before a workspace is touched."""
    try:
        prepared = prepare_project(spec, target)
        if check_compiler:
            _compile(prepared)
        else:
            _tool_paths()
    except (KeyError, TypeError, ValueError) as exc:
        return (str(exc),)
    return ()


def generate_project(spec: SpecAccess, target: EntityRef) -> GeneratedProject:
    prepared = prepare_project(spec, target)
    header, versions = _compile(prepared)
    files = dict(prepared.source_files)
    files["include/design.h"] = header
    files["src/main.cpp"] = _smoke_main(prepared).encode("utf-8")
    files["CMakeLists.txt"] = _cmake(prepared).encode("utf-8")
    files["README.md"] = _project_readme(prepared).encode("utf-8")
    manifest = {
        "schema_version": GENERATION_SCHEMA,
        "activity_id": ACTIVITY_ID,
        "activity_version": ACTIVITY_VERSION,
        "document_id": target.document_id,
        "design_id": target.entity_id,
        "source_revision_hash": spec.high.document["source_revision_hash"],
        "top_module": prepared.top_module,
        "tool_versions": versions,
        "source_sections": prepared.source_sections,
        "files": [
            {"path": path, "sha256": sha256_digest(data), "size": len(data)}
            for path, data in sorted(files.items())
        ],
    }
    files["generation-manifest.json"] = (
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    return GeneratedProject(
        files=files,
        top_module=prepared.top_module,
        design_vlnv=prepared.design_vlnv,
        component_count=prepared.component_count,
        instance_count=prepared.instance_count,
        connection_count=prepared.connection_count,
        source_sections=prepared.source_sections,
        tool_versions=versions,
    )


def _systemc_type(width: int) -> str:
    return "bool" if width == 1 else f"sc_dt::sc_uint<{width}>"


def _smoke_main(prepared: PreparedProject) -> str:
    lines = ["#include <systemc>", '#include "design.h"', "", "int sc_main(int, char**) {"]
    for name, _, width in prepared.top_ports:
        lines.append(f"  sc_core::sc_signal<{_systemc_type(width)}> signal_{name};")
    lines.append(f'  {prepared.top_module} dut("dut");')
    for name, _, _ in prepared.top_ports:
        lines.append(f"  dut.{name}(signal_{name});")
    lines.extend(["  sc_core::sc_start(sc_core::SC_ZERO_TIME);", "  return 0;", "}", ""])
    return "\n".join(lines)


def _cmake(prepared: PreparedProject) -> str:
    return (
        "cmake_minimum_required(VERSION 3.16)\n"
        f"project({prepared.top_module}_systemc LANGUAGES CXX)\n"
        "set(CMAKE_CXX_STANDARD 17)\n"
        "set(CMAKE_CXX_STANDARD_REQUIRED ON)\n"
        "find_package(SystemCLanguage QUIET)\n"
        "add_executable(systemc_smoke src/main.cpp)\n"
        "target_include_directories(systemc_smoke PRIVATE include)\n"
        "if(SystemCLanguage_FOUND)\n"
        "  target_link_libraries(systemc_smoke PRIVATE SystemC::systemc)\n"
        "else()\n"
        "  find_path(SYSTEMC_INCLUDE_DIR NAMES systemc HINTS \"$ENV{SYSTEMC_PREFIX}/include\")\n"
        "  find_library(SYSTEMC_LIBRARY NAMES systemc HINTS \"$ENV{SYSTEMC_PREFIX}/lib\" \"$ENV{SYSTEMC_PREFIX}/lib64\")\n"
        "  if(NOT SYSTEMC_INCLUDE_DIR OR NOT SYSTEMC_LIBRARY)\n"
        "    message(FATAL_ERROR \"SystemC headers/library not found; set SYSTEMC_PREFIX\")\n"
        "  endif()\n"
        "  target_include_directories(systemc_smoke PRIVATE ${SYSTEMC_INCLUDE_DIR})\n"
        "  target_link_libraries(systemc_smoke PRIVATE ${SYSTEMC_LIBRARY})\n"
        "endif()\n"
    )


def _project_readme(prepared: PreparedProject) -> str:
    return (
        f"# {prepared.display_name} native SystemC model\n\n"
        f"Top module: `{prepared.top_module}`.\n\n"
        "Build with SystemC 2.3.3 or later:\n\n"
        "```bash\n"
        "cmake -S . -B build -DCMAKE_PREFIX_PATH=/path/to/systemc\n"
        "cmake --build build\n"
        "./build/systemc_smoke\n"
        "```\n\n"
        "The source/ directory contains the temporary SystemVerilog compilation inputs.\n"
    )
