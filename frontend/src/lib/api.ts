import { AuthStatusResponse, RefreshTokenResponse, TokenResponse, User } from "@/types/auth";
import { AgentQueryRequest, AgentStepEvent, StreamCallbacks } from "@/types/agent";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

/**
 * Low-level HTTP client enforcing credentials: "include" for automatic cookie transit.
 */
export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...options,
    headers,
    credentials: "include", // Strictly enforce sending HTTP-only cookies
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    let errorMessage = `API request failed with status ${response.status}`;
    let errorData: unknown = null;
    try {
      errorData = await response.json();
      if (errorData && typeof errorData === "object" && "detail" in errorData) {
        errorMessage = String((errorData as { detail: unknown }).detail);
      } else if (errorData && typeof errorData === "object" && "message" in errorData) {
        errorMessage = String((errorData as { message: unknown }).message);
      }
    } catch {
      // Non-JSON response
    }
    throw new ApiError(errorMessage, response.status, errorData);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

export const api = {
  /**
   * Request a single-use SHA-256 magic link sent via transactional SMTP.
   */
  async requestMagicLink(email: string): Promise<AuthStatusResponse> {
    return apiFetch<AuthStatusResponse>("/auth/request-magic-link", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  /**
   * Verify an unhashed magic token and establish session cookies.
   */
  async verifyToken(token: string): Promise<TokenResponse> {
    return apiFetch<TokenResponse>("/auth/verify-token", {
      method: "POST",
      body: JSON.stringify({ token }),
    });
  },

  /**
   * Refresh expired access token using HTTP-only refresh token cookie.
   */
  async refreshAccessToken(): Promise<RefreshTokenResponse> {
    return apiFetch<RefreshTokenResponse>("/auth/refresh", {
      method: "POST",
    });
  },

  /**
   * Fetch current authenticated analyst profile.
   */
  async getMe(): Promise<User> {
    return apiFetch<User>("/auth/me", {
      method: "GET",
    });
  },

  /**
   * Revoke session on backend and clear cookies.
   */
  async logout(): Promise<AuthStatusResponse> {
    return apiFetch<AuthStatusResponse>("/auth/logout", {
      method: "POST",
    });
  },

  /**
   * Stream financial analyst queries with real-time SSE step and generation updates.
   */
  streamAgentQuery,
};

/**
 * Streams financial analyst queries to the CRAG agent via Server-Sent Events (SSE).
 *
 * Enforces credentials: "include" for automatic cookie transit, parses
 * streamed chunks using TextDecoder and a double-newline line buffer, and
 * dispatches typed events (step, generation, done, error) to callbacks.
 */
export async function streamAgentQuery(
  payload: AgentQueryRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal
): Promise<void> {
  const url = `${API_BASE_URL}/agent/query`;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include", // Strictly enforce sending HTTP-only cookies
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      let errorMessage = `API request failed with status ${response.status}`;
      let errorData: unknown = null;
      try {
        errorData = await response.json();
        if (errorData && typeof errorData === "object" && "detail" in errorData) {
          errorMessage = String((errorData as { detail: unknown }).detail);
        } else if (errorData && typeof errorData === "object" && "message" in errorData) {
          errorMessage = String((errorData as { message: unknown }).message);
        }
      } catch {
        // Non-JSON response
      }
      const apiError = new ApiError(errorMessage, response.status, errorData);
      callbacks.onError?.(apiError);
      throw apiError;
    }

    if (!response.body) {
      const apiError = new ApiError("Response body is not readable", response.status);
      callbacks.onError?.(apiError);
      throw apiError;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    const processEventBlock = (rawBlock: string) => {
      const lines = rawBlock.split("\n");
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("data:")) {
          const jsonStr = trimmed.slice(5).trim();
          if (jsonStr) {
            try {
              const event: AgentStepEvent = JSON.parse(jsonStr);
              if (event.type === "step") {
                callbacks.onStep?.(event);
              } else if (event.type === "generation") {
                callbacks.onGeneration?.(event.content || "");
              } else if (event.type === "done") {
                callbacks.onDone?.();
              } else if (event.type === "error") {
                callbacks.onError?.(event.message || "Unknown agent error");
              }
            } catch (parseErr) {
              console.warn("Failed to parse SSE JSON payload:", jsonStr, parseErr);
            }
          }
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let eventEndIndex: number;
      while ((eventEndIndex = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, eventEndIndex);
        buffer = buffer.slice(eventEndIndex + 2);
        processEventBlock(rawEvent);
      }
    }

    // Process any remaining buffered chunk
    const finalChunk = buffer + decoder.decode();
    if (finalChunk.trim()) {
      processEventBlock(finalChunk);
    }
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      // Aborted by user / signal, exit cleanly
      return;
    }
    const errorObj = err instanceof Error ? err : new Error(String(err));
    callbacks.onError?.(errorObj);
    throw errorObj;
  }
}
