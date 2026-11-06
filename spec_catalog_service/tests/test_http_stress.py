"""Real isolated HTTP Spec service stress testing scenario.

Covers:
- api_reference.spec creation with mux, register_enable, counter_modulo
- Explicit VLNV assignment and transaction atomicity
- Stale revision rejection (HTTP 409)
- Atomic rollback on failed operations (HTTP 422)
- Rejection of illegal module headers in SV bodies
- Kill and restart server persistence verification
"""

from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Generator

import httpx
import pytest
from spec_catalog_service.catalog.components.phase1 import (
    COUNTER_MODULO_DEF,
    MUX_DEF,
    REGISTER_ENABLE_DEF,
)


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = httpx.get(f"{url}/services", timeout=1.0)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise TimeoutError(f"Server at {url} failed to start within {timeout}s")


class ServerProcess:
    """Manages an isolated uvicorn subprocess running the Spec service API."""

    def __init__(self, port: int, state_dir: Path) -> None:
        self.port = port
        self.state_dir = state_dir
        self.base_url = f"http://127.0.0.1:{port}"
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        env = os.environ.copy()
        env["SPEC_EDITOR_STATE_ROOT"] = str(self.state_dir)
        from spec2gds.service_registry import service_config_path
        config = json.loads(service_config_path().read_text())
        config["spec_editor"]["spec_root"] = str(self.state_dir.parent)
        config["activities"]["scratch_root"] = str(self.state_dir / "generated")
        config["logging"]["file"] = str(self.state_dir / "events.jsonl")
        config_path = self.state_dir / "services.json"
        config_path.write_text(json.dumps(config))
        cmd = [sys.executable, "-m", "spec2gds.spec.api", "--host", "127.0.0.1",
               "--port", str(self.port), "--service-config", str(config_path)]
        self.process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _wait_for_server(self.base_url)

    def stop(self) -> None:
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None


