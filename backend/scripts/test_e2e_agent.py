import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows UTF-8 stdout safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.agent.graph import crag_agent
from backend.app.agent.state import AgentState
from backend.app.core.config import settings


async def run_e2e(
    query: str,
    ticker: str | None = "AAPL",
    fiscal_year: int | None = 2023,
    groq_api_key: str | None = None,
) -> None:
    print("=" * 70)
    print("FINANCIAL CRAG AGENT: END-TO-END VERIFICATION RUN")
    print("=" * 70)
    print(f"Query:       {query}")
    print(f"Target:      Ticker={ticker or 'ALL'}, Fiscal Year={fiscal_year or 'ALL'}")
    print(f"LLM:         {settings.LLM_PROVIDER} ({settings.LLM_MODEL_NAME})")

    resolved_key = (
        groq_api_key
        or settings.GROQ_API_KEY
        or os.environ.get("GROQ_API_KEY", "")
    )

    if not resolved_key:
        print("\n[!] Error: GROQ_API_KEY is not configured.")
        print("    Please set GROQ_API_KEY in backend/.env or run:")
        print("    python backend/scripts/test_e2e_agent.py --groq-key <gsk_...>")
        return

    # Ensure key is available to get_llm
    os.environ["GROQ_API_KEY"] = resolved_key
    settings.GROQ_API_KEY = resolved_key

    initial_state: AgentState = {
        "question": query,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
        "documents": [],
        "filtered_documents": [],
        "web_search_needed": False,
        "grade_explanations": [],
        "web_results": None,
        "search_query": None,
        "math_needed": False,
        "math_code": None,
        "math_result": None,
        "generation": None,
        "steps": [],
    }

    print("\n" + "-" * 70)
    print("THOUGHT INSPECTION STEPS (REAL-TIME STATE MACHINE LOG)")
    print("-" * 70)

    start_time = time.time()
    final_generation = None
    math_code_used = None
    math_result_used = None

    async for event in crag_agent.astream(initial_state, stream_mode="updates"):
        for node_name, state_update in event.items():
            # Print state step transition
            if "steps" in state_update and state_update["steps"]:
                latest_step = state_update["steps"][-1]
                print(f">> [{node_name.upper()}] {latest_step}")

            # Capture math code if executed
            if "math_code" in state_update and state_update["math_code"]:
                math_code_used = state_update["math_code"]

            if "math_result" in state_update and state_update["math_result"]:
                math_result_used = state_update["math_result"]

            # Capture final answer
            if "generation" in state_update and state_update["generation"]:
                final_generation = state_update["generation"]

    elapsed = time.time() - start_time
    print(f"\n[Execution Completed in {elapsed:.2f}s]")

    if math_code_used and math_result_used:
        print("\n" + "-" * 70)
        print("SANDBOX ARITHMETIC EXECUTION")
        print("-" * 70)
        print(f"Generated Python Code:\n{math_code_used.strip()}\n")
        print(f"Execution Output:\n{math_result_used.strip()}")

    print("\n" + "=" * 70)
    print("FINAL GENERATED RESPONSE (SYNTHESIZED MARKDOWN)")
    print("=" * 70)
    if final_generation:
        print(final_generation)
    else:
        print("[!] No generation produced.")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end CRAG agent verification script against live Supabase and Groq API."
    )
    parser.add_argument(
        "--query",
        type=str,
        default="What was Apple's total net sales in 2023 and how did it change from 2022?",
        help="Analyst question to evaluate",
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default="AAPL",
        help="Target company ticker (default: AAPL)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2023,
        help="Target fiscal year (default: 2023)",
    )
    parser.add_argument(
        "--groq-key",
        type=str,
        default=None,
        help="Optional Groq API key override",
    )
    args = parser.parse_args()

    asyncio.run(
        run_e2e(
            query=args.query,
            ticker=args.ticker,
            fiscal_year=args.year,
            groq_api_key=args.groq_key,
        )
    )


if __name__ == "__main__":
    main()
