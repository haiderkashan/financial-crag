"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, ApiError } from "@/lib/api";
import { User } from "@/types/auth";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  requestMagicLink: (email: string) => Promise<string>;
  verifyToken: (token: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const refreshProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const currentUser = await api.getMe();
      setUser(currentUser);
    } catch (err) {
      setUser(null);
      if (err instanceof ApiError && err.status !== 401) {
        setError(err.message);
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Check existing session cookie on mount
  useEffect(() => {
    refreshProfile();
  }, [refreshProfile]);

  const requestMagicLink = async (email: string): Promise<string> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.requestMagicLink(email);
      return response.message;
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Failed to dispatch magic link.";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const verifyToken = async (token: string): Promise<User> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.verifyToken(token);
      setUser(response.user);
      return response.user;
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Invalid or expired verification token.";
      setError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async (): Promise<void> => {
    setIsLoading(true);
    try {
      await api.logout();
    } catch {
      // Clear client state even if backend network call fails
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        error,
        requestMagicLink,
        verifyToken,
        logout,
        refreshProfile,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
