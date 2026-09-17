"use client";

import React, { useState, useEffect } from "react";
import { api, streamAgentQuery } from "@/lib/api";
import { AgentStepEvent } from "@/types/agent";

export default function TestStreamPage() {
  const [authStatus, setAuthStatus] = useState<string>("Not Authenticated");
  const [streamStatus, setStreamStatus] = useState<"idle" | "streaming" | "done" | "error">("idle");
  const [events, setEvents] = useState<AgentStepEvent[]>([]);
  const [generationText, setGenerationText] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Auto-authenticate on mount if needed
  useEffect(() => {
    async function checkAuth() {
      try {
        const me = await api.getMe();
        setAuthStatus(`Authenticated (${me.email})`);
      } catch {
        // Automatically establish dev session
        try {
          const reqRes = await api.requestMagicLink("test.analyst@hedgefund.com") as { status: string; dev_token?: string };
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
    setStreamStatus("streaming");
    setEvents([]);
    setGenerationText("");
    setErrorMsg(null);

    console.log("=== STARTING AGENT STREAM VERIFICATION ===");
    console.log("Query: What were Apple's net sales in 2023? | Ticker: AAPL | Year: 2023");

    try {
      await streamAgentQuery(
        {
          question: "What were Apple's net sales in 2023?",
          ticker: "AAPL",
          fiscal_year: 2023,
        },
        {
          onStep: (event) => {
            console.log(`[SSE STEP] Node: ${event.node} | Message: ${event.message}`);
            setEvents((prev) => [...prev, event]);
          },
          onGeneration: (content) => {
            console.log(`[SSE GENERATION] Received ${content.length} characters.`);
            setGenerationText(content);
          },
          onDone: () => {
            console.log("[SSE DONE] Stream completed successfully.");
            setStreamStatus("done");
          },
          onError: (err) => {
            console.error("[SSE ERROR]", err);
            setErrorMsg(String(err));
            setStreamStatus("error");
          },
        }
      );
    } catch (err: unknown) {
      console.error("[STREAM FAILED]", err);
      setErrorMsg(String(err));
      setStreamStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F7F5] text-[#111111] p-8 font-mono">
      <div className="max-w-4xl mx-auto border border-[#111111] p-6 bg-white">
        <h1 className="text-xl font-bold border-b border-[#111111] pb-2 mb-4">
          CRAG SSE STREAMING VERIFICATION HARNESS // SUB-PHASE 4.1
        </h1>

        <div className="mb-4 text-sm">
          <span className="font-bold">SESSION: </span>
          <span>{authStatus}</span>
        </div>

        <div className="flex gap-4 mb-6">
          <button
            onClick={handleStartStream}
            disabled={streamStatus === "streaming"}
            className="px-4 py-2 bg-[#111111] text-[#F7F7F5] hover:bg-[#E5A823] hover:text-[#111111] transition-colors disabled:opacity-50 font-bold"
          >
            {streamStatus === "streaming" ? "[ STREAMING... ]" : "[ TRIGGER STREAM QUERY ]"}
          </button>
        </div>

        {errorMsg && (
          <div className="p-3 mb-4 bg-red-100 border border-red-500 text-red-900 text-sm">
            ERROR: {errorMsg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="border border-[#111111] p-4 bg-[#111111] text-[#F7F7F5]">
            <h2 className="text-sm font-bold border-b border-[#333] pb-1 mb-2 text-[#E5A823]">
              THOUGHT LOGS ({events.length})
            </h2>
            <div className="space-y-2 text-xs max-h-96 overflow-y-auto">
              {events.map((e, idx) => (
                <div key={idx} className="border-l-2 border-[#E5A823] pl-2 py-1">
                  <span className="text-gray-400">[{e.node || "STATE"}]</span>{" "}
                  <span>{e.message}</span>
                </div>
              ))}
              {events.length === 0 && <span className="text-gray-500">// Awaiting query execution...</span>}
            </div>
          </div>

          <div className="border border-[#111111] p-4 bg-white">
            <h2 className="text-sm font-bold border-b border-[#111111] pb-1 mb-2">
              GENERATION CONTENT ({generationText.length} chars)
            </h2>
            <div className="text-xs max-h-96 overflow-y-auto whitespace-pre-wrap font-serif">
              {generationText || <span className="font-mono text-gray-400">// Awaiting generation event...</span>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
