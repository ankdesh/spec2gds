"""Protect process identity, conflict handling, and partial startup cleanup."""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import serve_all as launcher


def test_stop_retains_a_reused_pid(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "RECORD", tmp_path / "processes.json")
    monkeypatch.setattr(launcher, "identity", lambda _: "new-identity")
    monkeypatch.setattr(os, "killpg", lambda *_: pytest.fail("A reused PID must not be signalled"))
    launcher.stop([{"name": "old", "pgid": 123, "members": [{"pid": 123, "identity": "old-identity"}]}])
    assert json.loads(launcher.RECORD.read_text()) == []


def test_occupied_address_reports_pid_and_retains_listener():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError) as error:
            launcher.check_port({"host": "127.0.0.1", "port": port})
        assert f"127.0.0.1:{port}" in str(error.value)
        assert str(os.getpid()) in str(error.value)
        assert listener.getsockname()[1] == port


def test_partial_start_stops_only_created_groups(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "STATE", tmp_path)
    monkeypatch.setattr(launcher, "RECORD", tmp_path / "processes.json")
    monkeypatch.setattr(launcher, "check_port", lambda _: None)
    real_popen = subprocess.Popen
    children = []

    def popen(*_, **kwargs):
        if len(children) == 2:
            raise OSError("fixture startup failure")
        child = real_popen([sys.executable, "-c", "import time; time.sleep(60)"],
                           start_new_session=True, stdout=kwargs["stdout"], stderr=kwargs["stderr"])
        children.append(child)
        return child

    unrelated = real_popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    monkeypatch.setattr(subprocess, "Popen", popen)
    args = argparse.Namespace(host="127.0.0.1", public_host="design.test", spec_port=6410,
                              circuit_port=6411, circuit_ui_port=6412, assistant_port=6413,
                              service_config=None, require_designer_approval=False)
    try:
        with pytest.raises(OSError, match="fixture startup failure"):
            launcher.start(args, [])
        assert all(child.poll() is not None for child in children)
        assert unrelated.poll() is None
        assert json.loads(launcher.RECORD.read_text()) == []
        snapshot = next(tmp_path.glob("run_*/services.json"))
        assert Path(json.loads(snapshot.read_text())["logging"]["file"]).is_absolute()
    finally:
        os.killpg(unrelated.pid, signal.SIGTERM)
        unrelated.wait()


def test_stop_uses_records_after_configuration_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "RECORD", tmp_path / "processes.json")
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    record = {"name": "recorded", "pgid": child.pid, "members": [{"pid": child.pid, "identity": launcher.identity(child.pid)}]}
    monkeypatch.setattr(launcher, "resolve_config", lambda *_: pytest.fail("Stop must not read current configuration"))
    try:
        launcher.stop([record])
        assert child.wait(timeout=5) == -signal.SIGTERM
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
