# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Abstract Base Class and data models for Sandbox Providers in NOOA."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.config import SandboxConfig


class BaseSandboxProvider(ABC):
    """Abstract interface defining standard sandbox provider capabilities."""

    def __init__(self, config: SandboxConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier string for the provider implementation (e.g. 'local', 'container')."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Asynchronous initialization step for sandbox environment and resources."""
        ...

    @abstractmethod
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
        """Execute code within the sandbox environment and return an ExecutionResult."""
        ...

    @abstractmethod
    async def aclose(self) -> None:
        """Async teardown of sandbox resources."""
        ...

    @abstractmethod
    def close_sync(self) -> None:
        """Synchronous teardown of sandbox resources."""
        ...
