import argparse
import json
import os
import sys
import spec2gds.spec.odt_container.container as container
import spec2gds.spec.odt_container.manager as manager
import spec2gds.spec.odt_container.json_plugin as json_plugin
import spec2gds.spec.odt_container.verifier as verifier

def _build_default_manager() -> manager.PluginManager:
    """
    Bootstrap the default plugin manager registry.
    This registers the standard JSON modality handler so that the CLI commands
    can automatically route JSON data injection and extraction requests.
    """
    pm = manager.PluginManager()
    
    # Instantiate and register the test JSON plugin
    json_plug = json_plugin.SimpleJSONPlugin()
    pm.register_plugin(json_plug)
    
    return pm

def main() -> None:
    """
    Headless command-line interface entry point.
    Supports list-plugins, inject, extract, and validate command suites.
    """
    parser = argparse.ArgumentParser(
        description="Hybrid ODT Container Management Tool - Embeds structured hardware specs inside ODT."
    )
    # Target command routing
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. list-plugins command
    subparsers.add_parser(
        "list-plugins",
        help="List all registered modality plugins."
    )

    # 2. inject command
    inject_parser = subparsers.add_parser(
        "inject",
        help="Inject custom modality data payload into ODT container."
    )
    inject_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid ODT file."
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

    # 3. extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Extract custom modality payload from ODT container."
    )
    extract_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid ODT file."
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

    # 4. validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run verification on all files and links inside ODT container."
    )
    validate_parser.add_argument(
        "--container",
        required=True,
        help="Path to target hybrid ODT file."
    )

    args = parser.parse_args()
    # Bootstrap PluginManager and registers
    pm = _build_default_manager()

    try:
        # Route command actions
        if args.command == "list-plugins":
            # list-plugins: output currently loaded plugins
            plugins = pm.list_plugins()
            print(json.dumps({"plugins": plugins}, indent=2))

        elif args.command == "inject":
            # inject: serialize raw JSON metadata, validate, write to ZIP, update manifest, save
            if not os.path.exists(args.source):
                print(f"Error: Source file '{args.source}' does not exist.", file=sys.stderr)
                sys.exit(1)

            with open(args.source, "r", encoding="utf-8") as f:
                raw_content = f.read()

            try:
                payload = json.loads(raw_content)
            except Exception as e:
                print(f"Error: Injected payload is not valid JSON: {e}", file=sys.stderr)
                sys.exit(1)

            # Open existing container or instantiate a fresh blank text container
            # Handles 0-size files correctly inside HybridODTContainer.__init__
            cont = container.HybridODTContainer(
                args.container if os.path.exists(args.container) else None
            )

            # Delegate injection (runs schema validations automatically)
            pm.inject_payload(cont, args.modality, args.file, payload)
            
            # Enforce uncompressed mimetype alignments and save container ZIP
            cont.save(args.container)
            print(f"Successfully injected '{args.file}' into '{args.container}' under modality '{args.modality}'.")

        elif args.command == "extract":
            # extract: load hybrid ODT, extract targeted payload file, print/save
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)

            cont = container.HybridODTContainer(args.container)
            payload = pm.extract_payload(cont, args.modality, args.file)

            output_str = json.dumps(payload, indent=2)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(output_str)
                print(f"Extracted payload written to '{args.output}'.")
            else:
                print(output_str)

        elif args.command == "validate":
            # validate: run complete verifications of all files and links, print Pydantic report
            if not os.path.exists(args.container):
                print(f"Error: Container file '{args.container}' does not exist.", file=sys.stderr)
                sys.exit(1)

            cont = container.HybridODTContainer(args.container)
            engine = verifier.ContainerVerifier(cont, pm)
            report = engine.verify_all()

            # Output validation report as clean, pretty JSON
            print(report.model_dump_json(indent=2))
            
            # Exit with standard shell code 1 on link/schema validation failures
            if not report.is_fully_consistent:
                sys.exit(1)

    except Exception as e:
        print(f"CLI Command Execution Failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
