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
            "",
            "Available component definitions (only these may be instantiated):",
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

        instances = design.get("instances")
        lines.extend(["", "Instances:"])
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

        boundary_terminals = design.get("boundary_terminals")
        lines.extend(["", "Boundary terminals:"])
        if isinstance(boundary_terminals, list):
            for terminal in boundary_terminals:
                if isinstance(terminal, dict):
                    lines.append(
                        f"- {terminal.get('id')}: direction={terminal.get('direction')}, "
                        f"category={terminal.get('category')}, width={terminal.get('width')}"
                    )

        nets = design.get("nets")
        lines.extend(["", "Nets and endpoints:"])
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
    """Describe an entity-bound semantic Spec context without exposing XML."""

    def process(self, context: SpecAgentRequest) -> ProcessedContext:
        value = context.context
        document_id = str(value.get("document_id", ""))
        revision = str(value.get("source_revision_hash", ""))
        target = value.get("target")
        writable = value.get("writable")
        read_only = value.get("read_only")
        references = value.get("available_references")
        if not document_id or not revision or not isinstance(target, dict):
            raise ValueError("Spec context requires document, revision, and target identity.")
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
        )
