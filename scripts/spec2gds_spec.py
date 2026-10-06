"""CLI for the custom IP-XACT-centered V1 `.spec` package."""

import argparse
import fcntl
import json
import os
import pathlib
import sys
from contextlib import contextmanager, nullcontext

from spec2gds.spec.spec_format.archive import SpecPackage, SpecValidationError
from spec2gds.spec.spec_format.assistant import SpecChangeProposal
from spec2gds.spec.spec_format.ir import SpecRevision
from spec2gds.spec.spec_format.naming import (
    document_name,
    entity_name,
    normalize_package_names,
    readable_name,
)
from spec2gds.spec.spec_format.proposal_service import (
    ProposalApplyError,
    apply_assistant_proposal,
    reconcile_assistant_receipts,
)
from spec2gds.spec.spec_format.review_store import list_spec_reviews, review_bridge
from spec2gds.spec.spec_format.spec_service_store import document_key
from spec2gds.spec.spec_format.v1_api import V1Session
from spec2gds.spec.spec_format.workspace_target import (
    assistant_state_root,
    resolve_spec_target,
)


def _parser() -> argparse.ArgumentParser:
    """Build the V1 source-package command line parser."""
    parser = argparse.ArgumentParser(prog="spec2gds-spec", description="IP-XACT-centered spec2gds V1 package tool")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create", help="Create an empty V1 .spec package.")
    create.add_argument("--output", required=True)
    create.add_argument("--name", help="Readable specification name")
    create.add_argument("--document-id", help=argparse.SUPPRESS)

    validate = commands.add_parser("validate", help="Validate a V1 .spec package.")
    validate.add_argument("--container", required=True)

    inspect = commands.add_parser("inspect", help="Inspect a V1 .spec package.")
    inspect.add_argument("--container", required=True)
    inspect.add_argument("--format", choices=["json", "text"], default="text")

    unpack = commands.add_parser("unpack", help="Unpack a V1 .spec package.")
    unpack.add_argument("--container", required=True)
    unpack.add_argument("--output", required=True)

    pack = commands.add_parser("pack", help="Pack an unpacked V1 .spec directory.")
    pack.add_argument("--input", required=True)
    pack.add_argument("--output", required=True)
    for command in (create, validate, unpack, pack):
        command.add_argument("--json", action="store_true", help="Include exact technical identifiers")
    for action in ("architecture-reviews", "approve-architecture", "revise-architecture", "cancel-architecture"):
        review = commands.add_parser(action, help="Inspect or decide a stored architecture before content creation.")
        review.add_argument("target", help="Workspace directory or exact .spec path")
        review.add_argument("--json", action="store_true", help="Include exact technical identifiers")
        if action != "architecture-reviews":
            review.add_argument("review_id")
    for action in ("reviews", "history", "approve", "reject"):
        review = commands.add_parser(action, help=f"{action.capitalize()} assistant proposals for one specification.")
        review.add_argument("target", help="Workspace directory or exact .spec path")
        review.add_argument("--json", action="store_true", help="Include exact technical identifiers")
        if action == "history":
            review.add_argument("--before", type=int)
            review.add_argument("--limit", type=int, default=50)
        elif action != "reviews":
            review.add_argument("proposal_id", nargs="?")
    return parser


def _selected_review(reviews: list[dict], proposal_id: str | None, states: set[str]) -> dict:
    candidates = [item for item in reviews if item["state"] in states]
    if proposal_id:
        matches = [item for item in candidates if item["proposalId"] == proposal_id or str(item.get("ordinal")) == proposal_id]
        if len(matches) > 1:
            raise ValueError("Ambiguous review number; use the exact ID from --json.")
        selected = matches[0] if matches else None
        if selected is None:
            raise ValueError(f"No pending proposal with number or ID {proposal_id}.")
        return selected
    if not candidates:
        raise ValueError("No pending proposal for this specification.")
    if len(candidates) > 1:
        raise ValueError("Multiple proposals are pending; provide a review number: "
                         + ", ".join(str(item.get("ordinal", "unavailable")) for item in candidates))
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


