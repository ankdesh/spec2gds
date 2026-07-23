"""Command-line entry point for Docling document imports."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
from typing import Sequence

from spec2gds.agent_spec.importers.docling_reader import DoclingDocumentReader
from spec2gds.agent_spec.importers.document import DocumentImportOptions, DocumentToSpecConverter
from spec2gds.agent_spec.importers.ipxact_from_tables import (
    DEFAULT_OPENAI_MODEL,
    OpenAIHardwareTableEnricher,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a PDF, DOC/DOCX, ODT, or other Docling-supported file to V1 .spec."
    )
    parser.add_argument("input", help="Local source document.")
    parser.add_argument("-o", "--output", help="Destination .spec path; defaults beside the input.")
    parser.add_argument(
        "--openai",
        action="store_true",
        help="Extract IP-XACT ports and formal bus interfaces from source tables.",
    )
    parser.add_argument("--model", default=DEFAULT_OPENAI_MODEL, help="OpenAI model for --openai.")
    parser.add_argument("--vendor", default="spec2gds.imported")
    parser.add_argument("--library", default="documents")
    parser.add_argument("--component-name", default="")
    parser.add_argument("--component-version", default="1.0")
    parser.add_argument("--document-id", default="")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR for PDF inputs.")
    parser.add_argument("--image-scale", type=float, default=2.0)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing output package.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run one document import and return a shell-compatible status."""
    args = _parser().parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".spec")
    try:
        if not input_path.is_file():
            raise FileNotFoundError(f"Source document does not exist: {input_path}")
        if output_path.suffix.lower() != ".spec":
            raise ValueError("Output path must use the .spec extension.")
        if input_path.resolve() == output_path.resolve():
            raise ValueError("Input and output paths must differ.")
        if output_path.exists() and not args.force:
            raise FileExistsError(f"Refusing to overwrite existing package: {output_path}")
        if args.openai and not os.environ.get("OPENAI_API_KEY"):
            raise ValueError("--openai requires OPENAI_API_KEY in the environment.")

        reader = DoclingDocumentReader(ocr=not args.no_ocr, image_scale=args.image_scale)
        enricher = OpenAIHardwareTableEnricher(model=args.model) if args.openai else None
        converter = DocumentToSpecConverter(reader=reader, enricher=enricher)
        result = converter.convert(
            input_path,
            output_path,
            options=DocumentImportOptions(
                vendor=args.vendor,
                library=args.library,
                component_name=args.component_name,
                component_version=args.component_version,
                document_id=args.document_id,
            ),
        )
        report = asdict(result)
        report["output_path"] = str(result.output_path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
