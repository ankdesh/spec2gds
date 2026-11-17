"""Spec-owned interfaces for standalone Designs. Internal Designs use Components."""
from __future__ import annotations

import json
from dataclasses import asdict

import pydantic

from .models import ID_PATTERN, AnnotationSchemaEntry, EntityRef, StrictModel
from .rtl_interface import parameter_declarations, split_range

NAMESPACE = "spec2gds.design-interface"
ROOT = "annotations/design-interfaces"
FEATURE = "design-interface-v1"


class DesignWirePort(StrictModel):
    name: str
    direction: str
    range: str = ""
    description: str = ""

    @pydantic.model_validator(mode="after")
    def validate_port(self):
        if not ID_PATTERN.fullmatch(self.name) or self.direction not in {"in", "out", "inout"}:
            raise ValueError("Design ports need a valid ID and input, output, or bidirectional direction.")
        if self.range:
            split_range(self.range, require_pair=True)
        return self


class DesignParameter(StrictModel):
    name: str
    value: str
    rtl_type: str = ""
    description: str = ""


class DesignInterfaceV1(StrictModel):
    schema_version: int = 1
    design: EntityRef
    ports: tuple[DesignWirePort, ...] = ()
    parameters: tuple[DesignParameter, ...] = ()

    @pydantic.model_validator(mode="after")
    def validate_interface(self):
        if self.schema_version != 1 or self.design.entity_kind != "design":
            raise ValueError("Unsupported Design interface record.")
        if len({p.name for p in self.ports}) != len(self.ports):
            raise ValueError("Design port IDs must be unique.")
        parameter_declarations([p.model_dump() for p in self.parameters])
        if {p.name for p in self.ports} & {p.name for p in self.parameters}:
            raise ValueError("Ports and parameters must have distinct IDs.")
        return self


def interface_path(design_id):
    return f"{ROOT}/{design_id}.json"


def read_interface(files, design):
    data = files.get(interface_path(design.entity_id))
    return DesignInterfaceV1.model_validate_json(data) if data else DesignInterfaceV1(design=design)


