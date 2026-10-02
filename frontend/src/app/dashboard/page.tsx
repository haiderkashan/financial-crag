"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { QueryBar } from "@/components/QueryBar";

/**
 * Analyst Dashboard Shell adhering strictly to Design.md:
 * - Anti-AI aesthetic: brutalist, editorial Financial Times / Bloomberg Terminal vibe
 * - Zero icons (no Lucide, no SVG iconography)
 * - Strict typography: Newsreader (font-serif), JetBrains Mono (font-mono), Geist (font-sans)
 * - Sharp 1px solid black borders, zero border-radius
 * - 70/30 split layout: Synthesis Document (70%) / Thought Inspection (30%)
 * - Fixed QueryBar at screen bottom
 */
export default function DashboardPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();
  const [activeQuery, setActiveQuery] = useState<{
    question: string;
    ticker?: string;
    year?: number;
  } | null>(null);

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  const handleQuerySubmit = (question: string, ticker?: string, year?: number) => {
    setActiveQuery({ question, ticker, year });
    console.log("[Dashboard] Submitted Query:", { question, ticker, year });
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
            <span className="font-mono text-[10px] text-neutral-500 uppercase tracking-widest">
              PANEL: 70% WIDTH
            </span>
          </div>

          {/* Panel Content Body (Placeholder for Sub-Phase 4.5) */}
          <div className="flex-1 p-8 overflow-y-auto font-serif text-[#111111]">
            {activeQuery ? (
              <div className="space-y-4">
                <div className="border border-[#111111] bg-[#F7F7F5] p-4 font-mono text-xs">
                  <div className="text-neutral-500 uppercase tracking-wider mb-1">
                    ACTIVE DIRECTIVE:
                  </div>
                  <div className="font-bold text-[#111111]">{activeQuery.question}</div>
                  <div className="mt-2 text-neutral-600">
                    TARGET TICKER: {activeQuery.ticker || "NOT SPECIFIED"} | FISCAL YEAR:{" "}
                    {activeQuery.year || "NOT SPECIFIED"}
                  </div>
                </div>
                <div className="p-12 text-center text-neutral-400 italic">
                  [ SynthesisDocument component will render Markdown report here — Sub-Phase 4.5 ]
                </div>
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
          {/* Panel Header */}
          <div className="border-b border-[#333333] px-5 py-2.5 bg-[#1A1A1A] flex items-center justify-between flex-shrink-0 rounded-none">
            <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#E5A823]">
              THOUGHT INSPECTION // STATE MACHINE
            </span>
            <span className="font-mono text-[10px] text-neutral-400 uppercase tracking-widest">
              PANEL: 30% WIDTH
            </span>
          </div>

          {/* Panel Content Body (Placeholder for Sub-Phase 4.4) */}
          <div className="flex-1 p-6 overflow-y-auto font-mono text-xs">
            <div className="h-full flex flex-col items-center justify-center text-center p-4">
              <div className="border border-neutral-800 p-6 max-w-xs bg-[#161616]">
                <div className="text-[#E5A823] font-bold text-xs uppercase tracking-wider mb-2">
                  // STANDBY
                </div>
                <p className="text-neutral-400 text-[11px] leading-relaxed">
                  LangGraph CRAG state transitions, chunk retrieval rankings, relevance grading, and
                  sandboxed Python REPL traces will stream here in real-time.
                </p>
              </div>
            </div>
          </div>
        </aside>
      </main>

      {/* Bottom Bar: QueryBar */}
      <footer className="flex-shrink-0 w-full rounded-none">
        <QueryBar onSubmit={handleQuerySubmit} />
      </footer>
    </div>
  );
}