def _review_command(action: str, target: str, proposal_id: str | None = None, technical: bool = False) -> int:
    """Bridge an explicit CLI decision to the same stored owner proposal and receipt.

    Reconcile interrupted saves before approval/rejection and serialize mutating
    review actions. Listing history does not claim or run an Assistant request.
    """
    path = resolve_spec_target(target)
    document_id = SpecPackage.load(str(path)).manifest.document_id
    state_root = assistant_state_root(path)
    with nullcontext() if action == "reviews" else _review_lock(state_root):
        if action != "reviews" and (state_root / "assistant.sqlite3").exists():
            review_bridge(state_root, "recover")
        reviews = list_spec_reviews(state_root, document_id) if (state_root / "assistant.sqlite3").exists() else []
        session = V1Session(str(path))
        reconcile_assistant_receipts(session)
        journal = session.journal
        node_ids = {item["proposalId"] for item in reviews}
        cursor = None
        while True:
            page = journal.history(cursor)
            for item in page["items"]:
                if item["proposal_id"] in node_ids:
                    next(review for review in reviews if review["proposalId"] == item["proposal_id"])["ordinal"] = item["ordinal"]
                    if action == "reviews":
                        receipt = journal.get(item["proposal_id"])
                        stored = next(review for review in reviews if review["proposalId"] == item["proposal_id"])
                        stored.update(ordinal=item["ordinal"], state=receipt["state"], serviceResult=receipt["service_result"], diagnostics=receipt["diagnostics"])
                    continue
                receipt = journal.get(item["proposal_id"])
                reviews.append({"proposalId": receipt["proposal_id"], "sessionId": receipt["session_id"],
                    "ordinal": item["ordinal"], "state": receipt["state"], "baseRevision": receipt["artifact"]["base_source_revision_hash"],
                    "artifact": receipt["artifact"], "preview": receipt["preview"],
                    "diagnostics": receipt["diagnostics"], "serviceResult": receipt["service_result"]})
            cursor = page["next_cursor"]
            if cursor is None:
                break
        def bridge(command: str, selected: dict, result: dict | None = None) -> None:
            if selected["proposalId"] in node_ids:
                review_bridge(state_root, command, selected["proposalId"], result)
        if action == "reviews":
            if not technical:
                print(document_name(session.revision))
                for item in reviews:
                    print(f"Review {item.get('ordinal', 'unavailable')}: {item['artifact'].get('title', 'Proposed change')} · {item['state']}")
                return 0
            print(json.dumps({
                "schema_version": "spec2gds.assistant-workspace-reviews.v1",
                "spec_path": str(path),
                "reviews": [{
                    "proposal_id": item["proposalId"], "session_id": item["sessionId"],
                    "state": item["state"], "base_revision": item["baseRevision"],
                    "artifact": item["artifact"], "preview": item["preview"],
                    "diagnostics": item["diagnostics"], "service_result": item["serviceResult"],
                } for item in reviews],
            }, indent=2))
            return 0
        if action == "reject":
            selected = _selected_review(reviews, proposal_id, {"ready", "rejected", "stale", "reconcile"})
            journal.register(selected["artifact"], selected["sessionId"])
            if journal.get(selected["proposalId"])["state"] == "applied":
                raise ValueError("A saved change cannot be rejected retroactively.")
            journal.update(selected["proposalId"], state="discarded")
            bridge("discard", selected)
            print(json.dumps({"proposal_id": selected["proposalId"], "state": "discarded"}) if technical else f"Review {selected.get('ordinal')}: discarded")
            return 0
        selected = _selected_review(reviews, proposal_id, {"ready", "reconcile"})
        proposal = SpecChangeProposal.model_validate(selected["artifact"])
        if proposal.document_id != document_id:
            raise ValueError("Proposal targets a different specification document.")
        journal.register(selected["artifact"], selected["sessionId"])
        receipt = journal.get(selected["proposalId"])
        if receipt["state"] == "discarded":
            raise ValueError("This stored proposal was explicitly rejected.")
        journal.update(selected["proposalId"], state="applying")
        bridge("begin", selected)
        try:
            result = apply_assistant_proposal(session, proposal, application_mode="review", session_id=selected["sessionId"])
        except ProposalApplyError as exc:
            state = "stale" if exc.status == 409 else "rejected"
            journal.update(selected["proposalId"], state=state, diagnostics=exc.detail)
            bridge(state, selected)
            raise ValueError(f"Proposal apply failed: {exc.detail}") from exc
        except ValueError:
            journal.update(selected["proposalId"], state="stale")
            bridge("stale", selected)
            raise
        except OSError:
            journal.update(selected["proposalId"], state="reconcile")
            bridge("reconcile", selected)
            raise
        journal.update(selected["proposalId"], state="applied", service_result=result, diagnostics=[])
        journal.observe({"document_id": document_id, "owner_document_key": session.service_document_key,
            "source_revision_hash": result["source_revision_hash"], "origin": "assistant", "affected_entities": []})
        bridge("complete", selected, result)
        print(json.dumps(result, default=str) if technical else f"Review {selected.get('ordinal')}: saved changes to {document_name(session.revision)}")
        return 0

