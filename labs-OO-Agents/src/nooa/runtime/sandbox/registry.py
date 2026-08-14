# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Registry for discovering, registering, and instantiating Sandbox Providers."""

from __future__ import annotations

import os
from typing import Any, Type

from nooa.runtime.sandbox.base import BaseSandboxProvider
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.errors import SandboxUnavailable
from nooa.runtime.sandbox.providers.container import ContainerSandboxProvider
from nooa.runtime.sandbox.providers.local import LocalProcessSandboxProvider

_REGISTRY: dict[str, Type[BaseSandboxProvider]] = {}


def register_provider(name: str, provider_cls: Type[BaseSandboxProvider]) -> None:
    """Register a sandbox provider class under a string identifier."""
    if not issubclass(provider_cls, BaseSandboxProvider):
        raise TypeError(f"Provider {provider_cls} must subclass BaseSandboxProvider")
    _REGISTRY[name.lower()] = provider_cls


def get_provider_class(name: str) -> Type[BaseSandboxProvider]:
    """Retrieve a registered sandbox provider class by name."""
    key = name.lower()
    if key not in _REGISTRY:
        raise SandboxUnavailable(
            f"Unknown sandbox provider '{name}'. Available providers: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[key]


def list_providers() -> list[str]:
    """List all registered sandbox provider names."""
    return list(_REGISTRY.keys())


def create_sandbox_provider(
    config: SandboxConfig,
    agent: Any = None,
    *,
    cell_timeout: float | None = None,
    framework_builtins: dict[str, Any] | None = None,
    restrictions: Any = None,
    provider_name: str | None = None,
) -> BaseSandboxProvider:
    """Instantiate the configured SandboxProvider instance."""
    name = provider_name or getattr(config, "provider", None) or os.getenv("NOOA_SANDBOX_PROVIDER", "local")
    provider_cls = get_provider_class(name)
    return provider_cls(
        config=config,
        agent=agent,
        cell_timeout=cell_timeout,
        framework_builtins=framework_builtins,
        restrictions=restrictions,
    )


# Register default built-in providers
register_provider("local", LocalProcessSandboxProvider)
register_provider("container", ContainerSandboxProvider)
