# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Process-backed, OS-enforced sandbox for CodeAct cell execution.

Public surface:

* :class:`~nooa.runtime.sandbox.config.SandboxConfig` — declarative guardrails.
* :class:`~nooa.runtime.sandbox.base.BaseSandboxProvider` — abstract sandbox provider protocol.
* :class:`~nooa.runtime.sandbox.executor.SandboxedExecutor` — parent-side backend delegating to active provider.
* registry functions (:func:`register_provider`, :func:`create_sandbox_provider`).
* guard errors (:class:`CellTimeoutError`, :class:`CellMemoryError`, ...).
"""

from __future__ import annotations

from nooa.runtime.sandbox.base import BaseSandboxProvider
from nooa.runtime.sandbox.config import FileRule, SandboxConfig
from nooa.runtime.sandbox.errors import (
    CellMemoryError,
    CellSerializationError,
    CellTimeoutError,
    SandboxError,
    SandboxUnavailable,
    WorkerDiedError,
)
from nooa.runtime.sandbox.executor import SandboxedExecutor
from nooa.runtime.sandbox.session import SandboxSession
from nooa.runtime.sandbox.registry import (
    create_sandbox_provider,
    get_provider_class,
    list_providers,
    register_provider,
)

__all__ = [
    "SandboxConfig",
    "FileRule",
    "BaseSandboxProvider",
    "SandboxedExecutor",
    "SandboxSession",
    "register_provider",
    "get_provider_class",
    "list_providers",
    "create_sandbox_provider",
    "SandboxError",
    "SandboxUnavailable",
    "CellTimeoutError",
    "CellMemoryError",
    "CellSerializationError",
    "WorkerDiedError",
]
