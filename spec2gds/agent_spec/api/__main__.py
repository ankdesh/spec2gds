"""Run the local agent-spec API with uvicorn."""

import os

import spec2gds.agent_spec.api.app as agent_spec_app


def main() -> None:
    import uvicorn

    host = os.environ.get("AGENT_SPEC_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENT_SPEC_PORT", "8765"))
    uvicorn.run(agent_spec_app.create_app(), host=host, port=port)


if __name__ == "__main__":
    main()

