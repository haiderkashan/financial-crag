"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function DashboardPage() {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  if (isLoading) {
    return (
      <div className="flex-1 min-h-screen bg-[#F7F7F5] flex items-center justify-center p-6 font-mono text-xs">
        <div className="border border-[#111111] bg-white p-8">
          [ AUTHENTICATING ACTIVE SESSION... ]
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-[#F7F7F5] text-[#111111]">
      {/* Top Header Ticker */}
      <header className="border-b border-[#111111] px-6 py-3 flex flex-wrap items-center justify-between font-mono text-xs tracking-wider uppercase bg-[#F7F7F5]">
        <div className="flex items-center gap-4">
          <Link href="/" className="bg-[#111111] text-[#F7F7F5] px-2 py-0.5 font-bold hover:bg-[#E5A823] hover:text-black transition-colors">
            CRAG-SEC
          </Link>
          <span>ANALYST WORKSPACE // SESSION ACTIVE</span>
        </div>
        <div className="flex items-center gap-6">
          <span className="text-neutral-500">ANALYST: {user?.email || "UNKNOWN"}</span>
          <button
            onClick={handleLogout}
            className="text-black hover:text-[#E5A823] font-bold underline uppercase cursor-pointer"
          >
            [ Log Out ]
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-10 space-y-8">
        {/* Analyst Identity Card */}
        <section className="border border-[#111111] bg-white p-8 rounded-none">
          <div className="font-sans text-xs tracking-widest uppercase text-neutral-500 mb-2 pb-2 border-b border-[#111111]">
            Authenticated Security Principal
          </div>
          <h1 className="font-sans text-2xl md:text-3xl font-black uppercase tracking-tight text-[#111111] mb-6">
            Analyst Overview
          </h1>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono text-xs border border-[#111111] p-6 bg-[#F7F7F5]">
            <div>
              <div className="text-neutral-500 uppercase">Institutional Email</div>
              <div className="font-bold text-sm mt-1 break-all text-[#111111]">
                {user?.email || "N/A"}
              </div>
            </div>
            <div>
              <div className="text-neutral-500 uppercase">Principal UUID</div>
              <div className="font-bold text-xs mt-1 break-all text-neutral-700">
                {user?.id || "N/A"}
              </div>
            </div>
            <div>
              <div className="text-neutral-500 uppercase">Security Status</div>
              <div className="font-bold text-sm mt-1 text-[#E5A823]">
                {user?.is_active ? "[ ACTIVE_VERIFIED ]" : "[ SUSPENDED ]"}
              </div>
            </div>
          </div>
        </section>

        {/* Phase Modules Status */}
        <section className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Phase 2 Preview */}
          <div className="border border-[#111111] bg-white p-6 rounded-none space-y-4">
            <div className="font-sans text-xs tracking-widest uppercase text-neutral-500 border-b border-[#111111] pb-2">
              Phase 2 Module // Pending Deployment
            </div>
            <h2 className="font-sans text-xl font-bold uppercase text-[#111111]">
              SEC 10-K Ingestion Pipeline
            </h2>
            <p className="font-serif text-sm text-neutral-700 leading-relaxed">
              Automated document acquisition and structure-preserving tabular parsing via LlamaParse. Chunking and high-dimensional vector embeddings stored directly in Supabase pgvector.
            </p>
            <div className="font-mono text-xs text-neutral-500 pt-2">
              STATUS: READY FOR INGESTION SCRIPTS
            </div>
          </div>

          {/* Phase 3 Preview */}
          <div className="border border-[#111111] bg-white p-6 rounded-none space-y-4">
            <div className="font-sans text-xs tracking-widest uppercase text-neutral-500 border-b border-[#111111] pb-2">
              Phase 3 Module // Architecture Defined
            </div>
            <h2 className="font-sans text-xl font-bold uppercase text-[#111111]">
              LangGraph CRAG Agent
            </h2>
            <p className="font-serif text-sm text-neutral-700 leading-relaxed">
              State machine with corrective retrieval, retrieval grading nodes, autonomous web search fallback via Tavily, and sandboxed deterministic Python REPL arithmetic execution.
            </p>
            <div className="font-mono text-xs text-neutral-500 pt-2">
              STATUS: GRAPH BLUEPRINT DESIGNED
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#111111] px-6 py-4 flex items-center justify-between font-mono text-xs text-neutral-600 bg-[#F7F7F5]">
        <div>FINANCIAL CRAG DUE-DILIGENCE TERMINAL &copy; 2026</div>
        <div>SESSION ENCRYPTED // HTTP-ONLY COOKIE AUTH</div>
      </footer>
    </div>
  );
}
