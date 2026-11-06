"""Configuration (spec 13.3): layers, merge and validation with no I/O, title-block mappings."""

from cad_application.config.merge import merge_settings, parse_env_layer, parse_toml_layer
from cad_application.config.settings import ConfigError, Layer, Settings
from cad_application.config.title_blocks import load_title_block_mappings

__all__ = [
    "ConfigError",
    "Layer",
    "Settings",
    "load_title_block_mappings",
    "merge_settings",
    "parse_env_layer",
    "parse_toml_layer",
]
