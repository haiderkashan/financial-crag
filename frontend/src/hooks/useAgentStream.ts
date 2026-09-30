"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { streamAgentQuery } from "@/lib/api";
import {
  AgentQueryRequest,
  AgentStepEvent,
  AgentStreamState,
  AgentStreamStatus,
} from "@/types/agent";

export interface UseAgentStreamReturn {
  state: AgentStreamState;
  submitQuery: (payload: AgentQueryRequest) => Promise<void>;
  cancelQuery: () => void;
  resetState: () => void;
}

const INITIAL_STATE: AgentStreamState = {
  status: "idle",
  steps: [],
  activeNode: null,
  generation: "",
  error: null,
  elapsedMs: 0,
};

/**
 * Custom React hook for managing the lifecycle, SSE events, and state
 * transitions of an analyst query against the LangGraph CRAG agent.
 */
export function useAgentStream(): UseAgentStreamReturn {
  const [status, setStatus] = useState<AgentStreamStatus>(INITIAL_STATE.status);
  const [steps, setSteps] = useState<AgentStepEvent[]>(INITIAL_STATE.steps);
  const [activeNode, setActiveNode] = useState<string | null>(INITIAL_STATE.activeNode);
  const [generation, setGeneration] = useState<string>(INITIAL_STATE.generation);
  const [error, setError] = useState<string | null>(INITIAL_STATE.error);
  const [elapsedMs, setElapsedMs] = useState<number>(INITIAL_STATE.elapsedMs);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const cancelQuery = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearTimer();
    setStatus((prev) => (prev === "streaming" ? "idle" : prev));
    setActiveNode(null);
  }, [clearTimer]);

  const resetState = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearTimer();
    setStatus(INITIAL_STATE.status);
    setSteps(INITIAL_STATE.steps);
    setActiveNode(INITIAL_STATE.activeNode);
    setGeneration(INITIAL_STATE.generation);
    setError(INITIAL_STATE.error);
    setElapsedMs(INITIAL_STATE.elapsedMs);
  }, [clearTimer]);

  const submitQuery = useCallback(
    async (payload: AgentQueryRequest): Promise<void> => {
      // Abort any existing in-flight query before initiating a new one
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearTimer();

      const controller = new AbortController();
      abortControllerRef.current = controller;

      const startTime = Date.now();
      startTimeRef.current = startTime;

      setStatus("streaming");
      setSteps([]);
      setActiveNode(null);
      setGeneration("");
      setError(null);
      setElapsedMs(0);

      // Start live elapsed timer updating every 100ms
      timerRef.current = setInterval(() => {
        setElapsedMs(Date.now() - startTime);
      }, 100);

      try {
        await streamAgentQuery(
          payload,
          {
            onStep: (event: AgentStepEvent) => {
              setSteps((prev) => [...prev, event]);
              if (event.node) {
                setActiveNode(event.node);
              }
            },
            onGeneration: (content: string) => {
              setGeneration(content);
            },
            onDone: () => {
              clearTimer();
              setElapsedMs(Date.now() - startTime);
              setStatus("complete");
              setActiveNode(null);
              abortControllerRef.current = null;
            },
            onError: (err: Error | string) => {
              clearTimer();
              setElapsedMs(Date.now() - startTime);
              setStatus("error");
              setError(typeof err === "string" ? err : err.message);
              setActiveNode(null);
              abortControllerRef.current = null;
            },
          },
          controller.signal
        );
      } catch (err: unknown) {
        if (controller.signal.aborted) {
          // Handled cleanly on user cancellation
          return;
        }
        clearTimer();
        setElapsedMs(Date.now() - startTime);
        setStatus("error");
        setError(err instanceof Error ? err.message : String(err));
        setActiveNode(null);
        abortControllerRef.current = null;
      }
    },
    [clearTimer]
  );

  // Clean up timer and abort in-flight connection on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearTimer();
    };
  }, [clearTimer]);

  return {
    state: {
      status,
      steps,
      activeNode,
      generation,
      error,
      elapsedMs,
    },
    submitQuery,
    cancelQuery,
    resetState,
  };
}
