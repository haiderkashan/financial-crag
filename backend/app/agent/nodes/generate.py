from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.app.agent.llm import get_llm
from backend.app.agent.state import AgentState

GENERATE_SYSTEM_PROMPT = """You are a senior financial analyst at a due diligence firm. Synthesize a comprehensive, data-driven answer using ONLY the provided context. You write for sophisticated financial professionals.

RESPONSE RULES:
1. CITE EXACT NUMBERS from the SEC 10-K context — never approximate or round unless the source data is already rounded.
2. If a Python calculation was performed, present the EXACT computed result with the formula used.
3. If web search results supplement the SEC filing data, clearly attribute them: "According to [source], ..."
4. Structure your response with clear Markdown:
   - Use ## headers for major sections
   - Use tables (pipe syntax) for comparative data
   - Use **bold** for key metrics
   - Use `code blocks` for specific values
5. If the available data is insufficient to fully answer the question, explicitly state what information is missing rather than speculating.
6. NEVER fabricate data. If a number is not in the context, explicitly say so.
7. Be direct, authoritative, and concise (under 400 words). Conclude cleanly without dangling sentences."""


async def generate_node(state: AgentState) -> dict[str, Any]:
    """Synthesize final analytical response from SEC documents, web search, and math results.

    Assembles available context securely, prompts the LLM without intra-node token streaming,
    and returns the complete generated markdown content alongside observability steps.
    """
    question = (state.get("question") or "").strip()

    # 1. Format SEC 10-K context chunks
    chunks = state.get("filtered_documents") or state.get("documents") or []
    sec_sections: list[str] = []
    for c in chunks:
        ticker = c.get("ticker", "N/A")
        year = c.get("fiscal_year", "")
        section = c.get("section_title") or "General"
        meta_header = f"Document: {ticker} {year} 10-K | Section: {section}"
        sec_sections.append(f"[{meta_header}]\n{c.get('content', '').strip()}")

    sec_context = (
        "\n\n---\n\n".join(sec_sections)
        if sec_sections
        else "No SEC filing passages available."
    )

    # 2. Format supplemental web results if available
    web_results = state.get("web_results")
    web_section = (
        f"\n\nSupplemental Web Search Results:\n{web_results}"
        if web_results
        else ""
    )

    # 3. Format executed math computation if available
    math_result = state.get("math_result")
    math_code = state.get("math_code")
    math_section = ""
    if math_result:
        code_block = f"```python\n{math_code.strip()}\n```" if math_code else "N/A"
        math_section = (
            f"\n\nExecuted Arithmetic Computation:\n"
            f"Code Executed:\n{code_block}\n\n"
            f"Computation Output:\n{math_result.strip()}"
        )

    # 4. Describe assembled sources
    sources: list[str] = []
    if sec_sections:
        sources.append("Audited SEC 10-K Filings")
    if web_results:
        sources.append("Supplemental Web Search (Tavily)")
    if math_result:
        sources.append("Deterministic Python Calculation (Sandbox)")
    sources_description = " + ".join(sources) if sources else "Direct Analytical Knowledge"

    user_content = (
        f"Available Context Sources: {sources_description}\n\n"
        f"SEC 10-K Context:\n{sec_context}"
        f"{web_section}"
        f"{math_section}\n\n"
        f"Analyst Question: {question}"
    )

    llm = get_llm(temperature=0.0, max_tokens=800)

    try:
        messages = [
            SystemMessage(content=GENERATE_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
        response = await llm.ainvoke(messages)
        generation_text = str(response.content)
    except Exception as exc:
        generation_text = (
            f"An error occurred during final response generation: {type(exc).__name__}: {str(exc)}"
        )

    existing_steps = list(state.get("steps") or [])
    step_log = (
        f"[Generate] Synthesized response ({len(generation_text)} chars) from {sources_description}."
    )

    return {
        "generation": generation_text,
        "steps": existing_steps + [step_log],
    }
