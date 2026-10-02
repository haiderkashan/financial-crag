"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { QueryBar } from "@/components/QueryBar";
import { ThoughtPanel } from "@/components/ThoughtPanel";
import { useAgentStream } from "@/hooks/useAgentStream";

/**
 * Analyst Dashboard Shell adhering strictly to Design.md:
 * - Anti-AI aesthetic: brutalist, editorial Financial Times / Bloomberg Terminal vibe
 * - Zero icons (no Lucide, no SVG iconography)
 * - Strict typography: Newsreader (font-serif), JetBrains Mono (font-mono), Geist (font-sans)
 * - Sharp 1px solid black borders, zero border-radius
 * - 70/30 split layout: Synthesis Document (70%) / Thought Inspection (30%)
 * - Mounted ThoughtPanel receiving real-time state machine transitions
 * - Fixed QueryBar at screen bottom
 */
export default function DashboardPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const { state: agentState, submitQuery, cancelQuery, resetState } = useAgentStream();
  const [activeQuery, setActiveQuery] = useState<{
    question: string;
    ticker?: string;
    year?: number;
  } | null>(null);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const handleQuerySubmit = async (question: string, ticker?: string, year?: number) => {
    setActiveQuery({ question, ticker, year });
    try {
      await submitQuery({
        question,
        ticker,
        fiscal_year: year,
      });
    } catch (err) {
      console.error("[Dashboard] Query execution error:", err);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F7F7F5] flex items-center justify-center p-6 font-mono text-xs text-[#111111]">
        <div className="border border-[#111111] bg-white p-8 rounded-none">
          [ AUTHENTICATING ACTIVE SESSION... ]
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen min-h-screen flex flex-col bg-[#F7F7F5] text-[#111111] overflow-hidden rounded-none">
      {/* Header Bar */}
      <header className="border-b border-[#111111] px-6 py-3 flex items-center justify-between font-mono text-xs uppercase tracking-wider bg-[#F7F7F5] flex-shrink-0 rounded-none">
        <div className="flex items-center gap-4">
          <Link
            href="/"
            className="bg-[#111111] text-[#F7F7F5] px-2.5 py-0.5 font-bold hover:bg-white hover:text-[#111111] border border-[#111111] transition-colors rounded-none"
          >
            CRAG-SEC
          </Link>
          <span className="font-bold">SEC DUE-DILIGENCE TERMINAL</span>
          <span className="text-neutral-400">//</span>
          <span className="text-neutral-500">SESSION ACTIVE</span>
        </div>

        <div className="flex items-center gap-6">
          <span className="text-neutral-600">
            ANALYST: <span className="text-[#111111] font-semibold">{user?.email || "UNKNOWN"}</span>
          </span>
          <button
            onClick={handleLogout}
            className="text-[#111111] hover:text-[#E5A823] font-bold uppercase cursor-pointer rounded-none"
          >
            [ LOG OUT ]
          </button>
        </div>
      </header>

      {/* Main Content 70/30 Split */}
      <main className="flex-1 flex flex-col md:flex-row min-h-0 overflow-hidden">
        {/* Left Panel: Synthesis Document Area (70%) */}
        <section className="w-full md:w-[70%] border-b md:border-b-0 md:border-r border-[#111111] bg-white flex flex-col min-h-0 overflow-hidden rounded-none">
          {/* Panel Header */}
          <div className="border-b border-[#111111] px-5 py-2.5 bg-[#F7F7F5] flex items-center justify-between flex-shrink-0 rounded-none">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#111111]">
                SYNTHESIS REPORT // AUDITED DUE-DILIGENCE
              </span>
            </div>
            <div className="flex items-center gap-4 font-mono text-[10px] text-neutral-500 uppercase tracking-widest">
              {activeQuery && (
                <button
                  onClick={resetState}
                  disabled={agentState.status === "streaming"}
                  className="hover:text-black uppercase underline disabled:opacity-30 cursor-pointer"
                >
                  [ RESET ]
                </button>
              )}
              <span>PANEL: 70% WIDTH</span>
            </div>
          </div>

          {/* Panel Content Body (Placeholder for Sub-Phase 4.5) */}
          <div className="flex-1 p-8 overflow-y-auto font-serif text-[#111111]">
            {activeQuery ? (
              <div className="space-y-6">
                <div className="border border-[#111111] bg-[#F7F7F5] p-4 font-mono text-xs flex justify-between items-start">
                  <div>
                    <div className="text-neutral-500 uppercase tracking-wider mb-1">
                      ACTIVE DIRECTIVE:
                    </div>
                    <div className="font-bold text-[#111111]">{activeQuery.question}</div>
                    <div className="mt-2 text-neutral-600">
                      TARGET TICKER: {activeQuery.ticker || "ALL"} | FISCAL YEAR:{" "}
                      {activeQuery.year || "LATEST"}
                    </div>
                  </div>
                  {agentState.status === "streaming" && (
                    <button
                      onClick={cancelQuery}
                      className="border border-red-700 text-red-700 hover:bg-red-700 hover:text-white px-2 py-1 text-[11px] font-bold uppercase transition-colors"
                    >
                      [ CANCEL STREAM ]
                    </button>
                  )}
                </div>

                {/* Sub-Phase 4.5 Synthesis Document Output Placeholder */}
                {agentState.generation ? (
                  <div className="border border-[#111111] p-6 bg-white space-y-4">
                    <div className="font-mono text-[10px] text-neutral-400 uppercase tracking-wider pb-2 border-b border-neutral-200">
                      RAW SYNTHESIS OUTPUT (Sub-Phase 4.5 will typeset with react-markdown):
                    </div>
                    <div className="text-xs font-mono whitespace-pre-wrap leading-relaxed text-[#111111]">
                      {agentState.generation}
                    </div>
                  </div>
                ) : (
                  <div className="p-12 text-center text-neutral-400 italic">
                    {agentState.status === "streaming"
                      ? "[ Synthesizing due-diligence report from SEC 10-K filings... ]"
                      : "[ Awaiting agent generation... ]"}
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-8">
                <div className="border border-dashed border-neutral-300 p-8 max-w-md bg-[#F7F7F5]">
                  <div className="font-mono text-xs uppercase tracking-wider text-neutral-500 mb-2">
                    AWAITING DIRECTIVE
                  </div>
                  <p className="font-serif text-sm text-neutral-700 leading-relaxed">
                    Submit a due-diligence inquiry using the command bar below to generate an audited
                    financial synthesis report with table citations and deterministic math.
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Right Panel: Thought Inspection Area (30%) */}
        <aside className="w-full md:w-[30%] bg-[#111111] text-[#F7F7F5] flex flex-col min-h-0 overflow-hidden rounded-none">
          <ThoughtPanel
            status={agentState.status}
            steps={agentState.steps}
            activeNode={agentState.activeNode}
            elapsedMs={agentState.elapsedMs}
          />
        </aside>
      </main>

      {/* Bottom Bar: QueryBar */}
      <footer className="flex-shrink-0 w-full rounded-none">
        <QueryBar
          onSubmit={handleQuerySubmit}
          disabled={agentState.status === "streaming"}
        />
      </footer>
    </div>
  );
}
