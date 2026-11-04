"""Real direct launches, reload workers, proxies, and strict UI listeners."""

import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.extensive


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
def launch_config(tmp_path):
    value = json.loads((ROOT / "config/services.json").read_text())
    allocated = set()

    def port():
        while (selected := free_port()) in allocated:
            pass
        allocated.add(selected)
        return selected

    for name in ("spec_editor", "circuit_designer", "ai_assistant", "verification_planner", "spec_catalog"):
        selected = port()
        for surface in ("service", "ui"):
            value[name][surface].update(host="127.0.0.1", port=port() if name == "circuit_designer" and surface == "ui" else selected)
    value["spec_editor"]["dev_ui"].update(host="127.0.0.1", port=port())
    value["logging"]["viewer"].update(host="127.0.0.1", port=port())
    value["public_host"] = "unused-public.test"
    value["logging"]["file"] = str(tmp_path / "events.jsonl")
    value["activities"]["scratch_root"] = str(tmp_path / "generated")
    value["circuit_designer"]["preferences_file"] = str(tmp_path / "preferences.json")
    path = tmp_path / "services.json"
    path.write_text(json.dumps(value))
    return value, path


def get(url):
    with build_opener(ProxyHandler({})).open(url, timeout=1) as response:
        return response.read()


@contextmanager
def running(command, health, directory, *, cwd=ROOT):
    directory.mkdir(exist_ok=True)
    log = directory / "process.log"
    env = {**os.environ, "SPEC_SERVICE_PORT": "9", "AGENT_SPEC_HOST": "obsolete.test",
           "CIRCUIT_DESIGNER_PORT": "9", "CIRCUIT_DESIGNER_UI_PORT": "9",
           "SPEC2GDS_PUBLIC_HOST": "obsolete.test", "SPEC2GDS_SERVICE_CONFIG": "/missing/obsolete.json",
           "SPEC_EDITOR_STATE_ROOT": str(directory / "state")}
    with log.open("w") as stream:
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline = time.monotonic() + 30
        while True:
            assert child.poll() is None, log.read_text()
            try:
                get(health)
                break
            except OSError:
                assert time.monotonic() < deadline, log.read_text()
                time.sleep(0.1)
        yield child, log
    finally:
        try:
            os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
        except ProcessLookupError:
            pass
        # npm wrappers can leave descendants after their own exit.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # The wrapper can exit before the kernel closes a descendant's listener.
        address = urlsplit(health)
        deadline = time.monotonic() + 5
        while True:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    listener.bind((address.hostname, address.port))
                    break
                except OSError:
                    assert time.monotonic() < deadline, log.read_text()
            time.sleep(0.05)


def test_real_reload_worker_retains_cli_addresses(launch_config, tmp_path):
    _, path = launch_config
    selected = free_port()
    origin = f"http://127.0.0.1:{selected}"
    probe = tmp_path / "reload_probe.py"
    probe.write_text("VALUE = 1\n")
    command = [sys.executable, "-m", "spec2gds.spec.api", "--service-config", str(path), "--port", str(selected), "--reload"]
    with running(command, origin + "/health", tmp_path / "reload", cwd=tmp_path) as (_, log):
        before = re.findall(r"Started server process \[(\d+)\]", log.read_text())
        assert before
        time.sleep(1)
        probe.write_text("VALUE = 2\n")
        deadline = time.monotonic() + 15
        while len(re.findall(r"Started server process \[(\d+)\]", log.read_text())) < 2:
            assert time.monotonic() < deadline, log.read_text()
            time.sleep(0.2)
        directory = json.loads(get(origin + "/services"))["services"]
        assert directory["spec_editor"] == {"service_url": origin, "ui_url": origin + "/editor"}


def test_separate_planner_and_log_viewer_read_configuration(launch_config, tmp_path):
    config, path = launch_config
    planner = f"http://127.0.0.1:{config['verification_planner']['service']['port']}"
    viewer = f"http://127.0.0.1:{config['logging']['viewer']['port']}"
    with running([str(ROOT / ".venv/bin/verification-planner"), "--service-config", str(path), "--storage-dir", str(tmp_path / "plans")], planner + "/api/verification/v1/health", tmp_path / "planner"):
        assert b"Verification Planner" in get(planner)
    with running([str(ROOT / ".venv/bin/spec2gds-log-viewer"), "--service-config", str(path), "--no-open"], viewer + "/health", tmp_path / "viewer"):
        assert json.loads(get(viewer + "/api/logs"))["logging_enabled"] is False


def test_direct_circuit_and_vite_dev_preview_use_config(launch_config, tmp_path):
    config, path = launch_config
    service = f"http://127.0.0.1:{config['circuit_designer']['service']['port']}"
    ui = f"http://127.0.0.1:{config['circuit_designer']['ui']['port']}"
    base = ["npm", "--prefix", str(ROOT / "circuit-designer"), "run"]
    with running([*base, "service", "--", "--service-config", os.path.relpath(path, ROOT / "circuit-designer")], service + "/api/circuit-designer/v1/health", tmp_path / "circuit"):
        expected = json.loads(get(service + "/api/circuit-designer/v1/services"))
        for mode in ("dev:standalone", "preview:standalone"):
            with running([*base, mode, "--", "--service-config", str(path)], ui + "/api/circuit-designer/v1/health", tmp_path / mode.replace(":", "-")):
                assert json.loads(get(ui + "/api/circuit-designer/v1/services")) == expected
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("127.0.0.1", config["circuit_designer"]["ui"]["port"]))
            listener.listen()
            for mode in ("dev:standalone", "preview:standalone"):
                result = subprocess.run([*base, mode, "--", "--service-config", str(path)], cwd=ROOT, capture_output=True, text=True, timeout=15)
                assert result.returncode != 0
                assert "already in use" in result.stdout + result.stderr
            assert listener.getsockname()[1] == config["circuit_designer"]["ui"]["port"]


def test_spec_editor_dev_and_preview_proxy_the_configured_service(launch_config, tmp_path):
    config, path = launch_config
    service = f"http://127.0.0.1:{config['spec_editor']['service']['port']}"
    ui = f"http://127.0.0.1:{config['spec_editor']['dev_ui']['port']}"
    base = ["npm", "--prefix", str(ROOT / "circuit-designer"), "run"]
    command = [sys.executable, "-m", "spec2gds.spec.api", "--service-config", str(path)]
    with running(command, service + "/health", tmp_path / "spec-service"):
        expected = json.loads(get(service + "/services"))
        launches = [
            [*base, "dev:editor", "--", "--service-config", str(path)],
            [*base, "preview", "--workspace", "@spec2gds/spec-editor", "--", "--service-config", str(path)],
        ]
        for index, launch in enumerate(launches):
            with running(launch, ui + "/api/services", tmp_path / f"spec-ui-{index}"):
                assert json.loads(get(ui + "/api/services")) == expected
