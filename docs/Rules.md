# Agent & Coding Rules

## 1. Engineering Standards

- **DRY (Don't Repeat Yourself):** Abstract reusable logic into utility functions. No copy-pasting component structures.
- **SOLID Principles:** Keep modules focused. The agent graph should be strictly decoupled from the FastAPI routing logic.
- **Strict Typing:**
  - Frontend: Use strict TypeScript interfaces for all props and state.
  - Backend: Use Python Type Hints and Pydantic models for every function signature and API payload.
- **Error Boundaries:** Fail gracefully. If the AI agent crashes, the Next.js UI must display a clean, typographic error message, not a raw stack trace.

## 2. AI Agent Constraints

- **NO Hallucinating Libraries:** Stick strictly to the dependencies listed in `Architecture.md`. Do not install random npm or pip packages without user confirmation.
- **State Management:** All LangGraph state transitions must be logged to the console during development.

## 3. Git & Workflow

- Update `Memory.md` at the end of every significant coding session.
- Log all architectural changes or library choices in `decision_log.md`.
