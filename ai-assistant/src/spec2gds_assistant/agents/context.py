from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from xml.etree import ElementTree

from ..models import CircuitAgentRequest, ProcessedContext, SpecAgentRequest

ContextT = TypeVar("ContextT")


class ContextProcessor(ABC, Generic[ContextT]):
    """Convert domain context into deterministic text suitable for an LLM."""

    @abstractmethod
    def process(self, context: ContextT) -> ProcessedContext:
        """Return an LLM-readable representation without invoking a model."""


class CircuitContextProcessor(ContextProcessor[CircuitAgentRequest]):
    """Describe one semantic snapshot and its Circuit Designer SVG."""

    def process(self, context: CircuitAgentRequest) -> ProcessedContext:
        snapshot = context.snapshot
        revision = str(snapshot.get("revision", ""))
        document = snapshot.get("document")
        if not revision or not isinstance(document, dict):
            raise ValueError("Circuit context must be a snapshot with revision and document.")

        document_id = str(document.get("document_id", ""))
        if not document_id:
            raise ValueError("Circuit document_id is required.")

        components = document.get("components")
        design = document.get("design")
        if not isinstance(components, list) or not isinstance(design, dict):
            raise ValueError("Circuit document must contain components and design.")

        lines = [
            f"Circuit document: {document_id}",
            f"Revision: {revision}",
            f"Label: {document.get('label', document_id)}",
            f"Design: {design.get('id')} ({design.get('label', design.get('id'))})",
            "",
            "CIRCUIT OBJECT MODEL:",
            "- A component definition is a reusable type in components[].",
            "- An instance is a placed use of a component definition in design.instances[].",
            "- A component terminal is a reusable pin on every instance of that definition.",
            "- A boundary terminal is a top-level design port, not a component pin.",
            "- A net connects instance terminals and/or boundary terminals.",
            "",
            "COMPONENT DEFINITIONS (exact current JSON; copy the complete object when updating):",
        ]
        for value in components:
            if not isinstance(value, dict):
                continue
            lines.append(
                f"- {value.get('id')}: {value.get('label')} "
                f"(origin={value.get('origin')}, editable={value.get('editable')})"
            )
            terminals = value.get("terminals")
            if isinstance(terminals, list):
                for terminal in terminals:
                    if not isinstance(terminal, dict):
                        continue
                    lines.append(
                        "  - terminal "
                        f"{terminal.get('id')}: direction={terminal.get('direction')}, "
                        f"category={terminal.get('category')}, width={terminal.get('width')}"
                    )
            parameters = value.get("parameters")
            if isinstance(parameters, list) and parameters:
                lines.append(
                    "  - parameters: "
                    + json.dumps(parameters, sort_keys=True, separators=(",", ":"))
                )
            lines.append(
                "  - complete definition: "
                + json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            appearance = value.get("appearance")
            properties = appearance.get("properties") if isinstance(appearance, dict) else None
            if isinstance(properties, dict):
                lines.append(
                    "  - model-output appearance.properties: "
                    + json.dumps(
                        [
                            {"name": name, "value": property_value}
                            for name, property_value in sorted(properties.items())
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
        if not components:
            lines.append("- (none)")

        instances = design.get("instances")
        lines.extend(["", "INSTANCES (exact current JSON):"])
        if isinstance(instances, list):
            for instance in instances:
                if isinstance(instance, dict):
                    lines.append(
                        f"- {instance.get('id')}: component={instance.get('component_id')}, "
                        f"label={instance.get('label')}, "
                        "parameters="
                        + json.dumps(
                            instance.get("parameter_values", {}),
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    lines.append(
                        "  - complete instance: "
                        + json.dumps(
                            instance,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    parameter_values = instance.get("parameter_values", {})
                    if isinstance(parameter_values, dict):
                        lines.append(
                            "  - model-output parameter_values: "
                            + json.dumps(
                                [
                                    {"name": name, "value": value}
                                    for name, value in sorted(parameter_values.items())
                                ],
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        )
        if not instances:
            lines.append("- (none)")

        boundary_terminals = design.get("boundary_terminals")
        lines.extend(["", "BOUNDARY TERMINALS / TOP-LEVEL PORTS (exact current JSON):"])
        if isinstance(boundary_terminals, list):
            for terminal in boundary_terminals:
                if isinstance(terminal, dict):
                    lines.append(
                        f"- {terminal.get('id')}: direction={terminal.get('direction')}, "
                        f"category={terminal.get('category')}, width={terminal.get('width')}; "
                        "complete terminal="
                        + json.dumps(
                            terminal,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
        if not boundary_terminals:
            lines.append("- (none)")

        nets = design.get("nets")
        lines.extend(["", "NETS AND ENDPOINTS (exact current JSON):"])
        if isinstance(nets, list):
            for net in nets:
                if not isinstance(net, dict):
                    continue
                lines.append(
                    f"- {net.get('id')}: label={net.get('label')}, endpoints="
                    + json.dumps(
                        net.get("endpoints", []),
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
        if not nets:
            lines.append("- (none)")

        component_by_id = {
            str(value.get("id")): value
            for value in components
            if isinstance(value, dict) and value.get("id")
        }
        lines.extend([
            "",
            "VALID ENDPOINT CATALOG (use only these exact existing IDs):",
        ])
        endpoint_count = 0
        if isinstance(instances, list):
            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                instance_id = str(instance.get("id", ""))
                component = component_by_id.get(str(instance.get("component_id", "")))
                terminals = component.get("terminals") if isinstance(component, dict) else None
                if not isinstance(terminals, list):
                    continue
                for terminal in terminals:
                    if not isinstance(terminal, dict):
                        continue
                    endpoint_count += 1
                    lines.append(
                        "- instance endpoint "
                        f"{instance_id}.{terminal.get('id')}: "
                        f"direction={terminal.get('direction')}, width={terminal.get('width')}; "
                        "payload="
                        + json.dumps(
                            {
                                "kind": "instance",
                                "instance_id": instance_id,
                                "terminal_id": terminal.get("id"),
                                "slice": None,
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
        if isinstance(boundary_terminals, list):
            for terminal in boundary_terminals:
                if not isinstance(terminal, dict):
                    continue
                endpoint_count += 1
                lines.append(
                    f"- boundary endpoint {terminal.get('id')}: "
                    f"direction={terminal.get('direction')}, width={terminal.get('width')}; "
                    "payload="
                    + json.dumps(
                        {
                            "kind": "boundary",
                            "terminal_id": terminal.get("id"),
                            "slice": None,
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
        if not endpoint_count:
            lines.append("- (none; add a component terminal or boundary terminal first)")

        lines.extend([
            "",
            "SEMANTIC EDITING FACTS:",
            "- Existing IDs above are authoritative and must be reused exactly.",
            "- New IDs must be unique lowercase slugs matching existing naming style.",
            "- Adding a component definition does not place it; add_instance places one use.",
            "- Adding a component pin requires update_component with the full definition.",
            "- Adding a top-level port requires add_boundary_terminal.",
            "- In model output, parameter_values and appearance.properties are lists of {name,value}; serialization converts them to maps for Circuit Designer.",
            "- A new net carries one or more endpoints in create_net; later endpoints use connect_endpoint.",
            "- Endpoint slice is null for the whole terminal; otherwise use {lsb,width} within a numeric width.",
            "- Input/output direction is viewed at the component. A boundary input is a source into the design.",
        ])

        warnings: list[str] = []
        lines.extend(["", "Circuit Designer SVG:"])
        if context.svg:
            try:
                root = ElementTree.fromstring(context.svg)
                descendants = list(root.iter())
                instance_ids = sorted(
                    {
                        value
                        for element in descendants
                        if (value := element.get("data-instance-id"))
                    }
                )
                net_ids = sorted(
                    {
                        value
                        for element in descendants
                        if (value := element.get("data-net-id"))
                    }
                )
                lines.append(
                    "- rendered SVG "
                    f"viewBox={root.get('viewBox', 'unspecified')}, "
                    f"width={root.get('width', 'unspecified')}, "
                    f"height={root.get('height', 'unspecified')}"
                )
                lines.append(
                    f"- {len(descendants)} SVG elements; "
                    f"instance ids={json.dumps(instance_ids)}; "
                    f"net ids={json.dumps(net_ids)}"
                )
                lines.append(
                    "- The SVG is a visual aid. The semantic circuit document "
                    "above is authoritative for IDs and connectivity."
                )
            except ElementTree.ParseError:
                warnings.append("The supplied SVG could not be parsed.")
                lines.append("- supplied SVG was invalid and was not used")
        else:
            warnings.append("No SVG rendering was supplied.")
            lines.append("- no SVG rendering was supplied")

        return ProcessedContext(
            text="\n".join(lines),
            document_id=document_id,
            revision=revision,
            warnings=warnings,
        )


class SpecContextProcessor(ContextProcessor[SpecAgentRequest]):
    """Describe document- or entity-bound Spec context without exposing XML."""

    def process(self, context: SpecAgentRequest) -> ProcessedContext:
        value = context.context
        document_id = str(value.get("document_id", ""))
        revision = str(value.get("source_revision_hash", ""))
        scope = str(value.get("scope", "entity"))
        target = value.get("target")
        writable = value.get("writable")
        read_only = value.get("read_only")
        references = value.get("available_references")
        if not document_id or not revision:
            raise ValueError("Spec context requires document and revision identity.")
        if scope == "document":
            rendered = value.get("rendered_context")
            if not isinstance(rendered, dict):
                raise ValueError("Document Spec context requires a rendered context.")
            if (
                rendered.get("document_id") != document_id
                or rendered.get("source_revision_hash") != revision
                or rendered.get("target") is not None
                or not isinstance(rendered.get("text"), str)
            ):
                raise ValueError("Rendered document context identity does not match its binding.")
            lines = [
                f"Spec document: {document_id}",
                f"Source revision: {revision}",
                "Scope: complete specification",
                "WRITABLE BOUNDARY: create new top-level components or designs only.",
                "A new design may include initial instances of existing components, using "
                "their exact VLNV values from the semantic specification below.",
                "All existing entities and their contents are read-only in this scope.",
                "",
                str(rendered["text"]),
            ]
            if isinstance(references, dict):
                lines.extend(
                    [
                        "",
                        "EXISTING REFERENCES (copy exact identities and VLNV values):",
                        json.dumps(references, ensure_ascii=False, sort_keys=True, indent=2),
                    ]
                )
            if context.conversation_summary:
                lines.extend(["", "OLDER CONVERSATION SUMMARY:", context.conversation_summary])
            if context.recent_messages:
                lines.extend(
                    [
                        "",
                        "RECENT CONVERSATION (oldest to newest):",
                        json.dumps(
                            context.recent_messages,
                            ensure_ascii=False,
                            sort_keys=True,
                            indent=2,
                        ),
                    ]
                )
            warnings = [
                str(item) for item in value.get("diagnostics", []) if isinstance(item, str)
            ]
            return ProcessedContext(
                text="\n".join(lines),
                document_id=document_id,
                revision=revision,
                warnings=warnings,
                scope="document",
            )
        if scope != "entity" or not isinstance(target, dict):
            raise ValueError("Entity Spec context requires a target identity.")
        if not isinstance(writable, dict) or not isinstance(read_only, dict):
            raise ValueError("Spec context requires writable and read-only sections.")

        lines = [
            f"Spec document: {document_id}",
            f"Source revision: {revision}",
            "Selected target: " + json.dumps(target, sort_keys=True, separators=(",", ":")),
            "",
            "WRITABLE BOUNDARY (operations must stay inside these refs):",
            json.dumps(writable.get("entity_refs", []), ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "WRITABLE SEMANTIC IR:",
            json.dumps(writable.get("entity"), ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "WRITABLE OWNED INTERNAL DESIGN:",
            json.dumps(
                writable.get("owned_internal_design"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ),
            "",
            "WRITABLE RENDERED SECTIONS:",
            json.dumps(writable.get("sections", []), ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "WRITABLE LINKED NARRATIVE:",
            json.dumps(writable.get("linked_narrative", []), ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "READ-ONLY SURROUNDING CONTEXT (never target with operations):",
            json.dumps(read_only, ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "EXISTING REFERENCES ALLOWED IN TYPED OPERATIONS:",
            json.dumps(references or {}, ensure_ascii=False, sort_keys=True, indent=2),
            "",
            "PLAIN-LANGUAGE TASK MAPPING:",
            "- On a component target, create/add a port means upsert_component_port.",
            "- On a design target, create/add a component means upsert_instance using an available component reference.",
            "- On a design target, connect ports/nets means upsert_connection; physical wires use kind=ad_hoc.",
            "- For design connections, use only port/interface names listed on the referenced components; never invent endpoints.",
            "- An ad_hoc connection uses port_endpoints only; an interface connection uses interface_endpoints only.",
            "- Creating a new top-level component or design is outside this entity-bound context.",
        ]
        if context.conversation_summary:
            lines.extend(["", "OLDER CONVERSATION SUMMARY:", context.conversation_summary])
        if context.recent_messages:
            lines.extend([
                "",
                "RECENT CONVERSATION (oldest to newest):",
                json.dumps(context.recent_messages, ensure_ascii=False, sort_keys=True, indent=2),
            ])
        warnings = [str(item) for item in value.get("diagnostics", []) if isinstance(item, str)]
        return ProcessedContext(
            text="\n".join(lines),
            document_id=document_id,
            revision=revision,
            warnings=warnings,
            scope="entity",
        )
