"use client";

import React, { useRef, useEffect } from "react";
import { AgentStepEvent, AgentStreamStatus } from "@/types/agent";

interface ThoughtPanelProps {
  status: AgentStreamStatus;
  steps: AgentStepEvent[];
  activeNode: string | null;
  elapsedMs: number;
}

/**
 * ThoughtPanel: Real-time Thought Inspection Panel exposing the CRAG agent's
 * internal state machine transitions (retrieval, grading, tool decisions, math REPL).
 *
 * Adheres strictly to Design.md:
 * - Terminal dark mode: bg-[#111111] text-[#F7F7F5]
 * - JetBrains Mono (font-mono) typography
 * - Zero icons (uses ASCII indicators: [■], ▶, //)
 * - Pulsating mustard (#E5A823) indicator for active executing node
 * - Smooth auto-scroll following state progression
 */
export function ThoughtPanel({
  status,
  steps,
  activeNode,
  elapsedMs,
}: ThoughtPanelProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  // Smoothly scroll to the latest thought entry as steps or active node update
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [steps.length, activeNode, status]);

  const elapsedSeconds = (elapsedMs / 1000).toFixed(2);

  return (
    <div className="w-full h-full bg-[#111111] text-[#F7F7F5] font-mono flex flex-col min-h-0 overflow-hidden rounded-none select-text">
      {/* Panel Header */}
      <div className="border-b border-[#2A2A2A] px-4 py-2.5 bg-[#161616] flex items-center justify-between flex-shrink-0 rounded-none">
        <span className="text-xs font-bold uppercase tracking-wider text-[#E5A823]">
          // THOUGHT_INSPECTION_PANEL
        </span>
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest">
          {status === "streaming" && (
            <span className="text-[#E5A823] flex items-center gap-1">
              <span className="inline-block w-1.5 h-1.5 bg-[#E5A823] animate-ping" />
              [STREAMING]
            </span>
          )}
          {status === "complete" && (
            <span className="text-green-400">[COMPLETE]</span>
          )}
          {status === "error" && (
            <span className="text-red-400">[ERROR]</span>
          )}
          {status === "idle" && (
            <span className="text-neutral-500">[STANDBY]</span>
          )}
        </div>
      </div>

      {/* Stream Logs Body */}
      <div className="flex-1 p-5 overflow-y-auto min-h-0 space-y-3 text-xs leading-relaxed">
        {status === "idle" && steps.length === 0 && (
          <div className="text-neutral-500 italic py-4">
            // AWAITING ANALYST QUERY...
          </div>
        )}

        {/* Step Events Sequence */}
        {steps.map((step, idx) => (
          <div key={idx} className="flex items-start gap-2.5">
            <span className="text-neutral-400 select-none flex-shrink-0">[■]</span>
            <span className="text-[#F7F7F5] flex-1 break-words">{step.message}</span>
          </div>
        ))}

        {/* Pulsating Active Node Indicator (while streaming) */}
        {status === "streaming" && (
          <div className="flex items-center gap-2 text-[#E5A823] pt-1">
            <span className="text-[#E5A823] animate-pulse select-none">▶</span>
            <span className="font-bold tracking-wide uppercase">
              [EXECUTING_NODE]: {activeNode ? activeNode.toUpperCase() : "INITIALIZING..."}
            </span>
          </div>
        )}

        {/* Stream Completion Signal */}
        {status === "complete" && (
          <div className="pt-3 border-t border-[#2A2A2A] text-[#E5A823] font-bold text-[11px] tracking-wider uppercase">
            // EXECUTION COMPLETE — {elapsedSeconds}s
          </div>
        )}

        {/* Stream Error Signal */}
        {status === "error" && (
          <div className="pt-3 border-t border-[#2A2A2A] text-red-400 font-bold text-[11px] tracking-wider uppercase">
            // EXECUTION HALTED WITH ERROR — {elapsedSeconds}s
          </div>
        )}

        {/* Auto-scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
