#!/usr/bin/env python3
"""
E2E Test: MCP Protocol with tools/list and tools/call (executable)

Tests the built executable file instead of main.py.
Usage: python test_e2e_echo_executable.py [executable_name]
"""

import asyncio
import sys
from pathlib import Path

from test_e2e_echo_base import run_test


async def run_executable_test(executable_name: str):
    test_dir = Path(__file__).parent
    src_dir = test_dir.parent
    project_root = src_dir.parent
    executable = project_root / "targets" / "vsc-extension" / "executables" / executable_name
    
    if not executable.exists():
        raise Exception(f"Executable not found: {executable}")
    
    command = [str(executable)]
    await run_test(command, f"executable ({executable_name})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_e2e_echo_executable.py <executable_name>")
        print("Examples:")
        print("  python test_e2e_echo_executable.py mcpower-macos")
        print("  python test_e2e_echo_executable.py mcpower-windows.exe")
        print("  python test_e2e_echo_executable.py mcpower-linux")
        sys.exit(1)
    
    executable_name = sys.argv[1]
    
    try:
        asyncio.run(run_executable_test(executable_name))
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

