import { createContext } from "react";
import type { LoginInput, User } from "./types";

export interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (input: LoginInput) => Promise<void>;
  logout: () => Promise<void>;
  getErrorMessage: (error: unknown) => string;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
