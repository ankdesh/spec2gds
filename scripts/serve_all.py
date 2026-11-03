"""Start the three applications and stop only recorded process groups."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

from spec2gds_runtime.service_config import endpoint_url, listener_overrides, resolve_config

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "TEMP_serve-all"
RECORD = STATE / "processes.json"


def identity(pid: int, *, include_zombie: bool = False) -> str | None:
    """Linux start time prevents a reused PID from matching a saved process."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" and not include_zombie else fields[19]
    except (OSError, IndexError):
        return None


def members(group: int) -> list[dict]:
    result = []
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            pid = int(entry.name)
            try:
                if os.getpgid(pid) == group and (stamp := identity(pid)):
                    result.append({"pid": pid, "identity": stamp})
            except ProcessLookupError:
                pass
    return result


def tracked(record: dict) -> bool:
    for item in record["members"]:
        try:
            if identity(item["pid"]) == item["identity"] and os.getpgid(item["pid"]) == record["pgid"]:
                return True
        except ProcessLookupError:
            pass
    return False


def save(records: list[dict]) -> None:
    temporary = RECORD.with_suffix(".new")
    temporary.write_text(json.dumps(records, indent=2) + "\n")
    temporary.replace(RECORD)


def stop(records: list[dict]) -> None:
    for record in reversed(records):
        if not tracked(record):
            continue
        os.killpg(record["pgid"], signal.SIGTERM)
        deadline = time.monotonic() + 5
        while members(record["pgid"]) and time.monotonic() < deadline:
            time.sleep(0.1)
        # A process group with living members cannot have its ID reused.
        if members(record["pgid"]):
            os.killpg(record["pgid"], signal.SIGKILL)
        print(f"Stopped {record['name']}.")
    save([])


def check_port(endpoint: dict) -> None:
    host, port = endpoint["host"], endpoint["port"]
    try:
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError as exc:
        conflict = subprocess.run(["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], capture_output=True, text=True)
        raise RuntimeError(f"Cannot bind {host}:{port}: {exc}. Untracked listeners are retained.\n{conflict.stdout}") from exc


def start(args: argparse.Namespace, previous: list[dict]) -> None:
    if any(tracked(record) for record in previous):
        raise RuntimeError("Tracked applications are running. Use restart to apply configuration changes.")
    overrides = {}
    for name, port in (("spec_editor", args.spec_port), ("circuit_designer", args.circuit_port), ("ai_assistant", args.assistant_port)):
        overrides.update(listener_overrides(name, host=args.host, port=port))
    ui = {key: value for key, value in (("host", args.host), ("port", args.circuit_ui_port)) if value is not None}
    overrides["circuit_designer"]["ui"] = ui
    if args.public_host is not None:
        overrides["public_host"] = args.public_host
    config = resolve_config(args.service_config, overrides=overrides)
    endpoints = [config["spec_editor"]["service"], config["circuit_designer"]["service"], config["circuit_designer"]["ui"], config["ai_assistant"]["service"]]
    seen = set()
    for endpoint in endpoints:
        address = (endpoint["host"], endpoint["port"])
        if address in seen:
            raise RuntimeError(f"Two applications use {address[0]}:{address[1]}.")
        seen.add(address)
        check_port(endpoint)
    run = STATE / f"run_{uuid4().hex}"
    run.mkdir()
    snapshot = run / "services.json"
    snapshot.write_text(json.dumps(config, indent=2) + "\n")
    common = ["--service-config", str(snapshot)]
    commands = [
        ("Spec Editor", ROOT, ["uv", "run", "--no-sync", "spec2gds-server", *common, *(["--require-designer-approval"] if args.require_designer_approval else [])]),
        ("Circuit Designer", ROOT / "circuit-designer", ["npm", "run", "dev", "--", *common]),
        ("AI Assistant", ROOT / "ai-assistant", ["npm", "run", "dev", "--", *common, "--no-open"]),
    ]
    records, children = [], []
    try:
        for name, cwd, command in commands:
            log = run / (name.lower().replace(" ", "-") + ".log")
            with log.open("w") as output:
                child = subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
            children.append(child)
            records.append({"name": name, "pid": child.pid, "pgid": child.pid, "leader_identity": identity(child.pid, include_zombie=True), "members": [{"pid": child.pid, "identity": identity(child.pid)}], "command": command, "log": str(log), "config": str(snapshot), "endpoints": endpoints})
            save(records)
        checks = [(endpoints[0], "/health"), (endpoints[1], "/api/circuit-designer/v1/health"), (endpoints[2], "/api/circuit-designer/v1/health"), (endpoints[3], "/readyz")]
        opener = build_opener(ProxyHandler({}))
        pending = list(checks)
        deadline = time.monotonic() + 60
        while pending:
            for child, record in zip(children, records):
                if identity(child.pid, include_zombie=True) == record["leader_identity"]:
                    current_members = members(record["pgid"])
                    if current_members != record["members"]:
                        record["members"] = current_members
                        save(records)
                if child.poll() is not None:
                    raise RuntimeError(f"{record['name']} stopped during startup. See {record['log']}")
            for endpoint, path in pending[:]:
                try:
                    with opener.open(endpoint_url(endpoint, config["public_host"], local=True, origin=True) + path, timeout=1) as response:
                        if response.status == 200:
                            pending.remove((endpoint, path))
                except OSError:
                    pass
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Startup timed out. See {run}")
            time.sleep(0.1)
        for record in records:
            record["members"] = members(record["pgid"])
        save(records)
    except BaseException:
        stop(records)
        for child in children:
            child.wait()
        raise
    for name, key in (("Spec Editor", "spec_editor"), ("Circuit Designer", "circuit_designer"), ("AI Assistant", "ai_assistant")):
        print(f"{name}: {endpoint_url(config[key]['ui'], config['public_host'])}")
    print(f"Run records and logs: {run}")


def interrupt_startup(*_) -> None:
    raise KeyboardInterrupt


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Spec Editor, Circuit Designer, and AI Assistant. Precedence: CLI > file > defaults.")
    parser.add_argument("command", choices=("start", "stop", "restart"))
    parser.add_argument("--service-config", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--public-host")
    for name in ("spec", "circuit", "circuit-ui", "assistant"):
        parser.add_argument(f"--{name}-port", type=int)
    parser.add_argument("--require-designer-approval", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupt_startup)
    STATE.mkdir(exist_ok=True)
    with (STATE / "launcher.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = json.loads(RECORD.read_text()) if RECORD.exists() else []
        if args.command in ("stop", "restart"):
            stop(records)
            records = []
        if args.command in ("start", "restart"):
            start(args, records)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
