import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, setTokenProvider } from "../../shared/api";
import {
  getCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
} from "./api";
import { AuthContext } from "./context";
import type { LoginInput, User } from "./types";

export function AuthProvider({ children }: { children: ReactNode }) {
  const accessTokenRef = useRef<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  function setAccessToken(token: string | null) {
    accessTokenRef.current = token;
  }

  useEffect(() => {
    setTokenProvider(() => accessTokenRef.current);

    async function restoreSession() {
      try {
        const tokens = await refreshSession();
        setAccessToken(tokens.access_token);
        const response = await getCurrentUser();
        setUser(response.user);
      } catch {
        setAccessToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    void restoreSession();

    return () => setTokenProvider(null);
  }, []);

  async function login(input: LoginInput) {
    const tokens = await loginRequest(input);
    setAccessToken(tokens.access_token);
    const response = await getCurrentUser();
    setUser(response.user);
  }

  async function logout() {
    try {
      await logoutRequest();
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }

  function getErrorMessage(error: unknown): string {
    if (error instanceof ApiError) {
      return error.message;
    }
    return "Something went wrong. Please try again.";
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: user !== null,
        login,
        logout,
        getErrorMessage,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
