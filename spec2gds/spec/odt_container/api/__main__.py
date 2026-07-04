import uvicorn

import spec2gds.spec.odt_container.api.app as app_module


def main() -> None:
    """Run the local ODT editor API."""
    uvicorn.run(app_module.create_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
