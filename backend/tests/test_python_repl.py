import pytest

from backend.app.tools.python_repl import execute_sandboxed_python


def test_python_repl_arithmetic():
    """Verify basic financial arithmetic and formatting in sandboxed execution."""
    code = """
rev_2023 = 383_285
rev_2022 = 394_328
change = rev_2023 - rev_2022
growth = (change / rev_2022) * 100
print(f"Change: ${change:,.0f}M")
print(f"Growth: {growth:.2f}%")
"""
    result = execute_sandboxed_python(code)
    assert "Change: $-11,043M" in result
    assert "Growth: -2.80%" in result


def test_python_repl_math_module():
    """Verify pre-loaded math module functions work without explicit import."""
    code = """
val = math.sqrt(256)
log_val = round(math.log10(1000), 2)
print(f"Sqrt: {val}, Log: {log_val}")
"""
    result = execute_sandboxed_python(code)
    assert "Sqrt: 16.0, Log: 3.0" in result


def test_python_repl_security():
    """CRITICAL SECURITY TEST: Verify AST parser blocks all dangerous constructs."""
    # 1. Block standard import
    with pytest.raises(ValueError, match="Imports are forbidden"):
        execute_sandboxed_python("import os")

    # 2. Block from-import
    with pytest.raises(ValueError, match="Imports are forbidden"):
        execute_sandboxed_python("from sys import exit")

    # 3. Block dunder attribute access (sandbox escape attempt)
    with pytest.raises(ValueError, match="private/dunder attribute"):
        execute_sandboxed_python("x = ().__class__.__bases__[0]")

    # 4. Block dangerous builtins
    with pytest.raises(ValueError, match="forbidden"):
        execute_sandboxed_python("open('/etc/passwd', 'r')")

    with pytest.raises(ValueError, match="forbidden"):
        execute_sandboxed_python("eval('2 + 2')")

    with pytest.raises(ValueError, match="forbidden"):
        execute_sandboxed_python("exec('print(1)')")

    with pytest.raises(ValueError, match="forbidden"):
        execute_sandboxed_python("__import__('os')")


def test_python_repl_no_output():
    """Verify message when executed code produces no stdout."""
    code = "x = 42"
    result = execute_sandboxed_python(code)
    assert "no printed output" in result.lower()
    assert "print()" in result


def test_python_repl_runtime_error():
    """Verify runtime errors are captured into formatted error string."""
    code = "print(10 / 0)"
    result = execute_sandboxed_python(code)
    assert "Execution Error: ZeroDivisionError" in result
