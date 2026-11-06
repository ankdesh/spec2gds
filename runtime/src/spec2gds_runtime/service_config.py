"""Resolve service addresses. Precedence is command line, file, then defaults."""

from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from typing import Any

DEFAULTS_PATH = Path(__file__).with_name("service-defaults.json")
SERVICE_NAMES = ("spec_editor", "circuit_designer", "ai_assistant", "verification_planner", "spec_catalog")
SHARED_LISTENERS = ("spec_editor", "ai_assistant", "verification_planner", "spec_catalog")


def default_config_path() -> Path:
    """Use the repository configuration when present, else packaged defaults."""
    candidate = Path(__file__).resolve().parents[3] / "config/services.json"
    return candidate if candidate.is_file() else DEFAULTS_PATH


def _merge(base: dict, value: dict) -> dict:
    result = copy.deepcopy(base)
    for key, item in value.items():
        result[key] = _merge(result[key], item) if isinstance(item, dict) and isinstance(result.get(key), dict) else copy.deepcopy(item)
    return result


def primary_ipv4() -> str:
    """Find the preferred outbound IPv4 address without sending data."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 9))
            return str(probe.getsockname()[0])
    except OSError:
        return socket.gethostname()


def validate_host(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "/\\?#@ \t\n"):
        raise ValueError(f"{name} must be an IP address or a hostname.")
    host = value.strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    if ":" in host:
        try:
            socket.inet_pton(socket.AF_INET6, host.split("%", 1)[0])
        except OSError as exc:
            raise ValueError(f"{name} must be an IP address or a hostname.") from exc
    elif "[" in host or "]" in host:
        raise ValueError(f"{name} must be an IP address or a hostname.")
    return host


def validate_port(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= 65535:
        raise ValueError("port must be between 1 and 65535.")
    return value


def resolve_config(path: str | Path | None = None, *, overrides: dict | None = None) -> dict:
    """Read a configuration and resolve paths before making a run snapshot."""
    source = Path(path).expanduser().resolve() if path is not None else default_config_path()
    supplied = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(supplied, dict) or supplied.get("schema_version", 2) != 2:
        raise ValueError("Service registry schema_version must be 2.")
    # Preserve the documented storage alias when canonical scratch_root is absent.
    if isinstance(supplied.get("activities"), dict):
        activity = supplied["activities"]
        if "workspace_root" in activity and "scratch_root" not in activity:
            activity["scratch_root"] = activity["workspace_root"]
    value = _merge(json.loads(DEFAULTS_PATH.read_text()), supplied)
    value = _merge(value, overrides or {})
    public_host = value["public_host"]
    if isinstance(public_host, str) and public_host.lower() == "auto":
        public_host = primary_ipv4()
    value["public_host"] = validate_host(public_host, "public_host")
    for name in SERVICE_NAMES:
        if not isinstance(value[name], dict):
            raise ValueError(f"{name} must be an object.")
        for surface in (("service", "ui", "dev_ui") if name == "spec_editor" else ("service", "ui")):
            _validate_endpoint(value[name][surface], f"{name}.{surface}")
    for name in SHARED_LISTENERS:
        service, ui = value[name]["service"], value[name]["ui"]
        if any(service[key] != ui[key] for key in ("scheme", "host", "port")):
            raise ValueError(f"{name}.service and ui must use the same listener.")
    if not isinstance(value["logging"], dict):
        raise ValueError("logging must be an object.")
    _validate_endpoint(value["logging"]["viewer"], "logging.viewer")
    for section, field in (("spec_editor", "spec_root"), ("logging", "file"), ("activities", "scratch_root"), ("circuit_designer", "preferences_file"), ("spec_catalog", "catalog_root"), ("spec_catalog", "state_dir")):
        configured = value[section][field]
        if not isinstance(configured, str) or not configured.strip():
            raise ValueError(f"{section}.{field} must be a non-empty string.")
        candidate = Path(configured).expanduser()
        value[section][field] = str((source.parent / candidate).resolve())
    extensions = value["activities"]["extension_modules"]
    if not isinstance(extensions, list) or any(not isinstance(item, str) or not item.strip() for item in extensions):
        raise ValueError("activities.extension_modules must contain non-empty strings.")
    return value


def _validate_endpoint(endpoint: Any, name: str) -> None:
    if not isinstance(endpoint, dict):
        raise ValueError(f"{name} must be an object.")
    if endpoint["scheme"] not in ("http", "https"):
        raise ValueError(f"{name}.scheme must be http or https.")
    endpoint["host"] = validate_host(endpoint["host"], f"{name}.host")
    validate_port(endpoint["port"])
    if not isinstance(endpoint["base_path"], str) or any(c in endpoint["base_path"] for c in "?#"):
        raise ValueError(f"{name}.base_path must be a URL path.")


def listener_overrides(name: str, *, host: str | None = None, port: int | None = None) -> dict:
    """Update both surfaces of a shared listener."""
    fields = {key: item for key, item in (("host", host), ("port", port)) if item is not None}
    surfaces = ("service", "ui") if name in SHARED_LISTENERS else ("service",)
    return {name: {surface: fields.copy() for surface in surfaces}}


def local_host(host: str) -> str:
    return {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(host, host)


def endpoint_url(endpoint: dict, public_host: str, *, local: bool = False, origin: bool = False) -> str:
    host = endpoint["host"]
    host = local_host(host) if local else public_host if host in ("0.0.0.0", "::") else host
    authority = f"[{host}]" if ":" in host else host
    path = endpoint["base_path"].strip("/") if not origin else ""
    return f"{endpoint['scheme']}://{authority}:{endpoint['port']}" + (f"/{path}" if path else "")
