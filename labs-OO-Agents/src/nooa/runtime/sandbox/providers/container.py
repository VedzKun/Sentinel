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
            if isinstance(msg, EOFError):
                raise msg
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

    def __init__(
        self,
        config: Any,
        agent: Any = None,
        *,
        cell_timeout: float | None = None,
        framework_builtins: dict[str, Any] | None = None,
        restrictions: Any = None,
    ) -> None:
        from nooa.runtime.sandbox.config import resolve_spec
        from nooa.runtime.sandbox.base import BaseSandboxProvider
        import asyncio
        import tempfile
        import subprocess
        
        # Initialize BaseSandboxProvider directly to bypass LocalProcessSandboxProvider's
        # Unix-specific 'resource' module capability checks (Docker handles capabilities)
        BaseSandboxProvider.__init__(self, config)
        self._agent = agent
        self.cell_timeout = cell_timeout
        self._framework_builtins = framework_builtins or {}
        self._restrictions = restrictions
        self._spec = resolve_spec(config)
        self._degraded = []
        
        self._proc = None
        self._conn = None
        self._lock = asyncio.Lock()
        self._req_id = 0
        self._closed = False
        self._disabled = False

        self._container_id: str | None = None
        self._ipc_dir = tempfile.mkdtemp(prefix="nooa_ipc_")
        
        # We start the worker immediately
        self._start_worker()
        
        import atexit
        atexit.register(self._cleanup_container)

    @property
    def provider_name(self) -> str:
        return "container"
        
    def _cleanup_container(self):
        """Forcefully remove the container if it's still running."""
        import subprocess
        import os
        if hasattr(self, "_container_id") and self._container_id:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self._container_id],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass
        import shutil
        if os.path.exists(self._ipc_dir):
            try:
                shutil.rmtree(self._ipc_dir)
            except Exception:
                pass

    def _start_worker(self) -> None:
        """Launch the docker container running the worker."""
        import os
        import subprocess
        # Use FileConnection for robust IPC
        from nooa.runtime.sandbox.worker import FileConnection
        conn = FileConnection(self._ipc_dir, is_host=True)

        cmd = [
            "docker", "run", "-d", "--rm",
            # We add a stop timeout so the daemon aggressively kills it if it gets stuck
            "--stop-timeout", "1"
        ]
        
        # 1. Network isolation
        if self._spec.block_network:
            cmd.append("--network=none")
            
        # 2. Filesystem controls
        if self.config.filesystem:
            cmd.append("--read-only")
            cmd.extend(["--tmpfs", "/tmp:rw,size=64m,mode=1777"])
            # Mount the workspace if provided
            if self.config.workspace:
                workspace_abs = os.path.abspath(self.config.workspace)
                # Map to /workspace in Linux container instead of absolute host path to avoid colon conflicts
                cmd.extend(["-v", f"{workspace_abs}:/workspace:rw"])
            # Mount allowed paths
            for path in self.config.allow:
                path_abs = os.path.abspath(path)
                # For arbitrary allowed paths, mapping them exactly is hard cross-platform.
                # Let's map them to /allowed/<basename> as a workaround for now, or just /<basename>
                basename = os.path.basename(path_abs)
                cmd.extend(["-v", f"{path_abs}:/{basename}:ro"])
                
        # Mount the IPC directory
        ipc_abs = os.path.abspath(self._ipc_dir)
            
        cmd.extend(["-v", f"{ipc_abs}:/ipc:rw"])
            
        # 3. Resource Constraints
        if self._spec.max_memory_mb:
            cmd.append(f"--memory={self._spec.max_memory_mb}m")
            cmd.append(f"--memory-swap={self._spec.max_memory_mb}m")
        # Prevent fork bombs
        cmd.append("--pids-limit=64")
        # CPU limit
        cmd.append("--cpus=1.0")
        
        # 4. Syscall Hardening
        cmd.append("--security-opt=no-new-privileges")
        cmd.append("--cap-drop=ALL")
        
        # Image and entrypoint
        cmd.append("nooa-sandbox-worker")
        
        # Launch the docker container in detached mode to get the container ID
        try:
            proc_id = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            self._container_id = proc_id.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to start Docker container: {e.stderr}")
            
        # We need a dummy process object to satisfy LocalProcessSandboxProvider
        class DummyProc:
            def __init__(self, container_id):
                self.container_id = container_id
            def is_alive(self):
                if not self.container_id:
                    return False
                try:
                    res = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", self.container_id], capture_output=True, text=True)
                    return res.stdout.strip() == "true"
                except Exception:
                    return False
            def poll(self):
                if self.is_alive():
                    return None
                try:
                    res = subprocess.run(["docker", "inspect", "-f", "{{.State.ExitCode}}", self.container_id], capture_output=True, text=True)
                    code = res.stdout.strip()
                    return int(code) if code.isdigit() else 1
                except Exception:
                    return 1
            def terminate(self):
                pass
            def kill(self):
                pass
            def wait(self, timeout=None):
                pass
                
        wrapped_proc = DummyProc(self._container_id)
        
        from dataclasses import replace
        from nooa.runtime.sandbox.config import LandlockRule
        
        container_spec = self._spec
        if self._spec and getattr(self.config, "workspace", None):
            # Create container-side paths for landlock rules
            new_rules = []
            for rule in self._spec.landlock_rules:
                if rule.path == os.path.abspath(self.config.workspace):
                    new_rules.append(replace(rule, path="/workspace"))
                else:
                    new_rules.append(replace(rule, path=f"/{os.path.basename(rule.path)}"))
            # Allow IPC directory
            new_rules.append(LandlockRule(path="/ipc", write=True, required=True))
            container_spec = replace(self._spec, landlock_rules=tuple(new_rules))

        # Initialize the worker process exactly like local does
        init = {
            "agent": self._agent,
            "framework_builtins": getattr(self, "_framework_builtins", {}),
            "restrictions": getattr(self, "_restrictions", None),
            "spec": container_spec
        }
        
        # Write the init payload to IPC using our connection
        conn.send(init)
        
        self._proc = wrapped_proc
        self._conn = conn

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
