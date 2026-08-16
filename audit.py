#!/usr/bin/env python3
"""
Entry point for nooa-audit from project root.
"""
import os
import sys

# Forward directly to my_agent/audit.py
agent_audit_path = os.path.join(os.path.dirname(__file__), "my_agent", "audit.py")

if __name__ == "__main__":
    with open(agent_audit_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, agent_audit_path, "exec"), globals())