@pytest.fixture
def stress_env() -> Generator[tuple[Path, int], None, None]:
    temp_dir = Path("temp/TEMP_tests/http_stress").resolve()
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    port = _get_free_port()
    yield temp_dir, port
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def test_real_http_spec_service_lifecycle_and_stress(stress_env: tuple[Path, int]) -> None:
    temp_dir, port = stress_env
    state_dir = temp_dir / "server_state"
    state_dir.mkdir()
    spec_path = temp_dir / "api_reference.spec"

    server = ServerProcess(port=port, state_dir=state_dir)
    server.start()

    try:
        with httpx.Client(base_url=server.base_url, timeout=30.0) as client:
            # 1. Create api_reference.spec
            res_create = client.post(
                "/documents/create",
                json={
                    "path": str(spec_path),
                    "document_id": "api_reference",
                    "title": "API Reference Document",
                },
            )
            assert res_create.status_code == 200, res_create.text
            created = res_create.json()
            client.params = {"owner_document_key": created["owner_document_key"]}
            client.headers.update({"X-Spec-Edit-Context": created["edit_access"]["context_id"], "X-Spec-Participant": created["edit_access"]["participant_id"]})
            curr_rev = created["source_revision_hash"]

            # 2. Add mux, register_enable, counter_modulo with explicit VLNVs and SV sections
            ops = [
                # Mux
                {
                    "type": "create_entity",
                    "kind": "component",
                    "name": "mux",
                    "entity_id": "component_mux",
                    "vlnv": "spec2gds.local:logic:mux:1.0.0",
                },
                {"type": "update_parameter", "component": "component:component_mux", "parameter": {"name": "W", "value": "7"}},
                {"type": "update_parameter", "component": "component:component_mux", "parameter": {"name": "N", "value": "3"}},
                {
                    "type": "add_component_port",
                    "component": "component:component_mux",
                    "port": {"name": "data_i", "family": "wire", "direction": "in", "range": "(N*W)-1:0"},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_mux",
                    "port": {"name": "sel_i", "family": "wire", "direction": "in", "range": "(((N)<=1 ? 1 : $clog2(N)) - 1):0"},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_mux",
                    "port": {"name": "data_o", "family": "wire", "direction": "out", "range": "W-1:0"},
                },
                {
                    "type": "upsert_entity_section",
                    "owner": "component:component_mux",
                    "section_type": "sv",
                    "payload": {"content": MUX_DEF.systemverilog},
                },

                # Register Enable
                {
                    "type": "create_entity",
                    "kind": "component",
                    "name": "register_enable",
                    "entity_id": "component_register_enable",
                    "vlnv": "spec2gds.local:state:register_enable:1.0.0",
                },
                {"type": "update_parameter", "component": "component:component_register_enable", "parameter": {"name": "W", "value": "7"}},
                {
                    "type": "add_component_port",
                    "component": "component:component_register_enable",
                    "port": {"name": "clk_i", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_register_enable",
                    "port": {"name": "rst_ni", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_register_enable",
                    "port": {"name": "en_i", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_register_enable",
                    "port": {"name": "d_i", "family": "wire", "direction": "in", "range": "W-1:0"},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_register_enable",
                    "port": {"name": "q_o", "family": "wire", "direction": "out", "range": "W-1:0"},
                },
                {
                    "type": "upsert_entity_section",
                    "owner": "component:component_register_enable",
                    "section_type": "sv",
                    "payload": {"content": REGISTER_ENABLE_DEF.systemverilog},
                },

                # Counter Modulo
                {
                    "type": "create_entity",
                    "kind": "component",
                    "name": "counter_modulo",
                    "entity_id": "component_counter_modulo",
                    "vlnv": "spec2gds.local:state:counter_modulo:1.0.0",
                },
                {"type": "update_parameter", "component": "component:component_counter_modulo", "parameter": {"name": "W", "value": "5"}},
                {"type": "update_parameter", "component": "component:component_counter_modulo", "parameter": {"name": "MODULUS", "value": "7"}},
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "clk_i", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "rst_ni", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "en_i", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "clear_i", "family": "wire", "direction": "in", "range": None},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "count_o", "family": "wire", "direction": "out", "range": "W-1:0"},
                },
                {
                    "type": "add_component_port",
                    "component": "component:component_counter_modulo",
                    "port": {"name": "wrap_o", "family": "wire", "direction": "out", "range": None},
                },
                {
                    "type": "upsert_entity_section",
                    "owner": "component:component_counter_modulo",
                    "section_type": "sv",
                    "payload": {"content": COUNTER_MODULO_DEF.systemverilog},
                },
            ]

            res_tx = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": curr_rev,
                    "operations": ops,
                },
            )
            assert res_tx.status_code == 200, res_tx.text
            tx_data = res_tx.json()
            assert tx_data["committed"] is True
            curr_rev = tx_data["snapshot"]["source_revision_hash"]

            # Verify components in snapshot
            comps = {c["ref"]["entity_id"]: c for c in tx_data["snapshot"]["components"]}
            assert "component_mux" in comps
            assert comps["component_mux"]["vlnv"] == "spec2gds.local:logic:mux:1.0.0"
            assert "component_register_enable" in comps
            assert comps["component_register_enable"]["vlnv"] == "spec2gds.local:state:register_enable:1.0.0"
            assert "component_counter_modulo" in comps
            assert comps["component_counter_modulo"]["vlnv"] == "spec2gds.local:state:counter_modulo:1.0.0"

            # 3. Optimistic concurrency and stale revision conflict (409)
            revision_r = curr_rev

            # Client A edits mux description at revision_r -> succeeds
            res_client_a = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": revision_r,
                    "operations": [
                        {
                            "type": "set_entity_metadata",
                            "entity": "component:component_mux",
                            "short_description": "Edited by Client A",
                        }
                    ],
                },
            )
            assert res_client_a.status_code == 200
            rev_prime = res_client_a.json()["snapshot"]["source_revision_hash"]

            # Client B submits edit against stale revision_r -> 409 Conflict
            res_client_b_stale = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": revision_r,
                    "operations": [
                        {
                            "type": "set_entity_metadata",
                            "entity": "component:component_mux",
                            "short_description": "Edited by Client B",
                        }
                    ],
                },
            )
            assert res_client_b_stale.status_code == 409

            # Client B refreshes to rev_prime and resubmits -> succeeds
            res_client_b_ok = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": rev_prime,
                    "operations": [
                        {
                            "type": "set_entity_metadata",
                            "entity": "component:component_mux",
                            "short_description": "Edited by Client A and B",
                        }
                    ],
                },
            )
            assert res_client_b_ok.status_code == 200
            curr_rev = res_client_b_ok.json()["snapshot"]["source_revision_hash"]

            # 4. Atomic transaction rejection: valid op + invalid port range -> 422
            res_atomic_fail = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": curr_rev,
                    "operations": [
                        {
                            "type": "set_entity_metadata",
                            "entity": "component:component_mux",
                            "short_description": "Should Not Be Applied",
                        },
                        {
                            "type": "add_component_port",
                            "component": "component:component_mux",
                            "port": {"name": "bad_port", "family": "invalid_family"},
                        },
                    ],
                },
            )
            assert res_atomic_fail.status_code == 422

            # Verify valid op was NOT applied
            re_opened = client.post("/documents/open", json={"path": str(spec_path)})
            assert re_opened.status_code == 200
            re_snap = re_opened.json()
            mux_snap = next(c for c in re_snap["components"] if c["ref"]["entity_id"] == "component_mux")
            assert mux_snap.get("short_description") != "Should Not Be Applied"
            curr_rev = re_snap["source_revision_hash"]

            # Reject module header in SV body
            res_module_header = client.post(
                "/transactions",
                json={
                    "expected_source_revision_hash": curr_rev,
                    "operations": [
                        {
                            "type": "upsert_entity_section",
                            "owner": "component:component_mux",
                            "section_type": "sv",
                            "payload": {"content": "module illegal_module(); endmodule"},
                        }
                    ],
                },
            )
            assert res_module_header.status_code == 422
    finally:
        server.stop()

    # 5. Server restart and disk durability verification
    port2 = _get_free_port()
    server2 = ServerProcess(port=port2, state_dir=state_dir)
    server2.start()

    try:
        with httpx.Client(base_url=server2.base_url, timeout=30.0) as client:
            res_reopen = client.post("/documents/open", json={"path": str(spec_path)})
            assert res_reopen.status_code == 200
            snap = res_reopen.json()
            assert snap["source_revision_hash"] == curr_rev

            comps = {c["ref"]["entity_id"]: c for c in snap["components"]}
            assert "component_mux" in comps
            assert "component_register_enable" in comps
            assert "component_counter_modulo" in comps

            # Parameters check
            mux_params = {p["name"]: p["value"] for p in comps["component_mux"]["parameters"]}
            assert mux_params["W"] == "7"
            assert mux_params["N"] == "3"
    finally:
        server2.stop()
