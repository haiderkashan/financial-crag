import ast
import concurrent.futures
from io import StringIO
import math
import sys
from typing import Any

SAFE_BUILTINS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "float": float,
    "int": int,
    "str": str,
    "print": print,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "bool": bool,
}

SAFE_GLOBALS = {
    "__builtins__": SAFE_BUILTINS,
    "math": math,
}

FORBIDDEN_CALLS = {"eval", "exec", "open", "compile", "__import__"}


def _validate_ast_security(code: str) -> None:
    """Parse and inspect the AST to ensure code safety.

    Raises:
        ValueError: If imports, dunder attribute access, or forbidden calls are detected.
    """
    tree = ast.parse(code)
    for node in ast.walk(tree):
        # Disallow imports
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise ValueError("Imports are forbidden in arithmetic execution")

        # Disallow dunder / private attribute access (e.g., __class__, __subclasses__)
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError(
                f"Access to private/dunder attribute '{node.attr}' is forbidden"
            )

        # Disallow dangerous execution builtins
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_CALLS:
            raise ValueError(f"Call to '{node.id}' is forbidden")


def _execute_in_sandbox(code: str) -> str:
    """Executes validated code in restricted scope and captures stdout."""
    buffer = StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buffer
        local_scope: dict[str, Any] = {}
        exec(code, SAFE_GLOBALS, local_scope)
        output = buffer.getvalue().strip()
        if not output:
            return (
                "Code executed successfully with no printed output. "
                "Use print() to display calculated values."
            )
        return output
    finally:
        sys.stdout = old_stdout


def execute_sandboxed_python(code: str, timeout_seconds: int = 10) -> str:
    """Execute Python code in a restricted execution sandbox with strict timeout.

    Security guarantees:
    1. Rejects imports (ast.Import, ast.ImportFrom).
    2. Rejects dunder attribute lookups (__class__, etc.).
    3. Rejects eval/exec/open.
    4. Restricts execution to safe mathematical builtins and the math module.
    5. Enforces execution timeout via thread pool.

    Args:
        code: The Python script string to execute.
        timeout_seconds: Maximum allowed runtime in seconds (default: 10).

    Returns:
        The printed stdout string or formatted execution error.

    Raises:
        ValueError: If AST security validation fails.
    """
    # 1. Strict AST validation
    _validate_ast_security(code)

    # 2. Execute with cross-platform timeout
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_execute_in_sandbox, code)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError:
            return (
                f"Execution Error: Timeout: Calculation exceeded {timeout_seconds} "
                "seconds timeout."
            )
        except Exception as exc:
            return f"Execution Error: {type(exc).__name__}: {str(exc)}"
