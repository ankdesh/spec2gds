"""Run the local agent-spec document editor API with uvicorn."""

import os

import spec2gds.agent_spec.api.document_app as document_app


def main() -> None:
    """Start the API expected by the local React document editor."""
    import uvicorn

    host = os.environ.get("AGENT_SPEC_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENT_SPEC_PORT", "8000"))
    uvicorn.run(document_app.create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
