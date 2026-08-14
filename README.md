# Sentinel

Sentinel is an agentic AI repository featuring **NVIDIA-labs Object Oriented Agents (NOOA)** framework alongside custom AI agent implementations and secure sandbox execution environments.

---

## 🌟 Overview

Sentinel provides a robust infrastructure for building, running, and managing AI agents:
- **`labs-OO-Agents/`**: A model-agnostic, object-oriented framework (NOOA) for building reliable AI agents in Python with native sandbox isolation, custom tool registries, and execution control.
- **`my_agent/`**: Custom agent code and entrypoints utilizing the NOOA framework.

---

## 🔒 Container Sandbox Features

Sentinel includes runtime container sandbox execution (`labs-OO-Agents/src/nooa/runtime/sandbox/providers/container.py`) built for isolated worker execution with security hardening:

- **Network Isolation**: Restricts network calls using `--network=none` when `block_network` is enabled.
- **Filesystem Hardening**: Mounts root filesystems read-only (`--read-only`), mounts isolated ephemeral storage (`--tmpfs=/tmp`), and selectively mounts workspace paths.
- **Resource Limits**: Restricts memory (`--memory`), CPU usage (`--cpus`), and process limits (`--pids-limit`).
- **Syscall Hardening**: Drops all Linux capabilities (`--cap-drop=ALL`) and prevents privilege escalation (`--security-opt=no-new-privileges`).

---

## 🚀 Quick Start

### 1. Environment Setup

Ensure Python 3.10+ and Docker are installed.

```bash
# Navigate to the repo
cd Sentinel

# Install dependencies (using uv or pip)
cd labs-OO-Agents
uv sync
```

### 2. Running your Agent

Add your agent logic in `my_agent/main.py`:

```python
from nooa import Agent

class MySentinelAgent(Agent):
    """Custom Sentinel Agent."""
    pass
```

Run the entrypoint:

```bash
python my_agent/main.py
```

---

## 📁 Repository Structure

```
Sentinel/
├── README.md               # Main project overview & setup guide
├── my_agent/              # Custom agent implementations
│   └── main.py            # Entry point for custom agents
└── labs-OO-Agents/        # NOOA framework & sandbox runtime engine
    ├── src/nooa/          # Core NOOA agent abstractions & runtime providers
    ├── Dockerfile.sandbox  # Container sandbox worker image definition
    └── pyproject.toml     # Framework package configuration
```

---

## 📄 License

This project incorporates components under the Apache 2.0 License. Refer to `labs-OO-Agents/LICENSE` for details.