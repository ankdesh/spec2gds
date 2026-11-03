"""Prepare tutorial starts through the public Spec HTTP API and Activity SDK.

Uses an in-process production service, without a model or a running editor.
Never changes the active document in an existing service or overwrites a run.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs/tutorials/example.json"
STARTS = {"01": 0, "02": 0, "03": 1, "04": 2, "05": 3, "06": 4,
          "07": 5, "08": 5, "09": 5, "complete": 5}


def request(client, method, path, **kwargs):
    """Reject failed preparation with its public diagnostic."""
    response = client.request(method, path, **kwargs)
    if not response.is_success:
        raise ValueError(f"{method} {path}: {response.status_code} {response.text}")
    return response


def commit(client, operations):
    """Apply a batch against the current revision through /transactions."""
    source = request(client, "GET", "/documents/snapshot").json()
    return request(client, "POST", "/transactions", json={
        "expected_source_revision_hash": source["source_revision_hash"],
        "operations": operations, "validation_mode": "authoring",
    }).json()


def component_ops(key, data, body=True):
    """Convert the one canonical example to public API operations."""
    ref = f"component:{key}"
    operations = [{"type": "create_entity", "kind": "component", "name": data["name"], "entity_id": key},
                  {"type": "set_entity_metadata", "entity": ref,
                   "display_name": data["name"], "description": data["description"]}]
    for name, direction, bounds, description in data["ports"]:
        operations.append({"type": "add_component_port", "component": ref, "port": {
            "name": name, "family": "wire", "direction": direction,
            "range": bounds, "description": description}})
    if body and data.get("systemverilog"):
        operations.append({"type": "upsert_entity_section", "parent": ref,
                           "section_type": "sv", "payload": {"content": data["systemverilog"]}})
    return operations


def build_start(client, destination, stage, example):
    """Create one independent start, including only completed lesson content."""
    request(client, "POST", "/documents/create", json={
        "path": str(destination), "title": f"{example['title']} · {destination.stem}",
        "document_id": f"tutorial_{destination.stem.replace('-', '_')}",
    })
    components = example["components"]
    if stage >= 1:
        commit(client, component_ops("add16", components["add16"], body=stage >= 2))
    if stage >= 3:
        commit(client, component_ops("reg16", components["reg16"]) +
               component_ops("registered_adder", components["registered_adder"]))
    if stage >= 4:
        design = example["design"]
        operations = [{"type": "create_entity", "kind": "design", "name": design["name"],
                       "entity_id": design["id"], "entry_design": True}]
        operations += [{"type": "upsert_instance", "design": f"design:{design['id']}",
                        "instance": {"name": name, "component_vlnv": f"spec2gds.local:work:{components[key]['name']}:1.0"}}
                       for name, key in design["instances"]]
        # Use the identity returned by the service; readable names need not be VLNV names.
        source = request(client, "GET", "/documents/snapshot").json()
        identities = {item["ref"]["entity_id"]: item["vlnv"] for item in source["components"]}
        for operation, (_, key) in zip(operations[1:], design["instances"]):
            operation["instance"]["component_vlnv"] = identities[key]
        operations.append({"type": "set_internal_design", "component": "component:registered_adder",
                           "internal_design": f"design:{design['id']}"})
        commit(client, operations)
    if stage >= 5:
        operations = []
        for name, driver, sink, _width in example["design"]["nets"]:
            external, internal = [], []
            for endpoint in [driver, sink]:
                instance, port = endpoint.split(".")
                if instance == "top":
                    external.append(port)
                else:
                    internal.append({"instance_name": instance, "port_name": port})
            operations.append({"type": "upsert_connection", "design": f"design:{example['design']['id']}",
                               "connection": {"name": name, "kind": "ad_hoc",
                                              "port_endpoints": internal, "external_ports": external}})
        commit(client, operations)
        commit(client, [{"type": "upsert_narrative_block", "block": {
            "block_id": f"tutorial_{key}", "type": "paragraph",
            "text": f"{title}. Given {given}; when {when}; then {expected}.",
            "entity_refs": [{"document_id": request(client, 'GET', '/documents/snapshot').json()['document_id'],
                             "entity_kind": "component", "entity_id": "registered_adder"}],
        }} for key, title, given, when, expected, _ in example["verification"]])
    return request(client, "GET", "/documents/snapshot").json()


def prepare(output: Path, planner_url: str | None = None):
    """Write fresh starts under an ignored repository TEMP_ directory."""
    output = output.resolve()
    relative = output.relative_to(ROOT)
    if not any(part.startswith("TEMP_") for part in relative.parts):
        raise ValueError("Use an ignored repository TEMP_ directory for tutorial outputs.")
    if output.exists():
        raise FileExistsError(f"Use a fresh output directory; refusing to replace {output}")
    output.mkdir(parents=True)
    example = json.loads(EXAMPLE.read_text())
    config = json.loads((ROOT / "config/services.json").read_text())
    config["logging"].update(enabled=False, file=str(output / "events.jsonl"))
    config["activities"]["scratch_root"] = str(output / "generated")
    config["circuit_designer"]["preferences_file"] = str(output / "preferences.json")
    config_path = output / "services.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    # Scoped configuration for this process only; the tracked registry stays unchanged.
    saved = {key: os.environ.get(key) for key in ["SPEC_EDITOR_STATE_ROOT"]}
    os.environ["SPEC_EDITOR_STATE_ROOT"] = str(output / "spec-state")
    try:
        from fastapi.testclient import TestClient

        from spec2gds.spec.activities import ActivitySnapshot
        from spec2gds.spec.spec_format.archive import SpecPackage
        from spec2gds.spec.spec_format.ir import SpecRevision
        from spec2gds.spec.spec_format.v1_api import create_app

        starts = {}
        with TestClient(create_app(service_config=config_path)) as client:
            for lesson, stage in STARTS.items():
                destination = output / f"{lesson}-start.spec"
                source = build_start(client, destination, stage, example)
                starts[lesson] = {"path": str(destination), "source_revision_hash": source["source_revision_hash"]}
            build_tlm(client, output)
        source = SpecRevision.from_package(SpecPackage.load(str(output / "complete-start.spec")))
        target = next(item.ref for item in source.components if item.ref.entity_id == "registered_adder")
        snapshot = ActivitySnapshot.create(source, target)
        (output / "registered-adder.snapshot").write_bytes(snapshot.to_bytes())
        from scripts.tutorial_verification import prepare_verification
        verification = prepare_verification(output, snapshot, example, planner_url)
        (output / "register-prompt.txt").write_text(register_prompt(example))
        manifest = {"example": example["title"], "starts": starts, "verification": verification,
                    "snapshot_id": snapshot.manifest.snapshot_id, "functional_simulation": "unverified"}
        (output / "starts.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def register_prompt(example):
    """Provide the exact learning request without selecting a model."""
    data = example["components"]["reg16"]
    ports = "\n".join(f"{name}: {direction}, {bounds or 'scalar'}; {description}"
                      for name, direction, bounds, description in data["ports"])
    return (f"In this bound Spec, add one new Component named {data['name']}. Do not create another Spec or change the adder. "
            f"Prepare the architecture for my review before authoring.\n{data['description']}\n"
            f"Physical wire ports:\n{ports}\nUse this SystemVerilog module body:\n{data['systemverilog']}"
            "After approval, save the complete Component through the Spec service. Report its saved result or pending review state.\n")


def build_tlm(client, output):
    """Prepare a separate one-to-one TLM example through public XML transactions."""
    request(client, "POST", "/documents/create", json={
        "path": str(output / "tlm-start.spec"), "title": "TLM practice", "document_id": "tutorial_tlm",
    })
    namespace = "http://www.accellera.org/XMLSchema/IPXACT/1685-2022"

    def xml(root, key, body=""):
        return (f'<ipxact:{root} xmlns:ipxact="{namespace}" xml:id="{key}">'
                f'<ipxact:vendor>spec2gds.tutorial</ipxact:vendor><ipxact:library>tlm</ipxact:library>'
                f'<ipxact:name>{key}</ipxact:name><ipxact:version>1.0</ipxact:version>{body}</ipxact:{root}>')

    operations = [{"type": "upsert_document_xml", "kind": "bus_definition", "xml": xml("busDefinition", "tutorial_link",
                  '<ipxact:directConnection>true</ipxact:directConnection><ipxact:isAddressable>false</ipxact:isAddressable>')}]
    operations.append({"type": "upsert_document_xml", "kind": "abstraction_definition", "xml": xml(
        "abstractionDefinition", "tutorial_link_tlm",
        '<ipxact:busType vendor="spec2gds.tutorial" library="tlm" name="tutorial_link" version="1.0"/>'
        '<ipxact:ports><ipxact:port><ipxact:logicalName>payload</ipxact:logicalName><ipxact:wire>'
        '<ipxact:onInitiator><ipxact:direction>out</ipxact:direction></ipxact:onInitiator>'
        '<ipxact:onTarget><ipxact:direction>in</ipxact:direction></ipxact:onTarget>'
        '</ipxact:wire></ipxact:port></ipxact:ports>')})
    for key, role in [("initiator", "initiator"), ("target", "target")]:
        body = ('<ipxact:busInterfaces><ipxact:busInterface><ipxact:name>socket</ipxact:name>'
                '<ipxact:busType vendor="spec2gds.tutorial" library="tlm" name="tutorial_link" version="1.0"/>'
                '<ipxact:abstractionTypes><ipxact:abstractionType><ipxact:abstractionRef '
                'vendor="spec2gds.tutorial" library="tlm" name="tutorial_link_tlm" version="1.0"/>'
                '</ipxact:abstractionType></ipxact:abstractionTypes>'
                f'<ipxact:{role}/></ipxact:busInterface></ipxact:busInterfaces>')
        operations.append({"type": "upsert_document_xml", "kind": "component", "xml": xml("component", key, body)})
    operations += [{"type": "create_entity", "kind": "design", "name": "TLM practice", "entity_id": "tlm_practice"}]
    commit(client, operations)
    commit(client, [{"type": "upsert_instance", "design": "design:tlm_practice", "instance": {
        "name": f"u_{key}", "component_vlnv": f"spec2gds.tutorial:tlm:{key}:1.0"}} for key in ["initiator", "target"]] +
        [{"type": "upsert_connection", "design": "design:tlm_practice", "connection": {
            "name": "transaction", "kind": "interface", "interface_endpoints": [
                {"instance_name": "u_initiator", "interface_name": "socket"},
                {"instance_name": "u_target", "interface_name": "socket"}]}}])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Fresh directory beneath a repository TEMP_ folder")
    parser.add_argument("--planner-url", help="Optional running Verification Planner URL; add new tutorial plans only")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output, args.planner_url), indent=2))
    except (ValueError, FileExistsError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
