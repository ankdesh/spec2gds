from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
def circuit_snapshot() -> dict[str, Any]:
    document = {
        "protocol_version": "circuit-designer.v1",
        "document_id": "fixture_simple",
        "label": "Simple circuit",
        "components": [
            {
                "id": "producer",
                "label": "Producer",
                "origin": "local",
                "editable": True,
                "terminals": [
                    {
                        "id": "data",
                        "label": "Data",
                        "direction": "output",
                        "width": 1,
                        "category": "port",
                    }
                ],
                "parameters": [],
                "appearance": {"renderer_key": "default", "properties": {}},
            },
            {
                "id": "consumer",
                "label": "Consumer",
                "origin": "local",
                "editable": True,
                "terminals": [
                    {
                        "id": "data",
                        "label": "Data",
                        "direction": "input",
                        "width": 1,
                        "category": "port",
                    }
                ],
                "parameters": [],
                "appearance": {"renderer_key": "default", "properties": {}},
            },
        ],
        "design": {
            "id": "top",
            "label": "Top",
            "boundary_terminals": [],
            "instances": [
                {
                    "id": "producer_0",
                    "label": "Producer 0",
                    "component_id": "producer",
                    "parameter_values": {},
                }
            ],
            "nets": [],
        },
        "layout": {
            "grid_size": 20,
            "direction": "RIGHT",
            "instance_geometry": {},
            "terminal_placements": {},
            "net_routes": {},
            "label_geometry": {},
        },
    }
    return {"revision": "1", "document": document}
