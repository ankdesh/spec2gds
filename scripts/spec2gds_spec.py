"""CLI for the custom IP-XACT-centered V1 `.spec` package."""

import argparse
import fcntl
import json
import os
import pathlib
import sys
from contextlib import contextmanager, nullcontext

from spec2gds.agent_spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.agent_spec.spec_format.assistant import SpecChangeProposal
from spec2gds.agent_spec.spec_format.proposal_service import (
    ProposalApplyError,
    apply_assistant_proposal,
)
from spec2gds.agent_spec.spec_format.review_store import list_spec_reviews, review_bridge
from spec2gds.agent_spec.spec_format.v1_api import V1Session
from spec2gds.agent_spec.spec_format.workspace_target import (
    assistant_state_root,
    resolve_spec_target,
)


def _parser() -> argparse.ArgumentParser:
    """Build the V1 source-package command line parser."""
    parser = argparse.ArgumentParser(prog="spec2gds-spec", description="IP-XACT-centered spec2gds V1 package tool")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an empty V1 .spec package.")
    create.add_argument("--output", required=True)
    create.add_argument("--document-id")

    validate = commands.add_parser("validate", help="Validate a V1 .spec package.")
    validate.add_argument("--container", required=True)

    inspect = commands.add_parser("inspect", help="Inspect a V1 .spec package.")
    inspect.add_argument("--container", required=True)
    inspect.add_argument("--format", choices=["json", "text"], default="json")

    unpack = commands.add_parser("unpack", help="Unpack a V1 .spec package.")
    unpack.add_argument("--container", required=True)
    unpack.add_argument("--output", required=True)

    pack = commands.add_parser("pack", help="Pack an unpacked V1 .spec directory.")
    pack.add_argument("--input", required=True)
    pack.add_argument("--output", required=True)
    for action in ("reviews", "approve", "reject"):
        review = commands.add_parser(action, help=f"{action.capitalize()} assistant proposals for one specification.")
        review.add_argument("target", help="Workspace directory or exact .spec path")
        if action != "reviews":
            review.add_argument("proposal_id", nargs="?")
    return parser


def _selected_review(reviews: list[dict], proposal_id: str | None, states: set[str]) -> dict:
    candidates = [item for item in reviews if item["state"] in states]
    if proposal_id:
        selected = next((item for item in candidates if item["proposalId"] == proposal_id), None)
        if selected is None:
            raise ValueError(f"No pending proposal with ID {proposal_id}.")
        return selected
    if not candidates:
        raise ValueError("No pending proposal for this specification.")
    if len(candidates) > 1:
        raise ValueError("Multiple proposals are pending; provide one ID: "
                         + ", ".join(item["proposalId"] for item in candidates))
    return candidates[0]


@contextmanager
def _review_lock(state_root: pathlib.Path):
    """Serialize decisions for one package, including interrupted-run recovery."""
    state_root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(state_root / "approval.lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, "rb") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _review_command(action: str, target: str, proposal_id: str | None = None) -> int:
    path = resolve_spec_target(target)
    document_id = SpecPackage.load(str(path)).manifest.document_id
    state_root = assistant_state_root(path)
    with nullcontext() if action == "reviews" else _review_lock(state_root):
        if action != "reviews" and (state_root / "assistant.sqlite3").exists():
            review_bridge(state_root, "recover")
        reviews = list_spec_reviews(state_root, document_id)
        if action == "reviews":
            print(json.dumps({
                "schema_version": "spec2gds.assistant-workspace-reviews.v1",
                "spec_path": str(path),
                "reviews": [{
                    "proposal_id": item["proposalId"], "session_id": item["sessionId"],
                    "state": item["state"], "base_revision": item["baseRevision"],
                    "artifact": item["artifact"], "preview": item["preview"],
                    "diagnostics": item["diagnostics"], "owner_result": item["ownerResult"],
                } for item in reviews],
            }, indent=2))
            return 0
        if action == "reject":
            selected = _selected_review(reviews, proposal_id, {"ready", "rejected", "stale", "reconcile"})
            review_bridge(state_root, "discard", selected["proposalId"])
            print(json.dumps({"proposal_id": selected["proposalId"], "state": "discarded"}))
            return 0
        selected = _selected_review(reviews, proposal_id, {"ready", "reconcile"})
        proposal = SpecChangeProposal.model_validate(selected["artifact"])
        if proposal.document_id != document_id:
            raise ValueError("Proposal targets a different specification document.")
        review_bridge(state_root, "begin", selected["proposalId"])
        try:
            session = V1Session(str(path))
            result = apply_assistant_proposal(session, proposal)
        except ProposalApplyError as exc:
            review_bridge(state_root, "stale" if exc.status == 409 else "rejected", selected["proposalId"])
            raise ValueError(f"Proposal apply failed: {exc.detail}") from exc
        except ValueError:
            review_bridge(state_root, "stale", selected["proposalId"])
            raise
        except OSError:
            review_bridge(state_root, "reconcile", selected["proposalId"])
            raise
        review_bridge(state_root, "complete", selected["proposalId"], result)
        print(json.dumps(result, default=str))
        return 0

def main(argv: list[str] | None = None) -> int:
    """Execute one V1 package command and return a shell-compatible status."""
    args = _parser().parse_args(argv)
    try:
        if args.command in {"reviews", "approve", "reject"}:
            return _review_command(args.command, args.target, getattr(args, "proposal_id", None))
        if args.command == "create":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.create(document_id=args.document_id)
            package.save(str(output))
            print(json.dumps({"container": str(output), "document_id": package.manifest.document_id}, sort_keys=True))
            return 0
        if args.command == "validate":
            package = SpecPackage.load(args.container)
            print(json.dumps({"container": args.container, "source_hash": package.source_hash(), "valid": True}, sort_keys=True))
            return 0
        if args.command == "inspect":
            package = SpecPackage.load(args.container)
            report = {
                "manifest": package.manifest.model_dump(mode="json"),
                "source_hash": package.source_hash(),
                "paths": sorted(package.files),
            }
            if args.format == "text":
                print(f"document_id: {package.manifest.document_id}")
                print(f"source_hash: {report['source_hash']}")
                print("documents:")
                for entry in package.manifest.documents:
                    print(f"  - {entry.kind}: {entry.vlnv} ({entry.path})")
            else:
                print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "unpack":
            package = SpecPackage.load(args.container)
            package.unpack(args.output)
            print(json.dumps({"container": args.container, "output": args.output}, sort_keys=True))
            return 0
        if args.command == "pack":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.from_directory(args.input)
            package.save(str(output))
            print(json.dumps({"input": args.input, "container": str(output)}, sort_keys=True))
            return 0
    except (OSError, ValueError, SpecValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
