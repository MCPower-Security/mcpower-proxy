from typing import Dict, Any


def assert_failure(result: Dict[str, Any], message: str = "Handler should fail"):
    """Assert that the handler failed (non-zero exit code)"""
    if result['returncode'] == 0:
        raise AssertionError(
            f"{message}\n"
            f"Stdout: {result['stdout']}\n"
            f"Stderr: {result['stderr']}"
        )


def assert_json_output(result: Dict[str, Any], message: str = "Output should be valid JSON"):
    """Assert that the handler produced valid JSON output"""
    if result['output'] is None:
        raise AssertionError(
            f"{message}\n"
            f"Stdout: {result['stdout']}"
        )
    return result['output']
