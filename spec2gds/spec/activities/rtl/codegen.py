"""Deterministic SystemVerilog rendering from structure and stored semantics."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from spec2gds.spec.activities.view import SpecAccess
from spec2gds.spec.spec_format.ir import (
    ComponentIR,
    ConnectionIR,
    DesignIR,
    EndpointSliceIR,
    PortIR,
)
from spec2gds.spec.spec_format.models import EntityRef, sha256_digest
from spec2gds.spec.spec_format.naming import entity_name
from spec2gds.spec.spec_format.sections import SectionIR

ACTIVITY_ID = "rtl.generate"
ACTIVITY_VERSION = "1.3.0"
GENERATION_SCHEMA = "spec2gds.rtl-generation.v3"

_TEMPLATES = Environment(
    loader=PackageLoader("spec2gds.spec.activities.rtl", "templates"),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    newline_sequence="\n",
    keep_trailing_newline=True,
)

_SV_KEYWORDS = {
    "accept_on",
    "alias",
    "always",
    "always_comb",
    "always_ff",
    "always_latch",
    "and",
    "assert",
    "assign",
    "assume",
    "automatic",
    "before",
    "begin",
    "bind",
    "bins",
    "binsof",
    "bit",
    "break",
    "buf",
    "bufif0",
    "bufif1",
    "byte",
    "case",
    "casex",
    "casez",
    "cell",
    "chandle",
    "checker",
    "class",
    "clocking",
    "cmos",
    "config",
    "const",
    "constraint",
    "context",
    "continue",
    "cover",
    "covergroup",
    "coverpoint",
    "cross",
    "deassign",
    "default",
    "defparam",
    "design",
    "disable",
    "dist",
    "do",
    "edge",
    "else",
    "end",
    "endcase",
    "endchecker",
    "endclass",
    "endclocking",
    "endconfig",
    "endfunction",
    "endgenerate",
    "endgroup",
    "endinterface",
    "endmodule",
    "endpackage",
    "endprimitive",
    "endprogram",
    "endproperty",
    "endspecify",
    "endsequence",
    "endtable",
    "endtask",
    "enum",
    "event",
    "eventually",
    "expect",
    "export",
    "extends",
    "extern",
    "final",
    "first_match",
    "for",
    "force",
    "foreach",
    "forever",
    "fork",
    "forkjoin",
    "function",
    "generate",
    "genvar",
    "global",
    "highz0",
    "highz1",
    "if",
    "iff",
    "ifnone",
    "ignore_bins",
    "illegal_bins",
    "implements",
    "implies",
    "import",
    "incdir",
    "include",
    "initial",
    "inout",
    "input",
    "inside",
    "int",
    "integer",
    "interconnect",
    "interface",
    "intersect",
    "join",
    "join_any",
    "join_none",
    "large",
    "let",
    "liblist",
    "library",
    "local",
    "localparam",
    "logic",
    "longint",
    "macromodule",
    "matches",
    "medium",
    "modport",
    "module",
    "nand",
    "negedge",
    "nettype",
    "new",
    "nexttime",
    "nmos",
    "nor",
    "noshowcancelled",
    "not",
    "notif0",
    "notif1",
    "null",
    "or",
    "output",
    "package",
    "packed",
    "parameter",
    "pmos",
    "posedge",
    "primitive",
    "priority",
    "program",
    "property",
    "protected",
    "pull0",
    "pull1",
    "pulldown",
    "pullup",
    "pure",
    "rand",
    "randc",
    "randcase",
    "randsequence",
    "rcmos",
    "real",
    "realtime",
    "ref",
    "reg",
    "reject_on",
    "release",
    "repeat",
    "restrict",
    "return",
    "rnmos",
    "rpmos",
    "rtran",
    "rtranif0",
    "rtranif1",
    "s_always",
    "s_eventually",
    "s_nexttime",
    "s_until",
    "s_until_with",
    "scalared",
    "sequence",
    "shortint",
    "shortreal",
    "showcancelled",
    "signed",
    "small",
    "solve",
    "specify",
    "specparam",
    "static",
    "string",
    "strong",
    "strong0",
    "strong1",
    "struct",
    "super",
    "supply0",
    "supply1",
    "sync_accept_on",
    "sync_reject_on",
    "table",
    "tagged",
    "task",
    "this",
    "throughout",
    "time",
    "timeprecision",
    "timeunit",
    "tran",
    "tranif0",
    "tranif1",
    "tri",
    "tri0",
    "tri1",
    "triand",
    "trior",
    "trireg",
    "type",
    "typedef",
    "union",
    "unique",
    "unique0",
    "unsigned",
    "until",
    "until_with",
    "untyped",
    "use",
    "uwire",
    "var",
    "vectored",
    "virtual",
    "void",
    "wait",
    "wait_order",
    "wand",
    "weak",
    "weak0",
    "weak1",
    "while",
    "wildcard",
    "wire",
    "with",
    "within",
    "wor",
    "xnor",
    "xor",
}


@dataclass(frozen=True)
class NameMapping:
    """One source-to-RTL identifier mapping with its local namespace."""

    kind: str
    scope: str
    source_name: str
    rtl_name: str

    def as_json(self) -> dict[str, str]:
        """Return the source-to-generated identifier mapping for reports."""
        return {
            "kind": self.kind,
            "scope": self.scope,
            "source_name": self.source_name,
            "rtl_name": self.rtl_name,
        }


@dataclass(frozen=True)
class ProjectDiagnostics:
    """Fatal errors and non-fatal structural warnings from one preflight."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def messages(self) -> tuple[str, ...]:
        """Flatten blocking errors and non-blocking warnings for availability."""
        return (*self.errors, *self.warnings)


