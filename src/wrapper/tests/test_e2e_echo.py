#!/usr/bin/env python3
"""
E2E Test: MCP Protocol with tools/list and tools/call

Tests server initialization, tools/list (triggers /init API), and tools/call.
"""

import asyncio
import sys
from pathlib import Path

from test_e2e_echo_base import run_test


async def run_main_py_test():
    test_dir = Path(__file__).parent
    wrapper_dir = test_dir.parent
    src_dir = wrapper_dir.parent
    repo_root = src_dir.parent

    command = [
        "uvx",
        "--from",
        str(repo_root),
        "defenter-proxy",
    ]
    await run_test(command, "main.py")


if __name__ == "__main__":
    try:
        asyncio.run(run_main_py_test())
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
