import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.agent.llm import get_llm
from backend.app.agent.state import AgentState
from backend.app.tools.python_repl import execute_sandboxed_python

MATH_GENERATION_SYSTEM_PROMPT = """You are a financial calculation engine. Given the analyst's question and the financial context, write a self-contained Python script that performs the exact arithmetic required.

RULES:
1. Extract exact numbers from the provided financial context.
2. Use only standard Python arithmetic (+, -, *, /, **, %).
3. The `math` module is pre-loaded (math.log, math.sqrt, etc.). DO NOT write `import math`.
4. DO NOT import any modules (all imports are strictly forbidden).
5. Always use print() to output the calculated results with clear descriptive labels.
6. Format currency with commas: print(f"YoY Revenue Change: ${change:,.2f} million")
7. Format percentages to 2 decimal places: print(f"YoY Growth Rate: {rate:.2f}%")
8. Return ONLY executable Python code."""


def clean_python_code(raw_code: str) -> str:
    """Strip markdown code block fences (```python ... ```) from LLM output."""
    text = raw_code.strip()

    # Match code enclosed in standard markdown code blocks
    block_pattern = r"^```(?:python)?\s*\n?(.*?)\n?```$"
    match = re.search(block_pattern, text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Extract all code blocks if surrounded by conversational filler
    blocks = re.findall(
        r"```(?:python)?\s*\n?(.*?)\n?```", text, flags=re.DOTALL | re.IGNORECASE
    )
    if blocks:
        return "\n\n".join(b.strip() for b in blocks)

    return text


async def math_repl_node(state: AgentState) -> dict[str, Any]:
    """Generate Python calculation script from context and execute in sandbox.

    1. Combines available context (filtered SEC chunks + Tavily web results).
    2. Prompts LLM to generate precise arithmetic computation code.
    3. Strips markdown backticks (```python).
    4. Executes code inside restricted AST-validated Python sandbox.
    5. Returns math_code, math_result, and appends status to steps.
    """
    question = (state.get("question") or "").strip()

    # Build comprehensive context from SEC chunks and web search
    context_parts: list[str] = []
    sec_chunks = state.get("filtered_documents") or state.get("documents") or []
    if sec_chunks:
        sec_text = "\n\n---\n\n".join(
            [c.get("content", "").strip() for c in sec_chunks]
        )
        context_parts.append(f"SEC 10-K Chunks:\n{sec_text}")

    if state.get("web_results"):
        context_parts.append(f"Web Search Results:\n{state['web_results']}")

    combined_context = (
        "\n\n".join(context_parts) if context_parts else "No context available."
    )

    user_content = (
        f"Analyst Question: {question}\n\n"
        f"Financial Context:\n{combined_context}"
    )

    llm = get_llm(temperature=0.0)

    try:
        messages = [
            SystemMessage(content=MATH_GENERATION_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        response = await llm.ainvoke(messages)
        raw_code = str(response.content)
    except Exception as exc:
        raw_code = f"# Error generating math code: {exc}"

    clean_code = clean_python_code(raw_code)

    # Execute in sandbox
    try:
        math_result = execute_sandboxed_python(clean_code)
    except Exception as exc:
        math_result = f"Execution Error: {type(exc).__name__}: {str(exc)}"

    existing_steps = list(state.get("steps") or [])
    first_line = math_result.replace("\n", " ")[:80]
    step_log = f"[Math REPL] Executed Python script — Result: {first_line}..."

    return {
        "math_code": clean_code,
        "math_result": math_result,
        "steps": existing_steps + [step_log],
    }


def route_after_tool_decision(state: AgentState) -> str:
    """Conditional edge router following tool decision.

    Routes to 'math_repl' if math_needed is True.
    Otherwise proceeds directly to 'generate'.
    """
    if state.get("math_needed", False):
        return "math_repl"
    return "generate"
