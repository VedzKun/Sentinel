# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Containerized Sandbox Provider interface for container/microVM execution."""

from __future__ import annotations

import logging
from typing import Any

from nooa.events import ExecutionResult
from nooa.runtime.sandbox.base import BaseSandboxProvider
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.errors import SandboxUnavailable

logger = logging.getLogger(__name__)


from nooa.runtime.sandbox.providers.local import LocalProcessSandboxProvider
from nooa.runtime.sandbox.errors import SandboxUnavailable, WorkerDiedError

logger = logging.getLogger(__name__)


class ParentStdioConnection:
    """A thread-based pipe reader to mimic multiprocessing.Connection over Popen stdio.
    This avoids select.select() limitations on Windows pipes."""

    def __init__(self, proc: Any):
        import queue
        import threading

        self._proc = proc
        self._in = proc.stdout
        self._out = proc.stdin
        self._lock = threading.Lock()
        self._q = queue.Queue()
        self._stop = False
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()
        self._buffered_msg = None

    def _reader(self) -> None:
        import pickle
        import struct

        try:
            while not self._stop:
                header = self._in.read(4)
                if not header or len(header) < 4:
                    break
                length = struct.unpack("!I", header)[0]
                payload = self._in.read(length)
                if len(payload) < length:
                    break
                self._q.put(pickle.loads(payload))
        except Exception:
            pass
        finally:
            self._q.put(EOFError())

    def send(self, obj: Any) -> None:
        import pickle
        import struct

        if not self._out:
            raise BrokenPipeError()
        payload = pickle.dumps(obj)
        header = struct.pack("!I", len(payload))
        with self._lock:
            try:
                self._out.write(header + payload)
                self._out.flush()
            except OSError as e:
                raise BrokenPipeError() from e

    def recv(self) -> Any:
        import queue

        if self._buffered_msg is not None:
            msg = self._buffered_msg
            self._buffered_msg = None
            return msg
        try:
            msg = self._q.get(timeout=0.1)
            if isinstance(msg, EOFError):
                raise msg
            return msg
        except queue.Empty:
            raise EOFError()

    def poll(self, timeout: float = 0.0) -> bool:
        import queue

        if self._buffered_msg is not None:
            return True
        try:
            msg = self._q.get(timeout=timeout)
            if isinstance(msg, EOFError):
                self._buffered_msg = msg
                return True
            self._buffered_msg = msg
            return True
        except queue.Empty:
            return False

    def close(self) -> None:
        self._stop = True
        try:
            if self._in:
                self._in.close()
            if self._out:
                self._out.close()
        except Exception:
            pass


class ContainerSandboxProvider(LocalProcessSandboxProvider):
    """Containerized sandbox provider executing cell code inside an isolated OCI container."""

    @property
    def provider_name(self) -> str:
        return "container"

    def _start_worker(self) -> None:
        import subprocess

        init = {
            "agent": self._agent,
            "framework_builtins": self._framework_builtins,
            "restrictions": self._restrictions,
            "spec": self._spec,
        }
        
        # Launch the docker container with interactive stdio
        try:
            proc = subprocess.Popen(
                ["docker", "run", "-i", "--rm", "nooa-sandbox-worker"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # Keep stderr clean from our pipe
            )
        except FileNotFoundError:
            raise SandboxUnavailable("Docker is not installed or not in PATH")
            
        conn = ParentStdioConnection(proc)
        
        # Send initialization payload over our custom stdio connection
        conn.send(init)

        self._conn = conn
        self._proc = proc

    def _detach_worker(self) -> Any:
        proc, conn = self._proc, getattr(self, "_conn", None)
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
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

    async def _aterminate_worker(self) -> None:
        import asyncio
        import subprocess

        proc = self._detach_worker()
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                await asyncio.to_thread(proc.wait, 1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                await asyncio.to_thread(proc.wait)

    def _classify_worker_death(self, exc: WorkerDiedError) -> Exception:
        from nooa.runtime.sandbox.errors import CellTimeoutError, CellMemoryError
        proc = self._proc
        if proc:
            code = proc.poll()
            if code == 137: # SIGKILL (often OOM)
                return CellMemoryError(
                    "worker was killed (out-of-memory or resource limit). "
                )
        return exc
