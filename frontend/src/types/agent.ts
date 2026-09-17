/**
 * TypeScript definitions for the Financial CRAG Agent streaming interface.
 * Matches backend schemas defined in backend/app/models/agent.py.
 */

export interface AgentQueryRequest {
  question: string;
  ticker?: string;
  fiscal_year?: number;
}

export type AgentEventType = "step" | "generation" | "done" | "error";

export interface AgentStepEvent {
  type: AgentEventType;
  node?: string | null;
  message?: string | null;
  content?: string | null;
}

export type StepCallback = (event: AgentStepEvent) => void;
export type GenerationCallback = (content: string) => void;
export type DoneCallback = () => void;
export type ErrorCallback = (error: Error | string) => void;

export interface StreamCallbacks {
  onStep?: StepCallback;
  onGeneration?: GenerationCallback;
  onDone?: DoneCallback;
  onError?: ErrorCallback;
}
