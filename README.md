# 🛡️ Sentinel

**Sentinel** is an enterprise-grade AI agent and secure codebase auditing platform powered by the **NVIDIA-labs Object Oriented Agents (NOOA)** framework. It provides isolated runtime sandboxing, deep AST codebase analysis, and an interactive Streamlit UI to safely audit and run AI agents on arbitrary codebases.

---

## 🌟 Key Features

- 🔒 **Multi-Layered Sandbox Isolation**:
  - **Network Isolation**: Strict blocking of outbound network/sockets (`--network=none` / seccomp).
  - **Filesystem Hardening**: Mounts root filesystems read-only (`--read-only`), restricts writes to ephemeral `/tmp` and designated workspace directories.
  - **Resource Containment**: Strict memory constraints (`--memory`), CPU usage throttles (`--cpus`), and process limits (`--pids-limit`) to prevent fork bombs and runaway executions.
  - **Syscall Hardening**: Drops all Linux capabilities (`--cap-drop=ALL`) and prevents privilege escalation (`--security-opt=no-new-privileges`).
  - **Dual Provider Support**: Native Docker **`container`** execution (Linux kernel-level isolation) and fallback **`local`** process execution.

- 🔍 **Automated Codebase Auditor (`nooa-audit`)**:
  - Automatically shallow-clones any public Git repository.
  - Detects Python source roots and executes in-sandbox AST parsing.
  - Generates comprehensive metrics: LOC count, class/function hierarchies, decorator frequency, and largest files.
  - Runs active adversarial breach simulations (root filesystem writes, raw socket creation, and HTTP data exfiltration) to verify containment.

- 🖥️ **Interactive Streamlit Web Dashboard**:
  - Intuitive web interface to audit any GitHub repository URL on demand.
  - Configurable memory limits (MB), timeouts (seconds), and sandbox execution providers (`container` / `local`).
  - Real-time live execution logs streamed directly into the dashboard.

- 🤖 **Object-Oriented AI Agents**:
  - Model-agnostic agent framework supporting event sourcing, serialized execution, tool registries, and context management.

---

## 📁 Repository Structure

```
Sentinel/
├── app.py                     # Streamlit Web UI Dashboard
├── audit.py                   # Root CLI entrypoint for codebase auditor
├── README.md                  # Project documentation
├── .gitignore                 # Git ignore rules
│
├── my_agent/                  # Custom Agent implementations & Benchmark Demos
│   ├── audit.py               # Core codebase auditor engine & breach tester
│   ├── data_analyst_demo.py   # Real-world dirty dataset cleaning agent demo
│   ├── fastapi_demo.py        # FastAPI deep AST traversal benchmark
│   ├── ultimate_stress_test.py# Django stress test under tight memory/CPU constraints
│   └── main.py                # Base agent entrypoint
│
└── labs-OO-Agents/            # NOOA Framework & Sandbox Runtime Engine
    ├── src/nooa/              # Core abstractions, runtime providers & session APIs
    ├── Dockerfile.sandbox     # Worker container image definition
    └── pyproject.toml         # Framework package configuration
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Docker Desktop** (Required for container sandbox provider)
- **Git**

### 2. Installation

Clone the repository and install the dependencies:

```bash
# Clone repository
git clone https://github.com/VedzKun/Sentinel.git
cd Sentinel

# Install NOOA framework and dependencies
cd labs-OO-Agents
uv sync
cd ..

# Install Streamlit
pip install streamlit
```

### 3. Build Docker Sandbox Worker Image (Optional, for Container Provider)

```bash
docker build -t nooa-sandbox-worker -f labs-OO-Agents/Dockerfile.sandbox labs-OO-Agents
```

---

## 🖥️ Running the Streamlit Web UI

Launch the interactive web dashboard with:

```bash
streamlit run app.py
```

Once started, open **`http://localhost:8501`** in your browser:
1. Enter any GitHub repository URL (e.g., `https://github.com/tiangolo/fastapi`).
2. Adjust memory limit, timeout, and choose the execution provider (**`container`** or **`local`**).
3. Click **Run Audit** to see real-time streaming analysis and security tests.

---

## 💻 Running via CLI

### Audit Any Repository

Audit any public repository using the root `audit.py` entrypoint:

```bash
# Basic audit
python audit.py https://github.com/psf/requests

# Custom memory limits, timeouts, and provider selection
python audit.py https://github.com/django/django --memory-mb 512 --timeout 120 --provider container

# Retain cloned repository after audit
python audit.py https://github.com/tiangolo/fastapi --keep-repo

# Clean up workspace temporary files & downloaded repositories
python audit.py --clean
```

### CLI Arguments

| Argument | Description | Default |
| :--- | :--- | :--- |
| `repo_url` | Git repository URL to clone and audit | *Required* |
| `--memory-mb` | Memory limit for the sandbox in MB | `256` |
| `--timeout` | Execution timeout in seconds | `60.0` |
| `--provider` | Execution sandbox provider (`container` or `local`) | `container` |
| `--keep-repo` | Do not delete the cloned repository after the audit | `False` |
| `--clean` | Remove all temporary test repositories and workspace caches | `False` |

---

## 🧪 Benchmark Demos

Run pre-configured scenario benchmarks:

```bash
# 1. Data Analyst Scenario (Messy CSV cleaning & data pipeline in sandbox)
python my_agent/data_analyst_demo.py

# 2. FastAPI Benchmark (AST Traversal & route extraction)
python my_agent/fastapi_demo.py

# 3. Ultimate Stress Test (Django codebase traversal with 128MB tight memory limit)
python my_agent/ultimate_stress_test.py
```

---

## 🛡️ Sandbox Security Architecture

The sandbox uses defense-in-depth isolation:

```
+-------------------------------------------------------------------+
|                        Host Environment                           |
|  +-------------------------------------------------------------+  |
|  |                       NOOA Runtime                          |  |
|  |   +-----------------------------------------------------+   |  |
|  |   |                  SandboxSession                     |   |  |
|  |   |  (Docker Container / Isolated Local Worker Process) |   |  |
|  |   |                                                     |   |  |
|  |   |   - Read-Only Root Filesystem                       |   |  |
|  |   |   - Restricted Workspace R/W Mount                  |   |  |
|  |   |   - Network Intercept: Sockets Blocked              |   |  |
|  |   |   - Dropped Capabilities & Non-Privileged Execution |   |  |
|  |   |   - Hard Memory & CPU Execution Deadlines           |   |  |
|  |   +-----------------------------------------------------+   |  |
|  +-------------------------------------------------------------+  |
+-------------------------------------------------------------------+
```

---

## 📄 License

This project is licensed under the Apache 2.0 License. Refer to `labs-OO-Agents/LICENSE` for full details.