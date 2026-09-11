import { AuthStatusResponse, RefreshTokenResponse, TokenResponse, User } from "@/types/auth";

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
};
