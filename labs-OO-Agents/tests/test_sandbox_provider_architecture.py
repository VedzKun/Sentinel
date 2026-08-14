# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for SandboxProvider abstraction interface and registry (Phase 1)."""

import os
from typing import Any

import pytest

from nooa.events import ExecutionResult
from nooa.runtime.sandbox import (
    BaseSandboxProvider,
    SandboxConfig,
    SandboxedExecutor,
    SandboxUnavailable,
    create_sandbox_provider,
    get_provider_class,
    list_providers,
    register_provider,
)
from nooa.runtime.sandbox.providers.container import ContainerSandboxProvider
from nooa.runtime.sandbox.providers.local import LocalProcessSandboxProvider


class DummyMockSandboxProvider(BaseSandboxProvider):
    """Mock provider for architecture unit tests."""

    def __init__(self, config: SandboxConfig, **kwargs: Any) -> None:
        super().__init__(config)
        self.initialized = False
        self.closed = False
        self.executed_cells: list[str] = []

    @property
    def provider_name(self) -> str:
        return "dummy_mock"

    async def initialize(self) -> None:
        self.initialized = True

    async def run_cell(
        self,
        code: str,
        *,
        execution_count: int = 1,
        agent: Any = None,
        cell_timeout: float | None = None,
        framework_builtins: dict[str, Any] | None = None,
        restrictions: Any = None,
    ) -> ExecutionResult:
        self.executed_cells.append(code)
        return ExecutionResult(stdout=f"mocked: {code}", stderr="", error=None, defined_methods={})

    async def aclose(self) -> None:
        self.closed = True

    def close_sync(self) -> None:
        self.closed = True


def test_builtin_providers_registered():
    """Verify default providers ('local', 'container') are registered."""
    providers = list_providers()
    assert "local" in providers
    assert "container" in providers
    assert get_provider_class("local") is LocalProcessSandboxProvider
    assert get_provider_class("container") is ContainerSandboxProvider


def test_custom_provider_registration():
    """Verify dynamic registration of custom sandbox providers."""
    register_provider("dummy_mock", DummyMockSandboxProvider)
    assert "dummy_mock" in list_providers()
    assert get_provider_class("dummy_mock") is DummyMockSandboxProvider


def test_create_sandbox_provider_by_config():
    """Verify create_sandbox_provider respects SandboxConfig.provider."""
    register_provider("dummy_mock", DummyMockSandboxProvider)
    config = SandboxConfig(provider="dummy_mock", require=False)
    provider = create_sandbox_provider(config)
    assert isinstance(provider, DummyMockSandboxProvider)
    assert provider.provider_name == "dummy_mock"


def test_create_sandbox_provider_unknown_raises():
    """Verify unknown provider name raises SandboxUnavailable."""
    config = SandboxConfig(provider="unknown_nonexistent_provider", require=False)
    with pytest.raises(SandboxUnavailable, match="Unknown sandbox provider"):
        create_sandbox_provider(config)


@pytest.mark.asyncio
async def test_sandboxed_executor_delegates_to_provider():
    """Verify SandboxedExecutor seamlessly routes cell execution through provider."""
    register_provider("dummy_mock", DummyMockSandboxProvider)
    config = SandboxConfig(provider="dummy_mock", require=False)
    executor = SandboxedExecutor(agent=None, config=config, cell_timeout=10.0)

    assert isinstance(executor.provider, DummyMockSandboxProvider)
    result = await executor.run_cell("print('hello sandbox')")

    assert result.stdout == "mocked: print('hello sandbox')"
    assert executor.provider.executed_cells == ["print('hello sandbox')"]

    await executor.aclose()
    assert executor.provider.closed is True
