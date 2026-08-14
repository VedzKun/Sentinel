# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Local Process Sandbox Provider implementation."""

from __future__ import annotations

import asyncio
import concurrent.futures as futures
import logging
import multiprocessing as mp
import os
import signal
import time
from multiprocessing.connection import Connection
from typing import Any

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.base import BaseSandboxProvider
from nooa.runtime.sandbox.config import ResolvedSpec, SandboxConfig, resolve_spec
from nooa.runtime.sandbox.errors import (
    CellMemoryError,
    CellSerializationError,
    CellTimeoutError,
    SandboxUnavailable,
    WorkerDiedError,
)
from nooa.runtime.sandbox.guards import Capabilities, probe_capabilities
from nooa.runtime.sandbox.serialization import ResultDTO, dto_to_result, is_picklable
from nooa.runtime.sandbox.worker import worker_main

logger = logging.getLogger(__name__)

_CAPS_CACHE: Capabilities | None = None


def _capabilities() -> Capabilities:
    global _CAPS_CACHE
    if _CAPS_CACHE is None:
        _CAPS_CACHE = probe_capabilities()
    return _CAPS_CACHE


def check_enforceable(config: SandboxConfig, caps: Capabilities | None = None) -> list[str]:
    """Return the list of requested-but-unenforceable guardrails on this host."""
    caps = caps or _capabilities()
    missing: list[str] = []
    if not caps.linux:
        return ["sandbox requires Linux"]
    if config.filesystem and not caps.filesystem:
        missing.append("filesystem (Landlock unavailable)")
    if not config.network and not caps.network:
        missing.append("network isolation (seccomp unavailable)")
    if (config.max_memory_mb or config.max_cpu_seconds) and not caps.rlimit:
        missing.append("memory/cpu caps (rlimit unavailable)")
    return missing


