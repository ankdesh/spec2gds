"""Payload plugin interfaces and built-in plugin implementations."""

from spec2gds.agent_spec.plugins.base import ModalityPlugin, ModalityPluginConfig
from spec2gds.agent_spec.plugins.ipxact import IPXACTPlugin
from spec2gds.agent_spec.plugins.json_payload import SimpleJSONPlugin
from spec2gds.agent_spec.plugins.manager import PluginManager

__all__ = [
    "IPXACTPlugin",
    "ModalityPlugin",
    "ModalityPluginConfig",
    "PluginManager",
    "SimpleJSONPlugin",
]
