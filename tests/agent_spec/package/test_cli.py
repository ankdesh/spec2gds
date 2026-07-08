import os
import pathlib
import sys
import tempfile
import json
import io
import unittest.mock as mock
import spec2gds.agent_spec.package.cli as cli

def test_cli_list_plugins() -> None:
    """Test the CLI list-plugins command."""
    mock_argv = ["agent_spec_cli", "list-plugins"]
    
    stdout_capture = io.StringIO()
    with mock.patch.object(sys, "argv", mock_argv), mock.patch.object(sys, "stdout", stdout_capture):
        cli.main()
        
    output_str = stdout_capture.getvalue()
    result = json.loads(output_str)
    
    if "simple-json" not in result.get("plugins", []):
        raise AssertionError(f"Expected simple-json plugin in list, got: {output_str}")

def test_cli_inject_extract_and_validate() -> None:
    """Test CLI inject, extract, and validate operations end-to-end."""
    temp_container_fd, temp_container_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_container_fd)
    
    temp_json_fd, temp_json_path = tempfile.mkstemp(suffix=".json")
    os.close(temp_json_fd)
    
    temp_extract_fd, temp_extract_path = tempfile.mkstemp(suffix=".json")
    os.close(temp_extract_fd)
    
    try:
        # 1. Create a dummy JSON spec payload
        payload = {
            "title": "SPI Controller",
            "version": "1.0",
            "metadata": [
                {"name": "fifo_depth", "value": 16}
            ]
        }
        with open(temp_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
            
        # 2. Run CLI inject
        inject_argv = [
            "agent_spec_cli", "inject",
            "--container", temp_container_path,
            "--modality", "simple-json",
            "--file", "spi.json",
            "--source", temp_json_path
        ]
        with mock.patch.object(sys, "argv", inject_argv):
            cli.main()
            
        if not os.path.exists(temp_container_path) or os.path.getsize(temp_container_path) == 0:
            raise AssertionError("CLI inject failed to write non-empty hybrid container.")
            
        # 3. Run CLI extract
        extract_argv = [
            "agent_spec_cli", "extract",
            "--container", temp_container_path,
            "--modality", "simple-json",
            "--file", "spi.json",
            "--output", temp_extract_path
        ]
        with mock.patch.object(sys, "argv", extract_argv):
            cli.main()
            
        with open(temp_extract_path, "r", encoding="utf-8") as f:
            extracted_payload = json.load(f)
            
        if extracted_payload.get("title") != "SPI Controller":
            raise AssertionError(f"Extracted payload title does not match. Got: {extracted_payload}")
            
        # 4. Run CLI validate
        validate_argv = [
            "agent_spec_cli", "validate",
            "--container", temp_container_path
        ]
        stdout_capture = io.StringIO()
        with mock.patch.object(sys, "argv", validate_argv), mock.patch.object(sys, "stdout", stdout_capture):
            cli.main()
            
        report_str = stdout_capture.getvalue()
        report = json.loads(report_str)
        
        if not report.get("is_fully_consistent"):
            raise AssertionError(f"Expected container to be fully consistent, got report: {report_str}")
            
    finally:
        # Clean up temporary test files
        for p in [temp_container_path, temp_json_path, temp_extract_path]:
            if os.path.exists(p):
                os.remove(p)


def test_cli_inspect_reports_detailed_spec_anatomy() -> None:
    """Test that inspect emits package, semantic, and IP-XACT diagnostics."""
    sample_path = pathlib.Path("spec2gds/agent_spec/samples/generated/synthetic_basic_with_ipxact.spec")
    inspect_argv = [
        "agent_spec_cli",
        "inspect",
        "--container",
        str(sample_path),
    ]

    stdout_capture = io.StringIO()
    with mock.patch.object(sys, "argv", inspect_argv), mock.patch.object(sys, "stdout", stdout_capture):
        cli.main()

    report = json.loads(stdout_capture.getvalue())

    if report["document"]["sha256"] == "":
        raise AssertionError("Expected inspect report to include document hash.")
    if report["package"]["part_count"] <= 0:
        raise AssertionError("Expected inspect report to include package parts.")
    if report["semantic_document"]["block_count"] <= 0:
        raise AssertionError("Expected inspect report to include semantic blocks.")
    if not report["ipxact"]:
        raise AssertionError("Expected inspect report to include embedded IP-XACT summaries.")


def test_cli_sanitize_writes_output_copy() -> None:
    """Test that sanitize can write a structurally normalized copy."""
    sample_path = pathlib.Path("spec2gds/agent_spec/samples/generated/synthetic_basic_with_ipxact.spec")
    temp_output_fd, temp_output_path = tempfile.mkstemp(suffix=".spec")
    os.close(temp_output_fd)

    try:
        sanitize_argv = [
            "agent_spec_cli",
            "sanitize",
            "--container",
            str(sample_path),
            "--output",
            temp_output_path,
        ]
        stdout_capture = io.StringIO()
        with mock.patch.object(sys, "argv", sanitize_argv), mock.patch.object(sys, "stdout", stdout_capture):
            cli.main()

        result = json.loads(stdout_capture.getvalue())
        if not result["saved"]:
            raise AssertionError(f"Expected sanitize to save output, got: {result}")
        if not os.path.exists(temp_output_path) or os.path.getsize(temp_output_path) == 0:
            raise AssertionError("Expected sanitize output to be a non-empty .spec file.")

        inspect_argv = [
            "agent_spec_cli",
            "inspect",
            "--container",
            temp_output_path,
            "--format",
            "text",
        ]
        text_capture = io.StringIO()
        with mock.patch.object(sys, "argv", inspect_argv), mock.patch.object(sys, "stdout", text_capture):
            cli.main()
        if "Agent-Spec Diagnostic Report" not in text_capture.getvalue():
            raise AssertionError("Expected text inspect report after sanitize.")
    finally:
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
