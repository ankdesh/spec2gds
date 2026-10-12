"""Read-only SystemVerilog interface elaboration shared by reviews and Activities."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from xml.etree import ElementTree as ET

RTL_NAMESPACE = "urn:spec2gds:rtl"
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*\Z")
LITERAL = re.compile(r"[+-]?[0-9][0-9_]*\Z")


def unbracket(value: str) -> str:
    value = value.strip()
    return value[1:-1].strip() if value.startswith("[") and value.endswith("]") else value


def split_range(expression: str) -> tuple[str, str]:
    """Find a range separator without splitting a constant conditional expression."""
    for scope in re.finditer(r"::", expression):
        if not re.search(r"[A-Za-z_$][\w$]*\s*$", expression[:scope.start()]) or not re.match(r"\s*[A-Za-z_$]", expression[scope.end():]):
            raise ValueError("Wire port Range requires a valid left:right expression pair.")
    depth = 0
    conditional = 0
    separator = None
    for index, character in enumerate(expression):
        if character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif depth == 0 and character == "?":
            conditional += 1
        elif depth == 0 and character == ":" and not (expression[index:index + 2] == "::" or index and expression[index - 1:index + 1] == "::"):
            if conditional:
                conditional -= 1
            elif separator is not None:
                raise ValueError("Wire port Range requires one left:right expression pair.")
            else:
                separator = index
        if depth < 0:
            raise ValueError("Wire port Range has unbalanced delimiters.")
    if depth or conditional:
        raise ValueError("Wire port Range has unbalanced delimiters.")
    if separator is None:
        return expression, expression
    left, right = expression[:separator].strip(), expression[separator + 1:].strip()
    if not left or not right:
        raise ValueError("Wire port Range requires expressions on both sides of the colon.")
    return left, right


def parameter_declarations(parameters) -> str:
    names = set()
    declarations = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise ValueError("Each parameter must contain an ID, type, and default value.")
        name = parameter.get("name", "")
        value = parameter.get("value")
        rtl_type = parameter.get("rtl_type", parameter.get("data_type") or "")
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in names:
            raise ValueError(f"Parameter {name!r} requires a distinct RTL identifier.")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Parameter {name} needs a supplied default value.")
        if not isinstance(rtl_type, str):
            raise ValueError(f"Parameter {name} requires a declaration type string.")
        # Only declarations from explicit stored fields enter this header.
        if any(token in rtl_type for token in (";", "`", "\n")):
            raise ValueError(f"Parameter {name} has an invalid declaration type.")
        names.add(name)
        declarations.append(f"parameter {rtl_type + ' ' if rtl_type else ''}{name} = {value}")
    return ",\n    ".join(declarations)


def module_declaration(name: str, ports, parameters=()) -> str:
    header = f"module {name}"
    declarations = parameter_declarations(parameters)
    if declarations:
        header += f" #(\n    {declarations}\n)"
    port_lines = []
    for port in ports:
        direction = {"in": "input", "out": "output", "inout": "inout"}[port["direction"]]
        source_range = port.get("range")
        if source_range:
            expression = unbracket(source_range)
            left, right = split_range(expression)
            source_range = f" [{left}:{right}]"
        else:
            source_range = ""
        port_lines.append(f"    {direction} {'wire' if direction == 'inout' else 'logic'}{source_range} {port['name']}")
    return header + (" (\n" + ",\n".join(port_lines) + "\n);" if port_lines else ";")


def resolve_interface(ports, parameters=None, systemverilog="", overrides=None):
    """Resolve bounds from explicit source; never save or simulate a Spec."""
    if not isinstance(ports, list) or not isinstance(parameters or [], list):
        raise ValueError("Ports and parameters must be arrays.")
    parameters = parameters or []
    overrides = overrides or {}
    if not isinstance(overrides, dict) or not isinstance(systemverilog, str):
        raise ValueError("Overrides must be an object and SystemVerilog must be text.")
    parameter_declarations(parameters)
    names = set()
    literal_ports = []
    needs_compiler = False
    for port in ports:
        if not isinstance(port, dict):
            raise ValueError("Each port must contain an ID, direction, and range.")
        name = port.get("name", "")
        if not isinstance(name, str) or not name.strip() or name in names or port.get("direction") not in {"in", "out", "inout"}:
            raise ValueError(f"Port {name!r} requires a distinct RTL identifier and direction.")
        if "width" in port:
            raise ValueError(f"Port {name} width is calculated from its range; do not supply width.")
        names.add(name)
        value = port.get("range")
        if value is not None and not isinstance(value, str):
            raise ValueError(f"Port {name} range must be a string or null.")
        bounds = split_range(unbracket(value)) if value else (None, None)
        literal = all(bound is None or LITERAL.fullmatch(bound) for bound in bounds)
        needs_compiler |= not literal
        left, right = [int(bound.replace("_", "")) if bound is not None and literal else None for bound in bounds]
        literal_ports.append({"name": name, "range": value, "left": left, "right": right,
                              "width": abs(left - right) + 1 if left is not None else 1 if literal else None})
    parameter_names = {p["name"] for p in parameters}
    if any(name not in parameter_names for name in overrides):
        raise ValueError("Overrides must name declared Component parameters.")
    if not needs_compiler:
        return {"status": "resolved", "ports": literal_ports, "parameter_values": {}, "diagnostics": [], "compiler_required": False}
    executable = shutil.which("verilator")
    if executable is None:
        return {"status": "unresolved", "ports": [], "parameter_values": {}, "compiler_required": True,
                "diagnostics": [{"code": "VERILATOR_MISSING", "message": "Verilator is required to resolve the symbolic port bounds.", "blocking": True}]}
    version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
    payload = json.dumps({"ports": ports, "parameters": parameters, "systemverilog": systemverilog, "overrides": overrides}, sort_keys=True)
    return json.loads(_elaborate(executable, version, payload))


@lru_cache(maxsize=128)
def _elaborate(executable, version, payload):
    data = json.loads(payload)
    source = module_declaration("interface_check", data["ports"], data["parameters"]) + "\n" + data["systemverilog"] + "\nendmodule\n"
    diagnostics = []
    with tempfile.TemporaryDirectory(prefix="spec2gds-interface-") as directory:
        root = Path(directory)
        input_path, output_path = root / "interface.sv", root / "interface.xml"
        input_path.write_text(source)
        command = [executable, "--xml-only", "--xml-output", str(output_path), "--top-module", "interface_check", "--Mdir", str(root / "obj"), "-Wno-fatal"]
        command.extend(f"-G{name}={value}" for name, value in data["overrides"].items())
        try:
            run = subprocess.run([*command, str(input_path)], capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return json.dumps({"status": "unresolved", "ports": [], "parameter_values": {}, "compiler_required": True,
                               "diagnostics": [{"code": "ELABORATION_TIMEOUT", "message": "Port-bound elaboration did not finish within 30 seconds.", "blocking": True}]})
        for line in run.stderr.splitlines():
            if line.startswith(("%Error", "%Warning")):
                match = re.match(r"%(Error|Warning)(?:-([A-Z0-9_]+))?:\s*(.*)", line)
                if match:
                    diagnostics.append({"code": match[2] or match[1].upper(), "message": match[3].replace(str(input_path), "SystemVerilog"), "blocking": match[1] == "Error"})
        result = {"status": "unresolved", "ports": [], "parameter_values": {}, "diagnostics": diagnostics, "compiler_required": True, "compiler_version": version}
        if run.returncode or not output_path.exists():
            if not diagnostics:
                diagnostics.append({"code": "ELABORATION_FAILED", "message": run.stderr[:2000] or "Verilator could not resolve the interface.", "blocking": True})
            return json.dumps(result)
        tree = ET.parse(output_path)
        types = {node.get("id"): node for node in tree.findall(".//typetable/*")}
        module = tree.find(".//netlist/module[@name='interface_check']")
        variables = {node.get("name"): node for node in module.findall("var")} if module is not None else {}
        for port in data["ports"]:
            variable = variables.get(port["name"])
            dtype = types.get(variable.get("dtype_id")) if variable is not None else None
            visited = set()
            while dtype is not None and dtype.get("sub_dtype_id") and dtype.get("id") not in visited:
                visited.add(dtype.get("id"))
                dtype = types.get(dtype.get("sub_dtype_id"))
            if dtype is None:
                diagnostics.append({"code": "BOUND_UNRESOLVED", "message": f"Port {port['name']}: Verilator did not report its bounds.", "blocking": True})
                return json.dumps(result)
            if port.get("range") and (dtype.get("left") is None or dtype.get("right") is None):
                diagnostics.append({"code": "BOUND_UNRESOLVED", "message": f"Port {port['name']}: Verilator did not report exact range bounds.", "blocking": True})
                return json.dumps(result)
            left = int(dtype.get("left")) if port.get("range") else None
            right = int(dtype.get("right")) if port.get("range") else None
            result["ports"].append({"name": port["name"], "range": port.get("range"), "left": left, "right": right,
                                   "width": abs(left - right) + 1 if left is not None else 1})
        for parameter in data["parameters"]:
            variable = variables.get(parameter["name"])
            constant = variable.find("const") if variable is not None else None
            if constant is not None:
                dtype = types.get(variable.get("dtype_id"))
                visited = set()
                while dtype is not None and dtype.get("sub_dtype_id") and dtype.get("id") not in visited:
                    visited.add(dtype.get("id"))
                    dtype = types.get(dtype.get("sub_dtype_id"))
                # Verilator can emit an unsigned constant for a signed parameter,
                # or a signed initializer for an unsigned declaration. The declared
                # type determines the parameter value used by the interface.
                signed = dtype.get("signed") == "true" if dtype is not None else None
                result["parameter_values"][parameter["name"]] = _constant_value(constant.get("name", ""), signed)
        result["status"] = "resolved"
        result["input_digest"] = hashlib.sha256(payload.encode()).hexdigest()
        return json.dumps(result)


def _constant_value(value, signed=None):
    match = re.fullmatch(r"(\d+)'(s?)([hbd])([0-9a-fA-F_]+)", value)
    if not match:
        return value
    number = int(match[4].replace("_", ""), {"h": 16, "b": 2, "d": 10}[match[3]])
    bits = int(match[1])
    return number - (1 << bits) if (bool(match[2]) if signed is None else signed) and number & (1 << (bits - 1)) else number
