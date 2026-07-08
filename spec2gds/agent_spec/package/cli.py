"""Command-line entry points for inspecting and modifying `.spec` packages."""

import argparse
import json
import os
import sys

import spec2gds.agent_spec.package.archive as container
import spec2gds.agent_spec.plugins.manager as manager
import spec2gds.agent_spec.plugins.json_payload as json_plugin
import spec2gds.agent_spec.plugins.ipxact as ipxact_plugin
import spec2gds.agent_spec.package.verifier as verifier
import spec2gds.agent_spec.package.diagnostics as diagnostics


def _build_default_manager() -> manager.PluginManager:
    """
    Bootstrap the default plugin manager registry.
    This registers the standard JSON modality handler so that the CLI commands
    can automatically route JSON data injection and extraction requests.
    """
    pm = manager.PluginManager()
    
    # Keep the CLI self-contained: every command gets the built-in modalities
    # without requiring an external plugin configuration file.
    json_plug = json_plugin.SimpleJSONPlugin()
    pm.register_plugin(json_plug)
    
    # IP-XACT is the primary structured hardware payload used by samples and
    # benchmarks.
    ipxact_plug = ipxact_plugin.IPXACTPlugin()
    pm.register_plugin(ipxact_plug)
    
    return pm

def main() -> None:
    """
    Headless command-line interface entry point.
    Supports list-plugins, inject, extract, and validate command suites.
    """
    parser = argparse.ArgumentParser(
        description="Hybrid Agent-Spec Management Tool - Embeds structured hardware specs inside agent-spec."
    )
    # Subcommands keep package operations explicit and script-friendly.
    subparsers = parser.add_subparsers(dest="command", required=True)

    # `list-plugins` is useful in tests and for users checking what the local
    # CLI build can handle.
    subparsers.add_parser(
        "list-plugins",
        help="List all registered modality plugins."
    )

    # `inject` adds one structured payload to an existing or new archive.
    inject_parser = subparsers.add_parser(
        "inject",
        help="Inject custom modality data payload into agent-spec archive."
    )
    inject_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid agent-spec file."
    )
    inject_parser.add_argument(
        "--modality",
        required=True,
        help="Identifier of the target modality plugin."
    )
    inject_parser.add_argument(
        "--file",
        required=True,
        help="Name of the file path within the spec_data/ sub-directory."
    )
    inject_parser.add_argument(
        "--source",
        required=True,
        help="Local file path of the source payload to inject."
    )

    # `extract` prints or writes one plugin-owned payload.
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract custom modality payload from agent-spec archive."
    )
    extract_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid agent-spec file."
    )
    extract_parser.add_argument(
        "--modality",
        required=True,
        help="Identifier of the target modality plugin."
    )
    extract_parser.add_argument(
        "--file",
        required=True,
        help="Name of the file path within the spec_data/ sub-directory."
    )
    extract_parser.add_argument(
        "--output",
        help="Optional local file path to write the extracted payload. Defaults to stdout."
    )

    # `validate` checks manifest registration, payload schemas, and `spec://`
    # link resolution.
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run verification on all files and links inside agent-spec archive."
    )
    validate_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid agent-spec file."
    )

    # `inspect` prints the full package anatomy for debugging documents that
    # cannot be understood from the editor UI alone.
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Print a detailed diagnostic report for a .spec document."
    )
    inspect_parser.add_argument(
        "--container",
        required=True,
        help="Path to target .spec file."
    )
    inspect_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Report output format. Defaults to json for scriptability."
    )
    inspect_parser.add_argument(
        "--output",
        help="Optional file path to write the report. Defaults to stdout."
    )

    # `sanitize` performs conservative structural repairs while preserving
    # payload contents and IP-XACT protocol semantics.
    sanitize_parser = subparsers.add_parser(
        "sanitize",
        help="Normalize a .spec package and add missing safe metadata."
    )
    sanitize_parser.add_argument(
        "--container",
        required=True,
        help="Path to source .spec file."
    )
    sanitize_parser.add_argument(
        "--output",
        help="Path to write the sanitized .spec file. Required unless --in-place is set."
    )
    sanitize_parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rewrite the source .spec file in place."
    )
    sanitize_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report intended sanitization actions without writing a file."
    )

    args = parser.parse_args()
    # The manager is built after parsing so import-time users of this module do
    # not pay plugin setup cost.
    pm = _build_default_manager()

    try:
        # Route command actions. Each branch prints JSON or concise status text
        # and exits non-zero for user-actionable failures.
        if args.command == "list-plugins":
            plugins = pm.list_plugins()
            print(json.dumps({"plugins": plugins}, indent=2))

        elif args.command == "inject":
            if not os.path.exists(args.source):
                print(f"Error: Source file '{args.source}' does not exist.", file=sys.stderr)
                sys.exit(1)

            if args.modality == "ipxact":
                # IP-XACT is XML bytes; the plugin validator handles parsing and
                # schema checks after the file is read.
                with open(args.source, "rb") as f:
                    payload = f.read()
            else:
                # Non-binary built-ins currently expect JSON documents.
                with open(args.source, "r", encoding="utf-8") as f:
                    raw_content = f.read()
                try:
                    payload = json.loads(raw_content)
                except Exception as e:
                    print(f"Error: Injected payload is not valid JSON: {e}", file=sys.stderr)
                    sys.exit(1)

            # Open an existing package when present; otherwise create a blank ODT
            # package and save it to the requested path.
            cont = container.AgentSpecArchive(
                args.container if os.path.exists(args.container) else None
            )

            # Delegate injection so each plugin controls validation, path
            # normalization, serialization, and manifest media type.
            pm.inject_payload(cont, args.modality, args.file, payload)
            
            # `save` performs the final ODT mimetype normalization.
            cont.save(args.container)
            print(f"Successfully injected '{args.file}' into '{args.container}' under modality '{args.modality}'.")

        elif args.command == "extract":
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)

            cont = container.AgentSpecArchive(args.container)
            payload = pm.extract_payload(cont, args.modality, args.file)

            if args.modality == "ipxact":
                # pyEDAA components keep their XML root internally; serialize it
                # for CLI-friendly output.
                import lxml.etree
                output_str = lxml.etree.tostring(payload._xmlRoot, pretty_print=True).decode("utf-8")
            else:
                output_str = json.dumps(payload, indent=2)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_str)
                print(f"Extracted payload written to '{args.output}'.")
            else:
                print(output_str)

        elif args.command == "validate":
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)

            cont = container.AgentSpecArchive(args.container)
            engine = verifier.ContainerVerifier(cont, pm)
            report = engine.verify_all()

            # Output validation report as clean, pretty JSON so other tools can
            # consume it directly.
            print(report.model_dump_json(indent=2))
            
            # Exit with standard shell code 1 on link/schema validation failures.
            if not report.is_fully_consistent:
                sys.exit(1)

        elif args.command == "inspect":
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)

            report = diagnostics.build_diagnostic_report(args.container)
            if args.format == "text":
                output = diagnostics.render_text_report(report)
            else:
                output = json.dumps(report, indent=2, sort_keys=True)

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output)
                    f.write("\n")
            else:
                print(output)

            if report.get("errors"):
                sys.exit(1)

        elif args.command == "sanitize":
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)
            if not args.in_place and not args.output:
                print("Error: sanitize requires --output unless --in-place is set.", file=sys.stderr)
                sys.exit(1)

            result = diagnostics.sanitize_spec_document(
                args.container,
                output_path=args.output,
                in_place=args.in_place,
                dry_run=args.dry_run,
            )
            print(result.model_dump_json(indent=2))

    except Exception as e:
        print(f"CLI Command Execution Failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