def write_interface(package, value):
    value = DesignInterfaceV1.model_validate(value.model_dump())
    package.files[interface_path(value.design.entity_id)] = (json.dumps(value.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode()
    schemas = [s for s in package.manifest.annotation_schemas if s.namespace != NAMESPACE]
    schemas.append(AnnotationSchemaEntry(namespace=NAMESPACE, version=1, path_prefix=ROOT))
    features = sorted(set(package.manifest.required_features) | {FEATURE})
    package.manifest = package.manifest.model_copy(update={"annotation_schemas": schemas, "required_features": features})


def validate_interfaces(manifest, files):
    paths = [p for p in files if p.startswith(ROOT + "/")]
    if paths and (FEATURE not in manifest.required_features or not any(s.namespace == NAMESPACE and s.version == 1 for s in manifest.annotation_schemas)):
        raise ValueError("Design interfaces require a registered schema and required feature.")
    designs = {d.entity_id for d in manifest.documents if d.kind == "design"}
    internal = {c.internal_design.entity_id for c in manifest.component_compositions}
    for path in paths:
        value = DesignInterfaceV1.model_validate_json(files[path])
        if value.design.document_id != manifest.document_id or value.design.entity_id not in designs or path != interface_path(value.design.entity_id):
            raise ValueError("Design interface references an unknown or mismatched Design.")
        if value.design.entity_id in internal:
            raise ValueError("An internal Design uses its Component interface, not a separate Design interface.")


def boundary_interface(revision, design):
    """Return the sole semantic interface; no hidden Component is stored."""
    design = revision.resolve(design) if isinstance(design, EntityRef) else design
    return next((c for c in revision.components if revision.internal_design(c) == design), design)


def resolve_ports(interface, overrides=None):
    from .rtl_interface import resolve_interface
    result = resolve_interface(
        [{"name": p.name, "direction": p.direction, "range": (p.width[1:-1] if isinstance(p.width, str) else p.range) or None} for p in interface.ports if p.style == "wire"],
        [asdict(p) for p in interface.parameters], overrides=overrides,
    )
    if result["status"] != "resolved":
        raise ValueError(" · ".join(d["message"] for d in result["diagnostics"]))
    return {p["name"]: p for p in result["ports"]}


def instance_interface(revision, design, instance):
    """Expand child defaults in child scope and explicit overrides in parent scope."""
    import re
    from dataclasses import replace
    component = next(c for c in revision.components if c.vlnv == instance.component_vlnv)
    # A child default must be valid in its own scope, before applying parent overrides.
    resolve_ports(component)
    parent = boundary_interface(revision, design)
    defaults = {p.name: p.value for p in component.parameters}
    overrides = dict(instance.parameter_values)
    if set(overrides) - set(defaults):
        raise ValueError(f"Instance {instance.name} has an unknown parameter override.")
    expanded = dict(overrides)
    visiting = set()
    token = re.compile(r'"(?:\\.|[^"\\])*"|[A-Za-z_$][A-Za-z0-9_$]*')
    def expand(name):
        if name in expanded:
            return expanded[name]
        if name in visiting:
            raise ValueError(f"Cyclic parameter default: {name}")
        visiting.add(name)
        value = token.sub(lambda m: f"({expand(m[0])})" if m[0] in defaults else m[0], defaults[name])
        visiting.remove(name)
        expanded[name] = value
        return value
    for name in defaults:
        expand(name)
    ports = []
    for port in component.ports:
        declared_range = port.width[1:-1] if isinstance(port.width, str) else port.range
        effective_range = token.sub(lambda m: f"({expanded[m[0]]})" if m[0] in expanded else m[0], declared_range)
        ports.append(replace(port, range=effective_range, width=f"[{effective_range}]" if effective_range else 1))
    ports = tuple(ports)
    used_names = {p.name for p in parent.parameters} | {p.name for p in ports}
    probes = []
    for index, parameter in enumerate(component.parameters):
        name = f"__spec_parameter_{index}"
        while name in used_names:
            name += "_"
        used_names.add(name)
        probes.append(replace(parameter, name=name, value=expanded[parameter.name],
                              rtl_type=token.sub(lambda m: f"({expanded[m[0]]})" if m[0] in expanded else m[0], parameter.rtl_type or "")))
    return replace(component, ports=ports, parameters=(*parent.parameters, *probes))


def validate_design_connections(revision, design):
    """Check concrete wire endpoints after interface or instance edits."""
    boundary = boundary_interface(revision, design)
    boundary_shapes = resolve_ports(boundary)
    effective = {i.name: instance_interface(revision, design, i) for i in design.instances}
    shapes = {name: resolve_ports(value) for name, value in effective.items()}
    for connection in design.connections:
        if connection.kind != "ad_hoc":
            continue
        widths, directions = [], []
        for endpoint in (*connection.port_endpoints, *connection.external_ports):
            internal = hasattr(endpoint, "instance_name")
            interface = effective[endpoint.instance_name] if internal else boundary
            shape = shapes[endpoint.instance_name].get(endpoint.port_name) if internal else boundary_shapes.get(endpoint.port_name)
            if shape is None:  # Other port families keep their existing validation.
                continue
            if endpoint.symbolic_slice:
                continue
            if endpoint.slice:
                low = min(shape["left"] or 0, shape["right"] or 0)
                high = max(shape["left"] or 0, shape["right"] or 0)
                if endpoint.slice.lsb < low or endpoint.slice.lsb + endpoint.slice.width - 1 > high:
                    raise ValueError(f"Connection {connection.name} has an out-of-range slice.")
            widths.append(endpoint.slice.width if endpoint.slice else shape["width"])
            direction = next(p.direction for p in interface.ports if p.name == endpoint.port_name)
            directions.append(direction if internal else {"in": "out", "out": "in", "inout": "inout"}[direction])
        if len(set(widths)) > 1:
            raise ValueError(f"Connection {connection.name} has incompatible port widths.")
        if directions.count("out") > 1 and "inout" not in directions:
            raise ValueError(f"Connection {connection.name} has multiple ordinary drivers.")
