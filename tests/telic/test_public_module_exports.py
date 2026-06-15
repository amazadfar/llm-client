from __future__ import annotations

import importlib


PUBLIC_MODULES = [
    "telic.advanced",
    "telic.agent",
    "telic.compat",
    "telic.config",
    "telic.content",
    "telic.context",
    "telic.engine",
    "telic.errors",
    "telic.model_catalog",
    "telic.observability",
    "telic.provider_registry",
    "telic.providers",
    "telic.resilience",
    "telic.routing",
    "telic.tools",
    "telic.types",
    "telic.validation",
]


def test_public_modules_define_explicit_all_exports() -> None:
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        assert hasattr(module, "__all__"), module_name
        exported = getattr(module, "__all__")
        assert isinstance(exported, list), module_name
        assert exported, module_name
