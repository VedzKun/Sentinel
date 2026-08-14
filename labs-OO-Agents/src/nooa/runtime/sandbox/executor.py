# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Parent-side process backend facade for sandboxed cell execution.

:class:`SandboxedExecutor` delegates cell execution to a registered
:class:`BaseSandboxProvider` (e.g., local process, containerized environment,
or custom sandbox provider).
"""

from __future__ import annotations

import logging
from typing import Any

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.base import BaseSandboxProvider
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.guards import Capabilities, probe_capabilities
from nooa.runtime.sandbox.providers.local import check_enforceable
from nooa.runtime.sandbox.registry import create_sandbox_provider

logger = logging.getLogger(__name__)

__all__ = ["SandboxedExecutor", "check_enforceable"]


class SandboxedExecutor:
    """Run CodeAct cells via a configured SandboxProvider with hard timeout enforcement."""

    def __init__(
        self,
        agent: Any,
        config: SandboxConfig,
        *,
        cell_timeout: float | None,
        framework_builtins: dict[str, Any] | None = None,
        restrictions: Any = None,
    ) -> None:
        self._agent = agent
        self._config = config
        self._cell_timeout = cell_timeout
        self._framework_builtins = framework_builtins or {}
        self._restrictions = restrictions
        self._provider: BaseSandboxProvider = create_sandbox_provider(
            config,
            agent=agent,
            cell_timeout=cell_timeout,
            framework_builtins=framework_builtins,
            restrictions=restrictions,
        )

    @property
    def provider(self) -> BaseSandboxProvider:
        """The active sandbox provider instance."""
        return self._provider

    @property
    def degraded_guards(self) -> list[str]:
        """Guardrails that could not be enforced (only when require=False)."""
        return getattr(self._provider, "degraded_guards", [])

    async def run_cell(self, code: str, *, execution_count: int = 1) -> ExecutionResult:
        """Execute one cell in the configured sandbox provider and return an ``ExecutionResult``."""
        return await self._provider.run_cell(
            code,
            execution_count=execution_count,
            agent=self._agent,
            cell_timeout=self._cell_timeout,
            framework_builtins=self._framework_builtins,
            restrictions=self._restrictions,
        )

    async def aclose(self) -> None:
        """Async teardown of sandbox provider resources."""
        await self._provider.aclose()

    def close_sync(self) -> None:
        """Best-effort synchronous teardown for non-async cleanup paths."""
        self._provider.close_sync()
