"""Run the production V1 IP-XACT-centered local editor API with uvicorn."""

import os

from spec2gds.agent_spec.spec_format import v1_api


def main() -> None:
    """Start the ODT-free V1 local API and its lightweight editor surface."""
    import uvicorn

    host = os.environ.get("AGENT_SPEC_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENT_SPEC_PORT", "8000"))
    uvicorn.run(v1_api.create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
