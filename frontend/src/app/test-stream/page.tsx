"use client";

import React, { useState, useEffect } from "react";
import { api } from "@/lib/api";
import { useAgentStream } from "@/hooks/useAgentStream";

export default function TestStreamPage() {
  const [authStatus, setAuthStatus] = useState<string>("Checking Session...");
  const { state, submitQuery, cancelQuery, resetState } = useAgentStream();

  // Auto-authenticate on mount if needed
  useEffect(() => {
    async function checkAuth() {
      try {
        const me = await api.getMe();
        setAuthStatus(`Authenticated (${me.email})`);
      } catch {
        // Automatically establish dev session
        try {
          const reqRes = (await api.requestMagicLink("lead.analyst@hedgefund.com")) as {
            status: string;
            dev_token?: string;
          };
          if (reqRes.dev_token) {
            await api.verifyToken(reqRes.dev_token);
            const user = await api.getMe();
            setAuthStatus(`Authenticated (${user.email})`);
          } else {
            setAuthStatus("Auth required: request link dispatched");
          }
        } catch (err: unknown) {
          setAuthStatus(`Auth error: ${String(err)}`);
        }
      }
    }
    checkAuth();
  }, []);

  const handleStartStream = async () => {
    await submitQuery({
      question: "What were Apple's net sales in 2023?",
      ticker: "AAPL",
      fiscal_year: 2023,
    });
  };

  return (
    <div className="min-h-screen bg-[#F7F7F5] text-[#111111] p-8 font-mono">
      <div className="max-w-4xl mx-auto border border-[#111111] p-6 bg-white">
        <h1 className="text-xl font-bold border-b border-[#111111] pb-2 mb-4">
          useAgentStream HOOK VERIFICATION HARNESS // SUB-PHASE 4.2
        </h1>

        <div className="mb-4 text-sm flex justify-between items-center bg-[#F7F7F5] p-3 border border-[#111111]">
          <div>
            <span className="font-bold">SESSION: </span>
            <span>{authStatus}</span>
          </div>
          <div>
            <span className="font-bold">HOOK STATUS: </span>
            <span
              className={`font-bold px-2 py-0.5 ${
                state.status === "streaming"
                  ? "bg-[#E5A823] text-black"
                  : state.status === "complete"
                  ? "bg-green-700 text-white"
                  : state.status === "error"
                  ? "bg-red-700 text-white"
                  : "bg-gray-200 text-gray-800"
              }`}
            >
              [{state.status.toUpperCase()}]
            </span>
          </div>
        </div>

        {/* Live Metrics Dump */}
        <div className="grid grid-cols-4 gap-3 mb-4 text-xs">
          <div className="p-2 border border-[#111111] bg-[#F7F7F5]">
            <span className="font-bold block">STATUS:</span>
            <span data-testid="status-val">{state.status}</span>
          </div>
          <div className="p-2 border border-[#111111] bg-[#F7F7F5]">
            <span className="font-bold block">ACTIVE NODE:</span>
            <span data-testid="node-val">{state.activeNode || "none"}</span>
          </div>
          <div className="p-2 border border-[#111111] bg-[#F7F7F5]">
            <span className="font-bold block">ELAPSED:</span>
            <span data-testid="elapsed-val">{(state.elapsedMs / 1000).toFixed(2)}s</span>
          </div>
          <div className="p-2 border border-[#111111] bg-[#F7F7F5]">
            <span className="font-bold block">STEPS COUNT:</span>
            <span data-testid="steps-count">{state.steps.length}</span>
          </div>
        </div>

        <div className="flex gap-4 mb-6">
          <button
            onClick={handleStartStream}
            disabled={state.status === "streaming"}
            className="px-4 py-2 bg-[#111111] text-[#F7F7F5] hover:bg-[#E5A823] hover:text-[#111111] transition-colors disabled:opacity-50 font-bold"
          >
            {state.status === "streaming" ? "[ STREAMING... ]" : "[ TRIGGER QUERY VIA HOOK ]"}
          </button>

          {state.status === "streaming" && (
            <button
              onClick={cancelQuery}
              className="px-4 py-2 border border-red-700 text-red-700 hover:bg-red-700 hover:text-white transition-colors font-bold"
            >
              [ CANCEL QUERY ]
            </button>
          )}

          <button
            onClick={resetState}
            disabled={state.status === "streaming"}
            className="px-4 py-2 border border-[#111111] hover:bg-gray-100 transition-colors disabled:opacity-50 font-bold"
          >
            [ RESET STATE ]
          </button>
        </div>

        {state.error && (
          <div className="p-3 mb-4 bg-red-100 border border-red-500 text-red-900 text-sm">
            ERROR: {state.error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-[#111111] p-4 bg-[#111111] text-[#F7F7F5]">
            <h2 className="text-sm font-bold border-b border-[#333] pb-1 mb-2 text-[#E5A823]">
              STATE.STEPS ARRAY ({state.steps.length})
            </h2>
            <div className="space-y-2 text-xs max-h-96 overflow-y-auto">
              {state.steps.map((e, idx) => (
                <div key={idx} className="border-l-2 border-[#E5A823] pl-2 py-1">
                  <span className="text-gray-400">[{e.node || "STATE"}]</span>{" "}
                  <span>{e.message}</span>
                </div>
              ))}
              {state.steps.length === 0 && (
                <span className="text-gray-500">// Awaiting query execution...</span>
              )}
            </div>
          </div>

          <div className="border border-[#111111] p-4 bg-white">
            <h2 className="text-sm font-bold border-b border-[#111111] pb-1 mb-2">
              STATE.GENERATION ({state.generation.length} chars)
            </h2>
            <div className="text-xs max-h-96 overflow-y-auto whitespace-pre-wrap font-serif">
              {state.generation || (
                <span className="font-mono text-gray-400">// Awaiting generation event...</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