def main(argv: list[str] | None = None) -> int:
    """Execute one V1 package command and return a shell-compatible status."""
    args = _parser().parse_args(argv)
    try:
        if args.command in {"architecture-reviews", "approve-architecture", "revise-architecture", "cancel-architecture"}:
            path = resolve_spec_target(args.target)
            root = assistant_state_root(path)
            listing = review_bridge(root, "architecture-list")["architecture_reviews"]
            document_id = SpecPackage.load(str(path)).manifest.document_id
            owner_key = document_key(str(path), document_id)
            available = [item for item in listing if ((item.get("serviceDocumentKey") == owner_key and item.get("documentId") == document_id) or (item.get("destinationServiceDocumentKey") == owner_key and item.get("destinationDocumentId") == document_id))]
            for number, item in enumerate(available, 1):
                item.setdefault("reviewNumber", number)
            if args.command == "architecture-reviews":
                if args.json:
                    print(json.dumps({"architecture_reviews": available}, indent=2))
                else:
                    for item in available:
                        print(f"Architecture review {item['reviewNumber']}: {item.get('plan', {}).get('title', 'Architecture')} · {item['status']}")
                return 0
            matches = [item for item in available if item["reviewId"] == args.review_id or str(item["reviewNumber"]) == args.review_id]
            if len(matches) > 1:
                raise ValueError("Architecture review number is ambiguous; use its exact ID from --json.")
            selected = matches[0] if matches else None
            if selected is None:
                raise ValueError("Architecture review belongs to a different specification.")
            action = {"approve-architecture": "approved", "revise-architecture": "revised", "cancel-architecture": "cancelled"}[args.command]
            with _review_lock(root):
                result = review_bridge(root, f"architecture-{action}", selected["reviewId"])
            print(json.dumps(result, indent=2) if args.json else f"Architecture review {selected['reviewNumber']}: {action}")
            return 0
        if args.command in {"reviews", "approve", "reject"}:
            return _review_command(args.command, args.target, getattr(args, "proposal_id", None), args.json)
        if args.command == "history":
            path = resolve_spec_target(args.target)
            session = V1Session(str(path))
            reconcile_assistant_receipts(session)
            history = session.journal.history(args.before, args.limit)
            if args.json:
                print(json.dumps(history, indent=2))
            else:
                for item in history["items"]:
                    print(f"Review {item['ordinal']}: {item['title']} · {item['state']}")
            return 0
        if args.command == "create":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.create(document_id=args.document_id, title=args.name or readable_name(output.stem))
            normalize_package_names(package)
            package.save(str(output))
            print(json.dumps({"container": str(output), "document_id": package.manifest.document_id}, sort_keys=True) if args.json else f"Created {package.narrative.title}: {output}")
            return 0
        if args.command == "validate":
            package = SpecPackage.load(args.container)
            print(json.dumps({"container": args.container, "source_hash": package.source_hash(), "valid": True}, sort_keys=True) if args.json else f"Valid: {package.narrative.title or readable_name(pathlib.Path(args.container).stem)}")
            return 0
        if args.command == "inspect":
            package = SpecPackage.load(args.container)
            report = {
                "manifest": package.manifest.model_dump(mode="json"),
                "source_hash": package.source_hash(),
                "paths": sorted(package.files),
            }
            if args.format == "text":
                revision = SpecRevision.from_package(package)
                print(document_name(revision))
                print("documents:")
                for entity in (*revision.components, *revision.designs, *revision.bus_definitions, *revision.abstraction_definitions):
                    print(f"  - {entity.ref.entity_kind}: {entity_name(entity)}")
            else:
                print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "unpack":
            package = SpecPackage.load(args.container)
            package.unpack(args.output)
            print(json.dumps({"container": args.container, "output": args.output}, sort_keys=True) if args.json else f"Unpacked {package.narrative.title}: {args.output}")
            return 0
        if args.command == "pack":
            output = pathlib.Path(args.output)
            if output.exists():
                raise ValueError(f"Refusing to overwrite existing package: {output}")
            package = SpecPackage.from_directory(args.input)
            package.save(str(output))
            print(json.dumps({"input": args.input, "container": str(output)}, sort_keys=True) if args.json else f"Packed {package.narrative.title}: {output}")
            return 0
    except (OSError, ValueError, SpecValidationError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