class LocalProcessSandboxProvider(BaseSandboxProvider):
    """Executes CodeAct cells in a local guarded worker process."""

    def __init__(
        self,
        config: SandboxConfig,
        agent: Any = None,
        *,
        cell_timeout: float | None = None,
        framework_builtins: dict[str, Any] | None = None,
        restrictions: Any = None,
    ) -> None:
        super().__init__(config)
        self._agent = agent
        self._cell_timeout = cell_timeout
        self._framework_builtins = framework_builtins or {}
        self._restrictions = restrictions
        self._spec: ResolvedSpec = resolve_spec(config)

        caps = _capabilities()
        missing = check_enforceable(config, caps)
        if missing and config.require:
            raise SandboxUnavailable(
                "Cannot enforce requested sandbox guardrails: "
                + "; ".join(missing)
                + ". Set sandbox.require=False to run without them (unsafe), or "
                "disable the affected guardrail."
            )
        self._degraded = missing
        if missing:
            self._spec = self._prune_unenforceable(self._spec, caps)
            logger.warning(
                "sandbox running with UNENFORCED guardrails (require=False): %s",
                "; ".join(missing),
            )

        self._ctx = mp.get_context(config.start_method)
        self._proc: mp.process.BaseProcess | None = None
        self._conn: Connection | None = None
        self._lock = asyncio.Lock()
        self._req_id = 0
        self._closed = False
        self._disabled = False

        if config.filesystem and config.workspace:
            try:
                os.makedirs(config.workspace, exist_ok=True)
            except OSError as exc:
                raise SandboxUnavailable(
                    f"sandbox workspace {config.workspace!r} could not be created: {exc}"
                ) from exc

    @property
    def provider_name(self) -> str:
        return "local"

    @staticmethod
    def _prune_unenforceable(spec: ResolvedSpec, caps: Capabilities) -> ResolvedSpec:
        from dataclasses import replace

        return replace(
            spec,
            filesystem=spec.filesystem and caps.filesystem,
            landlock_rules=spec.landlock_rules if caps.filesystem else (),
            block_network=spec.block_network and caps.network,
            max_memory_mb=spec.max_memory_mb if caps.rlimit else 0,
            max_cpu_seconds=spec.max_cpu_seconds if caps.rlimit else 0,
        )

    @property
    def degraded_guards(self) -> list[str]:
        return list(self._degraded)

    async def initialize(self) -> None:
        await self._ensure_worker()

    def _start_worker(self) -> None:
        parent_conn, child_conn = self._ctx.Pipe(duplex=True)
        init = {
            "agent": self._agent,
            "framework_builtins": self._framework_builtins,
            "restrictions": self._restrictions,
            "spec": self._spec,
        }
        proc = self._ctx.Process(
            target=worker_main, args=(child_conn, init), daemon=True, name="nooa-sandbox-worker"
        )
        proc.start()
        child_conn.close()
        self._conn = parent_conn
        self._proc = proc

    def _detach_worker(self) -> Any:
        proc, conn = self._proc, self._conn
        self._proc = self._conn = None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return proc

    def _terminate_worker(self) -> None:
        proc = self._detach_worker()
        if proc is None:
            return
        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=1.0)

    async def _aterminate_worker(self) -> None:
        proc = self._detach_worker()
        if proc is None:
            return
        if proc.is_alive():
            proc.terminate()
            await asyncio.to_thread(proc.join, 1.0)
        if proc.is_alive():
            proc.kill()
            await asyncio.to_thread(proc.join, 1.0)

    async def _restart_worker(self) -> None:
        await self._aterminate_worker()
        if self.config.recovery == "disabled":
            self._disabled = True
            return
        self._start_worker()

    async def _ensure_worker(self) -> None:
        if self._disabled:
            raise WorkerDiedError(
                "sandbox worker was killed and recovery='disabled'; no further cells can run"
            )
        if self._proc is None or not self._proc.is_alive():
            await self._aterminate_worker()
            self._start_worker()

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

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
        if agent is not None:
            self._agent = agent
        if cell_timeout is not None:
            self._cell_timeout = cell_timeout
        if framework_builtins is not None:
            self._framework_builtins = framework_builtins
        if restrictions is not None:
            self._restrictions = restrictions

        if self._closed:
            raise WorkerDiedError("sandbox executor is closed")
        async with self._lock:
            if self._disabled:
                return self._synth_error(
                    WorkerDiedError(
                        "a prior cell was killed and recovery='disabled'; the sandbox "
                        "worker will not restart, so no further cells can run"
                    )
                )
            await self._ensure_worker()
            assert self._conn is not None
            req_id = self._next_id()
            try:
                self._conn.send(
                    {"op": "run", "id": req_id, "code": code, "execution_count": execution_count}
                )
            except (BrokenPipeError, OSError) as exc:
                await self._restart_worker()
                return self._synth_error(self._classify_worker_death(WorkerDiedError(str(exc))))
            deadline = None
            if self._cell_timeout:
                deadline = self._cell_timeout + self.config.timeout_grace_s
            loop = asyncio.get_running_loop()
            try:
                response = await asyncio.to_thread(self._recv_until_result, req_id, deadline, loop)
            except CellTimeoutError as exc:
                await self._restart_worker()
                return self._synth_error(exc)
            except WorkerDiedError as exc:
                err = self._classify_worker_death(exc)
                await self._restart_worker()
                return self._synth_error(err)
            dto: ResultDTO = response["result"]
            return dto_to_result(dto, signal_factory=self._signal_factory)

    def _recv_until_result(
        self, req_id: int, deadline: float | None, loop: asyncio.AbstractEventLoop
    ) -> dict[str, Any]:
        end = time.monotonic() + deadline if deadline else None
        poll = self.config.rss_poll_s if self.config.rss_poll_s > 0 else 0.1
        while True:
            conn = self._conn
            if conn is None:
                raise WorkerDiedError("sandbox worker connection lost")
            if end is not None:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise CellTimeoutError(
                        f"cell exceeded its {self._cell_timeout}s deadline and was killed"
                    )
                wait = min(remaining, poll)
            else:
                wait = poll
            if not conn.poll(max(0.01, wait)):
                if self._proc is None or not self._proc.is_alive():
                    raise WorkerDiedError("sandbox worker exited unexpectedly")
                continue
            try:
                msg = conn.recv()
            except (EOFError, OSError) as exc:
                raise WorkerDiedError("sandbox worker pipe closed") from exc
            mtype = msg.get("type")
            if mtype == "tool_call":
                broker_started = time.monotonic()
                self._service_tool_call(msg, loop)
                if end is not None:
                    end += time.monotonic() - broker_started
                continue
            if mtype == "fatal":
                raise WorkerDiedError(f"sandbox worker fatal: {msg.get('error')}")
            if mtype == "response" and msg.get("id") == req_id:
                return msg

    def _service_tool_call(self, msg: dict[str, Any], loop: asyncio.AbstractEventLoop) -> None:
        future = asyncio.run_coroutine_threadsafe(self._dispatch_tool_call(msg), loop)
        broker_timeout = self.config.broker_timeout_s or None
        try:
            response = future.result(timeout=broker_timeout)
        except futures.TimeoutError:
            future.cancel()
            raise CellTimeoutError(
                f"brokered self.* call exceeded broker_timeout_s={broker_timeout}s"
            ) from None
        response["type"] = "tool_result"
        response["tool_call_id"] = msg.get("tool_call_id")
        conn = self._conn
        if conn is not None:
            try:
                conn.send(response)
            except (BrokenPipeError, OSError) as exc:
                raise WorkerDiedError("sandbox worker pipe closed during tool call") from exc

    def _walk_path(self, path: list[str]) -> Any:
        obj: Any = self._agent
        for part in path:
            obj = getattr(obj, part)
        return obj

    async def _dispatch_tool_call(self, msg: dict[str, Any]) -> dict[str, Any]:
        from nooa.events import ExecutionSignal

        path = msg.get("path") or []
        display = ".".join(path)
        kind = msg.get("kind")
        try:
            if kind == "setattr":
                obj = self._walk_path(path[:-1])
                setattr(obj, path[-1], msg.get("value"))
                return {"ok": True, "result": None}
            if kind == "iter":
                items = list(self._walk_path(path))
                if not is_picklable(items):
                    return {
                        "ok": False,
                        "error_type": "CellSerializationError",
                        "error": (
                            f"iterating self.{display} produced non-picklable items that "
                            "cannot cross the sandbox boundary."
                        ),
                    }
                return {"ok": True, "result": items}
            target = self._walk_path(path)
            if kind == "attr":
                if is_picklable(target):
                    return {"ok": True, "result": target}
                return {"ok": True, "result": None, "proxy": True}
            value = target(*msg.get("args", ()), **msg.get("kwargs", {}))
            was_async = asyncio.iscoroutine(value) or asyncio.isfuture(value)
            if was_async:
                value = await value
            if not is_picklable(value):
                return {
                    "ok": False,
                    "error_type": "CellSerializationError",
                    "error": (
                        f"self.{display} returned a {type(value).__name__!r} that is not "
                        "picklable and cannot cross the sandbox boundary. Return a "
                        "picklable summary instead."
                    ),
                }
            return {"ok": True, "result": value, "was_async": was_async}
        except ExecutionSignal as sig:
            payload = getattr(sig, "result", None)
            return {
                "ok": False,
                "error_type": "ExecutionSignal",
                "error": str(sig),
                "signal_result": payload if is_picklable(payload) else None,
            }
        except CellSerializationError as exc:
            return {"ok": False, "error_type": "CellSerializationError", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}

    def _classify_worker_death(self, exc: WorkerDiedError) -> Exception:
        proc = self._proc
        code = getattr(proc, "exitcode", None)
        if code == -signal.SIGXCPU:
            return CellTimeoutError("cell exceeded its CPU-time limit and was killed")
        if code == -signal.SIGKILL:
            return CellMemoryError(
                "worker was killed (out-of-memory or resource limit). "
                "Reduce the cell's memory use or raise max_memory_mb."
            )
        return exc

    _RESET_NOTE = (
        " The worker was restarted, so variables/functions defined in earlier "
        "cells are gone — recompute any state you need."
    )

    def _synth_error(self, error: Exception) -> ExecutionResult:
        if isinstance(error, CellTimeoutError | CellMemoryError) and not self._disabled:
            error = type(error)(str(error) + self._RESET_NOTE)
        return ExecutionResult(stdout="", stderr="", error=error, defined_methods={})

    @staticmethod
    def _signal_factory(payload: Any) -> Any:
        from nooa.strategies.codeact import _ReturnResultSignal

        return _ReturnResultSignal(result=payload)

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        async with self._lock:
            conn = self._conn
            if conn is not None and self._proc is not None and self._proc.is_alive():
                try:
                    conn.send({"op": "shutdown", "id": self._next_id()})
                    await asyncio.to_thread(self._proc.join, 0.5)
                except Exception:
                    pass
            await self._aterminate_worker()

    def close_sync(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._terminate_worker()