@dataclass(frozen=True)
class GeneratedProject:
    """Complete deterministic RTL project before workspace publication."""

    files: dict[str, bytes]
    top_module: str
    wrapper_generated: bool
    module_count: int
    component_module_count: int
    instance_count: int
    net_count: int
    unconnected_port_count: int
    warnings: tuple[str, ...]
    name_mappings: tuple[NameMapping, ...]
    source_sections: tuple[dict[str, str], ...]
    source_entities: tuple[EntityRef, ...]
    implementation_status: dict[str, str]


@dataclass(frozen=True)
class _PortShape:
    text: str
    key: tuple[int, int] | None


@dataclass(frozen=True)
class _Endpoint:
    kind: str
    port: PortIR
    instance_name: str = ""
    slice: EndpointSliceIR | None = None
    component_id: str = ""


@dataclass(frozen=True)
class _Connection:
    source: ConnectionIR
    endpoints: tuple[_Endpoint, ...]
    shape: _PortShape


@dataclass(frozen=True)
class _DesignAnalysis:
    design: DesignIR
    parent: ComponentIR | None
    connections: tuple[_Connection, ...]


@dataclass(frozen=True)
class _Analysis:
    """Validated source graph consumed by the rendering-only normalization pass."""
    target: ComponentIR | DesignIR
    root_parent: ComponentIR | None
    components: tuple[ComponentIR, ...]
    designs: tuple[_DesignAnalysis, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    sections_by_parent: dict[str, SectionIR]
    port_shapes: dict[tuple[str, str], _PortShape]


@dataclass(frozen=True)
class _RtlPort:
    source_name: str
    name: str
    direction: str
    range_text: str
    resolved_range_text: str
    width: int


@dataclass(frozen=True)
class _RtlNet:
    source_name: str
    name: str
    range_text: str


@dataclass(frozen=True)
class _PortConnection:
    port_name: str
    expression: str


@dataclass(frozen=True)
class _RtlInstance:
    source_name: str
    name: str
    module_name: str
    connections: tuple[_PortConnection, ...]
    parameter_string: str = ""


@dataclass(frozen=True)
class _RtlModule:
    name: str
    file_path: str
    ports: tuple[_RtlPort, ...]
    nets: tuple[_RtlNet, ...]
    instances: tuple[_RtlInstance, ...]
    leaf: bool
    component_sv: SectionIR | None = None
    design_sv: SectionIR | None = None
    assignments: tuple[str, ...] = ()
    parameters: tuple = ()


class _IdentifierPool:
    """Allocate legal, deterministic identifiers without cross-scope collisions."""
    def __init__(self, used: set[str] | None = None) -> None:
        self.used = set(used or ())

    def allocate(self, source: str, stable_key: str) -> str:
        """Allocate a legal name with a stable hash suffix on collision."""
        base = _identifier(source)
        candidate = base
        suffix = hashlib.sha256(stable_key.encode("utf-8")).hexdigest()[:8]
        index = 1
        while candidate in self.used:
            candidate = f"{base}_{suffix}" if index == 1 else f"{base}_{suffix}_{index}"
            index += 1
        self.used.add(candidate)
        return candidate


class _Analyzer:
    """Traverse reachable SpecIR and collect every blocking RTL diagnostic."""
    def __init__(self, spec: SpecAccess) -> None:
        self.spec = spec
        self.components_by_vlnv = {item.vlnv: item for item in spec.low.components}
        self.components_by_id = {item.ref.entity_id: item for item in spec.low.components}
        self.designs_by_id = {item.ref.entity_id: item for item in spec.low.designs}
        self.parent_by_design_id = {
            item.internal_design.entity_id: self.components_by_id[item.component.entity_id]
            for item in spec.low.manifest.component_compositions
        }
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.shapes: dict[tuple[str, str], _PortShape] = {}
        self.sections_by_parent = {
            item.parent.entity_id: item
            for item in spec.low.entity_sections
            if item.section_type == "sv" and item.usage == "implementation"
        }

    def analyze(self, target: EntityRef) -> _Analysis:
        """Analyze the complete reachable hierarchy before any file is rendered."""
        entity = self.spec.low.resolve(target)
        if not isinstance(entity, (ComponentIR, DesignIR)):
            return _Analysis(
                target=DesignIR(target, "", (), ()),
                root_parent=None,
                components=(),
                designs=(),
                errors=("RTL generation requires a selected component or design.",),
                warnings=(),
                sections_by_parent={},
                port_shapes={},
            )

        root_parent = entity if isinstance(entity, ComponentIR) else self.parent_by_design_id.get(entity.ref.entity_id)
        seen_components: set[str] = set()
        design_pairs: dict[str, tuple[DesignIR, ComponentIR | None]] = {}

        def visit_component(component: ComponentIR) -> None:
            if component.ref.entity_id in seen_components:
                return
            seen_components.add(component.ref.entity_id)
            internal = self.spec.low.internal_design(component)
            if internal is not None:
                visit_design(internal, component)

        def visit_design(design: DesignIR, parent: ComponentIR | None) -> None:
            design_pairs.setdefault(design.ref.entity_id, (design, parent))
            for instance in design.instances:
                visit_component(self.components_by_vlnv[instance.component_vlnv])

        if root_parent is None:
            visit_design(entity, entity)
        else:
            visit_component(root_parent)

        components = [
            component
            for component in self.spec.low.components
            if component.ref.entity_id in seen_components
        ]
        for component in components:
            self._validate_component(component)
        for design, parent in design_pairs.values():
            if isinstance(parent, DesignIR):
                self._validate_component(parent)

        design_analyses = tuple(
            self._analyze_design(design, parent) for design, parent in design_pairs.values()
        )
        for item in design_analyses:
            self._validate_active_body_names(item)
        return _Analysis(
            target=entity,
            root_parent=root_parent,
            components=tuple(components),
            designs=design_analyses,
            errors=tuple(sorted(set(self.errors))),
            warnings=tuple(sorted(set(self.warnings))),
            sections_by_parent=self.sections_by_parent,
            port_shapes=self.shapes,
        )

    def _validate_active_body_names(self, analysis: _DesignAnalysis) -> None:
        """Require source names to survive unchanged when a body can reference them."""
        component_section = self.sections_by_parent.get(analysis.parent.ref.entity_id) if analysis.parent else None
        design_section = self.sections_by_parent.get(analysis.design.ref.entity_id)
        active = any(item is not None and item.content.strip() for item in (component_section, design_section))
        if not active:
            return
        names: list[tuple[str, str]] = []
        if analysis.parent is not None:
            names.extend(("port", item.name) for item in analysis.parent.ports)
        names.extend(("instance", item.name) for item in analysis.design.instances)
        names.extend(("connection", item.name) for item in analysis.design.connections)
        seen: dict[str, str] = {}
        for kind, name in names:
            if not _is_plain_identifier(name):
                self.errors.append(
                    f"Design {entity_name(analysis.design)} {kind} name {name!r} must be a plain non-keyword SystemVerilog identifier while SV is active."
                )
            previous = seen.get(name)
            if previous is not None:
                self.errors.append(
                    f"Design {entity_name(analysis.design)} {kind} name {name!r} collides with a {previous} in the module namespace."
                )
            else:
                seen[name] = kind

    def _validate_component(self, component: ComponentIR) -> None:
        section = self.sections_by_parent.get(component.ref.entity_id)
        for interface in component.interfaces:
            self.errors.append(
                f"Component {entity_name(component)} declares unsupported bus interface {interface.name}."
            )
        from dataclasses import asdict

        from spec2gds.spec.spec_format.rtl_interface import resolve_interface
        try:
            resolved = resolve_interface(
                [{"name": port.name, "direction": port.direction,
                  "range": port.width[1:-1] if isinstance(port.width, str) else None}
                 for port in component.ports if port.style == "wire"],
                [asdict(parameter) for parameter in component.parameters],
                section.content if section is not None else "",
            )
        except (ValueError, OSError) as exc:
            self.errors.append(f"Component {entity_name(component)} interface: {exc}")
            return
        if resolved["status"] != "resolved":
            self.errors.extend(item["message"] for item in resolved["diagnostics"])
            return
        shapes = {item["name"]: item for item in resolved["ports"]}
        for port in component.ports:
            if section is not None and section.content.strip() and not _is_plain_identifier(port.name):
                self.errors.append(
                    f"Component {entity_name(component)} port {port.name!r} must be a plain non-keyword SystemVerilog identifier while SV is active."
                )
            if port.style != "wire":
                self.errors.append(
                    f"Component {entity_name(component)} port {port.name} is {port.style}; only wire ports are supported."
                )
                continue
            evaluated = shapes.get(port.name)
            shape = _PortShape(
                port.width if isinstance(port.width, str) else "",
                (evaluated["left"], evaluated["right"]) if evaluated and evaluated["left"] is not None else None,
            ) if evaluated else None
            if shape is None:
                self.errors.append(
                    f"Component {entity_name(component)} port {port.name} uses unsupported symbolic range {port.width}."
                )
                continue
            self.shapes[(component.ref.entity_id, port.name)] = shape

    def _analyze_design(self, design: DesignIR, parent: ComponentIR | None) -> _DesignAnalysis:
        """Validate effective widths, slice bounds, overlap and ordinary drivers."""
        instances = {item.name: item for item in design.instances}
        from spec2gds.spec.spec_format.design_interfaces import instance_interface, resolve_ports
        for instance in design.instances:
            try:
                effective = instance_interface(self.spec.low, design, instance)
                evaluated = resolve_ports(effective)
                for port in effective.ports:
                    if port.style != "wire":
                        continue
                    bounds = evaluated[port.name]
                    self.shapes[(f"{design.ref.entity_id}/{instance.name}", port.name)] = _PortShape(
                        f"[{port.range}]" if port.range else "",
                        (bounds["left"], bounds["right"]) if port.range else None,
                    )
            except (ValueError, OSError) as exc:
                self.errors.append(f"Design {entity_name(design)} instance {instance.name}: {exc}")
        referenced: set[tuple[str, str]] = set()
        occupied: dict[tuple[str, str, str], list[tuple[int, int, str]]] = {}
        connections: list[_Connection] = []
        for connection in design.connections:
            label = f"Design {entity_name(design)} connection {connection.name}"
            if connection.kind != "ad_hoc":
                self.errors.append(f"{label} is an unsupported bus-interface connection.")
                continue
            start_errors = len(self.errors)
            if len(connection.external_ports) > 1:
                self.errors.append(f"{label} has multiple external boundary ports.")
            if connection.external_ports and parent is None:
                self.errors.append(f"{label} exposes a boundary port from an unowned design.")
            endpoints: list[_Endpoint] = []
            for endpoint in connection.port_endpoints:
                component = self.components_by_vlnv[instances[endpoint.instance_name].component_vlnv]
                port = next(item for item in component.ports if item.name == endpoint.port_name)
                if endpoint.symbolic_slice is not None:
                    self.errors.append(f"{label} uses unsupported symbolic part-select {endpoint.symbolic_slice}.")
                referenced.add((endpoint.instance_name, endpoint.port_name))
                endpoints.append(_Endpoint("instance", port, endpoint.instance_name, endpoint.slice, f"{design.ref.entity_id}/{endpoint.instance_name}"))
            for endpoint in connection.external_ports:
                if endpoint.symbolic_slice is not None:
                    self.errors.append(f"{label} uses unsupported symbolic part-select {endpoint.symbolic_slice}.")
                if parent is not None:
                    port = next(item for item in parent.ports if item.name == endpoint.port_name)
                    endpoints.append(_Endpoint("boundary", port, slice=endpoint.slice, component_id=parent.ref.entity_id))
            widths: list[int] = []
            for endpoint in endpoints:
                shape = self.shapes.get((endpoint.component_id, endpoint.port.name)) or _port_shape(endpoint.port)
                if shape is None:
                    continue
                left, right = shape.key if shape.key is not None else (0, 0)
                low, high = min(left, right), max(left, right)
                if endpoint.slice is not None:
                    low = endpoint.slice.lsb
                    high = low + endpoint.slice.width - 1
                    if left < right:
                        self.errors.append(f"{label} uses an unsupported ascending sliced range on {endpoint.port.name}.")
                    if low < min(left, right) or high > max(left, right):
                        self.errors.append(f"{label} slice [{high}:{low}] exceeds bounds of {endpoint.port.name} {shape.text or 'scalar'}.")
                    if endpoint.port.direction == "inout":
                        self.errors.append(f"{label} sliced bidirectional ports are unsupported.")
                widths.append(high - low + 1)
                key = (endpoint.kind, endpoint.instance_name, endpoint.port.name)
                for old_low, old_high, old_connection in occupied.get(key, []):
                    if low <= old_high and old_low <= high:
                        self.errors.append(f"{label} reuses endpoint {endpoint.instance_name}.{endpoint.port.name}: overlap with connection {old_connection}.")
                occupied.setdefault(key, []).append((low, high, connection.name))
            if widths and any(width != widths[0] for width in widths[1:]):
                self.errors.append(f"{label} connects incompatible ranges (effective widths {widths}).")
            sources = [endpoint for endpoint in endpoints
                       if (endpoint.kind == "instance" and endpoint.port.direction == "out")
                       or (endpoint.kind == "boundary" and endpoint.port.direction == "in")]
            bidirectional = [endpoint for endpoint in endpoints if endpoint.port.direction == "inout"]
            if len(sources) > 1:
                self.errors.append(f"{label} has multiple ordinary drivers.")
            elif not sources and not bidirectional:
                self.errors.append(f"{label} has no driver or bidirectional endpoint.")
            if len(self.errors) == start_errors and widths:
                width = widths[0]
                first_shape = self.shapes.get((endpoints[0].component_id, endpoints[0].port.name)) or _port_shape(endpoints[0].port)
                if (
                    endpoints[0].slice is not None
                    or not first_shape
                    or not first_shape.text
                    or (first_shape.key and abs(first_shape.key[0] - first_shape.key[1]) + 1 != width)
                ):
                    text = f"[{width-1}:0]" if width > 1 else ""
                    key = (width - 1, 0) if width > 1 else None
                else:
                    text = first_shape.text
                    key = first_shape.key
                shape = _PortShape(text, key)
                connections.append(_Connection(connection, tuple(endpoints), shape))
        for instance in design.instances:
            component = self.components_by_vlnv[instance.component_vlnv]
            for port in component.ports:
                if port.style == "wire" and (instance.name, port.name) not in referenced:
                    self.warnings.append(f"Design {entity_name(design)} instance {instance.name} port {port.name} is unconnected.")
        return _DesignAnalysis(design, parent, tuple(connections))


class _Normalizer:
    """Convert validated SpecIR into simple values accepted by Jinja templates."""
    def __init__(self, analysis: _Analysis) -> None:
        self.analysis = analysis
        self.mappings: list[NameMapping] = []
        self.module_names: dict[str, str] = {}
        self.port_names: dict[tuple[str, str], str] = {}
        self.module_pool = _IdentifierPool()
        self.design_analysis = {item.design.ref.entity_id: item for item in analysis.designs}

    def normalize(self) -> tuple[tuple[_RtlModule, ...], str, bool]:
        """Build rendering-only modules and select the generated top."""
        for component in self.analysis.components:
            source_name = component.vlnv.split(":")[2]
            module_name = self._allocate(
                self.module_pool,
                "module",
                component.vlnv,
                source_name,
                f"component:{component.ref.entity_id}",
            )
            self.module_names[component.ref.entity_id] = module_name
            port_pool = _IdentifierPool()
            for port in component.ports:
                self.port_names[(component.ref.entity_id, port.name)] = self._allocate(
                    port_pool,
                    "port",
                    component.vlnv,
                    port.name,
                    f"port:{component.ref.entity_id}:{port.name}",
                )

        for design in self.analysis.designs:
            if isinstance(design.parent, DesignIR):
                pool = _IdentifierPool()
                for port in design.parent.ports:
                    self.port_names[(design.parent.ref.entity_id, port.name)] = self._allocate(pool, "port", design.parent.vlnv, port.name, f"port:{design.parent.ref.entity_id}:{port.name}")
        modules = [self._component_module(component) for component in self.analysis.components]
        if self.analysis.root_parent is not None:
            top_module = self.module_names[self.analysis.root_parent.ref.entity_id]
            return tuple(modules), top_module, False

        design_name = self.analysis.target.vlnv.split(":")[2]
        wrapper_source = f"{design_name}_top"
        top_module = self._allocate(
            self.module_pool,
            "module",
            self.analysis.target.vlnv,
            wrapper_source,
            f"design:{self.analysis.target.ref.entity_id}:top",
        )
        modules.append(
            self._structural_module(
                self.design_analysis[self.analysis.target.ref.entity_id],
                top_module,
                f"rtl/designs/{top_module}.sv",
            )
        )
        return tuple(modules), top_module, True

    def _component_module(self, component: ComponentIR) -> _RtlModule:
        name = self.module_names[component.ref.entity_id]
        internal = next(
            (
                item
                for item in self.analysis.designs
                if item.parent is not None and item.parent.ref == component.ref
            ),
            None,
        )
        if internal is not None:
            return self._structural_module(
                internal,
                name,
                f"rtl/components/{name}.sv",
            )
        ports = self._ports(component)
        return _RtlModule(
            name=name,
            file_path=f"rtl/components/{name}.sv",
            ports=ports,
            nets=(),
            instances=(),
            leaf=True,
            parameters=component.parameters,
            component_sv=self.analysis.sections_by_parent.get(component.ref.entity_id),
        )

    def _structural_module(
        self, analysis: _DesignAnalysis, module_name: str, file_path: str
    ) -> _RtlModule:
        """Allocate stable HDL names and normalize validated nets and instance hookups.

        The identifier pool prevents source-name collisions. Unconnected-port policy
        and explicit stored bodies remain visible in the normalized module.
        """
        parent = analysis.parent
        ports = self._ports(parent) if parent is not None else ()
        local_pool = _IdentifierPool({port.name for port in ports})
        instance_names = {
            instance.name: self._allocate(
                local_pool,
                "instance",
                analysis.design.vlnv,
                instance.name,
                f"instance:{analysis.design.ref.entity_id}:{instance.name}",
            )
            for instance in analysis.design.instances
        }
        connection_names = {
            connection.source.name: self._allocate(
                local_pool,
                "connection",
                analysis.design.vlnv,
                connection.source.name,
                f"connection:{analysis.design.ref.entity_id}:{connection.source.name}",
            )
            for connection in analysis.connections
        }

        expressions: dict[tuple[str, str], str] = {}
        nets: list[_RtlNet] = []
        assignments: list[str] = []
        sliced: dict[tuple[str, str], list[_Endpoint]] = {}
        for connection in analysis.connections:
            for endpoint in connection.endpoints:
                if endpoint.kind == "instance" and endpoint.slice is not None:
                    sliced.setdefault((endpoint.instance_name, endpoint.port.name), []).append(endpoint)
        for key, endpoints in sorted(sliced.items()):
            name = local_pool.allocate(f"{key[0]}_{key[1]}_bits", f"slice:{analysis.design.ref.entity_id}:{key}")
            expressions[key] = name
            port = endpoints[0].port
            shape = self.analysis.port_shapes.get((endpoints[0].component_id, port.name)) or _port_shape(port)
            assert shape is not None
            nets.append(_RtlNet(port.name, name, shape.text))
            if port.direction == "in":
                left, right = shape.key if shape.key is not None else (0, 0)
                cursor = right
                for low, high in sorted((item.slice.lsb, item.slice.lsb + item.slice.width - 1) for item in endpoints):
                    if low > cursor:
                        assignments.append(f"assign {name}[{low-1}:{cursor}] = '0;")
                    cursor = high + 1
                if cursor <= left:
                    assignments.append(f"assign {name}[{left}:{cursor}] = '0;")
        for connection in analysis.connections:
            if connection.source.external_ports:
                assert parent is not None
                external = next(endpoint for endpoint in connection.endpoints if endpoint.kind == "boundary")
                ext_shape = self.analysis.port_shapes.get((parent.ref.entity_id, external.port.name)) or _port_shape(external.port)
                expression = _slice_expression(self.port_names[(parent.ref.entity_id, external.port.name)], external.slice, ext_shape)
            else:
                expression = connection_names[connection.source.name]
                nets.append(_RtlNet(connection.source.name, expression, connection.shape.text))
            for endpoint in connection.endpoints:
                if endpoint.kind != "instance":
                    continue
                key = (endpoint.instance_name, endpoint.port.name)
                if endpoint.slice is None:
                    expressions[key] = expression
                else:
                    inst_shape = self.analysis.port_shapes.get((endpoint.component_id, endpoint.port.name)) or _port_shape(endpoint.port)
                    bits = _slice_expression(expressions[key], endpoint.slice, inst_shape)
                    lhs, rhs = (bits, expression) if endpoint.port.direction == "in" else (expression, bits)
                    assignments.append(f"assign {lhs} = {rhs};")

        instances: list[_RtlInstance] = []
        for instance in analysis.design.instances:
            component = next(
                item
                for item in self.analysis.components
                if item.vlnv == instance.component_vlnv
            )
            hookups: list[_PortConnection] = []
            for port in component.ports:
                expression = expressions.get((instance.name, port.name))
                if expression is None:
                    expression = "'0" if port.direction == "in" else ""
                hookups.append(
                    _PortConnection(
                        port_name=self.port_names[(component.ref.entity_id, port.name)],
                        expression=expression,
                    )
                )
            param_assigns = [f".{name}({value})" for name, value in instance.parameter_values]
            param_str = " #(\n        " + ",\n        ".join(param_assigns) + "\n    )" if param_assigns else ""
            instances.append(
                _RtlInstance(
                    source_name=instance.name,
                    name=instance_names[instance.name],
                    module_name=self.module_names[component.ref.entity_id],
                    connections=tuple(hookups),
                    parameter_string=param_str,
                )
            )

        return _RtlModule(
            name=module_name,
            file_path=file_path,
            ports=ports,
            nets=tuple(nets),
            assignments=tuple(assignments),
            instances=tuple(instances),
            leaf=False,
            parameters=parent.parameters if parent is not None else (),
            component_sv=(
                self.analysis.sections_by_parent.get(parent.ref.entity_id)
                if isinstance(parent, ComponentIR) else None
            ),
            design_sv=self.analysis.sections_by_parent.get(analysis.design.ref.entity_id),
        )

    def _ports(self, component: ComponentIR | None) -> tuple[_RtlPort, ...]:
        if component is None:
            return ()
        ports = []
        for port in component.ports:
            bounds = self.analysis.port_shapes[(component.ref.entity_id, port.name)].key
            ports.append(_RtlPort(
                source_name=port.name,
                name=self.port_names[(component.ref.entity_id, port.name)],
                direction=port.direction,
                range_text=port.width if isinstance(port.width, str) else "",
                resolved_range_text=(
                    f"[{bounds[0]}:{bounds[1]}]" if bounds is not None else ""
                ),
                width=abs(bounds[0] - bounds[1]) + 1 if bounds is not None else 1,
            ))
        return tuple(ports)

    def _allocate(
        self,
        pool: _IdentifierPool,
        kind: str,
        scope: str,
        source_name: str,
        stable_key: str,
    ) -> str:
        rtl_name = pool.allocate(source_name, stable_key)
        self.mappings.append(NameMapping(kind, scope, source_name, rtl_name))
        return rtl_name


def validate_project(spec: SpecAccess, target: EntityRef) -> ProjectDiagnostics:
    """Return fatal and warning diagnostics for one selected component or design."""
    analysis = _Analyzer(spec).analyze(target)
    return ProjectDiagnostics(
        errors=tuple(f"Error: {item}" for item in analysis.errors),
        warnings=tuple(f"Warning: {item}" for item in analysis.warnings),
    )


def generate_project(spec: SpecAccess, target: EntityRef) -> GeneratedProject:
    """Render one validated component or design into a deterministic RTL tree."""
    analysis = _Analyzer(spec).analyze(target)
    if analysis.errors:
        raise ValueError(
            "Unsupported RTL topology: "
            + "; ".join(f"Error: {item}" for item in analysis.errors)
        )
    normalizer = _Normalizer(analysis)
    modules, top_module, wrapper_generated = normalizer.normalize()
    files = {
        module.file_path: _render_module(module).encode("utf-8") for module in modules
    }
    source_files = tuple(module.file_path.removeprefix("rtl/") for module in modules)
    top = next(module for module in modules if module.name == top_module)
    smoke_top = _IdentifierPool({module.name for module in modules}).allocate(
        "spec2gds_smoke_tb", "smoke-testbench"
    )
    smoke_ports = tuple(
        {
            "name": port.name,
            "direction": port.direction,
            "range_text": port.resolved_range_text,
            "width": port.width,
            "alternating": f"{port.width}'h{((1 << port.width) - 1) // 3:x}",
            "index": index,
        }
        for index, port in enumerate(top.ports)
    )
    has_scaffolds = any(
        module.leaf and not any(
            section is not None and section.content.strip()
            for section in (module.component_sv, module.design_sv)
        )
        for module in modules
    )
    files["sim/smoke_tb.sv"] = _render_template(
        "smoke_tb.sv.j2", top_module=top_module, smoke_top=smoke_top,
        ports=smoke_ports, has_scaffolds=has_scaffolds,
    ).encode("utf-8")
    files["rtl/files.f"] = _render_template("files.f.j2", files=source_files).encode("utf-8")
    files["Makefile"] = _render_template(
        "Makefile.j2", top_module=top_module, smoke_top=smoke_top,
        rtl_sources=tuple(module.file_path for module in modules),
    ).encode("utf-8")
    files["README.md"] = _render_template(
        "README.md.j2",
        design_name=entity_name(analysis.target),
        top_module=top_module,
        ports=smoke_ports,
    ).encode("utf-8")

    warnings = tuple(f"Warning: {item}" for item in analysis.warnings)
    mappings = tuple(normalizer.mappings)
    inventory = [
        {"path": path, "sha256": sha256_digest(data), "size": len(data)}
        for path, data in sorted(files.items())
    ]
    manifest = {
        "schema_version": GENERATION_SCHEMA,
        "activity_id": ACTIVITY_ID,
        "activity_version": ACTIVITY_VERSION,
        "document_id": target.document_id,
        "source_revision_hash": spec.high.document["source_revision_hash"],
        "target": target.model_dump(mode="json"),
        "target_vlnv": analysis.target.vlnv,
        "source_entities": [entity.ref.model_dump(mode="json") for entity in (*analysis.components, *(item.design for item in analysis.designs))],
        "implementation_status": {item.ref.entity_id: ("stored_sv_section" if (section := analysis.sections_by_parent.get(item.ref.entity_id)) is not None and section.content.strip() else "structured_composition" if any(design.parent == item for design in analysis.designs) else "unimplemented_scaffold") for item in analysis.components},
        "top_module": top_module,
        "wrapper_generated": wrapper_generated,
        "warnings": list(warnings),
        "name_mappings": [item.as_json() for item in mappings],
        "source_sections": [
            {
                "section_id": section.section_id,
                "sha256": section.source_sha256,
                "source_path": section.source_path,
                "output_path": module.file_path,
            }
            for module in modules
            for section in (module.component_sv, module.design_sv)
            if section is not None
        ],
        "files": inventory,
    }
    files["generation-manifest.json"] = _json_bytes(manifest)

    return GeneratedProject(
        files=files,
        top_module=top_module,
        wrapper_generated=wrapper_generated,
        module_count=len(modules),
        component_module_count=len(analysis.components),
        instance_count=sum(len(item.design.instances) for item in analysis.designs),
        net_count=sum(len(item.connections) for item in analysis.designs),
        unconnected_port_count=len(warnings),
        warnings=warnings,
        name_mappings=mappings,
        source_sections=tuple(manifest["source_sections"]),
        source_entities=tuple(EntityRef.model_validate(item) for item in manifest["source_entities"]),
        implementation_status=manifest["implementation_status"],
    )


def _render_module(module: _RtlModule) -> str:
    """Render normalized declarations, wiring and explicitly stored module bodies.

    Defaults make body-less leaf outputs compile safely; they do not infer design
    behavior. Jinja formats text after analysis has chosen topology and names.
    """
    body_sections = tuple(
        item for item in (module.component_sv, module.design_sv)
        if item is not None and item.content.strip()
    )
    has_body = bool(body_sections)
    unused_inputs = tuple(
        port.name
        for port in module.ports
        if module.leaf and not has_body and port.direction in {"in", "inout"}
    )
    direction = {"in": "input", "out": "output", "inout": "inout"}
    port_lines = tuple(
        f"    {direction[port.direction]} {'wire' if port.direction == 'inout' or not has_body else 'logic'}"
        f"{f' {port.range_text}' if port.range_text else ''} {port.name}"
        for port in module.ports
    )
    net_lines = tuple(
        f"    wire{f' {net.range_text}' if net.range_text else ''} {net.name};"
        for net in module.nets
    )
    instance_blocks = tuple(
        f"    {instance.module_name}{instance.parameter_string} {instance.name} (\n"
        + ",\n".join(
            f"        .{connection.port_name}({connection.expression})"
            for connection in instance.connections
        )
        + "\n    );"
        for instance in module.instances
    )
    default_assignments = tuple(
        f"    assign {port.name} = {'\'0' if port.direction == 'out' else '\'z'};"
        for port in module.ports
        if module.leaf and not has_body and port.direction in {"out", "inout"}
    )
    from dataclasses import asdict

    from spec2gds.spec.spec_format.rtl_interface import parameter_declarations
    header = f"module {module.name}"
    declarations = parameter_declarations([asdict(parameter) for parameter in module.parameters])
    if declarations:
        header += f" #(\n    {declarations}\n)"
    module_declaration = header + ";"
    if port_lines:
        module_declaration = (
            header + " (\n" + ",\n".join(port_lines) + "\n);"
        )
    sections: list[str] = []
    if net_lines:
        sections.append("\n".join(net_lines))
    if module.assignments:
        sections.append("\n".join(f"    {line}" for line in module.assignments))
    if instance_blocks:
        sections.append("\n\n".join(instance_blocks))
    for item in body_sections:
        sections.append(
            f"    // {item.title} section: {item.section_id}\n"
            f"`line 1 \"{item.source_path}\" 0\n"
            f"{item.content.rstrip()}\n"
            f"`line 1 \"{module.file_path}\" 0"
        )
    if default_assignments:
        sections.append("\n".join(default_assignments))
    if unused_inputs:
        sections.append(
            "    wire _unused_ok;\n"
            "    assign _unused_ok = 1'b0 && &{1'b0, "
            + ", ".join(unused_inputs)
            + ", 1'b0};"
        )
    return _render_template(
        "module.sv.j2",
        module_declaration=module_declaration,
        sections=tuple(sections),
    )


def _render_template(name: str, **context: object) -> str:
    """Render one packaged template from a normalized, deterministic context."""
    return _TEMPLATES.get_template(name).render(**context)


def _port_shape(port: PortIR) -> _PortShape | None:
    if port.width == 1:
        return _PortShape("", None)
    if not isinstance(port.width, str):
        return None
    match = re.fullmatch(r"\[\s*(-?[0-9]+)\s*:\s*(-?[0-9]+)\s*\]", port.width)
    if match is None:
        return None
    left, right = (int(item) for item in match.groups())
    return _PortShape(f"[{left}:{right}]", (left, right))


def _identifier(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_$]", "_", value)
    if not candidate:
        candidate = "rtl_id"
    if not re.match(r"[A-Za-z_]", candidate):
        candidate = f"rtl_{candidate}"
    if candidate in _SV_KEYWORDS:
        candidate = f"{candidate}_rtl"
    return candidate


def _is_plain_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value)) and value not in _SV_KEYWORDS


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _slice_expression(name: str, endpoint_slice: EndpointSliceIR | None, shape: _PortShape | None) -> str:
    if endpoint_slice is None:
        return name
    # Saved connections can explicitly select the only bit of a scalar. The
    # selection is valid logically, but a scalar has no packed HDL dimension.
    # Packed one-bit ports still need their declared index, including [5:5].
    if shape is not None and shape.key is None:
        if endpoint_slice.lsb != 0 or endpoint_slice.width != 1:
            raise ValueError("A scalar connection must select its only bit.")
        return name
    high = endpoint_slice.lsb + endpoint_slice.width - 1
    return f"{name}[{high}:{endpoint_slice.lsb}]" if endpoint_slice.width > 1 else f"{name}[{endpoint_slice.lsb}]"
