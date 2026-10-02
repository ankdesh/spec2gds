"""Deterministic C++ rendering for structural SystemC AT models."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from jinja2 import Environment, PackageLoader, StrictUndefined

from spec2gds.agent_spec.activities.view import SpecAccess
from spec2gds.agent_spec.spec_format.ir import (
    ComponentIR,
    ConnectionIR,
    DesignIR,
    InterfaceIR,
)
from spec2gds.agent_spec.spec_format.models import EntityRef, sha256_digest
from spec2gds.agent_spec.spec_format.naming import entity_name

GENERATOR_ID = "systemc.generate_at_skeleton"
GENERATOR_VERSION = "1.0.0"
GENERATION_SCHEMA = "spec2gds.systemc-at-generation.v1"

_TEMPLATES = Environment(
    loader=PackageLoader(
        "spec2gds.agent_spec.activities.systemc_at",
        "templates",
    ),
    undefined=StrictUndefined,
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
    newline_sequence="\n",
    keep_trailing_newline=True,
)

_CPP_KEYWORDS = {
    "alignas",
    "alignof",
    "and",
    "asm",
    "auto",
    "bool",
    "break",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "constexpr",
    "continue",
    "default",
    "delete",
    "do",
    "double",
    "else",
    "enum",
    "explicit",
    "export",
    "extern",
    "false",
    "float",
    "for",
    "friend",
    "goto",
    "if",
    "inline",
    "int",
    "long",
    "namespace",
    "new",
    "noexcept",
    "not",
    "nullptr",
    "operator",
    "or",
    "private",
    "protected",
    "public",
    "register",
    "reinterpret_cast",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "struct",
    "switch",
    "template",
    "this",
    "throw",
    "true",
    "try",
    "typedef",
    "typename",
    "union",
    "unsigned",
    "using",
    "virtual",
    "void",
    "volatile",
    "while",
    "xor",
}


@dataclass(frozen=True)
class GeneratedProject:
    """Complete deterministic project before workspace publication."""

    files: dict[str, bytes]
    top_class: str
    component_definition_count: int
    component_instance_count: int
    design_module_count: int
    connection_count: int


@dataclass(frozen=True)
class _Endpoint:
    instance_name: str
    interface_name: str
    role: str


@dataclass(frozen=True)
class _Binding:
    kind: str
    first: _Endpoint
    second: _Endpoint | None = None
    owner_interface: str = ""


@dataclass
class _Module:
    class_name: str
    header_path: str
    path: tuple[str, ...]
    component: ComponentIR | None
    design: DesignIR | None
    external_interfaces: tuple[InterfaceIR, ...]
    socket_names: dict[str, str]
    instance_name: str = ""
    member_name: str = ""
    children: list["_Module"] = field(default_factory=list)
    bindings: list[_Binding] = field(default_factory=list)


class _NamePool:
    """Allocate stable C++ class and header names for one generation run."""
    def __init__(self) -> None:
        self._class_names: set[str] = set()
        self._header_stems: set[str] = set()

    def module_names(self, *, kind: str, path: tuple[str, ...]) -> tuple[str, str]:
        """Allocate one unique C++ class name and matching header stem."""
        raw = f"{kind}_{'_'.join(path)}"
        class_name = self._unique(_pascal(raw), raw, self._class_names)
        header_stem = self._unique(_slug(raw), raw, self._header_stems)
        return class_name, header_stem

    @staticmethod
    def _unique(base: str, raw: str, used: set[str]) -> str:
        candidate = base
        suffix = hashlib.sha256(raw.encode()).hexdigest()[:8]
        index = 1
        while candidate in used:
            candidate = f"{base}_{suffix}" if index == 1 else f"{base}_{suffix}_{index}"
            index += 1
        used.add(candidate)
        return candidate


class _Generator:
    """Validate topology and build the hierarchy rendered by the templates."""
    def __init__(self, spec: SpecAccess) -> None:
        self.spec = spec
        self.components_by_vlnv = {item.vlnv: item for item in spec.low.components}
        self.names = _NamePool()
        self.diagnostics: list[str] = []

    def validate(self, design: DesignIR) -> tuple[str, ...]:
        """Collect all reachable topology diagnostics without publishing files."""
        self._build_design_module(
            design=design,
            owner_component=None,
            external_interface_names=(),
            path=(design.ref.entity_id,),
            instance_name="top",
            top=True,
        )
        return tuple(sorted(set(self.diagnostics)))

    def build(self, design: DesignIR) -> _Module:
        """Build the normalized module tree after successful preflight."""
        module = self._build_design_module(
            design=design,
            owner_component=None,
            external_interface_names=(),
            path=(design.ref.entity_id,),
            instance_name="top",
            top=True,
        )
        if self.diagnostics:
            raise ValueError("Unsupported SystemC topology: " + "; ".join(sorted(set(self.diagnostics))))
        return module

    def _build_design_module(
        self,
        *,
        design: DesignIR,
        owner_component: ComponentIR | None,
        external_interface_names: tuple[str, ...],
        path: tuple[str, ...],
        instance_name: str,
        top: bool,
    ) -> _Module:
        """Construct the reachable design hierarchy and accepted socket bindings.

        Component-owned interfaces determine boundary bindings. Reusable definitions
        and per-occurrence member names are kept separate during recursive descent.
        """
        context = "/".join(path)
        external_by_name = {
            item.name: item
            for item in (owner_component.interfaces if owner_component is not None else ())
            if item.name in external_interface_names
        }
        bindings = self._analyze_connections(design, owner_component, context)
        effective_bindings = [
            item
            for item in bindings
            if item.kind == "normal" or item.owner_interface in external_by_name
        ]
        if owner_component is not None:
            mapped = {item.owner_interface for item in effective_bindings if item.kind == "hierarchy"}
            for interface_name in external_interface_names:
                if interface_name not in mapped:
                    self.diagnostics.append(
                        f"{context}: composite interface {interface_name} has no supported hierarchy binding."
                    )

        used_by_instance: dict[str, set[str]] = {item.name: set() for item in design.instances}
        for binding in effective_bindings:
            used_by_instance[binding.first.instance_name].add(binding.first.interface_name)
            if binding.second is not None:
                used_by_instance[binding.second.instance_name].add(binding.second.interface_name)

        kind = "top" if top else "design"
        class_name, stem = self.names.module_names(kind=kind, path=path)
        header_path = f"include/designs/{stem}.h"
        socket_names = _unique_identifiers(
            external_by_name,
            reserved=("nb_transport_bw", "nb_transport_fw"),
        )
        module = _Module(
            class_name=class_name,
            header_path=header_path,
            path=path,
            component=owner_component,
            design=design,
            external_interfaces=tuple(external_by_name.values()),
            socket_names=socket_names,
            instance_name=instance_name,
            member_name=_identifier(instance_name),
            bindings=effective_bindings,
        )

        member_names = _unique_identifiers(
            (item.name for item in design.instances),
            reserved=(*socket_names.values(), "nb_transport_bw", "nb_transport_fw"),
        )
        for instance in design.instances:
            component = self.components_by_vlnv[instance.component_vlnv]
            used_names = tuple(
                item.name for item in component.interfaces if item.name in used_by_instance[instance.name]
            )
            child_path = (*path, instance.name)
            internal = self.spec.low.internal_design(component)
            if internal is None:
                child_class, child_stem = self.names.module_names(
                    kind="component", path=child_path
                )
                used_interfaces = tuple(
                    item for item in component.interfaces if item.name in used_names
                )
                child = _Module(
                    class_name=child_class,
                    header_path=f"include/components/{child_stem}.h",
                    path=child_path,
                    component=component,
                    design=None,
                    external_interfaces=used_interfaces,
                    socket_names=_unique_identifiers(
                        (item.name for item in used_interfaces),
                        reserved=("nb_transport_bw", "nb_transport_fw"),
                    ),
                    instance_name=instance.name,
                    member_name=member_names[instance.name],
                )
            else:
                child = self._build_design_module(
                    design=internal,
                    owner_component=component,
                    external_interface_names=used_names,
                    path=child_path,
                    instance_name=instance.name,
                    top=False,
                )
                child.member_name = member_names[instance.name]
            module.children.append(child)
        return module

    def _analyze_connections(
        self,
        design: DesignIR,
        owner_component: ComponentIR | None,
        context: str,
    ) -> list[_Binding]:
        instances = {item.name: item for item in design.instances}
        bindings: list[_Binding] = []
        for connection in design.connections:
            label = f"{context}: connection {connection.name}"
            if connection.kind != "interface":
                self.diagnostics.append(f"{label} is ad-hoc; only TLM interfaces are supported.")
                continue
            endpoints: list[_Endpoint] = []
            for endpoint in connection.interface_endpoints:
                instance = instances[endpoint.instance_name]
                component = self.components_by_vlnv[instance.component_vlnv]
                interface = next(
                    item for item in component.interfaces if item.name == endpoint.interface_name
                )
                endpoints.append(_Endpoint(endpoint.instance_name, interface.name, interface.role))

            if connection.hierarchy_interfaces:
                self._analyze_hierarchy_connection(
                    connection, owner_component, endpoints, label, bindings
                )
                continue
            if len(endpoints) != 2:
                self.diagnostics.append(
                    f"{label} has {len(endpoints)} endpoints; exactly one initiator and one target are required."
                )
                continue
            roles = {item.role for item in endpoints}
            if roles != {"initiator", "target"}:
                self.diagnostics.append(
                    f"{label} uses roles {', '.join(sorted(roles)) or '(none)'}; exactly one initiator and one target are required."
                )
                continue
            initiator = next(item for item in endpoints if item.role == "initiator")
            target = next(item for item in endpoints if item.role == "target")
            bindings.append(_Binding(kind="normal", first=initiator, second=target))
        return bindings

    def _analyze_hierarchy_connection(
        self,
        connection: ConnectionIR,
        owner_component: ComponentIR | None,
        endpoints: list[_Endpoint],
        label: str,
        bindings: list[_Binding],
    ) -> None:
        if owner_component is None:
            self.diagnostics.append(f"{label} exposes a hierarchy interface from a top-level design.")
            return
        if len(connection.hierarchy_interfaces) != 1 or len(endpoints) != 1:
            self.diagnostics.append(
                f"{label} is an ambiguous hierarchy connection; exactly one boundary and one internal endpoint are required."
            )
            return
        owner_name = connection.hierarchy_interfaces[0]
        owner_interface = next(
            (item for item in owner_component.interfaces if item.name == owner_name), None
        )
        if owner_interface is None:
            self.diagnostics.append(f"{label} references missing hierarchy interface {owner_name}.")
            return
        endpoint = endpoints[0]
        roles = {owner_interface.role, endpoint.role}
        if roles - {"initiator", "target"}:
            self.diagnostics.append(
                f"{label} uses unsupported hierarchy roles {', '.join(sorted(roles)) or '(none)'}."
            )
            return
        if owner_interface.role != endpoint.role:
            self.diagnostics.append(
                f"{label} changes role across a hierarchy boundary; same-role socket export is required."
            )
            return
        bindings.append(
            _Binding(kind="hierarchy", first=endpoint, owner_interface=owner_name)
        )


def validate_project(spec: SpecAccess, target: EntityRef) -> tuple[str, ...]:
    """Return all structural diagnostics for one selected design."""
    design = spec.low.resolve(target)
    if not isinstance(design, DesignIR):
        return ("SystemC AT generation requires a selected design.",)
    return _Generator(spec).validate(design)


def generate_project(spec: SpecAccess, target: EntityRef) -> GeneratedProject:
    """Render one validated selected design into a complete project tree."""
    design = spec.low.resolve(target)
    if not isinstance(design, DesignIR):
        raise TypeError("SystemC AT generation requires a selected design.")
    root = _Generator(spec).build(design)
    files: dict[str, bytes] = {}
    for module in _walk_modules(root):
        files[module.header_path] = _render_module(module).encode("utf-8")
    files["src/main.cpp"] = _render_main(root, design).encode("utf-8")
    files["CMakeLists.txt"] = _render_cmake(design).encode("utf-8")
    files["README.md"] = _render_readme(design).encode("utf-8")

    inventory = [
        {"path": path, "sha256": sha256_digest(data), "size": len(data)}
        for path, data in sorted(files.items())
    ]
    manifest = {
        "schema_version": GENERATION_SCHEMA,
        "generator_id": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "document_id": target.document_id,
        "source_revision_hash": spec.high.document["source_revision_hash"],
        "design_id": target.entity_id,
        "design_vlnv": design.vlnv,
        "files": inventory,
    }
    files["generation-manifest.json"] = _json_bytes(manifest)

    modules = tuple(_walk_modules(root))
    component_refs = {
        item.component.ref for item in modules if item.component is not None
    }
    return GeneratedProject(
        files=files,
        top_class=root.class_name,
        component_definition_count=len(component_refs),
        component_instance_count=sum(item.component is not None for item in modules),
        design_module_count=sum(item.design is not None for item in modules),
        connection_count=sum(len(item.bindings) for item in modules),
    )


def _walk_modules(root: _Module):
    yield root
    for child in root.children:
        yield from _walk_modules(child)


def _render_module(module: _Module) -> str:
    """Format a validated module/socket model through packaged templates.

    Topology decisions are already complete. Generated callbacks are structural
    stubs and must not be read as inferred timing or performance behavior.
    """
    guard = _identifier(module.header_path.upper().replace("/", "_").replace(".", "_"))
    includes = ["#include <systemc>"]
    roles = {item.role for item in module.external_interfaces}
    if module.design is None:
        includes.append("#include <tlm>")
    if "initiator" in roles:
        includes.append("#include <tlm_utils/simple_initiator_socket.h>")
    if "target" in roles:
        includes.append("#include <tlm_utils/simple_target_socket.h>")
    for child in module.children:
        includes.append(f'#include "{child.header_path.removeprefix("include/")}"')

    sockets = tuple(
        {
            "type": (
                "simple_initiator_socket"
                if interface.role == "initiator"
                else "simple_target_socket"
            ),
            "name": module.socket_names[interface.name],
        }
        for interface in module.external_interfaces
    )

    initializers = ["sc_core::sc_module(name)"]
    initializers.extend(
        f'{module.socket_names[item.name]}({_cpp_string(item.name)})'
        for item in module.external_interfaces
    )
    initializers.extend(
        f'{child.member_name}({_cpp_string(child.instance_name)})' for child in module.children
    )
    constructor_statements: list[str] = []
    if module.design is None:
        for interface in module.external_interfaces:
            socket = module.socket_names[interface.name]
            if interface.role == "initiator":
                constructor_statements.append(
                    f"{socket}.register_nb_transport_bw(this, &{module.class_name}::nb_transport_bw);"
                )
            else:
                constructor_statements.append(
                    f"{socket}.register_nb_transport_fw(this, &{module.class_name}::nb_transport_fw);"
                )
    else:
        children = {item.instance_name: item for item in module.children}
        for binding in module.bindings:
            first_child = children[binding.first.instance_name]
            first_socket = first_child.socket_names[binding.first.interface_name]
            if binding.kind == "hierarchy":
                owner_socket = module.socket_names[binding.owner_interface]
                if binding.first.role == "initiator":
                    constructor_statements.append(
                        f"{first_child.member_name}.{first_socket}.bind({owner_socket});"
                    )
                else:
                    constructor_statements.append(
                        f"{owner_socket}.bind({first_child.member_name}.{first_socket});"
                    )
            else:
                assert binding.second is not None
                second_child = children[binding.second.instance_name]
                second_socket = second_child.socket_names[binding.second.interface_name]
                constructor_statements.append(
                    f"{first_child.member_name}.{first_socket}.bind({second_child.member_name}.{second_socket});"
                )

    private_members = tuple(
        {"class_name": child.class_name, "member_name": child.member_name}
        for child in module.children
    )
    return _render_template(
        "module.h.j2",
        guard=guard,
        includes=tuple(sorted(set(includes))),
        class_name=module.class_name,
        sockets=sockets,
        initializers=tuple(initializers),
        constructor_statements=tuple(constructor_statements),
        private_members=private_members,
        has_target_callback=module.design is None and "target" in roles,
        has_initiator_callback=module.design is None and "initiator" in roles,
    )


def _render_main(root: _Module, design: DesignIR) -> str:
    include = root.header_path.removeprefix("include/")
    start_message = _cpp_string(f"[CYCLE: 0] [SYSTEM] Starting {entity_name(design)} (AT skeleton)\\n")
    finish_message = _cpp_string(
        f"[CYCLE: 10] [SYSTEM] Finished {entity_name(design)} (AT skeleton)\\n"
    )
    return _render_template(
        "main.cpp.j2",
        include=include,
        top_class=root.class_name,
        start_message=start_message,
        finish_message=finish_message,
    )


def _render_cmake(design: DesignIR) -> str:
    project = _identifier(design.vlnv.split(":")[2])
    return _render_template("CMakeLists.txt.j2", project=project)


def _render_readme(design: DesignIR) -> str:
    project = _identifier(design.vlnv.split(":")[2])
    return _render_template("README.md.j2", design_vlnv=entity_name(design), project=project)


def _render_template(name: str, **context: object) -> str:
    """Render a packaged deterministic text template with a normalized context."""
    return _TEMPLATES.get_template(name).render(**context)


def _unique_identifiers(values, *, reserved=()) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set(reserved)
    for value in values:
        base = _identifier(value)
        candidate = base
        suffix = hashlib.sha256(value.encode()).hexdigest()[:8]
        index = 1
        while candidate in used:
            candidate = f"{base}_{suffix}" if index == 1 else f"{base}_{suffix}_{index}"
            index += 1
        used.add(candidate)
        result[value] = candidate
    return result


def _identifier(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_]", "_", value)
    candidate = re.sub(r"_+", "_", candidate).strip("_") or "generated"
    if candidate[0].isdigit():
        candidate = f"n_{candidate}"
    if candidate in _CPP_KEYWORDS:
        candidate = f"generated_{candidate}"
    return candidate


def _slug(value: str) -> str:
    return _identifier(value).lower()


def _pascal(value: str) -> str:
    parts = [item for item in re.split(r"[^A-Za-z0-9]+", value) if item]
    candidate = "".join(item[:1].upper() + item[1:] for item in parts) or "Generated"
    if candidate[0].isdigit():
        candidate = f"N{candidate}"
    return candidate


def _cpp_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
