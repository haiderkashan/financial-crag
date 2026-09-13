import argparse
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows UTF-8 stdout safety
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.app.agent import AgentState, get_llm
from backend.app.core.config import settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify LangChain Groq LLM integration and AgentState schema."
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Optional Groq API key override (defaults to GROQ_API_KEY in backend/.env)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("SUB-PHASE 3.1 VERIFICATION: AGENT FOUNDATION & LLM FACTORY")
    print("=" * 60)

    # 1. Verify AgentState schema
    print("\n[1/3] Verifying AgentState TypedDict schema...")
    expected_fields = [
        "question",
        "ticker",
        "fiscal_year",
        "documents",
        "filtered_documents",
        "web_search_needed",
        "grade_explanations",
        "web_results",
        "search_query",
        "math_needed",
        "math_code",
        "math_result",
        "generation",
        "steps",
    ]
    state_annotations = AgentState.__annotations__
    for field in expected_fields:
        assert field in state_annotations, f"Missing field in AgentState: {field}"
    print(f"  [OK] AgentState defined with {len(state_annotations)} typed fields.")
    print(f"  [OK] Observation 'steps' list field verified: {state_annotations.get('steps')}")

    # 2. Check Groq API Key
    print("\n[2/3] Resolving Groq credentials...")
    groq_key = args.api_key or settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY", "")

    if not groq_key:
        print("  [!] Warning: GROQ_API_KEY is not configured in backend/.env or environment.")
        print("      To test live LLM invocation, set GROQ_API_KEY in backend/.env or run:")
        print("      python backend/scripts/test_llm_factory.py --api-key <your-groq-key>")
        print("\n  [OK] AgentState and get_llm imports verified successfully without network call.")
        return

    masked_key = groq_key[:6] + "..." + groq_key[-4:] if len(groq_key) > 10 else "***"
    print(f"  Using Groq key: {masked_key}")
    print(f"  Configured Provider: {settings.LLM_PROVIDER}")
    print(f"  Configured Model: {settings.LLM_MODEL_NAME}")

    # 3. Initialize LLM via Factory & Invoke
    print("\n[3/3] Initializing LLM via get_llm() and sending test prompt...")
    llm = get_llm(api_key=groq_key, temperature=0.0)
    print(f"  Initialized model: {type(llm).__name__} (model={getattr(llm, 'model_name', 'default')})")

    prompt = "Hello! Please respond with a single, brutalist sentence confirming that you are operational as a financial research LLM engine."
    print(f"  Prompt: '{prompt}'")
    print("  Awaiting response from Groq...")

    response = llm.invoke(prompt)
    print(f"\n[RESPONSE]:\n{response.content}\n")
    print("=" * 60)
    print("SUB-PHASE 3.1 VERIFICATION COMPLETE: ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
