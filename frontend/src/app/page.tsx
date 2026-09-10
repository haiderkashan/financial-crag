import Link from "next/link";

export default function Home() {
  return (
    <div className="flex-1 flex flex-col min-h-screen bg-[#F7F7F5] text-[#111111]">
      {/* Top Banner / Ticker */}
      <header className="border-b border-[#111111] px-6 py-3 flex flex-wrap items-center justify-between font-mono text-xs tracking-wider uppercase bg-[#F7F7F5]">
        <div className="flex items-center gap-4">
          <span className="bg-[#111111] text-[#F7F7F5] px-2 py-0.5 font-bold">CRAG-SEC</span>
          <span>SYSTEM STATE: ONLINE</span>
          <span className="hidden sm:inline text-neutral-500">|</span>
          <span className="hidden sm:inline">VERSION: 0.1.0</span>
        </div>
        <div className="flex items-center gap-6">
          <span>PIPELINE: LLAMAPARSE + PGVECTOR</span>
          <span className="text-[#E5A823] font-bold">[ READY ]</span>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-12 flex flex-col justify-between">
        <section className="border border-[#111111] bg-white p-8 md:p-12 mb-8 shadow-none">
          <div className="font-sans text-xs tracking-widest uppercase text-neutral-600 mb-4 pb-2 border-b border-[#111111]">
            Document Intelligence & Due-Diligence Protocol
          </div>

          <h1 className="font-sans text-3xl md:text-5xl font-black uppercase tracking-tight text-[#111111] mb-6 leading-none">
            Financial SEC Due-Diligence Terminal
          </h1>

          <p className="font-serif text-lg md:text-xl text-[#222222] leading-relaxed max-w-3xl mb-8">
            An enterprise-grade analytical engine engineered to extract, cross-validate, and compute financial metrics from complex SEC 10-K filings. Powered by Corrective Retrieval-Augmented Generation (CRAG), deterministic Python arithmetic execution, and autonomous web verification.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs border-t border-b border-[#111111] py-4 mb-8">
            <div>
              <div className="text-neutral-500 uppercase">Architecture</div>
              <div className="font-bold mt-1">Decoupled LangGraph + FastAPI</div>
            </div>
            <div>
              <div className="text-neutral-500 uppercase">Knowledge Base</div>
              <div className="font-bold mt-1">Supabase pgvector (10-K Filings)</div>
            </div>
            <div>
              <div className="text-neutral-500 uppercase">Execution Tooling</div>
              <div className="font-bold mt-1">Sandboxed Python REPL + Tavily</div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-4">
            <Link
              href="/login"
              className="inline-block bg-[#111111] hover:bg-[#E5A823] text-white hover:text-black font-mono text-sm px-6 py-3 font-semibold uppercase tracking-wider transition-colors border border-[#111111]"
            >
              [ -&gt; Access Analyst Portal ]
            </Link>
            <a
              href="https://github.com/haiderkashan/financial-crag"
              target="_blank"
              rel="noreferrer"
              className="inline-block bg-[#F7F7F5] hover:bg-neutral-200 text-[#111111] font-mono text-sm px-6 py-3 font-semibold uppercase tracking-wider transition-colors border border-[#111111]"
            >
              [ System Blueprints ]
            </a>
          </div>
        </section>

        {/* System Terminal Log View */}
        <section className="border border-[#111111] bg-[#111111] text-[#F7F7F5] p-6 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-neutral-800 pb-2 mb-4">
            <span className="text-neutral-400">SUBSYSTEM STATUS LOG</span>
            <span className="text-[#E5A823]">MONITORING ACTIVE</span>
          </div>
          <div className="space-y-1.5 text-neutral-300">
            <div>+ AUTH PROTOCOL ............ CUSTOM SMTP + CRYPTOGRAPHIC JWT</div>
            <div>+ VECTOR STORE ............. SUPABASE PGVECTOR EXTENSION ENABLED</div>
            <div>+ INGESTION PIPELINE ....... LLAMAPARSE STRUCTURE-AWARE PARSING</div>
            <div>+ CRAG STATE ENGINE ........ LANGGRAPH CORRECTIVE RETRIEVAL AGENT</div>
            <div>+ ARITHMETIC VALIDATION .... DETERMINISTIC PYTHON REPL EXECUTION</div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[#111111] px-6 py-4 flex flex-wrap items-center justify-between font-mono text-xs text-neutral-600 bg-[#F7F7F5]">
        <div>FINANCIAL CRAG INTELLIGENCE ENGINE &copy; 2026</div>
        <div>STRICT DESIGN STANDARD: EDITORIAL BRUTALISM // ZERO ICONS</div>
      </footer>
    </div>
  );
}
